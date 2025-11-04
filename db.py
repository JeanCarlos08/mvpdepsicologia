import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv  # mantido por compatibilidade, mas não será usado aqui

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

# Carrega um .env da pasta do arquivo, independente do CWD, com fallback de encoding
_LOCAL_ENV_PATH = Path(__file__).resolve().parent / ".env"

# Forçar encoding de cliente e mensagens para evitar erros de decodificação em respostas do servidor
os.environ.setdefault("PGCLIENTENCODING", "UTF8")
os.environ.setdefault("LC_MESSAGES", "C")  # mensagens em ASCII/inglês

def _load_env_with_fallback() -> None:
	"""Carrega variáveis do .env de forma tolerante a encoding (UTF-8 -> Latin-1).

	Evita depender do python-dotenv para leitura com encoding rígido, prevenindo
	UnicodeDecodeError quando o arquivo estiver salvo como ANSI/Latin-1.
	"""
	try:
		if not _LOCAL_ENV_PATH.exists():
			# Não há .env local; não força load_dotenv genérico para evitar ler um .env externo
			return

		# Primeiro tenta UTF-8 estrito; se falhar, usa Latin-1
		try:
			content = _LOCAL_ENV_PATH.read_text(encoding="utf-8")
		except UnicodeDecodeError:
			content = _LOCAL_ENV_PATH.read_text(encoding="latin-1", errors="strict")

		for raw in content.splitlines():
			line = raw.strip()
			if not line or line.startswith('#') or '=' not in line:
				continue
			key, val = line.split('=', 1)
			key = key.strip()
			val = val.strip()
			# remover comentário inline simples (quando não está entre aspas)
			if '#' in val and not (val.startswith('"') or val.startswith("'")):
				val = val.split('#', 1)[0].strip()
			# remover aspas simples/duplas em volta do valor
			val = val.strip('"').strip("'")
			if key and val and not os.getenv(key):
				try:
					os.environ[key] = val
				except Exception:
					# não bloquear por falhas ao setar env
					pass
	except Exception:
		# não bloquear em eventuais falhas; continue com variáveis já existentes
		pass

_load_env_with_fallback()

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
		cfg = {key: str(normalized[key]) for key in _REQUIRED_KEYS}
		# suporte opcional a SSL
		if "db_sslmode" in normalized and normalized["db_sslmode"].strip():
			cfg["db_sslmode"] = normalized["db_sslmode"].strip()
		return cfg

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
	# parse de query params (ex.: sslmode=require)
	db_cfg: Dict[str, str] = {
		"db_host": host,
		"db_port": str(parsed.port or 5432),
		"db_name": path,
		"db_user": unquote(parsed.username or ""),
		"db_password": unquote(parsed.password or ""),
	}
	try:
		from urllib.parse import parse_qs
		q = parse_qs(parsed.query or "")
		sslmode_vals = q.get("sslmode")
		if sslmode_vals and sslmode_vals[0].strip():
			db_cfg["db_sslmode"] = sslmode_vals[0].strip()
	except Exception:
		pass
	return db_cfg


