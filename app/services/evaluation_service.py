import os
import json
import base64
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple, List
from flask import current_app

from ..models import EvalStatus
from ..repositories import EvaluationRepository

# ReportLab (canvas + Platypus)
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from datetime import datetime, timezone
import pytz

BASE_DIR = Path(__file__).resolve().parent.parent  # .../app
TPL_PATH = BASE_DIR / "data" / "template_hr01f08.json"

LOCAL_TZ = None  # cache

def _tz():
    global LOCAL_TZ
    if LOCAL_TZ is None:
        LOCAL_TZ = pytz.timezone(current_app.config.get("DEFAULT_TZ", "America/Mexico_City"))
    return LOCAL_TZ

def to_local(dt_utc: datetime) -> datetime:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(_tz())

def to_local_iso(dt_utc: datetime) -> str:
    return to_local(dt_utc).isoformat(timespec="seconds")

def local_day_window(from_yyyy_mm_dd: str | None, to_yyyy_mm_dd: str | None):
    """Devuelve (desde_local_utc, hasta_local_utc) para filtrar por fecha local inclusiva.
       Si from == to (mismo día), toma 00:00 a 23:59:59.999 de ese día local."""
    tz = _tz()
    today = datetime.now(tz).date()

    if from_yyyy_mm_dd:
        y,m,d = map(int, from_yyyy_mm_dd.split("-"))
        dfrom_local = datetime(y,m,d,0,0,0, tzinfo=tz)
    else:
        dfrom_local = datetime(today.year, today.month, today.day, 0,0,0, tzinfo=tz)

    if to_yyyy_mm_dd:
        y,m,d = map(int, to_yyyy_mm_dd.split("-"))
        # fin de día local → sumar 1 día y usar inicio de día siguiente como límite abierto
        dto_local = datetime(y,m,d,0,0,0, tzinfo=tz)
        dto_local = dto_local.replace(hour=0, minute=0, second=0, microsecond=0)
        dto_local = dto_local + timedelta(days=1)
    else:
        # si no hay "to", usamos dfrom + 1 día
        from datetime import timedelta
        dto_local = dfrom_local + timedelta(days=1)

    # Convertimos a UTC para comparar con created_at (que está en UTC)
    dfrom_utc = dfrom_local.astimezone(timezone.utc)
    dto_utc   = dto_local.astimezone(timezone.utc)
    return dfrom_utc, dto_utc

@dataclass
class ValidationResult:
    ok: bool
    missing_required: List[str]
    missing_sign_roles: List[str]

