const API = '/api/v1';
const PROFILE = {Leather: 'leather', Footwear: 'footwear', 'Auto component': 'auto_component'};
const LIGHTS = ['normal', 'top', 'left', 'right', 'front', 'back', 'unknown'];
const state = {token: localStorage.getItem('leo_token') || '', user: null, view: 'overview', lot: null, inspection: null, engine: null, chosenCapture: null, previewUrl: null, evidenceUrl: null, zoom: 1, pan: {x: 0, y: 0}, pollToken: 0};
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set('Authorization', `Bearer ${state.token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(API + path, {...options, headers});
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json() : await response.blob();
  if (!response.ok) throw new Error(data.detail?.message || data.detail || `Request failed (${response.status})`);
  return data;
}

function toast(message, error = false) {
  const el = $('#toast'); el.textContent = message; el.classList.toggle('error', error); el.classList.add('show');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove('show'), 3500);
}
function header(title, subtitle, action = '') {
  return `<div class="page-head"><div><div class="eyebrow">LEO-EVE QUALITY OPERATIONS</div><h1>${title}</h1><p>${subtitle}</p></div>${action}</div>`;
}
function panel(title, content, subtitle = '') {
  return `<section class="panel"><div class="panel-head"><div><div class="panel-title">${title}</div>${subtitle ? `<div class="panel-subtitle">${subtitle}</div>` : ''}</div></div>${content}</section>`;
}
function badge(text, tone = '') { return `<span class="badge ${tone}">${esc(text)}</span>`; }

async function start() {
  if (!state.token) return showLogin();
  try {
    state.user = await api('/auth/me');
    $('#user-name').textContent = state.user.username;
    try { const station = await api('/settings/station'); $('#station-name').textContent = station.name || 'Local factory'; } catch { /* Station settings remain optional during login. */ }
    $('#logout').classList.remove('hidden'); $('#login-view').classList.add('hidden'); $('#content').classList.remove('hidden');
    await refreshEngine(); await render();
  } catch {
    state.token = ''; localStorage.removeItem('leo_token'); showLogin();
  }
}
function showLogin() { stopCamera(); $('#login-view').classList.remove('hidden'); $('#content').classList.add('hidden'); $('#logout').classList.add('hidden'); }

async function refreshEngine() {
  try {
    state.engine = await api('/engine/status');
    const available = state.engine.available === true;
    $('#engine-dot').className = available ? 'up' : 'down';
    $('#engine-label').textContent = available ? 'AI engine connected' : 'AI engine unavailable';
  } catch {
    state.engine = null; $('#engine-dot').className = 'down'; $('#engine-label').textContent = 'AI engine unavailable';
  }
}

async function render() {
  stopCamera();
  const sections = {overview:'OVERVIEW', inspection:'INSPECTION WORKSPACE', lots:'LOTS & PRODUCTS', gate:'EXPORT READY GATE', insights:'QUALITY INSIGHTS', settings:'STATION SETTINGS'};
  $('#section-name').textContent = sections[state.view] || 'OVERVIEW';
  document.querySelectorAll('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.view === state.view));
  const handlers = {overview: overview, inspection: inspectionWorkspace, lots: lotsPage, gate: gatePage, insights: insightsPage, settings: settingsPage};
  return (handlers[state.view] || overview)();
}

async function overview() {
  const [s, lots] = await Promise.all([api('/analytics/summary'), api('/lots')]);
  $('#content').innerHTML = header('Quality at a glance', 'A live view of production records and inspection decisions.', '<button class="primary" data-action="new-lot">＋ Create lot</button>') +
    `<div class="metrics">${[['Lots',s.lots,'Production records'],['Products',s.products,'Distinct physical units'],['Inspection attempts',s.inspections,'Includes reinspections'],['Pending review',s.pending_reviews,'Latest inspection needs a decision']].map(x=>`<div class="metric"><div class="metric-label">${x[0]}<span class="metric-icon">◈</span></div><div class="metric-value">${x[1]}</div><div class="metric-foot">${x[2]}</div></div>`).join('')}</div>`+
    `<div class="two-col">${panel('Recent lots', lots.length ? lotTable(lots.slice(0,6)) : empty('No production lots recorded yet.', 'Create a lot to start an inspection record.'), 'Counts are calculated from the local database')}${panel('Inspection rules', `<div class="detail-line"><b>AI advises. A person decides.</b><br>Every physical product must have a completed, covered inspection and a recorded human decision before it can be accepted.<br><br>${badge(s.engine_mode.toUpperCase(), 'neutral')}<br><br>Engine disconnections create failed inspection attempts without synthetic detections.</div>`, 'Evidence stays on this device')}</div>`;
}
function lotTable(lots) {
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Lot</th><th>Profile</th><th>Products</th><th>Accepted</th><th>Rejected</th><th>Progress</th></tr></thead><tbody>${lots.map(l=>`<tr><td><button class="text-button" data-lot="${l.id}">${esc(l.code)}</button></td><td>${esc(l.product_type)}</td><td>${l.product_count}/${l.expected_quantity}</td><td>${l.accepted_quantity}</td><td>${l.rejected_quantity}</td><td>${l.pending_quantity ? badge(`${l.pending_quantity} pending`, 'amber') : badge('Reviewed','green')}</td></tr>`).join('')}</tbody></table></div>`;
}
function empty(title, note = '') { return `<div class="empty"><div class="empty-mark">◇</div><b>${title}</b><span>${note}</span></div>`; }

