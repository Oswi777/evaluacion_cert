import os
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS

from .config import load_config
from .db import init_engine_and_session, Base, get_engine

# Blueprints
from .controllers.evaluation_api import bp as evaluation_bp
from .controllers.ui import bp as ui_bp  # UI


def _ensure_instance_folders(app: Flask):
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    (Path(app.instance_path) / "exports").mkdir(parents=True, exist_ok=True)
    (Path(app.instance_path) / "signatures").mkdir(parents=True, exist_ok=True)


def _absolutize_sqlite_url_if_needed(app: Flask):
    """
    Si DATABASE_URL es 'sqlite:///algo.db' o 'sqlite:///instance/dev.db',
    la convertimos a absoluta usando app.instance_path para evitar
    'sqlite3.OperationalError: unable to open database file'.
    """
    url = app.config.get("DATABASE_URL", "")
    if not url.lower().startswith("sqlite:///"):
        return

    # Parte después de 'sqlite:///'
    path_part = url[10:]  # len("sqlite:///") = 10
    # Si ya parece absoluta (ej. 'C:/...' o '/...' en POSIX), dejamos igual.
    p = Path(path_part)
    if p.is_absolute():
        return

    # Si es relativa, la anclamos en instance/
    # - si dieron 'instance/dev.db', respetamos el nombre del archivo
    # - si dieron 'dev.db', lo movemos a instance/dev.db
    if p.name:  # nombre de archivo
        abs_path = (Path(app.instance_path) / p.name).resolve()
    else:
        # Caso raro sin nombre; usamos dev.db por defecto
        abs_path = (Path(app.instance_path) / "dev.db").resolve()

    # En URLs de sqlite para Windows funciona: sqlite:///C:/ruta/archivo.db
    app.config["DATABASE_URL"] = f"sqlite:///{abs_path.as_posix()}"


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(load_config())
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Asegura carpetas dentro de instance/
    _ensure_instance_folders(app)

    # Normaliza ruta SQLite a absoluta si hace falta
    _absolutize_sqlite_url_if_needed(app)

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
