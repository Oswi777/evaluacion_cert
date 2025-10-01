// Tabs (home/admin)
document.querySelectorAll(".tab-btn").forEach(btn=>{
  btn.addEventListener("click", ()=>{
    document.querySelectorAll(".tab-btn").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab").forEach(s=>s.classList.remove("active"));
    document.getElementById("tab-"+btn.dataset.tab).classList.add("active");
  });
});

let CURRENT_ID = null;
let TEMPLATE = null;
let SIGN_ROLES = [];
let RESULT_OPTIONS = [];

// DOM refs
const genBox = document.getElementById("general-fields");
const secS = document.getElementById("sec-S");
const secP = document.getElementById("sec-P");
const secQ = document.getElementById("sec-Q");
const secVC = document.getElementById("sec-VC");
const resBox = document.getElementById("resultado-box");
const firmasBox = document.getElementById("firmas-box");
const edStatus = document.getElementById("ed-status");

// Plantilla
async function loadTemplate(){
  const res = await fetch("/api/evaluaciones/plantilla").then(r=>r.json());
  TEMPLATE = res;
  SIGN_ROLES = res.meta?.sign_roles || [];
  RESULT_OPTIONS = res.meta?.result_options || [];
}

// ---- UI builders ----
function inputControl(name, label, required){
  const isDate = ["fecha_ingreso","fecha_inicio_entrenamiento","fecha_revision"].includes(name);
  const wrap = document.createElement("label");
  if (isDate){
    wrap.innerHTML = `${label}<input type="date" name="${name}" ${required?"required":""}/>`;
  } else {
    wrap.innerHTML = `${label}<input name="${name}" ${required?"required":""}/>`;
  }
  return wrap;
}
function selectResult(name, label, options){
  const wrap = document.createElement("label");
  const opts = options.map(o=>`<option value="${o}">${o}</option>`).join("");
  wrap.innerHTML = `${label}<select name="${name}" required><option value="">Selecciona…</option>${opts}</select>`;
  return wrap;
}
function questionRow(q){
  const div = document.createElement("div");
  div.className = "qrow";
  const rev = ["r1","r2","r3"].map(r=>`
    <span class="rev">
      <small>${r.toUpperCase()}</small>
      <select name="${q.key}_${r}">
        <option value=""></option>
        <option value="si">Sí</option>
        <option value="no">No</option>
      </select>
    </span>
  `).join("");
  div.innerHTML = `
    <div class="qlabel">${q.label}</div>
    <div class="qrev">
      ${rev}
      <span class="qbulk">
        <button type="button" class="bulk-yes" data-key="${q.key}">Sí (1-2-3)</button>
        <button type="button" class="bulk-no" data-key="${q.key}">No (1-2-3)</button>
      </span>
    </div>
    <div class="qobs">
      <input name="${q.key}_obs" placeholder="Observaciones"/>
    </div>
  `;
  div.querySelector(".bulk-yes").addEventListener("click", ()=>{
    ["r1","r2","r3"].forEach(r=>{
      const el = div.querySelector(`select[name="${q.key}_${r}"]`);
      if (el) el.value = "si";
    });
  });
  div.querySelector(".bulk-no").addEventListener("click", ()=>{
    ["r1","r2","r3"].forEach(r=>{
      const el = div.querySelector(`select[name="${q.key}_${r}"]`);
      if (el) el.value = "no";
    });
  });
  return div;
}

function renderEditor(){
  // Generales
  genBox.innerHTML = "";
  TEMPLATE.general.forEach(g=> genBox.appendChild(inputControl(g.key, g.label, g.is_required)) );

  // Secciones
  function renderSection(container, arr){
    container.innerHTML = "";
    arr.forEach(q=> container.appendChild(questionRow(q)) );
  }
  renderSection(secS, TEMPLATE.S);
  renderSection(secP, TEMPLATE.P);
  renderSection(secQ, TEMPLATE.Q);
  renderSection(secVC, TEMPLATE.VC);

  // Resultado
  resBox.innerHTML = "";
  resBox.appendChild(selectResult("resultado_global","Resultado", RESULT_OPTIONS));
  resBox.appendChild(inputControl("comentarios","Comentarios", false));

  // Firmas
  firmasBox.innerHTML = "";
  SIGN_ROLES.forEach(role=>{
    const b = document.createElement("button");
    b.textContent = `Firmar: ${role.replaceAll("_"," ")}`;
    b.addEventListener("click", ()=> openSignature(role));
    firmasBox.appendChild(b);
  });
}

// ----- Reset + hidratación -----
function resetEditorFields(){
  const form = document.getElementById("editor");
  form.querySelectorAll("input, select, textarea").forEach(el=>{
    if (el.type === "checkbox" || el.type === "radio") el.checked = false;
    else el.value = "";
  });
}

