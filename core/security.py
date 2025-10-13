"""
Módulo de Segurança para o Sistema JULIANA
Funções de validação, sanitização e logging de auditoria
"""

from __future__ import annotations
import re, time, hashlib, logging
from pathlib import Path
from typing import Tuple, Dict

LOG_DIR = (Path(__file__).resolve().parent.parent / "logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "security.log"

def setup_logging() -> None:
    logger = logging.getLogger()
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def log_access(action: str, details: str = "") -> None:
    try:
        logging.info("%s | %s", action, details)
    except Exception:
        pass

_SANITIZE_PATTERN = re.compile(r'[\x00-\x1f\x7f<>\"\'\;\{\}\\]')

def sanitize_input(input_text: str, max_len: int = 500) -> str:
    if not isinstance(input_text, str):
        return ""
    text = input_text.strip()
    text = _SANITIZE_PATTERN.sub(" ", text)
    return text[:max_len]

def validate_file_upload(filename: str, file_size: int, max_size_mb: int = 50) -> Tuple[bool, str]:
    if not filename.lower().endswith(".pdf"):
        return False, "Extensão não permitida. Envie um PDF."
    if file_size > max_size_mb * 1024 * 1024:
        return False, f"Arquivo maior que {max_size_mb}MB."
    return True, "ok"

def generate_safe_filename(original_name: str) -> str:
    base = re.sub(r"[^\w\-\.]+", "_", original_name.strip().lower())
    ts = int(time.time())
    if "." in base:
        n, ext = base.rsplit(".", 1)
        return f"{n}_{ts}.{ext}"
    return f"{base}_{ts}"

def check_system_health() -> Dict:
    return {
        "log_dir_exists": LOG_DIR.exists(),
        "log_file_exists": LOG_FILE.exists(),
    }

def compute_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

setup_logging()
log_access("SECURITY_MODULE_LOADED", "Módulo carregado")
