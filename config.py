"""
Configuración central del sistema ETL para Odoo.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración global del sistema."""

    # Neo4j connection
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    # Odoo source paths
    ODOO_SOURCE_PATH = os.getenv("ODOO_SOURCE_PATH", "/path/to/odoo")

    # Cache and state
    CACHE_DIR = Path(".cache")
    STATE_FILE = CACHE_DIR / "state.json"

    # Performance tuning
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))  # Aumentado de 100 a 1000
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))

    # Filters
    EXCLUDE_PATTERNS = ["__pycache__", "*.pyc", ".git", "test_*"]
    EXCLUDE_MODELS = ["wizard", "transient"]

    @classmethod
    def ensure_cache_dir(cls):
        """Crear directorio de cache si no existe."""
        cls.CACHE_DIR.mkdir(exist_ok=True)
