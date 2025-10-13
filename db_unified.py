"""
Módulo de conexão e operações com PostgreSQL.
Versão unificada usando apenas psycopg2.
"""

from __future__ import annotations
import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Configurar encoding para Windows
if sys.platform == "win32":
    os.environ['PGCLIENTENCODING'] = 'UTF8'

from dotenv import load_dotenv
load_dotenv()

import psycopg2
import psycopg2.extras
from psycopg2 import OperationalError, errorcodes
from psycopg2 import sql as psql

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("DATABASE_URL ausente ou invalida. Defina em .env como postgresql://usuario:senha@host:5432/banco")

def _parse_db_url(url: str) -> Dict[str, Optional[str]]:
    """Quebra a DATABASE_URL em partes (sem expor senha em logs)."""
    u = urlparse(url)
    return {
        "scheme": u.scheme,
        "user": u.username,
        "password": u.password,
        "host": u.hostname or "127.0.0.1",
        "port": str(u.port or 5432),
        "dbname": u.path.lstrip("/") or None,
    }

def _build_conn_kwargs(parts: Dict[str, Optional[str]], override_db: Optional[str] = None) -> Dict[str, str]:
    return {
        "user": parts.get("user") or "postgres",
        "password": parts.get("password") or "",
        "host": parts.get("host") or "127.0.0.1",
        "port": parts.get("port") or "5432",
        "dbname": override_db or parts.get("dbname") or "postgres",
    }

def _ensure_database_exists():
    """Garante que o banco de dados alvo exista; cria se estiver ausente.
    Não lança exceção para não quebrar import; apenas tenta o melhor esforço.
    """
    parts = _parse_db_url(DATABASE_URL)
    target_db = parts.get("dbname")
    if not target_db:
        return

    # Primeiro, tenta conectar ao banco alvo rapidamente
    try:
        test_conn = psycopg2.connect(**_build_conn_kwargs(parts))
        test_conn.close()
        return  # Já existe
    except OperationalError as e:
        # Se o erro for "database does not exist", criamos
        if getattr(e, "pgcode", None) != errorcodes.INVALID_CATALOG_NAME:  # 3D000
            return  # outro erro (ex: auth), não tentamos criar

    # Conecta no banco "postgres" para criar o banco alvo
    try:
        admin_conn = psycopg2.connect(**_build_conn_kwargs(parts, override_db="postgres"))
        admin_conn.set_session(autocommit=True)
        with admin_conn.cursor() as cur:
            # Verifica existência
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target_db,))
            exists = cur.fetchone() is not None
            if not exists:
                # Cria banco com nome seguro (Identifier)
                cur.execute(
                    psql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8'").format(psql.Identifier(target_db))
                )
        admin_conn.close()
    except Exception:
        # Sem privilégios ou outra falha; silenciosamente seguimos
        pass

def _get_conn():
    """Retorna uma conexão com o PostgreSQL (criando DB se necessário)."""
    # Melhor esforço para garantir que o banco exista
    _ensure_database_exists()
    parts = _parse_db_url(DATABASE_URL)
    conn = psycopg2.connect(**_build_conn_kwargs(parts))
    try:
        conn.set_client_encoding('UTF8')
    except Exception:
        pass
    return conn

def _ensure_schema():
    """Cria a tabela atendimentos se não existir."""
    try:
        conn = _get_conn()
        try:
            conn.set_client_encoding('UTF8')
        except Exception:
            pass
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS atendimentos (
                    id SERIAL PRIMARY KEY,
                    empresa TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    modalidade TEXT NOT NULL,
                    data TEXT NOT NULL,
                    hora TEXT NOT NULL,
                    laudo_pdf TEXT,
                    avaliacao_pdf TEXT,
                    status TEXT DEFAULT 'Agendado',
                    observacoes TEXT
                )
                """)
                conn.commit()
        conn.close()
    except Exception as e:
        # evita falha no import quando o Postgres ainda não está disponível
        pass

_ensure_schema()

def ping_db() -> bool:
    """Testa a conexão com o banco de dados."""
    try:
        conn = _get_conn()
        try:
            conn.set_client_encoding('UTF8')
        except Exception:
            pass
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        conn.close()
        return True
    except Exception:
        return False

def inserir_atendimento(empresa: str, nome: str, modalidade: str, data: str, hora: str,
                        laudo_pdf: Optional[str], avaliacao_pdf: Optional[str], 
                        observacoes: Optional[str]) -> Optional[int]:
    """Insere um novo atendimento no banco de dados."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO atendimentos
                    (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes))
                new_id = cur.fetchone()[0]
                conn.commit()
                return int(new_id)
    except Exception as e:
        print(f"Erro ao inserir atendimento: {e}")
        return None

def listar_atendimentos() -> List[Dict[str, Any]]:
    """Lista todos os atendimentos do banco de dados."""
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, empresa, nome, modalidade, data, hora,
                           laudo_pdf, avaliacao_pdf, status, observacoes
                    FROM atendimentos ORDER BY id DESC
                """)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        print(f"Erro ao listar atendimentos: {e}")
        return []

def atualizar_atendimento(atendimento_id: int, **campos) -> bool:
    """Atualiza campos de um atendimento existente."""
    allowed = {"empresa","nome","modalidade","data","hora","laudo_pdf","avaliacao_pdf","status","observacoes"}
    sets = [(k, v) for k, v in campos.items() if k in allowed]
    if not sets:
        return False
    cols = ", ".join([f"{k}=%s" for k, _ in sets])
    vals = [v for _, v in sets]
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE atendimentos SET {cols} WHERE id=%s", (*vals, atendimento_id))
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        print(f"Erro ao atualizar atendimento: {e}")
        return False

def excluir_atendimento(atendimento_id: int) -> bool:
    """Exclui um atendimento do banco de dados."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM atendimentos WHERE id=%s", (atendimento_id,))
                conn.commit()
                return cur.rowcount > 0
    except Exception as e:
        print(f"Erro ao excluir atendimento: {e}")
        return False
