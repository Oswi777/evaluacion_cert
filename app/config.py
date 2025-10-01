import os
from dotenv import load_dotenv
load_dotenv()

def load_config():
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY", "change-me"),
        "DATABASE_URL": normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///instance/dev.db")),
        "DEFAULT_TZ": os.getenv("DEFAULT_TZ", "America/Mexico_City"),
    }

def normalize_db_url(url: str) -> str:
    # Compat: postgres:// → postgresql+psycopg2://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url
