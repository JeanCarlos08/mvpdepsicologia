import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

try:  # Streamlit Cloud fornece st.secrets
	import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
	st = None

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

# Carrega um .env que esteja no mesmo diret├│rio deste arquivo, independente do CWD.
_LOCAL_ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
	if _LOCAL_ENV_PATH.exists():
		load_dotenv(dotenv_path=_LOCAL_ENV_PATH, override=False)
	else:
		# fallback para comportamento padr├úo (procura em CWD e pais)
		load_dotenv()
except Exception:
	# N├úo bloquear inicializa├º├úo se houver falha ao ler .env
	pass

_REQUIRED_KEYS = ("db_host", "db_port", "db_name", "db_user", "db_password")
_URL_KEYS = ("database_url", "db_url", "postgres_url", "postgresql_url")
_DB_CACHE: Optional[Dict[str, str]] = None
_USE_SQLITE_FALLBACK = False
_SQLITE_DB = Path(__file__).resolve().parent / "gestao_clinica_fallback.db"


def _load_db_config() -> Dict[str, str]:
	global _DB_CACHE, _USE_SQLITE_FALLBACK
	if _DB_CACHE is not None and not _USE_SQLITE_FALLBACK:
		return _DB_CACHE

	if _USE_SQLITE_FALLBACK:
		return {"sqlite_path": str(_SQLITE_DB)}

	secrets = getattr(st, "secrets", None)
	config = None
	if secrets is not None:
		try:
			config = _build_config_from_mapping(secrets)
		except Exception:
			# Ignora falha ao ler st.secrets quando n├úo existe secrets.toml
			config = None
	if config is None:
		config = _build_config_from_mapping(os.environ)

	if config is None:
		print("ÔÜá´©Å PostgreSQL n├úo configurado, usando SQLite como fallback")
		_USE_SQLITE_FALLBACK = True
		return {"sqlite_path": str(_SQLITE_DB)}

	_DB_CACHE = config
	return config


def _normalize_mapping(mapping: Optional[Mapping[str, Any]]) -> Dict[str, str]:
	if mapping is None:
		return {}

	normalized: Dict[str, str] = {}
	try:
		items = mapping.items()  # type: ignore[attr-defined]
	except AttributeError:
		items = ((key, getattr(mapping, key)) for key in mapping)  # type: ignore[arg-type]
	for key, value in items:
		if value is None or value == "":
			continue
		normalized[str(key).lower()] = str(value)
	return normalized


def _build_config_from_mapping(source: Optional[Mapping[str, Any]]) -> Optional[Dict[str, str]]:
	normalized = _normalize_mapping(source)
	if not normalized:
		return None

	for url_key in _URL_KEYS:
		if url_key in normalized:
			return _parse_database_url(normalized[url_key])

	if all(key in normalized for key in _REQUIRED_KEYS):
		return {key: str(normalized[key]) for key in _REQUIRED_KEYS}

	return None


def _parse_database_url(url: str) -> Dict[str, str]:
	parsed = urlparse(url)
	if parsed.scheme not in {"postgres", "postgresql"}:
		raise RuntimeError("DATABASE_URL inv├ílida: utilize postgres:// ou postgresql://")

	host = parsed.hostname
	if not host:
		raise RuntimeError("DATABASE_URL inv├ílida: host ausente.")

	path = parsed.path.lstrip("/")
	if not path:
		raise RuntimeError("DATABASE_URL inv├ílida: nome do banco ausente.")

	return {
		"db_host": host,
		"db_port": str(parsed.port or 5432),
		"db_name": path,
		"db_user": unquote(parsed.username or ""),
		"db_password": unquote(parsed.password or ""),
	}


def get_connection():
	"""Retorna uma nova conex├úo (PostgreSQL ou SQLite fallback)."""
	global _USE_SQLITE_FALLBACK
	
	cfg = _load_db_config()
	
	if _USE_SQLITE_FALLBACK or "sqlite_path" in cfg:
		return sqlite3.connect(cfg["sqlite_path"])
	
	if not POSTGRES_AVAILABLE:
		print("ÔÜá´©Å psycopg2 n├úo dispon├¡vel, usando SQLite")
		_USE_SQLITE_FALLBACK = True
		return sqlite3.connect(str(_SQLITE_DB))
	
	try:
		return psycopg2.connect(
			host=cfg["db_host"],
			port=cfg["db_port"],
			dbname=cfg["db_name"],
			user=cfg["db_user"],
			password=cfg["db_password"],
			cursor_factory=psycopg2.extras.RealDictCursor,
		)
	except Exception as e:
		print(f"ÔÜá´©Å Erro PostgreSQL ({e}), usando SQLite fallback")
		_USE_SQLITE_FALLBACK = True
		return sqlite3.connect(str(_SQLITE_DB))


# Compatibilidade com a grafia solicitada
def get_conection():  # pragma: no cover
	return get_connection()


@contextmanager
def _connection_scope(commit: bool = True):
	conn = get_connection()
	try:
		yield conn
		if commit:
			conn.commit()
	except Exception:
		if hasattr(conn, 'rollback'):
			conn.rollback()
		raise
	finally:
		conn.close()


