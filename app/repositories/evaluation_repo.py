from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..db import get_session
from ..models import Evaluation, EvaluationResponse, Signature, EvalStatus

class EvaluationRepository:

    @staticmethod
    def new(folio: str) -> Evaluation:
        with get_session() as s:
            # UTC aware para evitar comparaciones naive/aware en filtros
            ev = Evaluation(folio=folio, status=EvalStatus.PENDIENTE, created_at=datetime.now(timezone.utc))
            s.add(ev)
            s.flush()
            return ev

    @staticmethod
    def get(eid: int) -> Optional[Evaluation]:
        with get_session() as s:
            return s.get(Evaluation, eid)

    @staticmethod
    def get_with_children(eid: int) -> Optional[Evaluation]:
        """Evaluation + responses + signatures (eager). Evita DetachedInstanceError."""
        with get_session() as s:
            stmt = (
                select(Evaluation)
                .options(
                    selectinload(Evaluation.responses),
                    selectinload(Evaluation.signatures),
                )
                .where(Evaluation.id == eid)
            )
            return s.execute(stmt).scalars().first()

    @staticmethod
    def exists(eid: int) -> bool:
        with get_session() as s:
            return s.get(Evaluation, eid) is not None

    @staticmethod
    def get_by_folio(folio: str) -> Optional[Evaluation]:
        with get_session() as s:
            stmt = select(Evaluation).where(Evaluation.folio == folio)
            return s.execute(stmt).scalars().first()

    @staticmethod
    def upsert_responses(evaluation_id: int, items: Iterable[dict]) -> Evaluation:
        with get_session() as s:
            ev = s.get(Evaluation, evaluation_id)
            if not ev:
                raise ValueError("evaluation_id no existe")

            existing = {r.field_key: r for r in ev.responses}

            for it in items:
                key = it["field_key"]
                val = it.get("value", "")
                req = bool(it.get("is_required", existing.get(key).is_required if key in existing else False))
                if key in existing:
                    r = existing[key]
                    r.value = val
                    r.is_required = req
                else:
                    s.add(EvaluationResponse(
                        evaluation_id=ev.id, field_key=key, value=val, is_required=req
                    ))

            ev.required_total = sum(1 for r in ev.responses if r.is_required)
            ev.required_filled = sum(1 for r in ev.responses if r.is_required and str(r.value).strip() != "")
            s.flush()
            return ev

    @staticmethod
    def get_responses(evaluation_id: int) -> list[dict]:
        with get_session() as s:
            ev = s.get(Evaluation, evaluation_id)
            if not ev:
                return []
            return [{"field_key": r.field_key, "value": r.value, "is_required": r.is_required} for r in ev.responses]

    @staticmethod
    def add_signature(evaluation_id: int, role: str, signer_name: str, image_path: str) -> Signature:
        with get_session() as s:
            sig = Signature(
                evaluation_id=evaluation_id, role=role, signer_name=signer_name, image_path=image_path
            )
            s.add(sig)
            s.flush()
            return sig

    @staticmethod
    def set_status(evaluation_id: int, status: EvalStatus) -> bool:
        with get_session() as s:
            ev = s.get(Evaluation, evaluation_id)
            if not ev:
                return False
            ev.status = status
            s.flush()
            return True

    @staticmethod
    def delete(eid: int) -> bool:
        with get_session() as s:
            ev = s.get(Evaluation, eid)
            if not ev:
                return False
            for r in list(ev.responses):
                s.delete(r)
            for sg in list(ev.signatures):
                s.delete(sg)
            s.delete(ev)
            s.flush()
            return True

    @staticmethod
    def list_by_status(status: EvalStatus) -> List[Evaluation]:
        with get_session() as s:
            stmt = (
                select(Evaluation)
                .where(Evaluation.status == status)
                .order_by(Evaluation.created_at.desc())
            )
            return list(s.execute(stmt).scalars().all())
