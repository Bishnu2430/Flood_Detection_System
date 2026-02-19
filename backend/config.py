import os
from pathlib import Path

from dotenv import load_dotenv


_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


class Settings:
    # Optional override
    DATABASE_URL = os.getenv("DATABASE_URL")

    # PostgreSQL (defaults match docker-compose.yml for local dev)
    POSTGRES_USER = os.getenv("POSTGRES_USER", "flood")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "floodpass")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "flooddb")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5433")

    # Ollama
    # Expect either full endpoint (e.g., http://localhost:11434/api/generate)
    # or just host (we'll handle missing path in llm_engine if needed).
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    # Serial
    # On Windows, typical ports are COM3/COM4. If unset, backend will auto-detect.
    SERIAL_PORT = os.getenv("SERIAL_PORT")
    SERIAL_BAUDRATE = int(os.getenv("SERIAL_BAUDRATE", "9600"))
    SERIAL_CONNECT_RETRY_SECONDS = float(os.getenv("SERIAL_CONNECT_RETRY_SECONDS", "2"))


settings = Settings()
