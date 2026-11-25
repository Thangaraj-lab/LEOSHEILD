"""Offline PDF summaries rendered with Pillow; original captures remain untouched."""
from __future__ import annotations

import json
import sqlite3
import textwrap
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


PAGE = (1275, 1650)


def _font(size: int):
    for path in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _text_page(title: str, subtitle: str, lines: list[str]) -> Image.Image:
    page = Image.new("RGB", PAGE, "white")
    draw = ImageDraw.Draw(page)
    draw.rectangle((0, 0, PAGE[0], 180), fill="#101b2b")
    draw.text((80, 48), "LEO SHIELD  /  QUALITY EVIDENCE", fill="#d8ee7d", font=_font(25))
    draw.text((80, 92), title, fill="white", font=_font(38))
    draw.text((80, 145), subtitle[:90], fill="#c6d1d6", font=_font(18))
    y = 220
    for line in lines:
        for wrapped in textwrap.wrap(str(line), width=88, break_long_words=True) or [""]:
            draw.text((80, y), wrapped, fill="#1d2b37", font=_font(19))
            y += 32
            if y > PAGE[1] - 100:
                break
        if y > PAGE[1] - 100:
            break
    draw.line((80, PAGE[1] - 70, PAGE[0] - 80, PAGE[1] - 70), fill="#dce4e5", width=2)
    draw.text((80, PAGE[1] - 53), "Generated from locally recorded evidence. Not a government export certificate.", fill="#64727a", font=_font(14))
    return page


def _capture_page(capture: sqlite3.Row | dict, image_path: Path) -> Image.Image:
    page = Image.new("RGB", PAGE, "white")
    draw = ImageDraw.Draw(page)
    draw.rectangle((0, 0, PAGE[0], 170), fill="#101b2b")
    draw.text((70, 45), f"CAPTURE {capture['sequence']} · {capture['lighting_mode'].upper()}", fill="#d8ee7d", font=_font(27))
    draw.text((70, 100), f"Evidence SHA-256: {capture['sha256']}", fill="white", font=_font(15))
    try:
        image = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        image.thumbnail((PAGE[0] - 140, PAGE[1] - 280))
        x = (PAGE[0] - image.width) // 2
        y = 210 + (PAGE[1] - 280 - image.height) // 2
        page.paste(image, (x, y))
    except (OSError, ValueError):
        draw.text((70, 230), "Capture image unavailable; the record hash remains listed.", fill="#ab443e", font=_font(20))
    return page