async function hydrateEditor(id){
  const data = await API.getResponses(id);
  if (data?.items && Array.isArray(data.items)) {
    const map = Object.fromEntries(data.items.map(x=>[x.field_key, x.value ?? ""]));
    const form = document.getElementById("editor");
    form.querySelectorAll("input, select, textarea").forEach(el=>{
      if (!el.name) return;
      if (map.hasOwnProperty(el.name)) el.value = map[el.name];
    });
  }
}

// ---- Admin lists + filtros ----
let ADMIN_FILTER = "both"; // "pend" | "comp" | "both"

function applyAdminFilter(){
  const colPend = document.querySelector("#tab-admin > .admin-grid > div:nth-child(1)");
  const colComp = document.querySelector("#tab-admin > .admin-grid > div:nth-child(2)");
  colPend.classList.remove("hidden");
  colComp.classList.remove("hidden");
  if (ADMIN_FILTER === "pend") colComp.classList.add("hidden");
  if (ADMIN_FILTER === "comp") colPend.classList.add("hidden");
}

async function loadPendientes(){
  const data = await API.listPendientes();
  const ul = document.getElementById("list-pendientes");
  ul.innerHTML = "";
  if (data?.error || !Array.isArray(data?.items)) {
    const msg = document.createElement("li");
    msg.className = "item";
    msg.innerHTML = `<div><strong>Error</strong><br/><small>${data?.error || "No se pudo obtener pendientes"}</small></div>`;
    ul.appendChild(msg);
    return;
  }
  data.items.forEach(item=>{
    const li = document.createElement("li");
    li.className = "item";
    li.innerHTML = `
      <div>
        <strong>${item.folio}</strong><br/>
        <small>Creada: ${new Date(item.created_at).toLocaleString()}</small>
      </div>
      <div class="row gap">
        <button data-id="${item.id}" class="btn-editar">Continuar</button>
        <button data-id="${item.id}" class="btn-delete">Eliminar</button>
      </div>`;
    ul.appendChild(li);
  });
  ul.querySelectorAll(".btn-editar").forEach(b=>{
    b.addEventListener("click", ()=> openEditor(+b.dataset.id));
  });
  ul.querySelectorAll(".btn-delete").forEach(b=>{
    b.addEventListener("click", async ()=>{
      if (!confirm("¿Eliminar esta evaluación? Esta acción no se puede deshacer.")) return;
      const r = await API.deleteEvaluation(+b.dataset.id);
      if (r?.ok) { await loadPendientes(); await loadCompletadas(); }
      else alert(r?.error || "No se pudo eliminar");
    });
  });
}

async function loadCompletadas(){
  const data = await API.listCompletadas();
  const ul = document.getElementById("list-completadas");
  ul.innerHTML = "";
  if (data?.error || !Array.isArray(data?.items)) {
    const msg = document.createElement("li");
    msg.className = "item";
    msg.innerHTML = `<div><strong>Error</strong><br/><small>${data?.error || "No se pudo obtener completadas"}</small></div>`;
    ul.appendChild(msg);
    return;
  }
  data.items.forEach(item=>{
    const li = document.createElement("li");
    li.className = "item";
    const url = API.exportUrl(item.id);
    li.innerHTML = `
      <div>
        <strong>${item.folio}</strong><br/>
        <small>Completada: ${new Date(item.created_at).toLocaleString()}</small>
      </div>
      <div class="row gap">
        <a href="${url}" target="_blank"><button>Exportar PDF</button></a>
        <button data-id="${item.id}" class="btn-delete">Eliminar</button>
      </div>`;
    ul.appendChild(li);
  });
  ul.querySelectorAll(".btn-delete").forEach(b=>{
    b.addEventListener("click", async ()=>{
      if (!confirm("¿Eliminar esta evaluación?")) return;
      const r = await API.deleteEvaluation(+b.dataset.id);
      if (r?.ok) { await loadPendientes(); await loadCompletadas(); }
      else alert(r?.error || "No se pudo eliminar");
    });
  });
}

document.getElementById("btn-refresh-pendientes")?.addEventListener("click", async ()=>{
  ADMIN_FILTER = "pend"; applyAdminFilter(); await loadPendientes();
});
document.getElementById("btn-refresh-completadas")?.addEventListener("click", async ()=>{
  ADMIN_FILTER = "comp"; applyAdminFilter(); await loadCompletadas();
});

// ---- Home actions ----
document.getElementById("home-admin").addEventListener("click", ()=>{
  document.querySelector(`.tab-btn[data-tab="admin"]`).click();
  ADMIN_FILTER = "both"; applyAdminFilter();
  loadPendientes(); loadCompletadas();
});

document.getElementById("home-empezar").addEventListener("click", async ()=>{
  const msg = document.getElementById("home-msg");
  msg.textContent = "";
  const manual = document.getElementById("home-folio").value.trim();
  const folio = manual || generateFolio();
  try{
    const res = await API.createEvaluation(folio);
    if (res.error){ msg.textContent = res.error; return; }
    openEditor(res.id, `Creada evaluación #${res.id} (${res.folio}).`);
  }catch(err){
    msg.textContent = "No se pudo crear la evaluación. Revisa el servidor.";
  }
});

