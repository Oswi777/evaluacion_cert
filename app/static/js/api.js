async function safeJson(res){
  const text = await res.text();
  try { return JSON.parse(text); } catch { return { error: "Non-JSON response", detail: text }; }
}

const API = {
  async createEvaluationByNoEmpleado(no_empleado) {
    const res = await fetch("/api/evaluaciones/create", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ no_empleado })
    });
    return safeJson(res);
  },

  async saveResponses(id, responses) {
    const res = await fetch(`/api/evaluaciones/${id}/responses`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ responses })
    });
    return safeJson(res);
  },
  async getResponses(id) {
    const res = await fetch(`/api/evaluaciones/${id}/responses`);
    return safeJson(res);
  },
  async sign(id, role, signer_name, image_base64) {
    const res = await fetch(`/api/evaluaciones/${id}/sign`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ role, signer_name, image_base64 })
    });
    return safeJson(res);
  },
  async complete(id) {
    const res = await fetch(`/api/evaluaciones/${id}/complete`, { method:"POST" });
    return safeJson(res);
  },
  async deleteEvaluation(id) {
    const res = await fetch(`/api/evaluaciones/${id}`, { method: "DELETE" });
    return safeJson(res);
  },
  async listPendientes(params = {}) {
    const qs = new URLSearchParams(params).toString();
    const res = await fetch(`/api/evaluaciones/pendientes${qs ? `?${qs}` : ""}`);
    return safeJson(res);
  },
  async listCompletadas(params = {}) {
    const qs = new URLSearchParams(params).toString();
    const res = await fetch(`/api/evaluaciones/completadas${qs ? `?${qs}` : ""}`);
    return safeJson(res);
  },
  exportUrl(id) {
    return `/api/evaluaciones/${id}/export`;
  }
};
