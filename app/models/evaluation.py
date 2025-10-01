from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SAEnum, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db import Base

class EvalStatus(str, Enum):
    PENDIENTE = "pendiente"
    COMPLETADA = "completada"

class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folio: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    status: Mapped[EvalStatus] = mapped_column(SAEnum(EvalStatus), default=EvalStatus.PENDIENTE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Métricas rápidas de validación (opcional)
    required_total: Mapped[int] = mapped_column(Integer, default=0)
    required_filled: Mapped[int] = mapped_column(Integer, default=0)

    responses: Mapped[list["EvaluationResponse"]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")
    signatures: Mapped[list["Signature"]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")

class EvaluationResponse(Base):
    __tablename__ = "evaluation_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id", ondelete="CASCADE"), index=True)
    field_key: Mapped[str] = mapped_column(String(120), index=True)  # e.g. "empleado_nombre", "area", "pregunta_1"
    value: Mapped[str] = mapped_column(Text, default="")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="responses")

class Signature(Base):
    __tablename__ = "signatures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("evaluations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(80))         # e.g. "evaluador", "supervisor", "entrenador"
    signer_name: Mapped[str] = mapped_column(String(120)) # nombre escrito o seleccionado
    image_path: Mapped[str] = mapped_column(String(255))  # ruta del PNG de firma (guardado server-side)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    evaluation: Mapped["Evaluation"] = relationship(back_populates="signatures")
