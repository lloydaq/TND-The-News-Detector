import os

from dotenv import load_dotenv

load_dotenv()


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT_SECONDS = _env_float("OLLAMA_TIMEOUT_SECONDS", 60)
MAX_ANALYSIS_SECONDS = _env_float("MAX_ANALYSIS_SECONDS", 180)
MAX_CONCURRENT_ANALYSES = _env_int("MAX_CONCURRENT_ANALYSES", 2)
