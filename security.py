"""
M├│dulo de Seguran├ºa para o Sistema JULIANA
Fun├º├Áes de valida├º├úo, sanitiza├º├úo e logging de auditoria
"""

import os
import re
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict


def setup_logging() -> None:
    """Configura o sistema de logging de seguran├ºa."""
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "security.log")
    # Evita reconfigurar m├║ltiplas vezes
    if not logging.getLogger().handlers:
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            encoding="utf-8"
        )


def log_access(action: str, details: str = "") -> None:
    """Registra a├º├Áes para auditoria."""
    try:
        setup_logging()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] {action}"
        if details:
            msg += f" - {details}"
        logging.info(msg)
        print(f"SECURITY LOG: {msg}")
    except Exception as e:
        print(f"Erro ao registrar log de seguran├ºa: {e}")


_SANITIZE_PATTERN = re.compile(r'[<>"\';{}\\]')


def sanitize_input(input_text: str) -> str:
    """Remove caracteres perigosos e limita tamanho."""
    if not input_text:
        return ""
    text = str(input_text).strip()
    cleaned = _SANITIZE_PATTERN.sub("", text)
    return cleaned[:500]


def validate_file_upload(filename: str, file_size: int, max_size_mb: int = 10) -> Tuple[bool, str]:
    """Valida upload de PDF."""
    if not filename:
        return False, "Nome do arquivo ├® obrigat├│rio"
    allowed = (".pdf", ".PDF")
    if not filename.endswith(allowed):
        return False, "Apenas arquivos PDF s├úo permitidos"
    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        return False, f"Arquivo muito grande. M├íximo: {max_size_mb}MB"
    dangerous = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    if any(c in filename for c in dangerous):
        return False, "Nome do arquivo cont├®m caracteres inv├ílidos"
    return True, "Arquivo v├ílido"


def generate_safe_filename(original_name: str) -> str:
    """Gera nome seguro com timestamp."""
    if not original_name:
        return f"arquivo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    safe = re.sub(r'[<>:"/\\|?*]', "_", original_name)
    safe = re.sub(r'\s+', '_', safe.strip())
    if '.' in safe:
        name, ext = safe.rsplit('.', 1)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{ts}_{name}.{ext}"
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{ts}_{safe}.pdf"


def check_system_health() -> Dict:
    """Retorna status b├ísico do m├│dulo de seguran├ºa."""
    status: Dict[str, object] = {
        "logs_directory": False,
        "log_file_writable": False,
        "disk_space_ok": True,
        "timestamp": datetime.now().isoformat()
    }
    try:
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        if os.path.exists(logs_dir):
            status["logs_directory"] = True
            log_file = os.path.join(logs_dir, "security.log")
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"# health {datetime.now().isoformat()}\n")
                status["log_file_writable"] = True
            except Exception:
                status["log_file_writable"] = False
        try:
            import shutil
            _, _, free = shutil.disk_usage(os.path.dirname(__file__))
            if free < 100 * 1024 * 1024:
                status["disk_space_ok"] = False
            status["free_mb"] = int(free / 1024 / 1024)
        except Exception:
            pass
    except Exception as e:
        status["error"] = str(e)
    return status


# Inicializa├º├úo
setup_logging()
log_access("SECURITY_MODULE_LOADED", "M├│dulo carregado com sucesso")

try:
    import streamlit as st  # opcional; evitar side-effects diretos
except ImportError:
    log_access("STREAMLIT_IMPORT_WARN", "Streamlit ausente - execu├º├úo headless")

def compute_sha256(file_bytes: bytes) -> str:
    """Retorna hash SHA256 hex de um conte├║do em mem├│ria."""
    import hashlib
    h = hashlib.sha256()
    h.update(file_bytes)
    return h.hexdigest()

if __name__ == "__main__":
    print(check_system_health())
