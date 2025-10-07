import os
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import inspect

from .config import load_config
from .db import init_engine_and_session, Base, get_engine

# Blueprints
from .controllers.evaluation_api import bp as evaluation_bp
from .controllers.ui import bp as ui_bp  # UI


def _ensure_instance_dirs(app: Flask):
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    (Path(app.instance_path) / "exports").mkdir(parents=True, exist_ok=True)
    (Path(app.instance_path) / "signatures").mkdir(parents=True, exist_ok=True)


def _resolve_sqlite_url(app: Flask, url: str) -> str:
    """
    Si la URL es SQLite y relativa (p.ej. sqlite:///instance/dev.db),
    la convertimos a absoluta dentro de app.instance_path.
    """
    if not url.startswith("sqlite"):
        return url

    # Si ya es absoluta (sqlite:////C:/... o sqlite:////home/...), no tocar
    if url.startswith("sqlite:////"):
        return url

    # Casos relativos comunes:
    # - sqlite:///instance/dev.db
    # - sqlite:///./instance/dev.db
    # - sqlite:///dev.db
    # Hacemos que el archivo viva en instance/dev.db siempre.
    dbfile = "dev.db"
    try:
        tail = url.split("sqlite:///")[1]
        # si viene algo como "instance/dev.db", respetamos el nombre de archivo
        maybe_name = Path(tail).name
        if maybe_name:
            dbfile = maybe_name
    except Exception:
        pass

    abs_path = Path(app.instance_path) / dbfile
    # En Windows, SQLAlchemy acepta sqlite:////C:/ruta/archivo.db (cuatro /)
    # Usamos as_posix para que convierta \ → /
    return f"sqlite:///{abs_path.as_posix()}"


def _maybe_create_tables():
    engine = get_engine()
    inspector = inspect(engine)
    force = os.getenv("FORCE_DB_CREATE", "").lower() in ("1", "true", "yes")
    try:
        have_evals = inspector.has_table("evaluations")
        have_resp = inspector.has_table("evaluation_responses")
        have_sigs = inspector.has_table("signatures")
        if force or not (have_evals and have_resp and have_sigs):
            print("🧱 Creando tablas (create_all). FORCE_DB_CREATE =", force)
            Base.metadata.create_all(bind=engine)
        else:
            print("✅ Tablas ya existen. No se ejecuta create_all().")
    except Exception:
        import traceback
        print("⚠️  No se pudo verificar/crear tablas automáticamente.")
        traceback.print_exc()


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(load_config())
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    _ensure_instance_dirs(app)

    # 🔧 Normaliza DATABASE_URL si es SQLite relativa → absoluta en instance/
    db_url = app.config.get("DATABASE_URL", "")
    app.config["DATABASE_URL"] = _resolve_sqlite_url(app, db_url)
    print("DATABASE_URL =", app.config["DATABASE_URL"])

    # DB
    init_engine_and_session(app.config["DATABASE_URL"])

    # Importa modelos antes de create_all
    from .models import Evaluation, EvaluationResponse, Signature  # noqa

    # Crea tablas si no existen (o fuerza con env var)
    _maybe_create_tables()

    # Blueprints
    app.register_blueprint(evaluation_bp, url_prefix="/api/evaluaciones")
    app.register_blueprint(ui_bp)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.errorhandler(Exception)
    def handle_exceptions(e):
        import traceback
        traceback.print_exc()
        code = getattr(e, "code", 500)
        return jsonify({"error": str(e), "type": e.__class__.__name__}), code

    return app