class EvaluationService:
    # ---------- Helpers básicos ----------
    @staticmethod
    def _load_template() -> dict:
        if not TPL_PATH.exists():
            raise FileNotFoundError(f"Plantilla no encontrada: {TPL_PATH}")
        return json.loads(TPL_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _instance_dir(subfolder: str) -> Path:
        """Devuelve una ruta dentro de instance/ y la crea si no existe."""
        base = Path(current_app.instance_path)  # <raíz>/instance
        path = base / subfolder
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ---------- Crear evaluación ----------
    @staticmethod
    def _seed_from_template(ev_id: int, tpl: dict, preset: dict | None = None):
        """Crea/actualiza todas las respuestas a partir de la plantilla.
           'preset' permite enviar valores iniciales (p.ej. no_empleado)."""
        preset = preset or {}
        seed_items: List[dict] = []

        # Generales
        for g in tpl.get("general", []):
            key = g["key"]
            seed_items.append({
                "field_key": key,
                "value": str(preset.get(key, "")),
                "is_required": bool(g.get("is_required", False))
            })

        # Secciones con r1/r2/r3 + obs
        for section_key in ["S", "P", "Q", "VC"]:
            for q in tpl.get(section_key, []):
                base = q["key"]
                seed_items += [
                    {"field_key": f"{base}_r1", "value": "", "is_required": True},
                    {"field_key": f"{base}_r2", "value": "", "is_required": False},
                    {"field_key": f"{base}_r3", "value": "", "is_required": False},
                    {"field_key": f"{base}_obs", "value": "", "is_required": False},
                ]

        # Resultado
        for r in tpl.get("resultado", []):
            seed_items.append({
                "field_key": r["key"],
                "value": "",
                "is_required": bool(r.get("is_required", False))
            })

        EvaluationRepository.upsert_responses(ev_id, seed_items)

    @staticmethod
    def create_by_no_empleado(no_empleado: str):
        """Genera folio con fecha local + no_empleado y pre-llena el campo 'no_empleado'."""
        tz = _tz()
        now_local = datetime.now(tz)
        folio = f"EC-{now_local.strftime('%Y%m%d')}-{no_empleado}"

        # Si ya existe, reusar (idempotente)
        ev = EvaluationRepository.get_by_folio(folio)
        if ev:
            return ev

        ev = EvaluationRepository.new(folio)
        tpl = EvaluationService._load_template()
        # pre-llenamos 'no_empleado'
        EvaluationService._seed_from_template(ev.id, tpl, preset={"no_empleado": no_empleado})
        return ev

    # Compat: creación por folio manual (no usada en UI actual, pero la dejamos)
    @staticmethod
    def create_evaluation(folio: str):
        ev = EvaluationRepository.get_by_folio(folio)
        if ev:
            return ev
        ev = EvaluationRepository.new(folio)
        tpl = EvaluationService._load_template()
        EvaluationService._seed_from_template(ev.id, tpl)
        return ev

    # ---------- Reglas de negocio ----------
    @staticmethod
    def required_sign_roles() -> List[str]:
        tpl = EvaluationService._load_template()
        return tpl.get("meta", {}).get("sign_roles", [])

    @staticmethod
    def save_responses(evaluation_id: int, responses: List[dict]):
        return EvaluationRepository.upsert_responses(evaluation_id, responses)

    @staticmethod
    def get_responses(evaluation_id: int) -> List[dict]:
        return EvaluationRepository.get_responses(evaluation_id)

    @staticmethod
    def save_signature_base64(evaluation_id: int, role: str, signer_name: str, b64png: str):
        sig_dir = EvaluationService._instance_dir("signatures")
        if "," in b64png:
            b64png = b64png.split(",", 1)[1]
        raw = base64.b64decode(b64png)
        fname = f"{uuid.uuid4().hex}.png"
        path = sig_dir / fname
        with open(path, "wb") as f:
            f.write(raw)
        return EvaluationRepository.add_signature(evaluation_id, role, signer_name, str(path))

    @staticmethod
    def validate(evaluation_id: int, required_sign_roles: List[str]) -> "ValidationResult":
        # EAGER load para evitar DetachedInstanceError
        ev = EvaluationRepository.get_with_children(evaluation_id)
        if not ev:
            return ValidationResult(False, ["_not_found_"], required_sign_roles)

        missing_required = [
            r.field_key
            for r in ev.responses
            if r.is_required and str(r.value or "").strip() == ""
        ]
        present_roles = {s.role for s in ev.signatures}
        missing_signs = [r for r in required_sign_roles if r not in present_roles]
        ok = (not missing_required) and (not missing_signs)
        return ValidationResult(ok, missing_required, missing_signs)

    @staticmethod
    def try_complete(evaluation_id: int, required_sign_roles: List[str]) -> Tuple[bool, "ValidationResult"]:
        vr = EvaluationService.validate(evaluation_id, required_sign_roles)
        if vr.ok:
            EvaluationRepository.set_status(evaluation_id, EvalStatus.COMPLETADA)
            return True, vr
        else:
            if EvaluationRepository.exists(evaluation_id):
                EvaluationRepository.set_status(evaluation_id, EvalStatus.PENDIENTE)
            return False, vr

    # ---------- Exportación PDF (igual que tenías, con nombre de archivo por folio) ----------
    @staticmethod
    def export_pdf(evaluation_id: int) -> str:
        ev = EvaluationRepository.get_with_children(evaluation_id)
        if not ev:
            raise ValueError("Evaluación no encontrada")

        tpl = EvaluationService._load_template()
        resp = {r.field_key: (r.value or "") for r in ev.responses}

        exports_dir = EvaluationService._instance_dir("exports")
        out_path = exports_dir / f"{ev.folio or f'evaluacion_{evaluation_id}'}.pdf"

        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=letter,
            topMargin=12*mm, bottomMargin=12*mm, leftMargin=12*mm, rightMargin=12*mm,
            title=f"Evaluación de Certificación {ev.folio}"
        )

        styles = getSampleStyleSheet()
        H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=18, spaceAfter=4*mm)
        H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=13, spaceBefore=2*mm, spaceAfter=1*mm)
        P = ParagraphStyle("P", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=12)
        PL = ParagraphStyle("PL", parent=P, alignment=TA_LEFT)
        PR = ParagraphStyle("PR", parent=P, alignment=TA_RIGHT)
        PC = ParagraphStyle("PC", parent=P, alignment=TA_CENTER)
        PCsmall = ParagraphStyle("PCs", parent=P, alignment=TA_CENTER, fontSize=8.5, leading=10)

        story = []

        # Encabezado
        logo_path = BASE_DIR / "static" / "logo.png"
        if logo_path.exists():
            img = Image(str(logo_path), width=35*mm, height=10*mm)
            header_cells = [[img, Paragraph("Evaluación de Certificación", H1), Paragraph(f"Folio: <b>{ev.folio}</b>", PR)]]
            col_w = [40*mm, None, 40*mm]
        else:
            header_cells = [[Paragraph("", P), Paragraph("Evaluación de Certificación", H1), Paragraph(f"Folio: <b>{ev.folio}</b>", PR)]]
            col_w = [10*mm, None, 40*mm]

        header = Table(header_cells, colWidths=col_w, hAlign="LEFT")
        story += [header, Spacer(1, 2*mm),
                  Table([[""]], colWidths=[None], rowHeights=[1],
                        style=[("LINEABOVE", (0,0), (-1,-1), 0.8, colors.black)]) ,
                  Spacer(1, 1*mm)]

        # Datos generales (ajusta nombres a los de tu plantilla)
        def cell(k, label):
            return Paragraph(f"<b>{label}:</b> {resp.get(k,'')}", P)

        left_rows = [
            [cell("nombre","Nombre del operador")],
            [cell("area","Área")],
            [cell("operacion","Operación")],
            [cell("no_operacion","No. Operación")],
            [cell("maquina","Máquina")],
            [cell("no_maquina","No. Máquina")],
        ]
        right_rows = [
            [cell("no_empleado","No. empleado")],
            [cell("fecha_ingreso","Fecha de ingreso")],
            [cell("fecha_inicio_entrenamiento","Fecha de inicio de entrenamiento")],
            [cell("fecha_revision","Fecha de revisión")],
        ]
        gen_tbl = Table([[Table(left_rows, hAlign="LEFT"), "", Table(right_rows, hAlign="LEFT")]], colWidths=[95*mm, 5*mm, None])
        gen_tbl.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        story += [gen_tbl, Spacer(1, 3*mm)]

        # Helper secciones
        def section_table(code: str, title: str, highlight=False):
            rows = [[
                Paragraph("<b>#</b>", PCsmall),
                Paragraph(f"<b>{title}</b>", PL),
                Paragraph("<b>1ra<br/>rev.</b>", PCsmall),
                Paragraph("<b>2da<br/>rev.</b>", PCsmall),
                Paragraph("<b>3ra<br/>rev.</b>", PCsmall),
                Paragraph("<b>Observaciones</b>", PCsmall),
            ]]
            for idx, q in enumerate(tpl.get(code, []), start=1):
                base = q["key"]; label = q.get("label", base)
                def yn(suf):
                    v = (resp.get(f"{base}_{suf}", "") or "").strip().lower()
                    return Paragraph("Sí", PC) if v=="si" else Paragraph("No", PC) if v=="no" else Paragraph("", PC)
                obs = resp.get(f"{base}_obs", "")
                rows.append([Paragraph(str(idx), PC), Paragraph(label, P), yn("r1"), yn("r2"), yn("r3"), Paragraph(obs, P)])
            colw = [8*mm, None, 14*mm, 14*mm, 14*mm, 45*mm]
            t = Table(rows, colWidths=colw, repeatRows=1, hAlign="LEFT")
            style = [
                ("GRID", (0,0), (-1,-1), 0.5, colors.black),
                ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("ALIGN", (0,0), (0,-1), "CENTER"),
                ("ALIGN", (2,1), (4,-1), "CENTER"),
                ("LEFTPADDING", (1,1), (1,-1), 3),
                ("RIGHTPADDING", (1,1), (1,-1), 3),
            ]
            t.setStyle(TableStyle(style))
            return t

        story += [section_table("S", "Conoce los pasos pero requiere supervisión. (en entrenamiento)"), Spacer(1,2*mm)]
        story += [section_table("P", "Puede ejecutar el trabajo con seguridad y calidad pero no en tiempo ciclo."), Spacer(1,2*mm)]
        story += [section_table("Q", "Puede ejecutar el trabajo con Seguridad, Calidad y en el Tiempo ciclo."), Spacer(1,2*mm)]
        story += [section_table("VC", "Domina la operación y puede enseñar a otros."), Spacer(1,3*mm)]

        # Resultado
        result = (resp.get("resultado_global","") or "").strip()
        result_opts = tpl.get("meta", {}).get("result_options", ["No aprueba","Re-entrenamiento","Re-ubicación","Aprobado"])
        def box(label):
            mark = "■" if label.lower()==result.lower() else "_"
            return Paragraph(f"{mark} {label}", P)
        res_tbl = Table([
            [Paragraph("<b>Resultado</b>", H2)],
            [box(result_opts[0])],
            [box(result_opts[1])],
            [box(result_opts[2])],
            [box(result_opts[3])],
            [Paragraph(f"<b>Comentarios:</b> {resp.get('comentarios','')}", P)]
        ], colWidths=[None])
        res_tbl.setStyle(TableStyle([
            ("BOX",(0,0),(-1,-1),0.5,colors.black),
            ("INNERGRID",(0,0),(-1,-1),0.25,colors.black),
            ("BACKGROUND",(0,0),(-1,0),colors.whitesmoke)
        ]))
        story += [res_tbl, Spacer(1, 4*mm)]

        # Firmas
        label_map = {
            "jefe_inmediato":"Jefe Inmediato",
            "ing_calidad":"Ing. de Calidad",
            "ing_manufactura":"Ing. de Manufactura",
            "seguridad_industrial":"Seguridad Industrial",
            "entrenamiento":"Entrenamiento",
            "nombre_operador":"Operador"
        }
        role_order = ["jefe_inmediato","ing_calidad","ing_manufactura","seguridad_industrial","entrenamiento","nombre_operador"]
        sig_by_role = {s.role: s for s in ev.signatures if s.role not in {}}

        def signature_cell(role_key: str | None):
            lbl = label_map.get(role_key, "") if role_key else ""
            s = sig_by_role.get(role_key) if role_key else None
            cell_w, cell_h = 65*mm, 26*mm

            if s and s.image_path and os.path.exists(s.image_path):
                img = Image(str(s.image_path))
                img._restrictSize(cell_w-6, cell_h-10)
                img.hAlign = "CENTER"
                box = Table([[img]], colWidths=[cell_w], rowHeights=[cell_h])
            else:
                box = Table([[Paragraph("", P)]], colWidths=[cell_w], rowHeights=[cell_h])

            box.setStyle(TableStyle([
                ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#a0a0a0")),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                ("ALIGN",(0,0),(-1,-1),"CENTER"),
                ("LEFTPADDING",(0,0),(-1,-1),3),
                ("RIGHTPADDING",(0,0),(-1,-1),3),
                ("TOPPADDING",(0,0),(-1,-1),3),
                ("BOTTOMPADDING",(0,0),(-1,-1),3),
            ]))

            label = Paragraph(f"<font size=8>{lbl}{(' — ' + s.signer_name) if s and s.signer_name else ''}</font>", P)
            cell = Table([[box],[label]], colWidths=[cell_w], rowHeights=[cell_h, 6*mm])
            cell.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
            return cell

        rows = []
        buffer_row = []
        for i, rk in enumerate(role_order, start=1):
            buffer_row.append(signature_cell(rk))
            if i % 3 == 0:
                rows.append(buffer_row); buffer_row = []
        if buffer_row:
            while len(buffer_row) < 3:
                buffer_row.append(signature_cell(None))
            rows.append(buffer_row)

        sig_tbl = Table(rows, colWidths=[65*mm,65*mm,65*mm], hAlign="LEFT",
                        style=[("VALIGN",(0,0),(-1,-1),"TOP"), ("BOTTOMPADDING",(0,0),(-1,-1),2)])
        story += [Paragraph("<b>Firmas</b>", H2), sig_tbl]

        def on_page(canv, _doc):
            canv.setFont("Helvetica", 8)
            canv.drawRightString(_doc.pagesize[0]-12*mm, 10*mm, "HR-01-F08 R02")
            canv.drawString(12*mm, 10*mm, "Generado por Evaluación SGE")

        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        return str(out_path)