def get_connection():
	"""Retorna uma nova conexão PostgreSQL (somente Postgres)."""
	if not POSTGRES_AVAILABLE:
		raise ImportError(
			"psycopg2 não instalado. Instale 'psycopg2-binary' e configure o PostgreSQL."
		)
	cfg = _load_db_config()
	try:
		conn_kwargs: Dict[str, Any] = dict(
			host=cfg["db_host"],
			port=cfg["db_port"],
			dbname=cfg["db_name"],
			user=cfg["db_user"],
			password=cfg["db_password"],
			cursor_factory=psycopg2.extras.RealDictCursor,
		)
		# aplicar sslmode se fornecido (Cloud geralmente exige 'require')
		sslmode = cfg.get("db_sslmode") if isinstance(cfg, dict) else None
		if sslmode:
			conn_kwargs["sslmode"] = sslmode
		conn = psycopg2.connect(**conn_kwargs)
	except UnicodeDecodeError:
		# Mensagens do servidor com acentuação em algumas instalações podem
		# disparar erro ao decodificar; normalize para uma mensagem segura.
		raise RuntimeError(
			"Falha ao conectar ao PostgreSQL: verifique usuário/senha e existência do banco (mensagem do servidor tinha acentuação)."
		)
	except Exception as e:
		# Reempacotar com mensagem clara, sem forçar decodificação adicional
		raise RuntimeError(f"Falha ao conectar ao PostgreSQL: {e}")
	try:
		# garantir client_encoding consistente
		conn.set_client_encoding('UTF8')
	except Exception:
		pass
	return conn


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
	"""
	CREATE TABLE IF NOT EXISTS arquivos (
		id SERIAL PRIMARY KEY,
		filename VARCHAR(255) NOT NULL,
		content BYTEA NOT NULL,
		content_type VARCHAR(100),
		size INTEGER,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS auditoria (
		id SERIAL PRIMARY KEY,
		acao VARCHAR(100) NOT NULL,
		entidade VARCHAR(100) NOT NULL,
		entidade_id INTEGER,
		detalhes TEXT,
		usuario VARCHAR(120),
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
)


def ensure_schema() -> None:
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		for statement in SCHEMA_STATEMENTS_POSTGRES:
			cur.execute(statement)


def ensure_indexes() -> None:
	"""Cria índices úteis (idempotentes) para acelerar filtros e buscas."""
	stmts = (
		"CREATE INDEX IF NOT EXISTS idx_atendimentos_empresa ON atendimentos(empresa)",
		"CREATE INDEX IF NOT EXISTS idx_atendimentos_nome ON atendimentos(nome)",
		"CREATE INDEX IF NOT EXISTS idx_atendimentos_data ON atendimentos(data)",
		"CREATE INDEX IF NOT EXISTS idx_atendimentos_status ON atendimentos(status)",
	)
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		for s in stmts:
			try:
				cur.execute(s)
			except Exception:
				# Não bloquear o app por falhas em algum índice antigo/legacy
				pass


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
		new_id = int(result["id"]) if result else 0
		try:
			registrar_auditoria("CREATE", "atendimentos", new_id, f"Atendimento criado: {nome} - {empresa}")
		except Exception:
			pass
		return new_id


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
		ok = cur.rowcount > 0
		if ok:
			try:
				registrar_auditoria("DELETE", "atendimentos", atendimento_id, "Atendimento excluído")
			except Exception:
				pass
		return ok


def _allowed_update_fields() -> List[str]:
	return [
		"empresa",
		"nome",
		"modalidade",
		"data",
		"hora",
		"status",
		"observacoes",
		"laudo_pdf",
		"avaliacao_pdf",
	]


def atualizar_campos_atendimento(atendimento_id: int, updates: Dict[str, Any]) -> bool:
	"""Atualiza campos permitidos do atendimento. Ignora chaves inválidas e None."""
	if not updates:
		return False
	set_parts = []
	params: List[Any] = []
	allowed = set(_allowed_update_fields())
	for key, val in updates.items():
		if key in allowed and val is not None:
			set_parts.append(f"{key} = %s")
			params.append(val)
	if not set_parts:
		return False
	params.append(atendimento_id)
	query = f"UPDATE atendimentos SET {', '.join(set_parts)} WHERE id = %s"
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute(query, tuple(params))
		ok = cur.rowcount > 0
		if ok:
			try:
				registrar_auditoria("UPDATE", "atendimentos", atendimento_id, f"Atualização de campos: {', '.join([k for k,v in updates.items() if k in allowed and v is not None])}")
			except Exception:
				pass
		return ok


def atualizar_status(atendimento_id: int, status: str) -> bool:
	status = (status or "").strip()
	if not status:
		return False
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute("UPDATE atendimentos SET status = %s WHERE id = %s", (status, atendimento_id))
		ok = cur.rowcount > 0
		if ok:
			try:
				registrar_auditoria("STATUS", "atendimentos", atendimento_id, f"Status -> {status}")
			except Exception:
				pass
		return ok


def set_anexo(atendimento_id: int, campo: str, marcador: Optional[str]) -> bool:
	"""Define laudo_pdf ou avaliacao_pdf para um marcador (ex.: db:123) ou NULL."""
	campo = (campo or "").strip().lower()
	if campo not in ("laudo_pdf", "avaliacao_pdf"):
		raise ValueError("Campo inválido: use 'laudo_pdf' ou 'avaliacao_pdf'")
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute(f"UPDATE atendimentos SET {campo} = %s WHERE id = %s", (marcador, atendimento_id))
		ok = cur.rowcount > 0
		if ok:
			try:
				registrar_auditoria("ATTACH", "atendimentos", atendimento_id, f"{campo} -> {marcador}")
			except Exception:
				pass
		return ok


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


# ---------- Arquivos (BYTEA) ----------
def salvar_arquivo(filename: str, content: bytes, content_type: Optional[str] = None) -> int:
	"""Salva um arquivo (PDF) no banco e retorna o id gerado."""
	query = """
	INSERT INTO arquivos (filename, content, content_type, size)
	VALUES (%s, %s, %s, %s)
	RETURNING id
	"""
	params = (filename, psycopg2.Binary(content), content_type or "application/pdf", len(content))
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute(query, params)
		row = cur.fetchone()
		return int(row["id"]) if row else 0


def obter_arquivo_por_id(file_id: int) -> Optional[Dict[str, Any]]:
	"""Obtém um arquivo pelo id."""
	query = "SELECT id, filename, content, content_type, size, criado_em FROM arquivos WHERE id = %s"
	with _connection_scope(commit=False) as conn:
		cur = _get_cursor(conn)
		cur.execute(query, (file_id,))
		row = cur.fetchone()
		return dict(row) if row else None


def listar_arquivos() -> List[Dict[str, Any]]:
	"""Lista arquivos disponíveis (sem trazer o conteúdo)."""
	query = "SELECT id, filename, content_type, size, criado_em FROM arquivos ORDER BY criado_em DESC, id DESC"
	with _connection_scope(commit=False) as conn:
		cur = _get_cursor(conn)
		cur.execute(query)
		rows = cur.fetchall()
		return [dict(r) for r in rows]


def excluir_arquivo(file_id: int) -> bool:
	"""Exclui um arquivo pelo id na tabela arquivos."""
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute("DELETE FROM arquivos WHERE id = %s", (file_id,))
		ok = cur.rowcount > 0
		if ok:
			try:
				registrar_auditoria("DELETE", "arquivos", file_id, "Arquivo excluído")
			except Exception:
				pass
		return ok


def desassociar_arquivo_de_atendimentos(file_id: int) -> int:
	"""Remove referências db:<id> de laudo_pdf e avaliacao_pdf. Retorna total de campos afetados."""
	marker = f"db:{file_id}"
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute("UPDATE atendimentos SET laudo_pdf = NULL WHERE laudo_pdf = %s", (marker,))
		c1 = cur.rowcount or 0
		cur.execute("UPDATE atendimentos SET avaliacao_pdf = NULL WHERE avaliacao_pdf = %s", (marker,))
		c2 = cur.rowcount or 0
		return int(c1 + c2)


def limpar_anexo_atendimento(atendimento_id: int, campo: str) -> bool:
	"""Limpa um campo de anexo (laudo_pdf|avaliacao_pdf) de um atendimento específico."""
	campo = (campo or "").strip().lower()
	if campo not in ("laudo_pdf", "avaliacao_pdf"):
		raise ValueError("Campo inválido: use 'laudo_pdf' ou 'avaliacao_pdf'")
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute(f"UPDATE atendimentos SET {campo} = NULL WHERE id = %s", (atendimento_id,))
		ok = cur.rowcount > 0
		if ok:
			try:
				registrar_auditoria("DETACH", "atendimentos", atendimento_id, f"{campo} -> NULL")
			except Exception:
				pass
		return ok


def registrar_auditoria(acao: str, entidade: str, entidade_id: Optional[int], detalhes: Optional[str], usuario: Optional[str] = None) -> None:
	"""Registra evento na tabela auditoria (tolerante a falhas)."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(
				"INSERT INTO auditoria (acao, entidade, entidade_id, detalhes, usuario) VALUES (%s, %s, %s, %s, %s)",
				(acao, entidade, entidade_id, detalhes, usuario),
			)
	except Exception:
		pass


def listar_auditoria(limit: int = 100) -> List[Dict[str, Any]]:
	"""Lista últimas entradas de auditoria."""
	limit = max(1, min(int(limit or 100), 1000))
	with _connection_scope(commit=False) as conn:
		cur = _get_cursor(conn)
		cur.execute("SELECT id, acao, entidade, entidade_id, detalhes, usuario, criado_em FROM auditoria ORDER BY id DESC LIMIT %s", (limit,))
		rows = cur.fetchall()
		return [dict(r) for r in rows]