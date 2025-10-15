import os
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
except ImportError:  # pragma: no cover
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


def _load_db_config() -> Dict[str, str]:
	"""Carrega configuração obrigatória do PostgreSQL; falha se ausente."""
	global _DB_CACHE
	if _DB_CACHE is not None:
		return _DB_CACHE

	secrets = getattr(st, "secrets", None)
	config = None
	if secrets is not None:
		try:
			config = _build_config_from_mapping(secrets)
		except Exception:
			config = None
	if config is None:
		config = _build_config_from_mapping(os.environ)

	if config is None:
		raise RuntimeError(
			"Banco não configurado. Defina DATABASE_URL ou as variáveis db_host, db_port, db_name, db_user, db_password."
		)

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
		raise RuntimeError("DATABASE_URL inválida: utilize postgres:// ou postgresql://")

	host = parsed.hostname
	if not host:
		raise RuntimeError("DATABASE_URL inválida: host ausente.")

	path = parsed.path.lstrip("/")
	if not path:
		raise RuntimeError("DATABASE_URL inválida: nome do banco ausente.")

	return {
		"db_host": host,
		"db_port": str(parsed.port or 5432),
		"db_name": path,
		"db_user": unquote(parsed.username or ""),
		"db_password": unquote(parsed.password or ""),
	}


def get_connection():
	"""Retorna uma nova conexão PostgreSQL (somente Postgres)."""
	if not POSTGRES_AVAILABLE:
		raise ImportError(
			"psycopg2 não instalado. Instale 'psycopg2-binary' e configure o PostgreSQL."
		)
	cfg = _load_db_config()
	return psycopg2.connect(
		host=cfg["db_host"],
		port=cfg["db_port"],
		dbname=cfg["db_name"],
		user=cfg["db_user"],
		password=cfg["db_password"],
		cursor_factory=psycopg2.extras.RealDictCursor,
	)


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
	"""Retorna cursor PostgreSQL (RealDictCursor já configurado na conexão)."""
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


def ensure_schema() -> None:
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		for statement in SCHEMA_STATEMENTS_POSTGRES:
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
		return [tuple(row[col] for col in columns) for row in rows]


def excluir_atendimento(atendimento_id: int) -> bool:
	query = "DELETE FROM atendimentos WHERE id = %s"
	params = (atendimento_id,)
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute(query, params)
		return cur.rowcount > 0


def get_db_diagnostics() -> Dict[str, str]:
	try:
		cfg = _load_db_config()
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
			tables = [row["table_name"] for row in cur.fetchall()]
		return {"backend": "PostgreSQL", "tables": ", ".join(sorted(tables)), "host": cfg["db_host"], "database": cfg["db_name"]}
	except Exception as exc:
		return {"backend": "PostgreSQL", "error": str(exc)}


def debug_config_snapshot() -> Dict[str, str]:
	"""Retorna um snapshot das chaves detectáveis para diagnóstico rápido."""
	info: Dict[str, str] = {"backend": "PostgreSQL"}
	normalized = _normalize_mapping(os.environ)
	for key in _REQUIRED_KEYS:
		info[key] = "OK" if key in normalized else "MISSING"
	for alias in _URL_KEYS:
		if alias in normalized:
			info[alias] = "FOUND"
	return info
