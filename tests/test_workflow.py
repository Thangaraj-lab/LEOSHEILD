import hashlib
import io
import json
import uuid
from datetime import timedelta, timezone

from PIL import Image
from fastapi import HTTPException
import pytest

from backend.app import main


def setup_local(tmp_path, monkeypatch, buyer="Buyer A"):
    monkeypatch.setattr(main, "STORAGE", tmp_path / "storage")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "storage" / "database" / "test.sqlite3")
    monkeypatch.setenv("BOOTSTRAP_USERNAME", "owner")
    monkeypatch.setenv("BOOTSTRAP_PASSWORD", "Local-only-test-password")
    main.initialize()
    login_result = main.login(main.Credentials(username="owner", password="Local-only-test-password"))
    with main.closing(main.connect()) as con:
        user = con.execute("SELECT id,username,role FROM users WHERE username='owner'").fetchone()
    lot = main.create_lot(main.LotInput(code="TEST-1", product_type="Leather", buyer=buyer, expected_quantity=1, supplier="Supplier S", machine="Drum M"), user)
    product = main.add_product(lot["id"], main.ProductInput(code="HIDE-1"), user)
    return user, lot, product, login_result["token"]


def image_bytes(color=(80, 110, 70)):
    image = Image.new("RGB", (200, 120), color)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class MemoryUpload:
    def __init__(self, payload, filename="sample.png", content_type="image/png"):
        self.payload, self.filename, self.content_type = payload, filename, content_type
        self.file=io.BytesIO(payload)


def test_inspection_capture_human_review_reinspection_and_reports(tmp_path, monkeypatch):
    user, lot, product, _ = setup_local(tmp_path, monkeypatch)
    payload = image_bytes()
    responses = [
        {"contract_version":"1.0.0","inspection_id":str(uuid.uuid4()),"product_id":"HIDE-1","lot_id":lot["id"],"profile":"leather","execution_mode":"real","status":"completed","recommendation":"no_defect_flagged","coverage":{"required_regions":5,"inspected_regions":5,"complete":True},"image_quality":{"acceptable":True,"warnings":[]},"defects":[{"defect_id":"d-1","label":"Scratch","bounding_box":{"x":0.2,"y":0.3,"width":0.1,"height":0.15}}],"actions":[{"action":"baseline_inspection","instruction":"Baseline image analyzed"}],"human_approval_required":True,"algorithm_version":"0.1.0","model_version":"model-a"},
        {"contract_version":"1.0.0","inspection_id":str(uuid.uuid4()),"product_id":"HIDE-1","lot_id":lot["id"],"profile":"leather","execution_mode":"real","status":"completed","recommendation":"review","coverage":{"required_regions":5,"inspected_regions":2,"complete":False},"image_quality":{"acceptable":True,"warnings":[]},"defects":[],"actions":[{"action":"additional_capture_request","instruction":"Left-side lighting image required."}],"human_approval_required":True},
    ]
    calls=[]
    def submit(self,*args):
        calls.append(args)
        return responses.pop(0)
    monkeypatch.setattr(main.AIEngineClient,"inspect_image",submit)
    monkeypatch.setattr(main.AIEngineClient,"get_json",lambda self,path:{"evidence_id":"engine-image-1","path_available":False})

    first=main.inspect_product(product["id"],user,MemoryUpload(payload),"leather","left","req-1")
    assert first["state"]=="completed" and first["execution_mode"]=="real"
    assert first["decision"] is None
    assert first["recommendation"]=="no_defect_flagged"
    assert first["captures"][0]["lighting_mode"]=="left"
    assert first["captures"][0]["sha256"]==hashlib.sha256(payload).hexdigest()
    assert first["defects"][0]["x"]==0.2 and first["defects"][0]["width"]==0.1
    assert first["engine_evidence"]=={"evidence_id":"engine-image-1","path_available":False}
    assert len(calls)==1

    duplicate=main.inspect_product(product["id"],user,MemoryUpload(payload),"leather","left","req-1")
    assert duplicate["id"]==first["id"] and len(calls)==1
    with pytest.raises(HTTPException) as exc:
        main.inspect_product(product["id"],user,MemoryUpload(image_bytes((10,20,30))),"leather","left","req-1")
    assert exc.value.status_code==409

    assert main.decide(first["id"],main.DecisionInput(outcome="PASS",notes="Visual review completed"),user)["outcome"]=="PASS"
    assert main.update_defect(first["id"],first["defects"][0]["id"],main.DefectUpdate(label="Surface scratch",status="corrected",notes="Confirmed under direct light"),user)["original_label"]=="Scratch"
    manual=main.add_manual_defect(first["id"],main.DefectInput(label="Edge nick",notes="Inspector marked"),user)
    assert manual["status"]=="manual"
    with main.closing(main.connect()) as con:
        assert main.lot_summary(con,lot["id"])["accepted_quantity"]==1

    second=main.inspect_product(product["id"],user,MemoryUpload(image_bytes((30,40,50)),"second.png"),"leather","normal","req-2")
    assert second["state"]=="completed" and second["captures"][0]["lighting_mode"]=="normal"
    with pytest.raises(HTTPException) as exc:
        main.decide(second["id"],main.DecisionInput(outcome="PASS",notes="Reviewed"),user)
    assert exc.value.status_code==409
    with main.closing(main.connect()) as con:
        stats=main.lot_summary(con,lot["id"])
    assert stats["product_count"]==1 and stats["inspections_count"]==2 and stats["pending_quantity"]==1
    main.put_buyer_requirements(main.BuyerRequirementsInput(buyer="Buyer A",profile="leather"),user)
    with main.closing(main.connect()) as con:
        gate=main.evaluate_export_gate(con,lot["id"])
    assert not gate["ready"] and any("incomplete mandatory inspection coverage" in x for x in gate["blockers"])

    extra=main.add_evidence(second["id"],user,MemoryUpload(image_bytes((70,40,50)),"extra.png"),"front")
    assert extra["submitted_to_engine"] is False
    after=main.get_inspection(second["id"],user)
    assert len(after["captures"])==2 and after["state"]=="completed"
    assert main.inspection_history(second["id"],user)[0]["id"]==second["id"]

    defect_analytics=main.quality_analytics(user)
    assert defect_analytics["data_state"]=="insufficient_data"
    assert defect_analytics["possible_source_note"].startswith("Supplier and machine")
    with main.closing(main.connect()) as con:
        pdf=main.inspection_report(con,main.STORAGE,first["id"])
    assert pdf.read_bytes().startswith(b"%PDF-")
    with main.closing(main.connect()) as con:
        lot_pdf=main.lot_report(con,main.STORAGE,lot["id"],gate,stats)
    assert lot_pdf.read_bytes().startswith(b"%PDF-")