def _get_cursor(conn):
	"""Retorna cursor compat├¡vel (dict-like para PostgreSQL, row_factory para SQLite)."""
	if _USE_SQLITE_FALLBACK or isinstance(conn, sqlite3.Connection):
		conn.row_factory = sqlite3.Row
		return conn.cursor()
	else:
		return conn.cursor()


SCHEMA_STATEMENTS_POSTGRES: Tuple[str, ...] = (
	"""
	CREATE TABLE IF NOT EXISTS atendimentos (
		id SERIAL PRIMARY KEY,
		empresa VARCHAR(255) NOT NULL,
		nome VARCHAR(255) NOT NULL,
		modalidade VARCHAR(100) NOT NULL,
		data VARCHAR(50) NOT NULL,
		hora VARCHAR(20) NOT NULL,
		laudo_pdf VARCHAR(255),
		avaliacao_pdf VARCHAR(255),
		status VARCHAR(50) DEFAULT 'Agendado',
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS notas (
		id SERIAL PRIMARY KEY,
		titulo VARCHAR(255) NOT NULL,
		conteudo TEXT,
		tags VARCHAR(255),
		favorita INTEGER DEFAULT 0
	);
	""",
)

SCHEMA_STATEMENTS_SQLITE: Tuple[str, ...] = (
	"""
	CREATE TABLE IF NOT EXISTS atendimentos (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		empresa TEXT NOT NULL,
		nome TEXT NOT NULL,
		modalidade TEXT NOT NULL,
		data TEXT NOT NULL,
		hora TEXT NOT NULL,
		laudo_pdf TEXT,
		avaliacao_pdf TEXT,
		status TEXT DEFAULT 'Agendado',
		observacoes TEXT,
		criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS notas (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		titulo TEXT NOT NULL,
		conteudo TEXT,
		tags TEXT,
		favorita INTEGER DEFAULT 0
	);
	""",
)


def ensure_schema() -> None:
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		statements = SCHEMA_STATEMENTS_SQLITE if _USE_SQLITE_FALLBACK else SCHEMA_STATEMENTS_POSTGRES
		for statement in statements:
			cur.execute(statement)


def create_tables_if_needed() -> None:  # compatibilidade legado
	ensure_schema()


def verificar_conexao() -> bool:
	try:
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute("SELECT 1")
		return True
	except Exception:
		return False


def inserir_atendimento(
	empresa: str,
	nome: str,
	modalidade: str,
	data: str,
	hora: str,
	laudo_pdf: Optional[str] = None,
	avaliacao_pdf: Optional[str] = None,
	observacoes: Optional[str] = None,
	status: Optional[str] = None,
) -> int:
	if _USE_SQLITE_FALLBACK:
		query = """
		INSERT INTO atendimentos
		(empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes, status)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, 'Agendado'))
		"""
		params = (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes, status)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			return cur.lastrowid or 0
	else:
		query = """
		INSERT INTO atendimentos
		(empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes, status)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, 'Agendado'))
		RETURNING id
		"""
		params = (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes, status)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			result = cur.fetchone()
			return int(result["id"]) if result else 0


def listar_atendimentos() -> List[Tuple]:
	columns = ["id", "empresa", "nome", "modalidade", "data", "hora", "laudo_pdf", "avaliacao_pdf", "status", "observacoes"]
	query = """
	SELECT id, empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, status, observacoes
	FROM atendimentos
	ORDER BY data DESC, hora DESC
	"""
	with _connection_scope(commit=False) as conn:
		cur = _get_cursor(conn)
		cur.execute(query)
		rows = cur.fetchall()
		if _USE_SQLITE_FALLBACK:
			return [tuple(row[col] for col in columns) for row in rows]
		else:
			return [tuple(row[col] for col in columns) for row in rows]


def excluir_atendimento(atendimento_id: int) -> bool:
	if _USE_SQLITE_FALLBACK:
		query = "DELETE FROM atendimentos WHERE id = ?"
		params = (atendimento_id,)
	else:
		query = "DELETE FROM atendimentos WHERE id = %s"
		params = (atendimento_id,)
		
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute(query, params)
		return cur.rowcount > 0


def get_db_diagnostics() -> Dict[str, str]:
	try:
		if _USE_SQLITE_FALLBACK:
			return {"backend": "SQLite", "database": str(_SQLITE_DB), "status": "fallback"}
		
		cfg = _load_db_config()
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
			tables = [row["table_name"] for row in cur.fetchall()]
		return {"backend": "PostgreSQL", "tables": ", ".join(sorted(tables)), "host": cfg["db_host"], "database": cfg["db_name"]}
	except Exception as exc:
		return {"backend": "SQLite (erro PostgreSQL)", "error": str(exc)}


def debug_config_snapshot() -> Dict[str, str]:
	"""Retorna um snapshot das chaves detect├íveis para diagn├│stico r├ípido."""
	if _USE_SQLITE_FALLBACK:
		return {"backend": "SQLite", "sqlite_path": str(_SQLITE_DB)}
	
	info: Dict[str, str] = {}
	normalized = _normalize_mapping(os.environ)
	for key in _REQUIRED_KEYS:
		info[key] = "OK" if key in normalized else "MISSING"
	for alias in _URL_KEYS:
		if alias in normalized:
			info[alias] = "FOUND"
	return info
