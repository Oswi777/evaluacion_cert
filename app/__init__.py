import os
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS

from .config import load_config
from .db import init_engine_and_session, Base, get_engine

# Blueprints
from .controllers.evaluation_api import bp as evaluation_bp
from .controllers.ui import bp as ui_bp  # UI

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(load_config())
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Asegura carpetas usando app.instance_path (correcto en Flask)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(Path(app.instance_path) / "exports").mkdir(parents=True, exist_ok=True)
    Path(Path(app.instance_path) / "signatures").mkdir(parents=True, exist_ok=True)

    # DB
    init_engine_and_session(app.config["DATABASE_URL"])

    # IMPORTA MODELOS ANTES DE create_all
    from .models import Evaluation, EvaluationResponse, Signature  # noqa

    # Crea tablas en dev (en prod usar Alembic)
    with get_engine().connect() as conn:
        Base.metadata.create_all(bind=conn)

    # Blueprints
    app.register_blueprint(evaluation_bp, url_prefix="/api/evaluaciones")
    app.register_blueprint(ui_bp)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # Siempre responde JSON en errores
    @app.errorhandler(Exception)
    def handle_exceptions(e):
        import traceback; traceback.print_exc()
        code = getattr(e, "code", 500)
        return jsonify({"error": str(e), "type": e.__class__.__name__}), code

    return app