def _save(pages: list[Image.Image], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not pages:
        pages = [_text_page("No evidence", "No report pages were available", [])]
    pages[0].save(output, "PDF", save_all=True, append_images=pages[1:], resolution=110.0)
    return output


def inspection_report(con: sqlite3.Connection, storage: Path, inspection_id: str) -> Path:
    row = con.execute("SELECT i.*,p.code product_code,p.lot_id,l.code lot_code,l.buyer FROM inspections i JOIN products p ON p.id=i.product_id JOIN lots l ON l.id=p.lot_id WHERE i.id=?", (inspection_id,)).fetchone()
    if not row:
        raise KeyError(inspection_id)
    result = json.loads(row["ai_result"] or "null")
    decision = con.execute("SELECT d.*,u.username FROM decisions d JOIN users u ON u.id=d.user_id WHERE d.inspection_id=? ORDER BY d.created_at DESC LIMIT 1", (inspection_id,)).fetchone()
    defects = con.execute("SELECT * FROM defects WHERE inspection_id=? ORDER BY created_at", (inspection_id,)).fetchall()
    captures = con.execute("SELECT * FROM captures WHERE inspection_id=? ORDER BY sequence", (inspection_id,)).fetchall()
    lines = [
        f"Lot: {row['lot_code']}   Product: {row['product_code']}   Buyer: {row['buyer'] or 'not specified'}",
        f"Inspection ID: {inspection_id}", f"State: {row['state']}   Execution mode: {row['execution_mode']}",
        f"Original AI recommendation: {row['recommendation'] or 'unavailable'}",
        f"Human decision: {decision['outcome'] if decision else 'not recorded'}; grade: {decision['grade'] if decision else '—'}",
        f"Decision by: {decision['username'] if decision else '—'}; reason: {decision['notes'] if decision else '—'}",
        f"Profile: {result.get('profile','unreported') if isinstance(result,dict) else 'unreported'}",
        f"Model version: {result.get('model_version','unreported') if isinstance(result,dict) else 'unreported'}; algorithm version: {result.get('algorithm_version','unreported') if isinstance(result,dict) else 'unreported'}",
        f"Coverage: {json.dumps(result.get('coverage','unreported')) if isinstance(result,dict) else 'unreported'}",
        f"Capture quality: {json.dumps(result.get('image_quality','unreported')) if isinstance(result,dict) else 'unreported'}",
        f"Inspection created: {row['created_at']}", f"Report generated: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}",
        f"AI-result JSON retained in local database; original image SHA-256: {row['image_sha256'] or 'unavailable'}", "Recorded defects:",
    ]
    lines += [f"- {d['label']} [{d['status']}] at normalized ({d['x']},{d['y']},{d['width']},{d['height']}) — {d['notes']}" for d in defects] or ["- No defect annotations recorded."]
    pages = [_text_page("Individual inspection report", f"Product {row['product_code']} · generated from this device", lines)]
    for capture in captures:
        folder = "images" if capture["source"] in {"operator_upload", "legacy_upload"} else "evidence"
        pages.append(_capture_page(capture, storage / folder / capture["filename"]))
    return _save(pages, storage / "reports" / f"inspection-{uuid.uuid4()}.pdf")


def lot_report(con: sqlite3.Connection, storage: Path, lot_id: str, gate: dict, lot_summary: dict) -> Path:
    lot = con.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
    if not lot:
        raise KeyError(lot_id)
    lines = [
        f"Lot: {lot['code']}   Profile: {lot['product_type']}   Buyer: {lot['buyer'] or 'not specified'}",
        f"Expected: {lot['expected_quantity']}   Registered: {lot_summary['product_count']}   Accepted: {lot_summary['accepted_quantity']}   Rejected: {lot_summary['rejected_quantity']}   Held: {lot_summary['held_quantity']}   Pending: {lot_summary['pending_quantity']}",
        f"Readiness: {'READY FOR DISPATCH AUTHORIZATION' if gate['ready'] else 'BLOCKED'}",
        f"Report generated UTC: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}",
        "Gate blockers and corrective actions:",
    ]
    dispatch=con.execute("SELECT d.quantity,d.created_at,u.username FROM dispatches d JOIN users u ON u.id=d.authorized_by WHERE d.lot_id=? ORDER BY d.created_at DESC LIMIT 1",(lot_id,)).fetchone()
    lines.append(f"Dispatch authorization: {'AUTHORIZED' if dispatch else 'NOT AUTHORIZED'}" + (f"; quantity {dispatch['quantity']}; approved by {dispatch['username']} at {dispatch['created_at']}" if dispatch else ""))
    lines += [f"- {b}" for b in gate["blockers"]] or ["- All configured checks pass."]
    lines.append("Products and latest human decisions:")
    products = con.execute("SELECT id,code FROM products WHERE lot_id=? ORDER BY created_at", (lot_id,)).fetchall()
    for product in products:
        latest=con.execute("SELECT id,state,recommendation FROM inspections WHERE product_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(product["id"],)).fetchone()
        human=con.execute("SELECT outcome,grade FROM decisions WHERE inspection_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(latest["id"],)).fetchone() if latest else None
        lines.append(f"- {product['code']}: inspection {latest['state'] if latest else 'not started'}; AI {latest['recommendation'] or 'unavailable' if latest else 'unavailable'}; human {human['outcome'] if human else 'not recorded'}{(' / '+human['grade']) if human and human['grade'] else ''}")
        if latest:
            result=json.loads(con.execute("SELECT ai_result FROM inspections WHERE id=?",(latest["id"],)).fetchone()["ai_result"] or "null")
            if isinstance(result,dict):lines.append(f"  Model: {result.get('model_version','unreported')}; algorithm: {result.get('algorithm_version','unreported')}")
    pages = [_text_page("Lot quality report", f"Lot {lot['code']} · evidence summary", lines)]
    inspections = con.execute("SELECT i.id FROM inspections i JOIN products p ON p.id=i.product_id WHERE p.lot_id=? ORDER BY i.created_at", (lot_id,)).fetchall()
    for insp in inspections:
        captures = con.execute("SELECT * FROM captures WHERE inspection_id=? ORDER BY sequence", (insp["id"],)).fetchall()
        for capture in captures:
            folder = "images" if capture["source"] in {"operator_upload", "legacy_upload"} else "evidence"
            pages.append(_capture_page(capture, storage / folder / capture["filename"]))
    return _save(pages, storage / "reports" / f"lot-{uuid.uuid4()}.pdf")
