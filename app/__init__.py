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
    """
    Crea las carpetas necesarias dentro de instance/:
    - exports/   (PDFs)
    - signatures/ (imágenes de firma)
    """
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(Path(app.instance_path) / "exports").mkdir(parents=True, exist_ok=True)
    Path(Path(app.instance_path) / "signatures").mkdir(parents=True, exist_ok=True)


def _maybe_create_tables():
    """
    Crea las tablas si no existen (primer arranque).
    Si la variable de entorno FORCE_DB_CREATE == "true", fuerza create_all()
    incluso si ya detecta tablas.

    Nota Supabase:
    - Para la PRIMERA creación en producción, usa conexión Direct (5432)
      en DATABASE_URL o define FORCE_DB_CREATE=true temporalmente.
    - En runtime normal, usa Transaction Pooler (6543).
    """
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
    except Exception as e:
        # No interrumpas el arranque si la verificación falla (por pooler),
        # pero deja trazas claras en logs.
        import traceback
        print("⚠️  No se pudo verificar/crear tablas automáticamente.")
        traceback.print_exc()


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(load_config())
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Estructura instance/
    _ensure_instance_dirs(app)

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

    # Siempre responde JSON en errores
    @app.errorhandler(Exception)
    def handle_exceptions(e):
        import traceback
        traceback.print_exc()
        code = getattr(e, "code", 500)
        return jsonify({"error": str(e), "type": e.__class__.__name__}), code

    return app
