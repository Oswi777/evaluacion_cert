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

# NUEVO: crear a partir de no_empleado (folio = EC-YYYYMMDD-<no_empleado> y campo prellenado)
@bp.post("/create")
def create():
    try:
        data = request.get_json(force=True) or {}
        no_empleado = str(data.get("no_empleado") or "").strip()
        folio_raw = str(data.get("folio") or "").strip()

        if no_empleado:
            ev = EvaluationService.create_by_no_empleado(no_empleado)
            return {"id": ev.id, "folio": ev.folio, "status": ev.status.value}, 200

        # Compat: si alguien aún envía folio manual (no recomendado)
        if folio_raw:
            ev = EvaluationService.create_evaluation(folio_raw)
            return {"id": ev.id, "folio": ev.folio, "status": ev.status.value}, 200

        return {"error": "no_empleado requerido"}, 400

    except FileNotFoundError as e:
        return {"error": "Plantilla no encontrada", "detail": str(e)}, 500
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error interno al crear", "detail": str(e)}, 500

@bp.get("/pendientes")
def list_pendientes():
    try:
        items = EvaluationRepository.list_by_status(EvalStatus.PENDIENTE)

        # Filtros opcionales
        q_noemp = (request.args.get("no_empleado") or "").strip()
        q_from = (request.args.get("from") or "").strip()
        q_to = (request.args.get("to") or "").strip()

        # date filtering by LOCAL day window
        from ..services.evaluation_service import local_day_window, to_local_iso
        if q_from or q_to:
            dt_from, dt_to = local_day_window(q_from, q_to)
            items = [x for x in items if (x.created_at >= dt_from and x.created_at < dt_to)]

        # filtrar por no_empleado leyendo responses (solo si viene parámetro)
        if q_noemp:
            filtered = []
            for x in items:
                resp = EvaluationService.get_responses(x.id)
                m = {r["field_key"]: r.get("value","") for r in resp}
                if (m.get("no_empleado") or "").strip() == q_noemp:
                    filtered.append(x)
            items = filtered

        return {"items": [
            {"id": x.id, "folio": x.folio, "created_at": x.created_at.isoformat(), "created_local": to_local_iso(x.created_at)}
            for x in items
        ]}, 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": "Error al listar pendientes", "detail": str(e)}, 500

@bp.get("/completadas")
def list_completadas():
    try:
        items = EvaluationRepository.list_by_status(EvalStatus.COMPLETADA)

        # Filtros opcionales
        q_noemp = (request.args.get("no_empleado") or "").strip()
        q_from = (request.args.get("from") or "").strip()
        q_to = (request.args.get("to") or "").strip()

        from ..services.evaluation_service import local_day_window, to_local_iso
        if q_from or q_to:
            dt_from, dt_to = local_day_window(q_from, q_to)
            items = [x for x in items if (x.created_at >= dt_from and x.created_at < dt_to)]

        if q_noemp:
            filtered = []
            for x in items:
                resp = EvaluationService.get_responses(x.id)
                m = {r["field_key"]: r.get("value","") for r in resp}
                if (m.get("no_empleado") or "").strip() == q_noemp:
                    filtered.append(x)
            items = filtered

        return {"items": [
            {"id": x.id, "folio": x.folio, "created_at": x.created_at.isoformat(), "created_local": to_local_iso(x.created_at)}
            for x in items
        ]}, 200
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
        data = request.get_json(force=True) or {}
        responses = data.get("responses", [])
        ev = EvaluationService.save_responses(eid, responses)

        # Devuelve labels de los faltantes para mostrar en UI
        tpl = EvaluationService._load_template()
        key2label = {g["key"]:g["label"] for g in tpl.get("general",[])}
        for sec in ["S","P","Q","VC"]:
            for q in tpl.get(sec,[]):
                base = q["key"]
                key2label[f"{base}_r1"] = f"{q['label']} (1ra rev.)"
                key2label[f"{base}_r2"] = f"{q['label']} (2da rev.)"
                key2label[f"{base}_r3"] = f"{q['label']} (3ra rev.)"
                key2label[f"{base}_obs"] = f"{q['label']} (Observaciones)"
        for r in tpl.get("resultado",[]):
            key2label[r["key"]] = r["label"]

        missing_labels = [key2label.get(k,k) for k in EvaluationService.validate(eid, _required_roles()).missing_required]

        return {
            "id": ev.id,
            "status": ev.status.value,
            "required_total": ev.required_total,
            "required_filled": ev.required_filled,
            "missing_labels": missing_labels
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
        # nombre de archivo = folio
        filename = f"{ev.folio}.pdf" if ev and ev.folio else f"evaluacion_{eid}.pdf"
        return send_file(pdf_path, mimetype="application/pdf", as_attachment=True, download_name=filename)
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
