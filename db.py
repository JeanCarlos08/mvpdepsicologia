import os
from contextlib import contextmanager
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

try:  # Streamlit Cloud fornece st.secrets
	import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
	st = None

load_dotenv()

_REQUIRED_KEYS = ("db_host", "db_port", "db_name", "db_user", "db_password")
_DB_CACHE: Optional[Dict[str, str]] = None


def _load_db_config() -> Dict[str, str]:
	global _DB_CACHE
	if _DB_CACHE is not None:
		return _DB_CACHE

	config: Dict[str, str] = {}

	secrets = getattr(st, "secrets", None)
	if secrets is not None and all(key in secrets for key in _REQUIRED_KEYS):
		config = {key: str(secrets[key]) for key in _REQUIRED_KEYS}
	else:
		for key in _REQUIRED_KEYS:
			value = os.getenv(key) or os.getenv(key.upper())
			if value is None:
				raise RuntimeError(
					f"Variável '{key}' não configurada. Defina em um arquivo .env ou em st.secrets."
				)
			config[key] = value

	_DB_CACHE = config
	return config


def get_connection():
	"""Retorna uma nova conexão psycopg2 usando RealDictCursor."""
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
		conn.rollback()
		raise
	finally:
		conn.close()


SCHEMA_STATEMENTS: Tuple[str, ...] = (
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
		with conn.cursor() as cur:
			for statement in SCHEMA_STATEMENTS:
				cur.execute(statement)


def create_tables_if_needed() -> None:  # compatibilidade legado
	ensure_schema()


def verificar_conexao() -> bool:
	try:
		with _connection_scope(commit=False) as conn:
			with conn.cursor() as cur:
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
	query = (
		"""
		INSERT INTO atendimentos
		(empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes, status)
		VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, 'Agendado'))
		RETURNING id
		"""
	)
	params = (
		empresa,
		nome,
		modalidade,
		data,
		hora,
		laudo_pdf,
		avaliacao_pdf,
		observacoes,
		status,
	)
	with _connection_scope() as conn:
		with conn.cursor() as cur:
			cur.execute(query, params)
			new_id = cur.fetchone()["id"]
			return int(new_id)


def listar_atendimentos() -> List[Tuple]:
	columns = [
		"id",
		"empresa",
		"nome",
		"modalidade",
		"data",
		"hora",
		"laudo_pdf",
		"avaliacao_pdf",
		"status",
		"observacoes",
	]
	query = (
		"""
		SELECT id, empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, status, observacoes
		FROM atendimentos
		ORDER BY data DESC, hora DESC
		"""
	)
	with _connection_scope(commit=False) as conn:
		with conn.cursor() as cur:
			cur.execute(query)
			rows = cur.fetchall()
			return [tuple(row[col] for col in columns) for row in rows]


def excluir_atendimento(atendimento_id: int) -> bool:
	query = "DELETE FROM atendimentos WHERE id = %s"
	with _connection_scope() as conn:
		with conn.cursor() as cur:
			cur.execute(query, (atendimento_id,))
			return cur.rowcount > 0


_ATENDIMENTO_FIELDS = {
	"empresa",
	"nome",
	"modalidade",
	"data",
	"hora",
	"laudo_pdf",
	"avaliacao_pdf",
	"status",
	"observacoes",
}


def atualizar_atendimento(atendimento_id: int, **kwargs) -> bool:
	campos_validos = {k: v for k, v in kwargs.items() if k in _ATENDIMENTO_FIELDS}
	if not campos_validos:
		return False

	set_clause = ", ".join(f"{campo} = %s" for campo in campos_validos)
	params: List = list(campos_validos.values()) + [atendimento_id]
	query = f"UPDATE atendimentos SET {set_clause} WHERE id = %s"

	with _connection_scope() as conn:
		with conn.cursor() as cur:
			cur.execute(query, params)
			return cur.rowcount > 0


def inserir_nota(titulo: str, conteudo: str, tags: str, favorita: int = 0) -> int:
	query = (
		"""
		INSERT INTO notas (titulo, conteudo, tags, favorita)
		VALUES (%s, %s, %s, %s)
		RETURNING id
		"""
	)
	params = (titulo, conteudo, tags, favorita)
	with _connection_scope() as conn:
		with conn.cursor() as cur:
			cur.execute(query, params)
			return int(cur.fetchone()["id"])


def listar_notas() -> List[Tuple]:
	query = "SELECT id, titulo, conteudo, tags, favorita FROM notas ORDER BY id DESC"
	columns = ["id", "titulo", "conteudo", "tags", "favorita"]
	with _connection_scope(commit=False) as conn:
		with conn.cursor() as cur:
			cur.execute(query)
			rows = cur.fetchall()
			return [tuple(row[c] for c in columns) for row in rows]


def atualizar_nota(nota_id: int, **kwargs) -> bool:
	allowed = {"titulo", "conteudo", "tags", "favorita"}
	campos = {k: v for k, v in kwargs.items() if k in allowed}
	if not campos:
		return False
	set_clause = ", ".join(f"{campo} = %s" for campo in campos)
	params: List = list(campos.values()) + [nota_id]
	query = f"UPDATE notas SET {set_clause} WHERE id = %s"
	with _connection_scope() as conn:
		with conn.cursor() as cur:
			cur.execute(query, params)
			return cur.rowcount > 0


def excluir_nota(nota_id: int) -> bool:
	query = "DELETE FROM notas WHERE id = %s"
	with _connection_scope() as conn:
		with conn.cursor() as cur:
			cur.execute(query, (nota_id,))
			return cur.rowcount > 0


def get_db_diagnostics() -> Dict[str, str]:
	try:
		cfg = _load_db_config()
		with _connection_scope(commit=False) as conn:
			with conn.cursor() as cur:
				cur.execute(
					"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
				)
				tables = [row["table_name"] for row in cur.fetchall()]
		return {"tables": ", ".join(sorted(tables)), "host": cfg["db_host"], "database": cfg["db_name"]}
	except Exception as exc:
		return {"error": str(exc)}