async function lotsPage() {
  const lots = await api('/lots');
  $('#content').innerHTML = header('Lots & products', 'Register physical products and track the latest human disposition.', '<button class="primary" data-action="new-lot">＋ Create lot</button>') + (lots.length ? lotTable(lots) : `<div class="panel">${empty('No lots recorded.', 'Create the first production lot.')}</div>`);
}
function lotForm() {
  $('#content').innerHTML = header('Create production lot', 'Add the batch information used to organize inspection evidence.') + panel('Lot details', `<form id="lot-form"><div class="form-grid"><label class="field">Lot identifier<input name="code" required maxlength="80" placeholder="AMB-26-001"></label><label class="field">Industry profile<select name="product_type"><option>Leather</option><option>Footwear</option><option>Auto component</option></select></label><label class="field">Buyer<input name="buyer" maxlength="120" placeholder="Required for export readiness"></label><label class="field">Expected quantity<input name="expected_quantity" type="number" min="1" max="100000" required value="1"></label><label class="field">Supplier (optional)<input name="supplier" maxlength="120"></label><label class="field">Machine or drum (optional)<input name="machine" maxlength="120"></label></div><button class="primary">Save lot <span>→</span></button><button class="quiet" type="button" data-action="lots">Cancel</button></form>`);
}