// ---- Editor flow ----
async function openEditor(id, statusMsg=""){
  CURRENT_ID = id;
  document.querySelectorAll(".tab").forEach(s=>s.classList.remove("active"));
  document.getElementById("tab-editor").classList.add("active");
  edStatus.textContent = statusMsg || `Editando evaluación #${CURRENT_ID}`;
  resetEditorFields();             // limpia UI (evita “copiar” datos entre evaluaciones)
  await hydrateEditor(CURRENT_ID); // carga valores guardados
  document.getElementById("tab-editor").scrollIntoView({behavior:"smooth", block:"start"});
}

document.getElementById("btn-guardar").addEventListener("click", async ()=>{
  if(!CURRENT_ID){ alert("Primero crea una evaluación."); return; }
  const form = document.getElementById("editor");
  const inputs = form.querySelectorAll("input, select, textarea");
  const responses = [];
  inputs.forEach(el=>{
    if(!el.name) return;
    responses.push({ field_key: el.name, value: el.value ?? "" });
  });
  const r = await API.saveResponses(CURRENT_ID, responses);
  if (r?.error) { edStatus.textContent = `Error al guardar: ${r.error}`; return; }
  edStatus.textContent = `Guardado. Requeridos: ${r.required_filled}/${r.required_total}`;
  const adminVisible = document.getElementById("tab-admin").classList.contains("active");
  if (adminVisible) await loadPendientes();
});

document.getElementById("btn-completar").addEventListener("click", async ()=>{
  if(!CURRENT_ID){ alert("Primero crea una evaluación."); return; }
  const r = await API.complete(CURRENT_ID);
  if (r.error){ edStatus.textContent = `Error: ${r.error}`; return; }
  if (r.ok){
    edStatus.textContent = "¡Completada! Exporta desde el Panel administrador.";
    await loadPendientes(); await loadCompletadas();
  } else {
    const faltan = [];
    if (r.missing_required?.length) faltan.push(`Campos: ${r.missing_required.slice(0,5).join(", ")}${r.missing_required.length>5?"…":""}`);
    if (r.missing_sign_roles?.length) faltan.push(`Firmas: ${r.missing_sign_roles.join(", ")}`);
    edStatus.textContent = "Faltantes → " + faltan.join(" | ");
  }
});

const modal = document.getElementById("modal-firma");
const sigTitle = document.getElementById("firma-title");
const sigName = document.getElementById("firma-nombre");
let PENDING_ROLE = null;

function openSignature(role){
  if (!CURRENT_ID) return alert("Primero crea una evaluación.");
  PENDING_ROLE = role;
  sigTitle.textContent = `Firma — ${role.replaceAll("_"," ")}`;
  sigName.value = "";
  modal.classList.remove("hidden");
  // Inicializa/limpia listeners y canvas SIEMPRE que se abre
  SIG.open();
  SIG.clear();
}
document.getElementById("sig-clear").addEventListener("click", ()=> SIG.clear());
document.getElementById("sig-cancel").addEventListener("click", ()=>{
  SIG.close();
  modal.classList.add("hidden");
});
document.getElementById("sig-guardar").addEventListener("click", async ()=>{
  const name = sigName.value.trim();
  if (!name) return alert("Escribe el nombre del firmante");
  const dataUrl = SIG.toDataURL();
  const r = await API.sign(CURRENT_ID, PENDING_ROLE, name, dataUrl);
  if (r.error) { alert(r.error); return; }
  SIG.close();
  modal.classList.add("hidden");
  // feedback UI
  const who = (r.role || "").replaceAll("_"," ");
  const msg = `Firma guardada: ${who} — ${r.signer_name}`;
  document.getElementById("ed-status").textContent = msg;
});

// ---- Ajustes menores: cuando abras/cambies de evaluación resetea e hidrata ----
async function openEditor(id, statusMsg=""){
  CURRENT_ID = id;
  document.querySelectorAll(".tab").forEach(s=>s.classList.remove("active"));
  document.getElementById("tab-editor").classList.add("active");
  edStatus.textContent = statusMsg || `Editando evaluación #${CURRENT_ID}`;
  resetEditorFields();
  await hydrateEditor(CURRENT_ID);
  document.getElementById("tab-editor").scrollIntoView({behavior:"smooth", block:"start"});
}

// ---- Utils ----
function generateFolio(){
  const d = new Date();
  const pad = n => String(n).padStart(2,"0");
  return `EC-${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

// ---- Boot ----
(async ()=>{
  await loadTemplate();
  renderEditor();               // prepara el editor (sin datos aún)
  // Home por defecto; el editor se abre automáticamente al crear/continuar.
})();
