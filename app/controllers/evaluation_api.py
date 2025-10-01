import json
from flask import Blueprint, request, send_file
from ..services import EvaluationService
from ..repositories import EvaluationRepository
from ..models import EvalStatus
from ..db import get_engine
from ..services.evaluation_service import TPL_PATH

bp = Blueprint("api_evaluaciones", __name__)

def _required_roles():
    return EvaluationService.required_sign_roles()

@bp.get("/diag")
def diag():
    ok_template = TPL_PATH.exists()
    try:
        with get_engine().connect() as c:
            c.exec_driver_sql("SELECT 1")
        ok_db = True
        db_error = None
    except Exception as e:
        ok_db = False
        db_error = str(e)
    return {
        "template_exists": ok_template,
        "template_path": str(TPL_PATH),
        "db_ok": ok_db,
        **({"db_error": db_error} if db_error else {})
    }, (200 if ok_template and ok_db else 500)

@bp.post("/create")
def create():
    try:
        data = request.get_json(force=True)
        folio = str(data.get("folio") or "").strip()
        if not folio:
            return {"error": "folio requerido"}, 400
        ev = EvaluationService.create_evaluation(folio)
        return {"id": ev.id, "folio": ev.folio, "status": ev.status.value}, 200
    except FileNotFoundError as e:
        return {"error": "Plantilla no encontrada", "detail": str(e)}, 500
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error interno al crear", "detail": str(e)}, 500

@bp.get("/pendientes")
def list_pendientes():
    try:
        items = EvaluationRepository.list_by_status(EvalStatus.PENDIENTE)
        return {"items": [{"id": x.id, "folio": x.folio, "created_at": x.created_at.isoformat()} for x in items]}, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al listar pendientes", "detail": str(e)}, 500

@bp.get("/completadas")
def list_completadas():
    try:
        items = EvaluationRepository.list_by_status(EvalStatus.COMPLETADA)
        return {"items": [{"id": x.id, "folio": x.folio, "created_at": x.created_at.isoformat()} for x in items]}, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al listar completadas", "detail": str(e)}, 500

@bp.get("/<int:eid>/responses")
def get_responses(eid: int):
    try:
        data = EvaluationService.get_responses(eid)
        if not data:
            return {"items": [], "warning": "no encontrada o sin respuestas"}, 200
        return {"items": data}, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al obtener respuestas", "detail": str(e)}, 500

@bp.post("/<int:eid>/responses")
def upsert_responses(eid: int):
    try:
        data = request.get_json(force=True)
        responses = data.get("responses", [])
        ev = EvaluationService.save_responses(eid, responses)
        return {
            "id": ev.id,
            "status": ev.status.value,
            "required_total": ev.required_total,
            "required_filled": ev.required_filled
        }, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al guardar respuestas", "detail": str(e)}, 500

@bp.post("/<int:eid>/sign")
def sign(eid: int):
    try:
        data = request.get_json(force=True)
        role = str(data.get("role") or "").strip()
        signer_name = str(data.get("signer_name") or "").strip()
        b64 = data.get("image_base64")
        if not role or not signer_name or not b64:
            return {"error": "role, signer_name e image_base64 son requeridos"}, 400
        sig = EvaluationService.save_signature_base64(eid, role, signer_name, b64)
        return {"id": sig.id, "role": sig.role, "signer_name": sig.signer_name}, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al guardar firma", "detail": str(e)}, 500

@bp.post("/<int:eid>/complete")
def complete(eid: int):
    try:
        ok, vr = EvaluationService.try_complete(eid, _required_roles())
        return {
            "ok": ok,
            "missing_required": vr.missing_required,
            "missing_sign_roles": vr.missing_sign_roles
        }, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al completar", "detail": str(e)}, 500

@bp.delete("/<int:eid>")
def delete_eval(eid: int):
    try:
        ok = EvaluationRepository.delete(eid)
        if not ok:
            return {"error": "no encontrada"}, 404
        return {"ok": True}, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al eliminar", "detail": str(e)}, 500

@bp.get("/<int:eid>/export")
def export_pdf(eid: int):
    try:
        ev = EvaluationRepository.get(eid)
        if not ev:
            return {"error": "no encontrada"}, 404
        if str(ev.status.value) != "completada":
            return {"error": "la evaluación no está completada"}, 400
        pdf_path = EvaluationService.export_pdf(eid)
        return send_file(pdf_path, mimetype="application/pdf", as_attachment=True, download_name=f"evaluacion_{eid}.pdf")
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al exportar", "detail": str(e)}, 500

@bp.get("/plantilla")
def plantilla():
    try:
        tpl = EvaluationService._load_template()
        return tpl, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al leer plantilla", "detail": str(e)}, 500