def test_export_gate_buyer_measurement_lab_quantity_and_dispatch(tmp_path, monkeypatch):
    user,lot,product,_=setup_local(tmp_path,monkeypatch)
    result={"status":"completed","recommendation":"review","coverage":{"required_regions":1,"inspected_regions":1,"complete":True},"image_quality":{"acceptable":True,"warnings":[]},"defects":[],"human_approval_required":True}
    inspection_id=str(uuid.uuid4()); created=main.now(); payload=image_bytes()
    image_name=f"{inspection_id}.png";(main.STORAGE/"images"/image_name).write_bytes(payload)
    with main.closing(main.connect()) as con:
        con.execute("INSERT INTO inspections(id,product_id,state,recommendation,execution_mode,ai_result,image_name,image_sha256,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(inspection_id,product["id"],"completed","review","real",json.dumps(result),image_name,hashlib.sha256(payload).hexdigest(),created,created))
        con.execute("INSERT INTO captures VALUES(?,?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),inspection_id,1,image_name,hashlib.sha256(payload).hexdigest(),"normal","operator_upload",None,'{}',created));con.commit()
    main.decide(inspection_id,main.DecisionInput(outcome="GRADE",grade="A",notes="Grade A by surface checklist"),user)
    with main.closing(main.connect()) as con:
        blocked=main.evaluate_export_gate(con,lot["id"])
    assert any("Buyer quality requirements" in x for x in blocked["blockers"])
    main.put_buyer_requirements(main.BuyerRequirementsInput(buyer="Buyer A",profile="leather",required_measurements=["Thickness"],required_labs=["Chemical"]),user)
    with main.closing(main.connect()) as con:
        blocked=main.evaluate_export_gate(con,lot["id"])
    assert any("Thickness" in x for x in blocked["blockers"]) and any("Chemical" in x for x in blocked["blockers"])
    main.record_measurement(lot["id"],main.MeasurementInput(name="Thickness",value=1.2,unit="mm"),user)
    report_id=str(uuid.uuid4())
    with main.closing(main.connect()) as con:
        con.execute("INSERT INTO lab_reports VALUES(?,?,?,?,?,?,?,?)",(report_id,lot["id"],"Chemical","pending_review",None,None,None,main.now()));con.commit()
    main.review_lab_report(report_id,main.LabReviewInput(status="accepted"),user)
    with main.closing(main.connect()) as con:
        gate=main.evaluate_export_gate(con,lot["id"])
    assert gate["ready"] and gate["accepted_quantity"]==1 and gate["rejected_quantity"]==0
    with pytest.raises(HTTPException) as exc:
        main.authorize_dispatch(lot["id"],main.DispatchInput(quantity=2),user)
    assert exc.value.status_code==409
    dispatch=main.authorize_dispatch(lot["id"],main.DispatchInput(quantity=1),user)
    assert dispatch["status"]=="authorized" and dispatch["quantity"]==1
    with pytest.raises(HTTPException):
        main.authorize_dispatch(lot["id"],main.DispatchInput(quantity=1),user)


def test_auth_input_image_and_engine_validation(tmp_path, monkeypatch):
    user,lot,product,_=setup_local(tmp_path,monkeypatch)
    assert user["role"]=="owner"
    with pytest.raises(HTTPException) as exc:
        main.login(main.Credentials(username="owner",password="wrong"))
    assert exc.value.status_code==401
    for bad in ({"status":"completed"},{"status":"completed","recommendation":"PASS"},{"status":"completed","recommendation":"review","contract_version":"99.0"},{"status":"completed","recommendation":"review","human_approval_required":False},[]):
        with pytest.raises(ValueError):main.validate_engine_result(bad)
    with pytest.raises(HTTPException):main.verify_image(b"not an image","image/png")
    assert main.verify_image(image_bytes(),"image/png")==("PNG",200,120)
    with pytest.raises(HTTPException):main.verify_image(b"","image/jpeg")
    with pytest.raises(HTTPException):main.inspect_product(product["id"],user,MemoryUpload(b"bad"),"leather","left","invalid-1")
    with pytest.raises(HTTPException) as invalid_profile:
        main.inspect_product(product["id"],user,MemoryUpload(image_bytes()),"unsupported","left","invalid-2")
    assert invalid_profile.value.status_code==422
    with pytest.raises(HTTPException) as unauthorized:
        main.authorize_dispatch(lot["id"],main.DispatchInput(quantity=1),{"role":"inspector"})
    assert unauthorized.value.status_code==403
    assert main.app.openapi()["info"]["title"]=="LEO Shield Business API"


def test_async_engine_job_polling_preserves_initial_recommendation(tmp_path,monkeypatch):
    user,lot,product,_=setup_local(tmp_path,monkeypatch)
    upstream=str(uuid.uuid4())
    initial={"inspection_id":upstream,"status":"pending","recommendation":"review","defects":[],"human_approval_required":True}
    completed={"inspection_id":upstream,"status":"completed","recommendation":"no_defect_flagged","coverage":{"required_regions":2,"inspected_regions":2,"complete":True},"image_quality":{"acceptable":True},"defects":[],"human_approval_required":True}
    monkeypatch.setattr(main.AIEngineClient,"inspect_image",lambda self,*args:initial)
    poll_calls=[]
    def read(self,path):
        poll_calls.append(path)
        return {"evidence_id":"e-1","available":False} if path.endswith("/evidence") else completed
    monkeypatch.setattr(main.AIEngineClient,"get_json",read)
    attempt=main.inspect_product(product["id"],user,MemoryUpload(image_bytes()),"leather","top","poll-1")
    assert attempt["state"]=="pending" and attempt["recommendation"]=="review"
    with main.closing(main.connect()) as con:
        con.execute("UPDATE inspections SET updated_at=? WHERE id=?",((main.datetime.now(timezone.utc)-timedelta(seconds=3)).isoformat(),attempt["id"]));con.commit()
    refreshed=main.refresh_inspection(attempt["id"],user)
    assert refreshed["state"]=="completed" and refreshed["pollable"] is False
    assert refreshed["inspection"]["recommendation"]=="review"
    assert refreshed["inspection"]["ai_result"]["recommendation"]=="no_defect_flagged"
    assert len(refreshed["inspection"]["engine_events"])==2
    assert poll_calls==[f"/inspections/{upstream}",f"/inspections/{upstream}/evidence"]


def test_engine_disconnect_is_saved_failed_and_restart_recovers_submission(tmp_path,monkeypatch):
    user,lot,product,_=setup_local(tmp_path,monkeypatch)
    def disconnected(self,*args):raise main.httpx.ConnectError("Laptop 1 unavailable")
    monkeypatch.setattr(main.AIEngineClient,"inspect_image",disconnected)
    attempt=main.inspect_product(product["id"],user,MemoryUpload(image_bytes()),"leather","unknown","disconnect-1")
    assert attempt["state"]=="failed" and attempt["recommendation"] is None
    assert "integration_error" in attempt["ai_result"]
    assert main.decide(attempt["id"],main.DecisionInput(outcome="HOLD",notes="Engine connection unavailable"),user)["outcome"]=="HOLD"
    orphan_id=str(uuid.uuid4());timestamp=main.now()
    with main.closing(main.connect()) as con:
        con.execute("INSERT INTO inspections(id,product_id,state,recommendation,execution_mode,ai_result,image_name,image_sha256,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(orphan_id,product["id"],"pending",None,"real",'{"lifecycle":"submitting"}',None,None,timestamp,timestamp));con.commit()
    main.initialize()
    recovered=main.get_inspection(orphan_id,user)
    assert recovered["state"]=="failed" and "restarted" in recovered["ai_result"]["integration_error"]
    with main.closing(main.connect()) as con:
        stats=main.lot_summary(con,lot["id"])
    assert stats["product_count"]==1 and stats["inspections_count"]==2 and stats["held_quantity"]==0 and stats["pending_quantity"]==1