async function productsFor(lotId) { return api(`/lots/${lotId}/products`); }
async function lotDetails(id) {
  const lot = (await api('/lots')).find(row => row.id === id); if (!lot) return toast('Lot not found', true); state.lot = lot;
  const [products, gate, stats] = await Promise.all([productsFor(id), api(`/lots/${id}/export-gate`), api(`/lots/${id}/summary`)]);
  const decision = p => p.inspection?.decision ? esc(p.inspection.decision.outcome) : 'Pending';
  $('#content').innerHTML = header(esc(lot.code), `${esc(lot.product_type)} · ${esc(lot.buyer || 'No buyer configured')} · ${lot.product_count}/${lot.expected_quantity} products`, `<button class="secondary" data-action="add-product">＋ Register product</button>`) +
    `<div class="metrics small-metrics">${[['Accepted',stats.accepted_quantity],['Rejected',stats.rejected_quantity],['Held',stats.held_quantity],['Pending',stats.pending_quantity]].map(x=>`<div class="metric"><div class="metric-label">${x[0]}</div><div class="metric-value">${x[1]}</div></div>`).join('')}</div>`+
    `<div class="two-col">${panel('Physical products', products.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Product ID</th><th>Latest inspection</th><th>Decision</th><th></th></tr></thead><tbody>${products.map(p=>`<tr><td><b>${esc(p.code)}</b></td><td>${p.inspection ? badge(p.inspection.state, p.inspection.state==='completed'?'green':'amber') : 'No inspection'}</td><td>${decision(p)}</td><td>${p.inspection ? `<button class="quiet" data-open-inspection="${p.inspection.id}">View evidence</button>` : ""}<button class="quiet" data-product="${p.id}">${p.inspection ? "Reinspect" : "Inspect"}</button></td></tr>`).join('')}</tbody></table></div>` : empty('No products registered.') , `${stats.inspections_count} inspection attempts; reinspections do not add physical units`)}${panel('Export Ready Gate', `<div class="gate-summary ${gate.ready?'gate-ready':'gate-blocked'}">${gate.ready?'READY FOR AUTHORIZATION':'BLOCKED'}</div><div class="gate-list">${gate.blockers.length?gate.blockers.map(x=>`<div class="gate-item">${esc(x)}</div>`).join(''):empty('All configured checks pass.')}</div><div class="detail-line">${esc(gate.scope_note)}</div>`, 'Current verified state')}</div>`+
    `<div class="panel actions-row"><button class="secondary" data-report-lot="${id}">Download lot quality report PDF</button></div>`;
}
async function addProduct() {
  const list = await productsFor(state.lot.id);
  $('#content').innerHTML = header('Register product', `Lot ${esc(state.lot.code)} · ${list.length}/${state.lot.expected_quantity} registered`) + panel('Product identity', `<form id="product-form"><label class="field">Unique product ID<input name="code" required maxlength="80" placeholder="HIDE-001"></label><button class="primary">Register product</button><button class="quiet" type="button" data-action="back-lot">Cancel</button></form>`);
}

async function inspectionWorkspace() {
  stopCamera();
  const lots = await api('/lots'); let options = '';
  for (const lot of lots) for (const product of await productsFor(lot.id)) options += `<option value="${product.id}" data-lot="${lot.id}" data-profile="${PROFILE[lot.product_type] || 'leather'}">${esc(lot.code)} · ${esc(product.code)}</option>`;
  const caps = state.engine?.capabilities;
  const autoLights = extractCapability(caps, ['supported_lighting_modes','lighting_modes']);
  const profiles = extractCapability(caps, ['supported_profiles','profiles','inspection_profiles']);
  $('#content').innerHTML = header('Capture & inspect', 'Capture a live photo or choose an image file and record the operator-selected lighting condition.') +
    `<div class="inspection-grid"><div class="inspection-main">${panel('Inspection setup', lots.length && options ? `<form id="inspection-form"><div class="form-grid"><label class="field">Product<select name="product_id" required>${options}</select></label><label class="field">Industry profile<select name="industry_profile"><option value="leather">Leather</option><option value="footwear">Footwear</option><option value="auto_component">Auto component</option></select></label><label class="field">Lighting condition<select name="lighting_mode">${LIGHTS.map(x=>`<option value="${x}">${x[0].toUpperCase()+x.slice(1)}</option>`).join('')}</select></label><div class="field">Hardware-controlled modes<div id="supported-lights">${autoLights.length ? autoLights.map(x=>badge(x,'green')).join(' ') : badge('No verified lighting capability','neutral')}</div></div></div>${cameraMarkup()}<label class="dropzone" for="inspection-file"><span>↑</span><b id="file-label">Choose product photograph</b>JPEG or PNG · max 12 MiB · at least 64 × 64<input id="inspection-file" type="file" name="image" accept="image/jpeg,image/png" required></label><div id="upload-preview" class="preview-empty">The selected image preview will appear here before submission.</div><button class="primary" id="submit-inspection">Start inspection <span>→</span></button></form>` : `${empty('Register a product before inspection.')}<button class="primary" data-action="new-lot">Create lot</button>`, 'Manual lighting metadata is recorded with every submitted image')}${panel('Connection and capability report', enginePanel(caps, autoLights, profiles), 'Live Laptop 1 responses only')}</div><aside class="inspection-side">${panel('LEO-EVE activity', state.engine?.available ? empty('No inspection is running.', 'Actual engine events will appear here after a result is received.') : `<div class="status-callout danger">Laptop 1 engine is unavailable. Real inspection submissions will be saved as failed attempts, with no generated detections.</div>`, 'No inferred or fabricated events')}${panel('Capture guidance', `<div class="detail-line">Keep the product and camera still when changing lighting direction. The lighting label is recorded as supplied by the operator. This workstation does not issue ESP32 lighting commands.</div>`, 'Operator-assisted evidence')}</aside></div>`;
  bindCamera($('#inspection-form'));
  $('#inspection-file')?.addEventListener('change', e => previewFile(e.target.files[0]));
  const productSelect = $('#inspection-form select[name=product_id]');
  const syncProfile = () => {
    $('#inspection-form [name=industry_profile]').value = productSelect.selectedOptions[0].dataset.profile;
  };
  if (productSelect) {
    productSelect.addEventListener('change', syncProfile);
    syncProfile();
  }
}
function extractCapability(payload, names) {
  if (!payload || typeof payload !== 'object') return [];
  for (const name of names) if (Array.isArray(payload[name])) return payload[name].filter(x=>typeof x==='string');
  return [];
}
function enginePanel(caps, lights, profiles) {
  if (!state.engine) return `<div class="status-callout danger">Engine status could not be retrieved.</div>`;
  const hw=state.engine.hardware;
  const hardware=capabilityAvailability(hw);
  return `<div class="status-list"><div><span>AI engine</span>${badge(state.engine.available?'Connected':'Unavailable',state.engine.available?'green':'red')}</div><div><span>Hardware status</span>${badge(hardware===true?'Available':hardware===false?'Unavailable':'Unknown',hardware===true?'green':hardware===false?'red':'neutral')}</div><div><span>Algorithm</span><b>${esc(caps?.algorithm_version||'Not reported')}</b></div><div><span>Model</span><b>${esc(caps?.model_version||caps?.model_availability||'Not reported')}</b></div></div><div class="detail-line" style="margin-top:12px">${profiles.length?`Engine profiles: ${profiles.map(esc).join(', ')}`:'No profile capabilities reported.'}<br>${lights.length?`Engine lighting modes: ${lights.map(esc).join(', ')}`:'No automated lighting modes reported.'}</div>${caps?`<details class="raw-details"><summary>Actual capabilities payload</summary><pre class="json-box">${esc(JSON.stringify(caps,null,2))}</pre></details>`:''}`;
}
function capabilityAvailability(payload){if(payload===true||payload===false)return payload;if(!payload||typeof payload!=='object')return null;for(const key of ['available','connected','ready','hardware_available'])if(typeof payload[key]==='boolean')return payload[key];const value=String(payload.status||'').toLowerCase();if(['connected','available','ready','ok'].includes(value))return true;if(['disconnected','unavailable','offline','error'].includes(value))return false;return null;}
function previewFile(file) {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  if (!file) return;
  $('#file-label').textContent=file.name;
  state.previewUrl=URL.createObjectURL(file);
  $('#upload-preview').innerHTML=`<div class="image-stage"><div class="image-transform"><img id="preview-image" alt="Selected original product image"><svg class="defect-overlay" aria-hidden="true"></svg></div></div><div class="zoom-controls"><button class="quiet" data-zoom="out">−</button><button class="quiet" data-zoom="reset">Reset zoom</button><button class="quiet" data-zoom="in">＋</button><span>Drag to pan</span></div>`;
  $('#preview-image').src=state.previewUrl;
  resetPanZoom(); attachPanZoom();
}

async function showInspection(id, captureId = state.chosenCapture) {
  const pollToken=++state.pollToken;const selected=captureId;const record=await api(`/inspections/${id}`); state.inspection=record; state.chosenCapture=record.captures?.find(c=>c.id===selected)?.id||record.captures?.[0]?.id||null; state.zoom=1; state.pan={x:0,y:0};
  const res=record.ai_result||{}; const capture=record.captures?.find(x=>x.id===state.chosenCapture); const originalResult=record.engine_events?.find(e=>e.event_type==='initial_engine_result')?.payload||res;
  const actions=Array.isArray(res.actions)?res.actions:[];
  const activity=actions.length?`<ol class="activity-list">${actions.map((a,i)=>`<li><span class="activity-number">${i+1}</span><div><b>${esc(a.action||a.type||a.name||'Engine action')}</b><p>${esc(a.instruction||a.reason||a.description||'')}</p></div></li>`).join('')}</ol>`:empty('No LEO-EVE action events were returned.','The engine did not provide activity records for this inspection.');
  const cover=res.coverage;
  const coverage=cover?`${cover.inspected_regions??'—'} / ${cover.required_regions??'—'} regions · ${cover.complete===true?'Complete':cover.complete===false?'Incomplete':'Unknown'}`:'Coverage was not reported by the engine.';
  const quality=res.image_quality;
  const instruction=record.state==='awaiting_capture'?activityInstruction(actions):'';
  stopCamera();
  $('#content').innerHTML=header('Human verification',`Product ${esc(record.product_code)} · inspection ${esc(record.id.slice(0,8))}`,`<button class="secondary" data-report-inspection="${record.id}">Inspection report PDF</button>`)+
    `<div class="inspection-grid review-grid"><div class="inspection-main">${panel('Product evidence',capture?`<div class="capture-switcher">${record.captures.map(c=>`<button class="capture-chip ${c.id===state.chosenCapture?'selected':''}" data-capture="${c.id}">#${c.sequence} · ${esc(c.lighting_mode)} · ${esc(c.source)}</button>`).join('')}</div><div class="image-stage"><div class="image-transform"><img id="evidence-image" alt="Recorded product evidence"><svg class="defect-overlay" aria-label="Recorded normalized defect regions"></svg></div></div><div class="zoom-controls"><button class="quiet" data-zoom="out">−</button><button class="quiet" data-zoom="reset">Reset zoom</button><button class="quiet" data-zoom="in">＋</button><span>Drag to pan</span></div><div class="detail-line hash-line">Capture SHA-256: <code>${esc(capture.sha256)}</code> · ${capture.metadata.width||'—'} × ${capture.metadata.height||'—'} · ${esc(capture.lighting_mode)} lighting</div>`:empty('No image evidence is attached to this inspection.') , 'Original files are stored locally and remain unchanged')}${panel('Additional operator evidence', `${instruction?`<div class="request-banner">${esc(instruction)}</div>`:''}<form id="evidence-form"><div class="form-grid"><label class="field">Lighting used<select name="lighting_mode">${LIGHTS.map(x=>`<option value="${x}">${x[0].toUpperCase()+x.slice(1)}</option>`).join('')}</select></label><label class="field">Additional photo<input type="file" name="image" accept="image/jpeg,image/png" required></label></div>${cameraMarkup()}<button class="secondary">Save operator evidence</button></form><div class="notice">Additional photos are stored with lighting metadata, but the agreed Laptop 1 contract does not define how to resubmit them to the engine. Saving here does not change the AI result or inspection status.</div>`, 'Stored separately; not represented as reprocessed by AI')}</div><aside class="inspection-side">${panel('Inspection state',`<div class="state-heading">${badge(record.state,record.state==='completed'?'green':'amber')} ${badge(record.execution_mode.toUpperCase(),'neutral')}</div><div id="poll-state" class="detail-line">${['pending','capturing','analyzing'].includes(record.state)?'Waiting for the engine job status…':''}</div><div class="recommendation"><small>ORIGINAL AI RECOMMENDATION</small><b>${esc(record.recommendation||'Unavailable')}</b></div><div class="status-list"><div><span>Coverage</span><b>${esc(coverage)}</b></div><div><span>Image quality</span><b>${quality?quality.acceptable===true?'Acceptable':quality.acceptable===false?'Unacceptable':'Unknown':'Not reported'}</b></div><div><span>Human decision</span><b>${esc(record.decision?.outcome||'Not recorded')}</b></div></div>${quality?`<div class="detail-line">Warnings: ${esc((quality.warnings||[]).join('; ')||'None reported')}</div>`:''}${record.engine_evidence?`<details class="raw-details"><summary>Laptop 1 evidence metadata</summary><pre class="json-box">${esc(JSON.stringify(record.engine_evidence,null,2))}</pre></details>`:''}`, 'AI output does not approve the product')}${panel('Recorded defects', defectsPanel(record), 'Only engine and inspector annotations are listed')}${decisionPanel(record)}${panel('LEO-EVE activity',activity,'Events returned by Laptop 1')}${panel('Capture and model details',`<div class="detail-line">Profile: ${esc(res.profile||'Not reported')}<br>Algorithm version: ${esc(res.algorithm_version||'Not reported')}<br>Model version: ${esc(res.model_version||'Not reported')}<br>Processing time: ${res.processing_time_ms??'Not reported'} ms</div><details class="raw-details"><summary>Initial AI response</summary><pre class="json-box">${esc(JSON.stringify(originalResult,null,2))}</pre></details><details class="raw-details"><summary>Actual engine status events (${record.engine_events?.length||0})</summary><pre class="json-box">${esc(JSON.stringify(record.engine_events||[],null,2))}</pre></details>`, 'Original AI record is preserved')}</aside></div>`;
  bindCamera($('#evidence-form'));
  if(capture) await loadImage($('#evidence-image'),capture.image_url);
  if (capture?.sequence === 1) renderDefectOverlay(record.defects || []);
  attachPanZoom();
  if(['pending','capturing','analyzing'].includes(record.state)&&record.ai_result?.inspection_id)pollInspection(id,pollToken);
  else if(['pending','capturing','analyzing'].includes(record.state))$('#poll-state').textContent='Engine job ID unavailable; this result cannot be polled until the agreed contract provides one.';
}
async function pollInspection(id,pollToken){for(let i=0;i<60;i++){await new Promise(resolve=>setTimeout(resolve,2000));if(pollToken!==state.pollToken||state.view!=='inspection')return;try{const result=await api(`/inspections/${id}/refresh`);if(pollToken!==state.pollToken)return;const el=$('#poll-state');if(el)el.textContent=result.error?`Status check failed: ${result.error}`:`Laptop 1 status: ${result.state}`;if(!result.pollable){await showInspection(id);return;}if(result.inspection&&result.inspection.engine_events?.length!==state.inspection?.engine_events?.length){await showInspection(id);return;}}catch(error){const el=$('#poll-state');if(el)el.textContent=`Status check failed: ${error.message}`;}}const el=$('#poll-state');if(el)el.textContent='Polling window ended; latest engine state remains pending.';}
function activityInstruction(actions) {
  const action=actions.find(a=>String(a.action||a.type||'').toLowerCase().includes('capture')||String(a.action||a.type||'').toLowerCase().includes('image')||String(a.action||a.type||'').toLowerCase().includes('lighting'));
  return action?.instruction||action?.reason||action?.description||'The engine requested additional evidence. Follow the recorded engine action above before collecting another image.';
}
async function loadImage(img,url) {
  try { const response=await fetch(url,{headers:{Authorization:`Bearer ${state.token}`}}); if(!response.ok)throw new Error(); const blob=await response.blob();if(state.evidenceUrl)URL.revokeObjectURL(state.evidenceUrl);state.evidenceUrl=URL.createObjectURL(blob);await new Promise((resolve,reject)=>{img.onload=()=>{const svg=img.parentElement.querySelector('svg');svg.setAttribute('viewBox',`0 0 ${img.naturalWidth} ${img.naturalHeight}`);resolve();};img.onerror=reject;img.src=state.evidenceUrl;}); }
  catch { img.alt='Evidence image could not be retrieved'; }
}
function renderDefectOverlay(defects) {
  const svg=$('.defect-overlay');const img=$('.image-transform img');if(!svg||!img?.naturalWidth)return;
  svg.innerHTML='';svg.setAttribute('viewBox',`0 0 ${img.naturalWidth} ${img.naturalHeight}`);
  defects.forEach((d,index)=>{if(![d.x,d.y,d.width,d.height].every(Number.isFinite))return;const i=index;
    const x=d.x*img.naturalWidth,y=d.y*img.naturalHeight,w=d.width*img.naturalWidth,h=d.height*img.naturalHeight;
    const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');rect.setAttribute('x',x);rect.setAttribute('y',y);rect.setAttribute('width',w);rect.setAttribute('height',h);rect.setAttribute('class',`box ${d.status==='false_positive'?'false-positive':''}`);svg.appendChild(rect);
    const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('cx',x);circle.setAttribute('cy',y);circle.setAttribute('r',Math.max(18,Math.min(img.naturalWidth,img.naturalHeight)*.025));circle.setAttribute('class','marker');svg.appendChild(circle);
    const text=document.createElementNS('http://www.w3.org/2000/svg','text');text.setAttribute('x',x);text.setAttribute('y',y);text.setAttribute('class','marker-text');text.textContent=String(i+1);svg.appendChild(text);
  });
}
function defectsPanel(record) {
  const defects=record.defects||[];
  const rows=defects.map((d,i)=>`<div class="defect-row"><span class="defect-marker">${i+1}</span><div class="defect-copy"><b>${esc(d.label)}</b><small>Original: ${esc(d.original_label||'operator entry')} · ${esc(d.status)}</small></div><button class="quiet" data-defect="${d.id}" data-defect-action="edit">Correct</button><button class="quiet danger-text" data-defect="${d.id}" data-defect-action="false">False positive</button></div>`).join('');
  return `${defects.length?rows:empty('No defect records were returned or entered.','An empty list is not an automatic Pass.')}<form id="manual-defect-form" class="manual-defect-form"><div class="form-grid"><label class="field">Add a missing defect<input name="label" required maxlength="100" placeholder="Defect label"></label><label class="field">Inspector note<input name="notes" maxlength="500" placeholder="Reason or location"></label><label class="field">Normalized x (optional)<input name="x" type="number" min="0" max="1" step="any"></label><label class="field">Normalized y (optional)<input name="y" type="number" min="0" max="1" step="any"></label><label class="field">Width (optional)<input name="width" type="number" min="0.001" max="1" step="any"></label><label class="field">Height (optional)<input name="height" type="number" min="0.001" max="1" step="any"></label></div><button class="quiet">＋ Add manual defect</button></form>`;
}
function decisionPanel(record) {
  if(record.state!=='completed')return panel('Human verification',`${empty('Acceptance is unavailable until the inspection is complete.','Record HOLD or REJECT if the current evidence cannot support acceptance.')}<div class="decision-row"><button class="quiet" data-decision="HOLD">Hold</button><button class="quiet danger-text" data-decision="REJECT">Reject</button></div><label class="field reason-field">Decision reason<input id="decision-reason" maxlength="1000" required></label>`, 'No automatic decision');
  const res=record.ai_result||{}, canAccept=res.coverage?.complete===true&&res.image_quality?.acceptable===true;
  return panel('Inspector decision',`${record.decision?`<div class="notice">Latest saved decision: <b>${esc(record.decision.outcome)}</b> · ${esc(record.decision.notes)}</div>`:''}${canAccept?'':`<div class="status-callout danger">Pass and Grade are blocked until complete coverage and acceptable capture quality are recorded.</div>`}<div class="decision-row">${canAccept?'<button class="primary" data-decision="PASS">Pass</button><button class="secondary" data-decision="GRADE">Grade</button>':''}<button class="quiet danger-text" data-decision="REJECT">Reject</button><button class="quiet" data-decision="HOLD">Hold</button></div><label class="field reason-field">Decision reason<input id="decision-reason" maxlength="1000" required placeholder="Explain the verification decision"></label><label class="field grade-field">Grade<input id="decision-grade" maxlength="40" placeholder="e.g. A / B"></label>`, 'Inspector must record the reason');
}
function resetPanZoom() { state.zoom=1;state.pan={x:0,y:0}; }
function applyTransform() { const el=$('.image-transform'); if(el)el.style.transform=`translate(${state.pan.x}px,${state.pan.y}px) scale(${state.zoom})`; }
function attachPanZoom() {
  const stage=$('.image-stage'),transform=$('.image-transform'); if(!stage||!transform)return;
  stage.onpointerdown=e=>{if(e.target.closest('button'))return;stage.setPointerCapture(e.pointerId);stage.dataset.dragX=e.clientX-state.pan.x;stage.dataset.dragY=e.clientY-state.pan.y;};
  stage.onpointermove=e=>{if(!stage.hasPointerCapture(e.pointerId))return;state.pan={x:e.clientX-Number(stage.dataset.dragX),y:e.clientY-Number(stage.dataset.dragY)};applyTransform();};
  stage.onpointerup=e=>{if(stage.hasPointerCapture(e.pointerId))stage.releasePointerCapture(e.pointerId);};
  stage.onwheel=e=>{e.preventDefault();state.zoom=Math.max(1,Math.min(4,state.zoom+(e.deltaY<0?.15:-.15)));applyTransform();};
}
function setZoom(action) { if(action==='reset')resetPanZoom();else state.zoom=Math.max(1,Math.min(4,state.zoom+(action==='in'?.25:-.25)));applyTransform(); }

async function gatePage() {
  const lots=await api('/lots');const rows=await Promise.all(lots.map(async lot=>({lot,gate:await api(`/lots/${lot.id}/export-gate`)})));
  $('#content').innerHTML=header('Export Ready Gate','Buyer rules, complete evidence and human decisions are checked on the backend.')+(rows.length?`<div class="panel table-wrap"><table class="table"><thead><tr><th>Lot</th><th>Registered</th><th>Accepted</th><th>Rejected</th><th>Gate</th><th>Blocking items</th><th>Report</th></tr></thead><tbody>${rows.map(({lot,gate})=>`<tr><td><button class="text-button" data-lot="${lot.id}">${esc(lot.code)}</button></td><td>${gate.registered_quantity}/${gate.expected_quantity}</td><td>${gate.accepted_quantity}</td><td>${gate.rejected_quantity}</td><td>${badge(gate.ready?'READY':'BLOCKED',gate.ready?'green':'red')}</td><td>${esc(gate.blockers.join(' · ')||'Configured checks pass')}</td><td><button class="quiet" data-report-lot="${lot.id}">PDF</button></td></tr>${gate.ready?`<tr><td colspan="7"><form class="dispatch-form" data-dispatch="${lot.id}"><label>Authorize accepted quantity <input name="quantity" type="number" min="1" value="${gate.accepted_quantity}" required></label><button class="primary">Owner: authorize dispatch</button></form></td></tr>`:''}`).join('')}</tbody></table><div class="notice">Reports are local quality summaries. No QR certificate, public verification or government export approval is issued.</div></div>`:empty('No lots to evaluate.'));
}

async function insightsPage() {
  const data=await api('/analytics/quality');
  const categories=data.defect_frequency_by_label||[];
  const sourceTable=(map)=>Object.entries(map||{}).map(([name,row])=>`<div class="source-row"><b>${esc(name)}</b><span>${row.products_with_recorded_defects}/${row.product_count} products</span><strong>${row.rate===null?'—':(row.rate*100).toFixed(1)+'%'}</strong></div>`).join('')||empty('Insufficient grouped records.');
  $('#content').innerHTML=header('Quality insights','Transparent summaries calculated from recorded inspection and human-review data.')+
    `<div class="two-col">${panel('Recorded defect frequency',data.data_state==='insufficient_data'?empty('Insufficient recorded data.','Defect categories appear after actual engine or inspector annotations are stored.'):`<div class="bar-list">${categories.map(x=>`<div class="bar-row"><span>${esc(x.label)}</span><div class="bar-track"><i style="width:${Math.max(3,100*x.distinct_products/Math.max(1,categories[0]?.distinct_products||1))}%"></i></div><b>${x.distinct_products}</b></div>`).join('')}</div>`,'Distinct products with latest-inspection annotations')}${panel('Human decision divergence',`<div class="metric-value">${data.human_decisions.recorded_divergences} / ${data.human_decisions.count}</div><div class="detail-line">${esc(data.human_decisions.interpretation)}</div>`,'Operational review signal')}${panel('Defect rate by lot',data.defect_rate_by_lot.length?`<div class="table-wrap"><table class="table"><thead><tr><th>Lot</th><th>Products with defects</th><th>Total</th><th>Rate</th></tr></thead><tbody>${data.defect_rate_by_lot.map(x=>`<tr><td>${esc(x.lot_code)}</td><td>${x.products_with_recorded_defects}</td><td>${x.product_count}</td><td>${x.rate===null?'—':(x.rate*100).toFixed(1)+'%'}</td></tr>`).join('')}</tbody></table></div>`:empty('No lot records.'))}${panel('Defect rate by supplier',sourceTable(data.defect_rate_by_supplier),'Recorded associations; not root-cause attribution')}${panel('Defect rate by machine or drum',sourceTable(data.defect_rate_by_machine),'Recorded associations; not root-cause attribution')}${panel('Repeated patterns',data.repeated_defect_patterns.length?data.repeated_defect_patterns.map(x=>`<div class="source-row"><b>${esc(x.label)}</b><span>${x.distinct_products} distinct products</span></div>`).join(''):empty('No repeated label pattern or insufficient data.'))}${panel('Inspection processing time',`<div class="metric-value">${data.inspection_processing_time_ms.mean===null?'—':Math.round(data.inspection_processing_time_ms.mean)} ms</div><div class="detail-line">${data.inspection_processing_time_ms.sample_count} engine-reported durations · median ${data.inspection_processing_time_ms.median===null?'—':Math.round(data.inspection_processing_time_ms.median)+' ms'}</div>`,'Measured results only')}</div>`;
}

async function settingsPage() {
  const [station,rules]=await Promise.all([api('/settings/station'),api('/quality-rules/buyers')]);
  $('#content').innerHTML=header('Station settings','Configure the local station and buyer rules. Engine authentication token stays in the backend environment.')+`<div class="two-col">${panel('Inspection station',`<form id="station-form"><label class="field">Station name<input name="name" value="${esc(station.name)}" required></label><label class="field">Laptop 1 AI engine URL<input name="engine_url" value="${esc(station.engine_url)}" required></label><div class="detail-line">Connection token: ${station.token_configured?'Configured in backend environment':'Not configured'}</div><button class="primary">Save station</button><button class="secondary" type="button" data-action="test-engine">Test connection</button></form><div id="engine-test-result"></div>`,`Engine status comes from actual health, hardware and capabilities endpoints`)}${panel('Buyer quality requirements',`<form id="buyer-rule-form"><label class="field">Buyer name<input name="buyer" required></label><label class="field">Inspection profile<select name="profile"><option value="leather">Leather</option><option value="footwear">Footwear</option><option value="auto_component">Auto component</option></select></label><label class="field check-field"><input type="checkbox" name="require_coverage" checked> Require complete coverage</label><label class="field">Required measurement names<input name="required_measurements" placeholder="Thickness, Weight (comma separated)"></label><label class="field">Required lab report types<input name="required_labs" placeholder="Chemical, Physical (comma separated)"></label><button class="primary">Save buyer rule</button></form><div class="rule-list">${rules.map(r=>`<div>${esc(r.buyer)} · ${esc(r.profile)} · ${r.required_measurements.length} measurements · ${r.required_labs.length} lab reports</div>`).join('')||empty('No buyer rules configured.')}</div>`, 'Readiness is blocked for unconfigured buyers')}</div>`;
}

async function loadAuthenticatedBlob(path) {
  const response=await fetch(path,{headers:{Authorization:`Bearer ${state.token}`}});
  if(!response.ok)throw new Error((await response.json()).detail||'Download failed');
  const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=response.headers.get('content-disposition')?.match(/filename="?([^";]+)"?/i)?.[1]||'leo-report.pdf';a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}

document.addEventListener('click', async event => {
  const nav=event.target.closest('[data-view]');
  if(nav){state.view=nav.dataset.view;try{await render()}catch(e){toast(e.message,true)}return;}
  const zoom=event.target.closest('[data-zoom]');if(zoom){setZoom(zoom.dataset.zoom);return;}
  const lot=event.target.closest('[data-lot]');if(lot){state.view='lots';try{stopCamera();await lotDetails(lot.dataset.lot)}catch(e){toast(e.message,true)}return;}
  const review = event.target.closest('[data-open-inspection]');
  if (review) {
    state.view = 'inspection';
    return showInspection(review.dataset.openInspection).catch(error => toast(error.message, true));
  }
  const product=event.target.closest('[data-product]');if(product){state.view='inspection';try{await inspectionWorkspace();const select=$('#inspection-form [name=product_id]');select.value=product.dataset.product;select.dispatchEvent(new Event('change'));}catch(e){toast(e.message,true)}return;}
  const capture=event.target.closest('[data-capture]');if(capture){state.chosenCapture=capture.dataset.capture;return showInspection(state.inspection.id).catch(e=>toast(e.message,true));}
  const action=event.target.closest('[data-action]')?.dataset.action;
  if(action==='new-lot'){stopCamera();lotForm();return;}if(action==='lots'){state.view='lots';return render();}if(action==='add-product'){return addProduct();}if(action==='back-lot'){return lotDetails(state.lot.id);}if(action==='test-engine'){const el=$('#engine-test-result');el.innerHTML='<div class="notice">Checking configured Laptop 1 endpoints…</div>';await refreshEngine();el.innerHTML=`<div class="status-callout ${state.engine?.available?'success':'danger'}">${state.engine?.available?'Health endpoint connected':'Connection or health check failed'}<pre class="json-box">${esc(JSON.stringify(state.engine,null,2))}</pre></div>`;return;}
  const reportInspection=event.target.closest('[data-report-inspection]');if(reportInspection){try{await loadAuthenticatedBlob(`${API}/reports/inspections/${reportInspection.dataset.reportInspection}.pdf`)}catch(e){toast(e.message,true)}return;}
  const reportLot=event.target.closest('[data-report-lot]');if(reportLot){try{await loadAuthenticatedBlob(`${API}/reports/lots/${reportLot.dataset.reportLot}.pdf`)}catch(e){toast(e.message,true)}return;}
  const decision=event.target.closest('[data-decision]');if(decision){const reason=$('#decision-reason')?.value.trim()||'';if(!reason){toast('Enter a decision reason first.',true);$('#decision-reason')?.focus();return;}const grade=$('#decision-grade')?.value.trim()||null;if(decision.dataset.decision==='GRADE'&&!grade){toast('Enter a grade before saving.',true);$('#decision-grade')?.focus();return;}try{await api(`/inspections/${state.inspection.id}/decisions`,{method:'POST',body:JSON.stringify({outcome:decision.dataset.decision,grade,notes:reason})});toast('Human decision saved.');await showInspection(state.inspection.id)}catch(e){toast(e.message,true)}return;}
  const defect=event.target.closest('[data-defect-action]');if(defect){const old=state.inspection.defects.find(d=>d.id===defect.dataset.defect);const falsePositive=defect.dataset.defectAction==='false';const label=falsePositive?old.label:prompt('Corrected defect label:',old.label);if(label===null)return;const notes=prompt(falsePositive?'Reason for marking false positive:':'Reason for correction:',old.notes||'')||'';try{await api(`/inspections/${state.inspection.id}/defects/${old.id}`,{method:'PATCH',body:JSON.stringify({label,status:falsePositive?'false_positive':'corrected',notes})});toast('Annotation updated; original AI response is preserved.');await showInspection(state.inspection.id)}catch(e){toast(e.message,true)}return;}
});

document.addEventListener('submit',async event=>{
  event.preventDefault();const form=event.target;
  try{
    if(form.id==='login-form'){const fd=new FormData(form);const data=await api('/auth/login',{method:'POST',body:JSON.stringify({username:fd.get('username'),password:fd.get('password')})});state.token=data.token;localStorage.setItem('leo_token',state.token);return start();}
    if(form.id==='lot-form'){const fd=new FormData(form);const data=await api('/lots',{method:'POST',body:JSON.stringify(Object.fromEntries(fd))});state.lot=data;state.view='lots';toast('Lot created.');return lotDetails(data.id);}
    if(form.id==='product-form'){const fd=new FormData(form);await api(`/lots/${state.lot.id}/products`,{method:'POST',body:JSON.stringify({code:fd.get('code')})});toast('Product registered.');return lotDetails(state.lot.id);}
    if(form.id==='inspection-form'){const button=$('#submit-inspection');const file=fdFile(form);if(!file)throw new Error('Choose an image first.');stopCamera();button.disabled=true;button.textContent='Submitting to Laptop 1…';const fd=new FormData(form);const key=crypto.randomUUID();const data=await api(`/products/${fd.get('product_id')}/inspections`,{method:'POST',headers:{'Idempotency-Key':key},body:(()=>{const body=new FormData();body.append('image',file);body.append('industry_profile',fd.get('industry_profile'));body.append('lighting_mode',fd.get('lighting_mode'));return body})()});state.view='inspection';toast(data.state==='completed'?'Engine result received. Human verification is still required.':`Inspection state: ${data.state}`);return showInspection(data.id);}
    if(form.id==='evidence-form'){const fd=new FormData(form),file=fd.get('image');if(!file?.size)throw new Error('Choose an additional image.');const body=new FormData();body.append('image',file);body.append('lighting_mode',fd.get('lighting_mode'));stopCamera();const saved=await api(`/inspections/${state.inspection.id}/evidence`,{method:'POST',body});toast('Additional evidence saved locally. It was not submitted to Laptop 1.');return showInspection(state.inspection.id, saved.id);}
    if(form.id==='manual-defect-form'){const fd=new FormData(form);const body={label:fd.get('label'),notes:fd.get('notes')||''};for(const k of ['x','y','width','height'])if(fd.get(k)!=='')body[k]=Number(fd.get(k));await api(`/inspections/${state.inspection.id}/defects`,{method:'POST',body:JSON.stringify(body)});toast('Manual defect added.');return showInspection(state.inspection.id);}
    if(form.id==='station-form'){const fd=new FormData(form);const station=await api('/settings/station',{method:'PUT',body:JSON.stringify(Object.fromEntries(fd))});$('#station-name').textContent=station.name||'Local factory';toast('Station settings saved.');await refreshEngine();return settingsPage();}
    if(form.id==='buyer-rule-form'){const fd=new FormData(form);await api('/quality-rules/buyers',{method:'PUT',body:JSON.stringify({buyer:fd.get('buyer'),profile:fd.get('profile'),require_coverage:fd.has('require_coverage'),required_measurements:fd.get('required_measurements').split(',').map(x=>x.trim()).filter(Boolean),required_labs:fd.get('required_labs').split(',').map(x=>x.trim()).filter(Boolean)})});toast('Buyer requirements saved.');return settingsPage();}
    if(form.matches('.dispatch-form')){const fd=new FormData(form);await api(`/lots/${form.dataset.dispatch}/authorize-dispatch`,{method:'POST',body:JSON.stringify({quantity:Number(fd.get('quantity'))})});toast('Dispatch authorization recorded.');return gatePage();}
  }catch(error){if(form.id==='login-form')$('#login-error').textContent=error.message;else toast(error.message,true);const button=$('#submit-inspection');if(button){button.disabled=false;button.innerHTML='Start inspection <span>→</span>';}}
});
function fdFile(form){return new FormData(form).get('image');}

$('#logout').addEventListener('click',async()=>{try{await api('/auth/logout',{method:'POST'})}catch{}state.token='';localStorage.removeItem('leo_token');showLogin();});
start();
