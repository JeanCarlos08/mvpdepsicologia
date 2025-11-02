import json
import os
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except Exception as e:
    print(json.dumps({"ok": False, "error": f"tomllib indisponível: {e}"}, ensure_ascii=False))
    sys.exit(0)

try:
    import psycopg2
    import psycopg2.extras
except Exception as e:
    print(json.dumps({"ok": False, "error": f"psycopg2 ausente: {e}", "hint": "Instale 'psycopg2-binary'"}, ensure_ascii=False))
    sys.exit(0)

secrets_path = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"
if not secrets_path.exists():
    print(json.dumps({"ok": False, "error": f"Arquivo não encontrado: {secrets_path}"}, ensure_ascii=False))
    sys.exit(0)

raw = secrets_path.read_bytes()
secrets = tomllib.loads(raw.decode("utf-8", errors="replace"))

# Normaliza chaves para minúsculas
norm = {k.lower(): v for k, v in secrets.items()}

def redact(s: str, keep: int = 2) -> str:
    s = str(s)
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "*" * (len(s) - keep)

out = {"ok": False, "mode": None, "using": {}, "message": None}

if any(k in norm for k in ("database_url", "db_url", "postgres_url", "postgresql_url")):
    url_key = next(k for k in ("database_url", "db_url", "postgres_url", "postgresql_url") if k in norm)
    url = str(norm[url_key])
    out["mode"] = "url"
    out["using"] = {"key": url_key, "value": redact(url, 16)}
    try:
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT current_database() AS db, current_user AS user")
        row = cur.fetchone()
        out["ok"] = True
        out["message"] = f"Conectado a '{row['db']}' como '{row['user']}'"
        conn.close()
    except Exception as e:
        out["ok"] = False
        out["message"] = f"Falha ao conectar via URL: {e}"
else:
    required = ["db_host", "db_port", "db_name", "db_user", "db_password"]
    missing = [k for k in required if k not in norm or not str(norm[k]).strip()]
    out["mode"] = "separate"
    out["using"] = {k: redact(norm.get(k, "")) for k in required}
    if missing:
        out["message"] = f"Chaves ausentes: {', '.join(missing)}"
    else:
        try:
            conn = psycopg2.connect(
                host=str(norm["db_host"]),
                port=int(norm["db_port"]),
                dbname=str(norm["db_name"]),
                user=str(norm["db_user"]),
                password=str(norm["db_password"]),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            cur = conn.cursor()
            cur.execute("SELECT current_database() AS db, current_user AS user")
            row = cur.fetchone()
            out["ok"] = True
            out["message"] = f"Conectado a '{row['db']}' como '{row['user']}'"
            conn.close()
        except Exception as e:
            out["ok"] = False
            out["message"] = f"Falha ao conectar via campos separados: {e}"

print(json.dumps(out, ensure_ascii=False))
