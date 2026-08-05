import json
import io
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
		# Segurança Sênior: Logar internamente e manter erro genérico para o usuário
		raise RuntimeError("Falha ao conectar ao banco de dados. Verifique as credenciais.")
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
		data DATE NOT NULL,
		hora TIME NOT NULL,
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
	"""
	CREATE INDEX IF NOT EXISTS idx_atendimentos_data_hora ON atendimentos (data DESC, hora DESC);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_atendimentos_empresa ON atendimentos (empresa);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_atendimentos_nome ON atendimentos (nome);
	""",
	"""
	CREATE TABLE IF NOT EXISTS user_preferences (
		id SERIAL PRIMARY KEY,
		pref_key VARCHAR(100) UNIQUE NOT NULL,
		pref_value TEXT,
		updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS pacientes (
		id SERIAL PRIMARY KEY,
		nome VARCHAR(255) NOT NULL,
		cpf VARCHAR(20),
		rg VARCHAR(30),
		data_nascimento DATE,
		telefone VARCHAR(30),
		email VARCHAR(255),
		endereco VARCHAR(255),
		observacoes TEXT,
		ativo INTEGER DEFAULT 1,
		foto_b64 TEXT,
		foto_mime VARCHAR(50),
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS anamnese (
		id SERIAL PRIMARY KEY,
		paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
		queixa_principal TEXT,
		historico_doenca TEXT,
		historico_familiar TEXT,
		medicamentos TEXT,
		alergias TEXT,
		habitos TEXT,
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS evolucoes (
		id SERIAL PRIMARY KEY,
		paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
		data DATE NOT NULL,
		texto TEXT NOT NULL,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_pacientes_nome ON pacientes (nome);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_pacientes_cpf ON pacientes (cpf);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_anamnese_paciente ON anamnese (paciente_id);
	""",
	"""
	CREATE TABLE IF NOT EXISTS agendamentos (
		id SERIAL PRIMARY KEY,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		paciente_nome VARCHAR(255),
		empresa VARCHAR(255),
		medico VARCHAR(255) NOT NULL DEFAULT 'Dr(a). Cláudia',
		especialidade VARCHAR(255),
		data DATE NOT NULL,
		hora TIME NOT NULL,
		hora_fim TIME,
		duracao_min INTEGER DEFAULT 50,
		tipo VARCHAR(100) DEFAULT 'Consulta',
		status VARCHAR(50) DEFAULT 'Agendado',
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS lembretes (
		id SERIAL PRIMARY KEY,
		agendamento_id INTEGER REFERENCES agendamentos(id) ON DELETE CASCADE,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		paciente_nome VARCHAR(255),
		empresa VARCHAR(255),
		data_hora_envio TIMESTAMPTZ NOT NULL,
		data_hora_enviado TIMESTAMPTZ,
		canal VARCHAR(50) DEFAULT 'SMS',
		status VARCHAR(50) DEFAULT 'Pendente',
		mensagem TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS triagem (
		id SERIAL PRIMARY KEY,
		agendamento_id INTEGER REFERENCES agendamentos(id) ON DELETE SET NULL,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		data DATE NOT NULL,
		peso NUMERIC(6,2),
		altura NUMERIC(5,2),
		pressao VARCHAR(10),
		temperatura NUMERIC(5,2),
		freq_cardiaca INTEGER,
		saturacao NUMERIC(5,2),
		glicemia INTEGER,
		queixa_principal TEXT,
		historico_resumido TEXT,
		observacoes TEXT,
		gravidade VARCHAR(50) DEFAULT 'Normal',
		avaliado_por VARCHAR(255),
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS fila_espera (
		id SERIAL PRIMARY KEY,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		paciente_nome VARCHAR(255) NOT NULL,
		empresa VARCHAR(255),
		data DATE NOT NULL,
		hora_chegada TIME NOT NULL,
		prioridade VARCHAR(50) DEFAULT 'Normal',
		status VARCHAR(50) DEFAULT 'Aguardando',
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS teleconsulta (
		id SERIAL PRIMARY KEY,
		agendamento_id INTEGER REFERENCES agendamentos(id) ON DELETE SET NULL,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		medico VARCHAR(255) NOT NULL,
		data DATE NOT NULL,
		hora TIME NOT NULL,
		link VARCHAR(500),
		plataforma VARCHAR(100) DEFAULT 'Google Meet',
		status VARCHAR(50) DEFAULT 'Agendado',
		duracao_min INTEGER DEFAULT 50,
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS prescricoes (
		id SERIAL PRIMARY KEY,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		paciente_nome VARCHAR(255),
		atendimento_id INTEGER,
		medico VARCHAR(255) NOT NULL,
		data DATE NOT NULL,
		medicamentos TEXT NOT NULL,
		orientacoes TEXT,
		validade_dias INTEGER DEFAULT 10,
		assinatura_digital BOOLEAN DEFAULT FALSE,
		status VARCHAR(50) DEFAULT 'Ativa',
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS atestados (
		id SERIAL PRIMARY KEY,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		paciente_nome VARCHAR(255),
		atendimento_id INTEGER,
		medico VARCHAR(255) NOT NULL,
		data DATE NOT NULL,
		diagnostico TEXT,
		cid VARCHAR(20),
		dias_afastamento INTEGER,
		tipo VARCHAR(100) DEFAULT 'Atestado médico',
		orientacoes TEXT,
		assinatura_digital BOOLEAN DEFAULT FALSE,
		status VARCHAR(50) DEFAULT 'Emitido',
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS encaminhamentos (
		id SERIAL PRIMARY KEY,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		paciente_nome VARCHAR(255),
		atendimento_id INTEGER,
		medico VARCHAR(255) NOT NULL,
		data DATE NOT NULL,
		especialidade VARCHAR(255) NOT NULL,
		profissional_destino VARCHAR(255),
		motivo TEXT,
		urgente BOOLEAN DEFAULT FALSE,
		status VARCHAR(50) DEFAULT 'Emitido',
		retorno_relatorio BOOLEAN DEFAULT FALSE,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS modelos_laudos (
		id SERIAL PRIMARY KEY,
		nome VARCHAR(255) NOT NULL,
		categoria VARCHAR(100) DEFAULT 'Geral',
		titulo VARCHAR(255),
		cabecalho TEXT,
		corpo TEXT NOT NULL,
		rodape TEXT,
		tipo_exame VARCHAR(255),
		assinatura_digital BOOLEAN DEFAULT FALSE,
		ativo INTEGER DEFAULT 1,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS laudos_emitidos (
		id SERIAL PRIMARY KEY,
		modelo_id INTEGER REFERENCES modelos_laudos(id) ON DELETE SET NULL,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		paciente_nome VARCHAR(255),
		empresa VARCHAR(255),
		medico VARCHAR(255),
		tipo_exame VARCHAR(255),
		conteudo TEXT NOT NULL,
		versao INTEGER DEFAULT 1,
		codigo_autenticacao VARCHAR(50),
		assinatura_digital BOOLEAN DEFAULT FALSE,
		status VARCHAR(50) DEFAULT 'Emitido',
		enviado_email BOOLEAN DEFAULT FALSE,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS laudo_versoes (
		id SERIAL PRIMARY KEY,
		laudo_id INTEGER NOT NULL REFERENCES laudos_emitidos(id) ON DELETE CASCADE,
		versao INTEGER NOT NULL,
		conteudo TEXT NOT NULL,
		editado_por VARCHAR(255),
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS lancamentos (
		id SERIAL PRIMARY KEY,
		tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('Receita', 'Despesa')),
		categoria VARCHAR(100) NOT NULL,
		descricao VARCHAR(255),
		valor NUMERIC(12,2) NOT NULL DEFAULT 0,
		data DATE NOT NULL,
		forma_pagamento VARCHAR(50),
		status VARCHAR(50) DEFAULT 'Pago',
		empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL,
		empresa_nome VARCHAR(255),
		convenio VARCHAR(255),
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS notas_fiscais (
		id SERIAL PRIMARY KEY,
		empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL,
		empresa_nome VARCHAR(255),
		numero VARCHAR(50),
		serie VARCHAR(10),
		tipo VARCHAR(50) DEFAULT 'NFSe',
		data_emissao DATE NOT NULL,
		valor NUMERIC(12,2) NOT NULL DEFAULT 0,
		descricao VARCHAR(255),
		status VARCHAR(50) DEFAULT 'Emitida',
		caminho_arquivo VARCHAR(500),
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS consentimentos (
		id SERIAL PRIMARY KEY,
		paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
		paciente_nome VARCHAR(255),
		tipo VARCHAR(100) NOT NULL,
		descricao TEXT,
		assinado_em DATE,
		validade DATE,
		ip_origem VARCHAR(45),
		assentimento BOOLEAN NOT NULL DEFAULT FALSE,
		documento_versao VARCHAR(20),
		registrado_por VARCHAR(255),
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_consentimentos_paciente ON consentimentos (paciente_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_lancamentos_data ON lancamentos (data);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_lancamentos_tipo ON lancamentos (tipo);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_notas_fiscais_empresa ON notas_fiscais (empresa_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_modelos_laudos_categoria ON modelos_laudos (categoria);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_laudos_emitidos_paciente ON laudos_emitidos (paciente_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_laudo_versoes_laudo ON laudo_versoes (laudo_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_prescricoes_paciente ON prescricoes (paciente_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_atestados_paciente ON atestados (paciente_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_encaminhamentos_paciente ON encaminhamentos (paciente_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_agendamentos_data ON agendamentos (data);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_agendamentos_paciente ON agendamentos (paciente_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_lembretes_agendamento ON lembretes (agendamento_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_triagem_agendamento ON triagem (agendamento_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_fila_espera_data ON fila_espera (data);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_teleconsulta_data ON teleconsulta (data);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_evolucoes_paciente ON evolucoes (paciente_id);
	""",
	"""
	CREATE TABLE IF NOT EXISTS empresas (
		id SERIAL PRIMARY KEY,
		nome VARCHAR(255) NOT NULL,
		cnpj VARCHAR(30),
		razao_social VARCHAR(255),
		endereco VARCHAR(255),
		telefone VARCHAR(30),
		email VARCHAR(255),
		responsavel VARCHAR(255),
		quantidade_funcionarios INTEGER DEFAULT 0,
		plano VARCHAR(100),
		data_contrato DATE,
		validade_contrato DATE,
		ativo INTEGER DEFAULT 1,
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS convenios (
		id SERIAL PRIMARY KEY,
		empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
		operadora VARCHAR(255) NOT NULL,
		numero_carteira VARCHAR(100),
		validade DATE,
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
	"""
	CREATE TABLE IF NOT EXISTS faturamento_empresa (
		id SERIAL PRIMARY KEY,
		empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
		mes INTEGER NOT NULL,
		ano INTEGER NOT NULL,
		valor_total NUMERIC(12,2) DEFAULT 0,
		quantidade_atendimentos INTEGER DEFAULT 0,
		observacoes TEXT,
		criado_em TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
		UNIQUE (empresa_id, mes, ano)
	);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_empresas_nome ON empresas (nome);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_empresas_cnpj ON empresas (cnpj);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_convenios_empresa ON convenios (empresa_id);
	""",
	"""
	CREATE INDEX IF NOT EXISTS idx_faturamento_empresa ON faturamento_empresa (empresa_id);
	""",
	"""
	CREATE TABLE IF NOT EXISTS google_oauth (
		id INTEGER PRIMARY KEY DEFAULT 1,
		token_json TEXT NOT NULL,
		updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
	);
	""",
)


def _migrate_date_time_columns() -> None:
	"""Migra colunas data/hora de VARCHAR para DATE/TIME no PostgreSQL se necessário."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			# Verifica o tipo atual da coluna 'data'
			cur.execute("""
				SELECT data_type 
				FROM information_schema.columns 
				WHERE table_name = 'atendimentos' AND column_name = 'data'
			""")
			res = cur.fetchone()
			if res and res['data_type'] in ('character varying', 'text'):
				# Migrar data: DD/MM/YYYY -> DATE
				cur.execute("""
					ALTER TABLE atendimentos 
					ALTER COLUMN data TYPE DATE 
					USING TO_DATE(data, 'DD/MM/YYYY')
				""")
				# Migrar hora: HH:MM -> TIME
				cur.execute("""
					ALTER TABLE atendimentos 
					ALTER COLUMN hora TYPE TIME 
					USING hora::TIME
				""")
	except Exception as e:
		print(f"MIGRATION_WARNING: Erro ao migrar colunas: {e}")

def _migrate_modalidade_periodico() -> None:
	"""Corrige registros antigos com modalidade 'Período' para 'Periódico'."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(
				"UPDATE atendimentos SET modalidade = %s WHERE modalidade = %s",
				("Periódico", "Período")
			)
	except Exception:
		pass

_SCHEMA_OK: bool = False


def ensure_schema(force: bool = False) -> None:
	"""Garante que a estrutura do banco esteja correta e migrada.

	Idempotente por processo: só executa de fato na primeira chamada,
	exceto quando force=True (ex.: botão "Reinicializar DB").
	"""
	global _SCHEMA_OK
	if _SCHEMA_OK and not force:
		return
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		for statement in SCHEMA_STATEMENTS_POSTGRES:
			try:
				cur.execute(statement)
			except Exception:
				pass
	
	# Rodar migração de tipos se necessário (Sênior)
	_migrate_date_time_columns()
	# Corrigir nome de modalidade Período -> Periódico
	_migrate_modalidade_periodico()

	# Garantir índices atualizados
	ensure_indexes()

	_SCHEMA_OK = True


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


# ---------- Preferências do Usuário ----------

# ─────────────────────────────────────────────────────────────
# Empresas / Convênios / Faturamento
# ─────────────────────────────────────────────────────────────

def inserir_empresa(dados: Dict[str, Any]) -> Optional[int]:
	"""Insere uma empresa. Retorna o id criado ou None em falha."""
	try:
		query = """
		INSERT INTO empresas (
			nome, cnpj, razao_social, endereco, telefone, email, responsavel,
			quantidade_funcionarios, plano, data_contrato, validade_contrato, ativo, observacoes
		)
		VALUES (%(nome)s, %(cnpj)s, %(razao_social)s, %(endereco)s, %(telefone)s, %(email)s,
				%(responsavel)s, %(quantidade_funcionarios)s, %(plano)s, %(data_contrato)s,
				%(validade_contrato)s, %(ativo)s, %(observacoes)s)
		RETURNING id
		"""
		params = {
			"nome": dados.get("nome") or "",
			"cnpj": dados.get("cnpj") or None,
			"razao_social": dados.get("razao_social") or None,
			"endereco": dados.get("endereco") or None,
			"telefone": dados.get("telefone") or None,
			"email": dados.get("email") or None,
			"responsavel": dados.get("responsavel") or None,
			"quantidade_funcionarios": int(dados.get("quantidade_funcionarios") or 0),
			"plano": dados.get("plano") or None,
			"data_contrato": dados.get("data_contrato"),
			"validade_contrato": dados.get("validade_contrato"),
			"ativo": 1 if dados.get("ativo", True) else 0,
			"observacoes": dados.get("observacoes") or None,
		}
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			empresa_id = int(row["id"]) if row else None
			if empresa_id:
				try:
					registrar_auditoria("CREATE", "empresas", empresa_id, f"Empresa criada: {params['nome']}")
				except Exception:
					pass
			return empresa_id
	except Exception:
		return None


def listar_empresas(filtro: Optional[str] = None, ativas_apenas: bool = False) -> List[Dict[str, Any]]:
	try:
		where = []
		params: List[Any] = []
		if filtro:
			q = f"%{filtro.strip()}%"
			where.append("(nome ILIKE %s OR cnpj ILIKE %s OR razao_social ILIKE %s OR email ILIKE %s)")
			params.extend([q, q, q, q])
		if ativas_apenas:
			where.append("ativo = 1")
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT id, nome, cnpj, razao_social, endereco, telefone, email, responsavel,
			   quantidade_funcionarios, plano, data_contrato, validade_contrato, ativo, observacoes, criado_em
		FROM empresas
		{where_sql}
		ORDER BY nome ASC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_empresa(empresa_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = """
		SELECT id, nome, cnpj, razao_social, endereco, telefone, email, responsavel,
			   quantidade_funcionarios, plano, data_contrato, validade_contrato, ativo, observacoes, criado_em
		FROM empresas WHERE id = %s
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (empresa_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def atualizar_empresa(empresa_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"nome", "cnpj", "razao_social", "endereco", "telefone", "email", "responsavel",
				   "quantidade_funcionarios", "plano", "data_contrato", "validade_contrato", "ativo", "observacoes"}
		set_parts = []
		params: List[Any] = []
		for key, val in dados.items():
			if key in allowed and val is not None:
				set_parts.append(f"{key} = %s")
				params.append(val)
		if not set_parts:
			return False
		set_parts.append("atualizado_em = NOW()")
		params.append(empresa_id)
		query = f"UPDATE empresas SET {', '.join(set_parts)} WHERE id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def excluir_empresa(empresa_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM empresas WHERE id = %s", (empresa_id,))
			ok = cur.rowcount > 0
			if ok:
				try:
					registrar_auditoria("DELETE", "empresas", empresa_id, "Empresa excluída")
				except Exception:
					pass
			return ok
	except Exception:
		return False


def buscar_empresas_duplicadas(nome: str, cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		nome_clean = (nome or "").strip().lower()
		if not nome_clean:
			return []
		if cnpj and cnpj.strip():
			query = """
			SELECT id, nome, cnpj, telefone, ativo FROM empresas
			WHERE LOWER(nome) = %s OR (cnpj IS NOT NULL AND cnpj = %s)
			"""
			params = (nome_clean, cnpj.strip())
		else:
			query = "SELECT id, nome, cnpj, telefone, ativo FROM empresas WHERE LOWER(nome) = %s"
			params = (nome_clean,)
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


# ── Convênios ────────────────────────────────────────────────

def inserir_convenio(empresa_id: int, dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO convenios (empresa_id, operadora, numero_carteira, validade, observacoes)
		VALUES (%s, %s, %s, %s, %s)
		RETURNING id
		"""
		params = (
			empresa_id,
			dados.get("operadora") or "",
			dados.get("numero_carteira") or None,
			dados.get("validade"),
			dados.get("observacoes") or None,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_convenios(empresa_id: int) -> List[Dict[str, Any]]:
	try:
		query = """
		SELECT id, empresa_id, operadora, numero_carteira, validade, observacoes, criado_em
		FROM convenios WHERE empresa_id = %s ORDER BY operadora
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (empresa_id,))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def excluir_convenio(convenio_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM convenios WHERE id = %s", (convenio_id,))
			return cur.rowcount > 0
	except Exception:
		return False


# ── Faturamento por empresa ──────────────────────────────────

def salvar_faturamento_empresa(empresa_id: int, mes: int, ano: int, valor_total: float, quantidade: int, observacoes: Optional[str] = None) -> bool:
	try:
		query = """
		INSERT INTO faturamento_empresa (empresa_id, mes, ano, valor_total, quantidade_atendimentos, observacoes)
		VALUES (%s, %s, %s, %s, %s, %s)
		ON CONFLICT (empresa_id, mes, ano)
		DO UPDATE SET valor_total = EXCLUDED.valor_total,
					  quantidade_atendimentos = EXCLUDED.quantidade_atendimentos,
					  observacoes = EXCLUDED.observacoes
		"""
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (empresa_id, mes, ano, valor_total, quantidade, observacoes))
			return cur.rowcount > 0
	except Exception:
		return False


def listar_faturamento_empresa(empresa_id: int, ano: Optional[int] = None) -> List[Dict[str, Any]]:
	try:
		if ano:
			query = """
			SELECT id, empresa_id, mes, ano, valor_total, quantidade_atendimentos, observacoes, criado_em
			FROM faturamento_empresa WHERE empresa_id = %s AND ano = %s ORDER BY mes
			"""
			params = (empresa_id, ano)
		else:
			query = """
			SELECT id, empresa_id, mes, ano, valor_total, quantidade_atendimentos, observacoes, criado_em
			FROM faturamento_empresa WHERE empresa_id = %s ORDER BY ano DESC, mes
			"""
			params = (empresa_id,)
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_faturamento(empresa_id: int, mes: int, ano: int) -> Optional[Dict[str, Any]]:
	try:
		query = """
		SELECT id, empresa_id, mes, ano, valor_total, quantidade_atendimentos, observacoes
		FROM faturamento_empresa WHERE empresa_id = %s AND mes = %s AND ano = %s
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (empresa_id, mes, ano))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def contar_atendimentos_empresa(nome_empresa: str) -> int:
	"""Conta atendimentos de uma empresa pelo nome."""
	try:
		query = "SELECT COUNT(*) AS total FROM atendimentos WHERE empresa = %s"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (nome_empresa,))
			row = cur.fetchone()
			return int(row["total"]) if row else 0
	except Exception:
		return 0


def listar_empresas_com_contrato_vencendo(dias: int = 30) -> List[Dict[str, Any]]:
	"""Lista empresas cujo contrato vence dentro de X dias ou já venceu."""
	try:
		query = """
		SELECT id, nome, cnpj, telefone, validade_contrato, responsavel
		FROM empresas
		WHERE ativo = 1 AND validade_contrato IS NOT NULL
		  AND validade_contrato <= CURRENT_DATE + %s
		ORDER BY validade_contrato
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (int(dias),))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


# ─────────────────────────────────────────────────────────────
# Agenda / Agendamentos
# ─────────────────────────────────────────────────────────────

def inserir_agendamento(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO agendamentos (
			paciente_id, paciente_nome, empresa, medico, especialidade, data, hora,
			hora_fim, duracao_min, tipo, status, observacoes
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
		RETURNING id
		"""
		params = (
			dados.get("paciente_id"),
			dados.get("paciente_nome") or None,
			dados.get("empresa") or None,
			dados.get("medico") or "Dr(a). Cláudia",
			dados.get("especialidade") or None,
			dados["data"],
			dados["hora"],
			dados.get("hora_fim"),
			dados.get("duracao_min") or 50,
			dados.get("tipo") or "Consulta",
			dados.get("status") or "Agendado",
			dados.get("observacoes") or None,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_agendamentos(data: Optional[str] = None, medico: Optional[str] = None,
						status: Optional[str] = None, inicio: Optional[str] = None,
						fim: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if data:
			where.append("data = %s"); params.append(data)
		if medico:
			where.append("medico = %s"); params.append(medico)
		if status:
			where.append("status = %s"); params.append(status)
		if inicio and fim:
			where.append("data BETWEEN %s AND %s"); params.extend([inicio, fim])
		elif inicio:
			where.append("data >= %s"); params.append(inicio)
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT id, paciente_id, paciente_nome, empresa, medico, especialidade, data, hora,
			   hora_fim, duracao_min, tipo, status, observacoes, criado_em
		FROM agendamentos {where_sql}
		ORDER BY data, hora
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_agendamento(ag_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = """
		SELECT id, paciente_id, paciente_nome, empresa, medico, especialidade, data, hora,
			   hora_fim, duracao_min, tipo, status, observacoes, criado_em
		FROM agendamentos WHERE id = %s
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (ag_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def atualizar_agendamento(ag_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"paciente_id", "paciente_nome", "empresa", "medico", "especialidade",
				   "data", "hora", "hora_fim", "duracao_min", "tipo", "status", "observacoes"}
		set_parts, params = [], []
		for k, v in dados.items():
			if k in allowed and v is not None:
				set_parts.append(f"{k} = %s"); params.append(v)
		if not set_parts:
			return False
		set_parts.append("atualizado_em = NOW()")
		params.append(ag_id)
		query = f"UPDATE agendamentos SET {', '.join(set_parts)} WHERE id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def cancelar_agendamento(ag_id: int) -> bool:
	return atualizar_agendamento(ag_id, {"status": "Cancelado"})


def reagendar_agendamento(ag_id: int, nova_data: str, nova_hora: str) -> bool:
	return atualizar_agendamento(ag_id, {"data": nova_data, "hora": nova_hora, "status": "Reagendado"})


def marcar_checkin(ag_id: int) -> bool:
	return atualizar_agendamento(ag_id, {"status": "Check-in"})


def excluir_agendamento(ag_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM agendamentos WHERE id = %s", (ag_id,))
			return cur.rowcount > 0
	except Exception:
		return False


def verificar_conflito(medico: str, data: str, hora: str, duracao_min: int = 50, excluir_id: Optional[int] = None) -> bool:
	"""Verifica se há conflito de horário para o médico."""
	try:
		hora_fim_calculada = _somar_minutos_hora(hora, duracao_min)
		where = "medico = %s AND data = %s AND status != 'Cancelado'"
		params: List[Any] = [medico, data]
		if excluir_id:
			where += " AND id != %s"
			params.append(excluir_id)
		query = f"""
		SELECT COUNT(*) AS total FROM agendamentos
		WHERE {where} AND hora < %s
		  AND (hora_fim IS NOT NULL AND hora_fim > %s)
		"""
		params.extend([hora_fim_calculada, hora])
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			row = cur.fetchone()
			return int(row["total"]) > 0 if row else False
	except Exception:
		return False


def contar_agendamentos_medico(medico: str, data: str) -> int:
	try:
		query = "SELECT COUNT(*) AS total FROM agendamentos WHERE medico = %s AND data = %s AND status NOT IN ('Cancelado')"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (medico, data))
			row = cur.fetchone()
			return int(row["total"]) if row else 0
	except Exception:
		return 0


def _somar_minutos_hora(hora_str: str, minutos: int) -> str:
	"""Soma minutos a uma hora 'HH:MM' e retorna 'HH:MM:SS'."""
	try:
		h, m = map(int, str(hora_str).split(":")[:2])
		total = h * 60 + m + minutos
		nh, nm = divmod(total % (24 * 60), 60)
		return f"{nh:02d}:{nm:02d}:00"
	except Exception:
		return hora_str


# ── Lembretes ────────────────────────────────────────────────

def criar_lembrete(agendamento_id: int, paciente_id: Optional[int], paciente_nome: Optional[str],
				   empresa: Optional[str], canal: str, data_hora_envio, mensagem: str) -> Optional[int]:
	try:
		query = """
		INSERT INTO lembretes (agendamento_id, paciente_id, paciente_nome, empresa, data_hora_envio, canal, mensagem)
		VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (agendamento_id, paciente_id, paciente_nome, empresa, data_hora_envio, canal, mensagem)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_lembretes_pendentes(canal: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where = "status = 'Pendente' AND data_hora_envio <= NOW()"
		params: List[Any] = []
		if canal:
			where += " AND canal = %s"; params.append(canal)
		query = f"""
		SELECT l.*, a.data AS agendamento_data, a.hora AS agendamento_hora, a.medico
		FROM lembretes l LEFT JOIN agendamentos a ON l.agendamento_id = a.id
		WHERE {where} ORDER BY l.data_hora_envio
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def marcar_lembrete_enviado(lembrete_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("UPDATE lembretes SET status='Enviado', data_hora_enviado=NOW() WHERE id=%s", (lembrete_id,))
			return cur.rowcount > 0
	except Exception:
		return False


def criar_lembretes_agendamento(agendamento_id: int) -> None:
	"""Cria lembretes automáticos: 24h antes (SMS) e 2h antes (WhatsApp) do agendamento."""
	try:
		ag = obter_agendamento(agendamento_id)
		if not ag or ag["status"] in ("Cancelado", "Concluído"):
			return
		data = ag["data"]
		hora = ag["hora"]
		if hasattr(data, "strftime"):
			data = data.strftime("%Y-%m-%d")
		if hasattr(hora, "strftime"):
			hora = hora.strftime("%H:%M")
		from datetime import datetime as _dt, timedelta
		dt_consulta = _dt.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
		# 24h antes
		dt_24 = dt_consulta - timedelta(hours=24)
		if dt_24 > _dt.now():
			msg24 = f"Lembrete: Você tem consulta amanhã às {hora} com {ag.get('medico','')}. Caso não possa comparecer, entre em contato."
			criar_lembrete(agendamento_id, ag.get("paciente_id"), ag.get("paciente_nome"),
						   ag.get("empresa"), "SMS", dt_24, msg24)
		# 2h antes
		dt_2 = dt_consulta - timedelta(hours=2)
		if dt_2 > _dt.now():
			msg2h = f"Lembrete rápido: Sua consulta é daqui a 2 horas, às {hora}. Confirme sua presença!"
			criar_lembrete(agendamento_id, ag.get("paciente_id"), ag.get("paciente_nome"),
						   ag.get("empresa"), "WhatsApp", dt_2, msg2h)
	except Exception:
		pass


# ── Triagem ──────────────────────────────────────────────────

def salvar_triagem(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO triagem (
			agendamento_id, paciente_id, data, peso, altura, pressao, temperatura,
			freq_cardiaca, saturacao, glicemia, queixa_principal, historico_resumido,
			observacoes, gravidade, avaliado_por
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("agendamento_id"), dados.get("paciente_id"), dados["data"],
			dados.get("peso"), dados.get("altura"), dados.get("pressao") or None,
			dados.get("temperatura"), dados.get("freq_cardiaca"),
			dados.get("saturacao"), dados.get("glicemia"),
			dados.get("queixa_principal") or None, dados.get("historico_resumido") or None,
			dados.get("observacoes") or None, dados.get("gravidade") or "Normal",
			dados.get("avaliado_por") or None,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_triagens(data: Optional[str] = None, paciente_id: Optional[int] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if data:
			where.append("t.data = %s"); params.append(data)
		if paciente_id:
			where.append("t.paciente_id = %s"); params.append(paciente_id)
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT t.*, a.medico, a.hora
		FROM triagem t LEFT JOIN agendamentos a ON t.agendamento_id = a.id
		{where_sql} ORDER BY t.data DESC, t.criado_em DESC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


# ── Fila de Espera ──────────────────────────────────────────

def entrar_fila_espera(paciente_nome: str, empresa: Optional[str], data: str, hora: str,
					   prioridade: str = "Normal", observacoes: Optional[str] = None) -> Optional[int]:
	try:
		query = """
		INSERT INTO fila_espera (paciente_nome, empresa, data, hora_chegada, prioridade, observacoes)
		VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (paciente_nome, empresa, data, hora, prioridade, observacoes)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_fila_espera(data: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if data:
			where.append("data = %s"); params.append(data)
		else:
			where.append("data = CURRENT_DATE")
		if status:
			where.append("status = %s"); params.append(status)
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT id, paciente_nome, empresa, data, hora_chegada, prioridade, status, observacoes
		FROM fila_espera {where_sql}
		ORDER BY CASE prioridade WHEN 'Urgente' THEN 1 WHEN 'Prioritário' THEN 2 ELSE 3 END, hora_chegada
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def atualizar_fila_espera(fila_id: int, status: str) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("UPDATE fila_espera SET status = %s WHERE id = %s", (status, fila_id))
			return cur.rowcount > 0
	except Exception:
		return False


def remover_fila_espera(fila_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM fila_espera WHERE id = %s", (fila_id,))
			return cur.rowcount > 0
	except Exception:
		return False


# ── Teleconsulta ────────────────────────────────────────────

def criar_teleconsulta(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO teleconsulta (agendamento_id, paciente_id, medico, data, hora, link, plataforma, duracao_min, observacoes)
		VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("agendamento_id"), dados.get("paciente_id"), dados["medico"],
			dados["data"], dados["hora"], dados.get("link") or None,
			dados.get("plataforma") or "Google Meet", dados.get("duracao_min") or 50,
			dados.get("observacoes") or None,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_teleconsulta(data: Optional[str] = None, medico: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if data:
			where.append("t.data = %s"); params.append(data)
		if medico:
			where.append("t.medico = %s"); params.append(medico)
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT t.*, a.paciente_nome, a.especialidade
		FROM teleconsulta t LEFT JOIN agendamentos a ON t.agendamento_id = a.id
		{where_sql} ORDER BY t.data, t.hora
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


# ─────────────────────────────────────────────────────────────
# Prescrições / Atestados / Encaminhamentos
# ─────────────────────────────────────────────────────────────

def inserir_prescricao(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO prescricoes (
			paciente_id, paciente_nome, atendimento_id, medico, data, medicamentos,
			orientacoes, validade_dias, assinatura_digital, status
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("paciente_id"), dados.get("paciente_nome") or None,
			dados.get("atendimento_id"), dados["medico"], dados["data"],
			dados["medicamentos"], dados.get("orientacoes") or None,
			dados.get("validade_dias") or 10,
			True if dados.get("assinatura_digital") else False,
			dados.get("status") or "Ativa",
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_prescricoes(paciente_id: Optional[int] = None, filtro: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if paciente_id:
			where.append("paciente_id = %s"); params.append(paciente_id)
		if filtro:
			where.append("(paciente_nome ILIKE %s OR medico ILIKE %s)")
			q = f"%{filtro}%"; params.extend([q, q])
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT id, paciente_id, paciente_nome, atendimento_id, medico, data, medicamentos,
			   orientacoes, validade_dias, assinatura_digital, status, criado_em
		FROM prescricoes {where_sql} ORDER BY data DESC, id DESC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_prescricao(presc_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = """SELECT * FROM prescricoes WHERE id = %s"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (presc_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def atualizar_prescricao(presc_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"paciente_id", "paciente_nome", "atendimento_id", "medico", "data",
				   "medicamentos", "orientacoes", "validade_dias", "assinatura_digital", "status"}
		set_parts, params = [], []
		for k, v in dados.items():
			if k in allowed and v is not None:
				set_parts.append(f"{k} = %s"); params.append(v)
		if not set_parts:
			return False
		params.append(presc_id)
		query = f"UPDATE prescricoes SET {', '.join(set_parts)} WHERE id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def excluir_prescricao(presc_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM prescricoes WHERE id = %s", (presc_id,))
			return cur.rowcount > 0
	except Exception:
		return False


def inserir_atestado(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO atestados (
			paciente_id, paciente_nome, atendimento_id, medico, data, diagnostico,
			cid, dias_afastamento, tipo, orientacoes, assinatura_digital, status
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("paciente_id"), dados.get("paciente_nome") or None,
			dados.get("atendimento_id"), dados["medico"], dados["data"],
			dados.get("diagnostico") or None, dados.get("cid") or None,
			dados.get("dias_afastamento"), dados.get("tipo") or "Atestado médico",
			dados.get("orientacoes") or None,
			True if dados.get("assinatura_digital") else False,
			dados.get("status") or "Emitido",
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_atestados(paciente_id: Optional[int] = None, filtro: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if paciente_id:
			where.append("paciente_id = %s"); params.append(paciente_id)
		if filtro:
			where.append("(paciente_nome ILIKE %s OR cid ILIKE %s)")
			q = f"%{filtro}%"; params.extend([q, q])
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT id, paciente_id, paciente_nome, atendimento_id, medico, data, diagnostico,
			   cid, dias_afastamento, tipo, orientacoes, assinatura_digital, status, criado_em
		FROM atestados {where_sql} ORDER BY data DESC, id DESC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_atestado(atest_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = """SELECT * FROM atestados WHERE id = %s"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (atest_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def atualizar_atestado(atest_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"paciente_id", "paciente_nome", "atendimento_id", "medico", "data",
				   "diagnostico", "cid", "dias_afastamento", "tipo", "orientacoes",
				   "assinatura_digital", "status"}
		set_parts, params = [], []
		for k, v in dados.items():
			if k in allowed and v is not None:
				set_parts.append(f"{k} = %s"); params.append(v)
		if not set_parts:
			return False
		params.append(atest_id)
		query = f"UPDATE atestados SET {', '.join(set_parts)} WHERE id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def excluir_atestado(atest_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM atestados WHERE id = %s", (atest_id,))
			return cur.rowcount > 0
	except Exception:
		return False


def inserir_encaminhamento(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO encaminhamentos (
			paciente_id, paciente_nome, atendimento_id, medico, data, especialidade,
			profissional_destino, motivo, urgente, status, retorno_relatorio
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("paciente_id"), dados.get("paciente_nome") or None,
			dados.get("atendimento_id"), dados["medico"], dados["data"],
			dados["especialidade"], dados.get("profissional_destino") or None,
			dados.get("motivo") or None, True if dados.get("urgente") else False,
			dados.get("status") or "Emitido",
			True if dados.get("retorno_relatorio") else False,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_encaminhamentos(paciente_id: Optional[int] = None, filtro: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if paciente_id:
			where.append("paciente_id = %s"); params.append(paciente_id)
		if filtro:
			where.append("(paciente_nome ILIKE %s OR especialidade ILIKE %s OR profissional_destino ILIKE %s)")
			q = f"%{filtro}%"; params.extend([q, q, q])
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT id, paciente_id, paciente_nome, atendimento_id, medico, data, especialidade,
			   profissional_destino, motivo, urgente, status, retorno_relatorio, criado_em
		FROM encaminhamentos {where_sql} ORDER BY data DESC, id DESC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_encaminhamento(enc_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = """SELECT * FROM encaminhamentos WHERE id = %s"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (enc_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def atualizar_encaminhamento(enc_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"paciente_id", "paciente_nome", "atendimento_id", "medico", "data",
				   "especialidade", "profissional_destino", "motivo", "urgente",
				   "status", "retorno_relatorio"}
		set_parts, params = [], []
		for k, v in dados.items():
			if k in allowed and v is not None:
				set_parts.append(f"{k} = %s"); params.append(v)
		if not set_parts:
			return False
		params.append(enc_id)
		query = f"UPDATE encaminhamentos SET {', '.join(set_parts)} WHERE id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def excluir_encaminhamento(enc_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM encaminhamentos WHERE id = %s", (enc_id,))
			return cur.rowcount > 0
	except Exception:
		return False


# ─────────────────────────────────────────────────────────────
# Laudos / Modelos de Laudos
# ─────────────────────────────────────────────────────────────

def inserir_modelo_laudo(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO modelos_laudos (nome, categoria, titulo, cabecalho, corpo, rodape, tipo_exame, assinatura_digital, ativo)
		VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("nome") or "", dados.get("categoria") or "Geral",
			dados.get("titulo") or None, dados.get("cabecalho") or None,
			dados["corpo"], dados.get("rodape") or None,
			dados.get("tipo_exame") or None,
			True if dados.get("assinatura_digital") else False,
			1 if dados.get("ativo", True) else 0,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_modelos_laudos(categoria: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if categoria:
			where.append("categoria = %s"); params.append(categoria)
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"SELECT * FROM modelos_laudos {where_sql} ORDER BY nome"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_modelo_laudo(modelo_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = "SELECT * FROM modelos_laudos WHERE id = %s"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (modelo_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def atualizar_modelo_laudo(modelo_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"nome", "categoria", "titulo", "cabecalho", "corpo", "rodape",
				   "tipo_exame", "assinatura_digital", "ativo"}
		set_parts, params = [], []
		for k, v in dados.items():
			if k in allowed and v is not None:
				set_parts.append(f"{k} = %s"); params.append(v)
		if not set_parts:
			return False
		set_parts.append("atualizado_em = NOW()")
		params.append(modelo_id)
		query = f"UPDATE modelos_laudos SET {', '.join(set_parts)} WHERE id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def excluir_modelo_laudo(modelo_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM modelos_laudos WHERE id = %s", (modelo_id,))
			return cur.rowcount > 0
	except Exception:
		return False


def inserir_laudo_emitido(dados: Dict[str, Any]) -> Optional[int]:
	"""Cria um laudo emitido + registro de versão 1."""
	import hashlib, random, string
	try:
		codigo = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
		query = """
		INSERT INTO laudos_emitidos (
			modelo_id, paciente_id, paciente_nome, empresa, medico, tipo_exame, conteudo,
			versao, codigo_autenticacao, assinatura_digital, status, enviado_email
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("modelo_id"), dados.get("paciente_id"), dados.get("paciente_nome") or None,
			dados.get("empresa") or None, dados.get("medico") or None,
			dados.get("tipo_exame") or None, dados["conteudo"], 1,
			codigo, True if dados.get("assinatura_digital") else False,
			dados.get("status") or "Emitido",
			True if dados.get("enviado_email") else False,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			laudo_id = int(row["id"]) if row else None
			if laudo_id:
				cur.execute("""
				INSERT INTO laudo_versoes (laudo_id, versao, conteudo, editado_por)
				VALUES (%s, 1, %s, %s)
				""", (laudo_id, dados["conteudo"], dados.get("medico") or None))
			return laudo_id
	except Exception:
		return None


def listar_laudos_emitidos(paciente_id: Optional[int] = None, filtro: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if paciente_id:
			where.append("paciente_id = %s"); params.append(paciente_id)
		if filtro:
			where.append("(paciente_nome ILIKE %s OR tipo_exame ILIKE %s OR codigo_autenticacao ILIKE %s)")
			q = f"%{filtro}%"; params.extend([q, q, q])
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT * FROM laudos_emitidos {where_sql} ORDER BY criado_em DESC, id DESC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_laudo_emitido(laudo_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = "SELECT * FROM laudos_emitidos WHERE id = %s"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (laudo_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def adicionar_versao_laudo(laudo_id: int, conteudo: str, editado_por: Optional[str] = None) -> bool:
	"""Cria nova versão do laudo (incrementa versão principal)."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("SELECT versao FROM laudos_emitidos WHERE id = %s", (laudo_id,))
			row = cur.fetchone()
			if not row:
				return False
			nova_versao = int(row["versao"]) + 1
			cur.execute("UPDATE laudos_emitidos SET versao = %s, conteudo = %s, atualizado_em = NOW() WHERE id = %s",
						(nova_versao, conteudo, laudo_id))
			cur.execute("""
			INSERT INTO laudo_versoes (laudo_id, versao, conteudo, editado_por)
			VALUES (%s, %s, %s, %s)
			""", (laudo_id, nova_versao, conteudo, editado_por))
			return True
	except Exception:
		return False


def listar_versoes_laudo(laudo_id: int) -> List[Dict[str, Any]]:
	try:
		query = """
		SELECT id, laudo_id, versao, conteudo, editado_por, criado_em
		FROM laudo_versoes WHERE laudo_id = %s ORDER BY versao DESC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (laudo_id,))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def verificar_autenticidade_laudo(codigo: str) -> Optional[Dict[str, Any]]:
	try:
		query = """
		SELECT id, paciente_nome, medico, tipo_exame, versao, codigo_autenticacao, criado_em, status
		FROM laudos_emitidos WHERE codigo_autenticacao = %s
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (codigo.strip(),))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def excluir_laudo_emitido(laudo_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM laudos_emitidos WHERE id = %s", (laudo_id,))
			return cur.rowcount > 0
	except Exception:
		return False


# ─────────────────────────────────────────────────────────────
# Financeiro / Lançamentos / Notas Fiscais
# ─────────────────────────────────────────────────────────────

def inserir_lancamento(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO lancamentos (
			tipo, categoria, descricao, valor, data, forma_pagamento, status,
			empresa_id, empresa_nome, convenio, observacoes
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados["tipo"], dados["categoria"], dados.get("descricao") or None,
			dados["valor"], dados["data"], dados.get("forma_pagamento") or None,
			dados.get("status") or "Pago", dados.get("empresa_id"),
			dados.get("empresa_nome") or None, dados.get("convenio") or None,
			dados.get("observacoes") or None,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_lancamentos(periodo_inicio: Optional[str] = None, periodo_fim: Optional[str] = None,
					   tipo: Optional[str] = None, categoria: Optional[str] = None,
					   limite: Optional[int] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if periodo_inicio:
			where.append("data >= %s"); params.append(periodo_inicio)
		if periodo_fim:
			where.append("data <= %s"); params.append(periodo_fim)
		if tipo:
			where.append("tipo = %s"); params.append(tipo)
		if categoria:
			where.append("categoria = %s"); params.append(categoria)
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT * FROM lancamentos {where_sql} ORDER BY data DESC, id DESC
		"""
		if limite:
			query += f" LIMIT {int(limite)}"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_lancamento(lanc_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = "SELECT * FROM lancamentos WHERE id = %s"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (lanc_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def atualizar_lancamento(lanc_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"tipo", "categoria", "descricao", "valor", "data", "forma_pagamento",
				   "status", "empresa_id", "empresa_nome", "convenio", "observacoes"}
		set_parts, params = [], []
		for k, v in dados.items():
			if k in allowed and v is not None:
				set_parts.append(f"{k} = %s"); params.append(v)
		if not set_parts:
			return False
		params.append(lanc_id)
		query = f"UPDATE lancamentos SET {', '.join(set_parts)} WHERE id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def excluir_lancamento(lanc_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM lancamentos WHERE id = %s", (lanc_id,))
			return cur.rowcount > 0
	except Exception:
		return False


def resumo_financeiro(periodo_inicio: Optional[str] = None, periodo_fim: Optional[str] = None) -> Dict[str, Any]:
	"""Resumo financeiro do período: receitas, despesas, resultado, por categoria e por forma de pagamento."""
	try:
		where, params = [], []
		if periodo_inicio:
			where.append("data >= %s"); params.append(periodo_inicio)
		if periodo_fim:
			where.append("data <= %s"); params.append(periodo_fim)
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(f"""
				SELECT tipo, COALESCE(SUM(valor),0) AS total, COUNT(*) AS qtd
				FROM lancamentos {where_sql} GROUP BY tipo
			""", tuple(params))
			por_tipo = {r["tipo"]: {"total": float(r["total"]), "qtd": r["qtd"]} for r in cur.fetchall()}
			cur.execute(f"""
				SELECT categoria, tipo, COALESCE(SUM(valor),0) AS total
				FROM lancamentos {where_sql} GROUP BY categoria, tipo ORDER BY total DESC
			""", tuple(params))
			por_categoria = [dict(r) for r in cur.fetchall()]
			cur.execute(f"""
				SELECT forma_pagamento, COALESCE(SUM(valor),0) AS total
				FROM lancamentos {where_sql} GROUP BY forma_pagamento ORDER BY total DESC
			""", tuple(params))
			por_pagamento = [dict(r) for r in cur.fetchall()]
			receitas = por_tipo.get("Receita", {}).get("total", 0)
			despesas = por_tipo.get("Despesa", {}).get("total", 0)
			return {
				"receitas": receitas,
				"despesas": despesas,
				"resultado": receitas - despesas,
				"por_tipo": por_tipo,
				"por_categoria": por_categoria,
				"por_pagamento": por_pagamento,
			}
	except Exception:
		return {"receitas": 0, "despesas": 0, "resultado": 0, "por_tipo": {}, "por_categoria": [], "por_pagamento": []}


def inserir_nota_fiscal(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO notas_fiscais (
			empresa_id, empresa_nome, numero, serie, tipo, data_emissao, valor,
			descricao, status, caminho_arquivo, observacoes
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("empresa_id"), dados.get("empresa_nome") or None,
			dados.get("numero") or None, dados.get("serie") or None,
			dados.get("tipo") or "NFSe", dados["data_emissao"], dados["valor"],
			dados.get("descricao") or None, dados.get("status") or "Emitida",
			dados.get("caminho_arquivo") or None, dados.get("observacoes") or None,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_notas_fiscais(filtro: Optional[str] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if filtro:
			where.append("(empresa_nome ILIKE %s OR numero ILIKE %s)")
			q = f"%{filtro}%"; params.extend([q, q])
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"SELECT * FROM notas_fiscais {where_sql} ORDER BY data_emissao DESC, id DESC"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def excluir_nota_fiscal(nota_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM notas_fiscais WHERE id = %s", (nota_id,))
			return cur.rowcount > 0
	except Exception:
		return False


# ─────────────────────────────────────────────────────────────
# LGPD / Consentimentos
# ─────────────────────────────────────────────────────────────

def registrar_consentimento(dados: Dict[str, Any]) -> Optional[int]:
	try:
		query = """
		INSERT INTO consentimentos (
			paciente_id, paciente_nome, tipo, descricao, assinado_em, validade,
			ip_origem, assentimento, documento_versao, registrado_por
		) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
		"""
		params = (
			dados.get("paciente_id"), dados.get("paciente_nome") or None,
			dados["tipo"], dados.get("descricao") or None,
			dados.get("assinado_em"), dados.get("validade"),
			dados.get("ip_origem") or None,
			True if dados.get("assentimento") else False,
			dados.get("documento_versao") or None,
			dados.get("registrado_por") or None,
		)
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return int(row["id"]) if row else None
	except Exception:
		return None


def listar_consentimentos(paciente_id: Optional[int] = None) -> List[Dict[str, Any]]:
	try:
		where, params = [], []
		if paciente_id:
			where.append("paciente_id = %s"); params.append(paciente_id)
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"SELECT * FROM consentimentos {where_sql} ORDER BY criado_em DESC, id DESC"
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def revogar_consentimento(cons_id: int) -> bool:
	"""Revoga (anula) um consentimento."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("UPDATE consentimentos SET assentimento = FALSE, tipo = tipo || ' (REVOGADO)' WHERE id = %s", (cons_id,))
			return cur.rowcount > 0
	except Exception:
		return False


def exportar_dados_paciente_lgpd(paciente_id: int) -> bytes:
	"""Gera JSON com todos os dados de um paciente (direito de portabilidade LGPD)."""
	try:
		base = {"paciente": None, "anamnese": None, "evolucoes": [], "atendimentos": [], "consentimentos": []}
		base["paciente"] = obter_paciente(paciente_id)
		base["anamnese"] = obter_anamnese(paciente_id)
		base["evolucoes"] = listar_evolucoes(paciente_id)
		base["consentimentos"] = listar_consentimentos(paciente_id)
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute("SELECT id, empresa, nome, modalidade, data, hora, status, observacoes FROM atendimentos WHERE nome = %s",
						(base["paciente"]["nome"] if base["paciente"] else "",))
			base["atendimentos"] = [dict(r) for r in cur.fetchall()]
		return json.dumps(base, indent=2, default=str).encode("utf-8")
	except Exception:
		return json.dumps({"erro": "não foi possível exportar"}).encode("utf-8")


def backup_completo() -> bytes:
	"""Gera backup JSON de todas as tabelas (versão melhorada de exportar_dados_seguranca)."""
	try:
		tables = ["empresas", "convenios", "faturamento_empresa", "pacientes", "anamnese",
				  "evolucoes", "agendamentos", "triagem", "prescricoes", "atestados",
				  "encaminhamentos", "laudos_emitidos", "lancamentos", "notas_fiscais",
				  "consentimentos", "atendimentos", "notas", "arquivos", "auditoria", "users"]
		backup = {"timestamp": datetime_agora_iso(), "tables": {}}
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			for table in tables:
				try:
					cur.execute(f"SELECT * FROM {table}")
					backup["tables"][table] = [dict(r) for r in cur.fetchall()]
				except Exception:
					backup["tables"][table] = []
		return json.dumps(backup, indent=2, default=str).encode("utf-8")
	except Exception:
		return json.dumps({"erro": "backup falhou"}).encode("utf-8")


def datetime_agora_iso() -> str:
	from datetime import datetime
	return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def _format_paciente(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
	if not row:
		return None
	return dict(row)


# ─────────────────────────────────────────────────────────────
# Pacientes / Prontuário
# ─────────────────────────────────────────────────────────────

def inserir_paciente(dados: Dict[str, Any]) -> Optional[int]:
	"""Insere um paciente. Retorna o id criado ou None em falha."""
	try:
		query = """
		INSERT INTO pacientes (
			nome, cpf, rg, data_nascimento, telefone, email, endereco, observacoes, ativo
		)
		VALUES (%(nome)s, %(cpf)s, %(rg)s, %(data_nascimento)s, %(telefone)s,
				%(email)s, %(endereco)s, %(observacoes)s, %(ativo)s)
		RETURNING id
		"""
		params = {
			"nome": dados.get("nome") or "",
			"cpf": dados.get("cpf") or None,
			"rg": dados.get("rg") or None,
			"data_nascimento": dados.get("data_nascimento"),
			"telefone": dados.get("telefone") or None,
			"email": dados.get("email") or None,
			"endereco": dados.get("endereco") or None,
			"observacoes": dados.get("observacoes") or None,
			"ativo": 1 if dados.get("ativo", True) else 0,
		}
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			paciente_id = int(row["id"]) if row else None
			if paciente_id:
				try:
					registrar_auditoria("CREATE", "pacientes", paciente_id, f"Paciente criado: {params['nome']}")
				except Exception:
					pass
			return paciente_id
	except Exception:
		return None


def listar_pacientes(filtro: Optional[str] = None, ativos_apenas: bool = False) -> List[Dict[str, Any]]:
	"""Lista pacientes com busca opcional por nome/CPF/telefone/email."""
	try:
		where = []
		params: List[Any] = []
		if filtro:
			q = f"%{filtro.strip()}%"
			where.append(
				"(nome ILIKE %s OR cpf ILIKE %s OR telefone ILIKE %s OR email ILIKE %s)"
			)
			params.extend([q, q, q, q])
		if ativos_apenas:
			where.append("ativo = 1")
		where_sql = f"WHERE {' AND '.join(where)}" if where else ""
		query = f"""
		SELECT id, nome, cpf, rg, data_nascimento, telefone, email, endereco, observacoes, ativo, criado_em
		FROM pacientes
		{where_sql}
		ORDER BY nome ASC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return [_format_paciente(r) for r in cur.fetchall()]
	except Exception:
		return []


def obter_paciente(paciente_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = """
		SELECT id, nome, cpf, rg, data_nascimento, telefone, email, endereco, observacoes,
			   ativo, foto_b64, foto_mime, criado_em
		FROM pacientes WHERE id = %s
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (paciente_id,))
			return _format_paciente(cur.fetchone())
	except Exception:
		return None


def atualizar_paciente(paciente_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"nome", "cpf", "rg", "data_nascimento", "telefone", "email",
				   "endereco", "observacoes", "ativo", "foto_b64", "foto_mime"}
		set_parts = []
		params: List[Any] = []
		for key, val in dados.items():
			if key in allowed and val is not None:
				set_parts.append(f"{key} = %s")
				params.append(val)
		if not set_parts:
			return False
		set_parts.append("atualizado_em = NOW()")
		params.append(paciente_id)
		query = f"UPDATE pacientes SET {', '.join(set_parts)} WHERE id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def excluir_paciente(paciente_id: int) -> bool:
	"""Exclui um paciente (registros de anamnese/evoluções são removidos via CASCADE)."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM pacientes WHERE id = %s", (paciente_id,))
			ok = cur.rowcount > 0
			if ok:
				try:
					registrar_auditoria("DELETE", "pacientes", paciente_id, "Paciente excluído")
				except Exception:
					pass
			return ok
	except Exception:
		return False


def buscar_pacientes_duplicados(nome: str, cpf: Optional[str] = None) -> List[Dict[str, Any]]:
	"""Detecta possíveis cadastros duplicados por nome (e CPF, se informado)."""
	try:
		nome_clean = (nome or "").strip().lower()
		if not nome_clean:
			return []
		if cpf and cpf.strip():
			query = """
			SELECT id, nome, cpf, telefone, ativo FROM pacientes
			WHERE LOWER(nome) = %s OR (cpf IS NOT NULL AND cpf = %s)
			"""
			params = (nome_clean, cpf.strip())
		else:
			query = "SELECT id, nome, cpf, telefone, ativo FROM pacientes WHERE LOWER(nome) = %s"
			params = (nome_clean,)
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			return [_format_paciente(r) for r in cur.fetchall()]
	except Exception:
		return []


def salvar_foto_paciente(paciente_id: int, foto_b64: str, mime: str) -> bool:
	return atualizar_paciente(paciente_id, {"foto_b64": foto_b64, "foto_mime": mime})


# ── Anamnese ────────────────────────────────────────────────

def salvar_anamnese(paciente_id: int, dados: Dict[str, Any]) -> bool:
	try:
		query = """
		INSERT INTO anamnese (
			paciente_id, queixa_principal, historico_doenca, historico_familiar,
			medicamentos, alergias, habitos, observacoes
		)
		VALUES (%(paciente_id)s, %(queixa_principal)s, %(historico_doenca)s,
				%(historico_familiar)s, %(medicamentos)s, %(alergias)s, %(habitos)s, %(observacoes)s)
		ON CONFLICT (id) DO NOTHING
		RETURNING id
		"""
		params = {
			"paciente_id": paciente_id,
			"queixa_principal": dados.get("queixa_principal") or None,
			"historico_doenca": dados.get("historico_doenca") or None,
			"historico_familiar": dados.get("historico_familiar") or None,
			"medicamentos": dados.get("medicamentos") or None,
			"alergias": dados.get("alergias") or None,
			"habitos": dados.get("habitos") or None,
			"observacoes": dados.get("observacoes") or None,
		}
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, params)
			row = cur.fetchone()
			return bool(row and row["id"])
	except Exception:
		return False


def obter_anamnese(paciente_id: int) -> Optional[Dict[str, Any]]:
	try:
		query = """
		SELECT id, paciente_id, queixa_principal, historico_doenca, historico_familiar,
			   medicamentos, alergias, habitos, observacoes, criado_em, atualizado_em
		FROM anamnese WHERE paciente_id = %s
		ORDER BY id DESC LIMIT 1
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (paciente_id,))
			row = cur.fetchone()
			return dict(row) if row else None
	except Exception:
		return None


def atualizar_anamnese(paciente_id: int, dados: Dict[str, Any]) -> bool:
	try:
		allowed = {"queixa_principal", "historico_doenca", "historico_familiar",
				   "medicamentos", "alergias", "habitos", "observacoes"}
		set_parts = []
		params: List[Any] = []
		for key, val in dados.items():
			if key in allowed and val is not None:
				set_parts.append(f"{key} = %s")
				params.append(val)
		if not set_parts:
			return False
		set_parts.append("atualizado_em = NOW()")
		params.append(paciente_id)
		query = f"UPDATE anamnese SET {', '.join(set_parts)} WHERE paciente_id = %s"
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, tuple(params))
			return cur.rowcount > 0
	except Exception:
		return False


def salvar_ou_atualizar_anamnese(paciente_id: int, dados: Dict[str, Any]) -> bool:
	"""Cria a anamnese se não existir; caso contrário, atualiza."""
	if obter_anamnese(paciente_id):
		return atualizar_anamnese(paciente_id, dados)
	return salvar_anamnese(paciente_id, dados)


# ── Evoluções clínicas ──────────────────────────────────────

def inserir_evolucao(paciente_id: int, data_ev: Any, texto: str) -> bool:
	try:
		query = """
		INSERT INTO evolucoes (paciente_id, data, texto)
		VALUES (%s, %s, %s)
		"""
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (paciente_id, data_ev, texto))
			return cur.rowcount > 0
	except Exception:
		return False


def listar_evolucoes(paciente_id: int, limite: int = 200) -> List[Dict[str, Any]]:
	try:
		query = """
		SELECT id, paciente_id, data, texto, criado_em
		FROM evolucoes WHERE paciente_id = %s
		ORDER BY data DESC, id DESC
		LIMIT %s
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (paciente_id, limite))
			return [dict(r) for r in cur.fetchall()]
	except Exception:
		return []


def excluir_evolucao(evolucao_id: int) -> bool:
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM evolucoes WHERE id = %s", (evolucao_id,))
			return cur.rowcount > 0
	except Exception:
		return False


def listar_atendimentos_do_paciente(paciente_id: int) -> List[Tuple]:
	"""Retorna os atendimentos vinculados a um paciente pelo nome."""
	try:
		pac = obter_paciente(paciente_id)
		if not pac:
			return []
		nome = (pac.get("nome") or "").strip()
		if not nome:
			return []
		query = """
		SELECT id, empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, status, observacoes
		FROM atendimentos
		WHERE LOWER(nome) = %s
		ORDER BY data DESC, hora DESC
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (nome.lower(),))
			return [tuple(r[col] for col in ("id", "empresa", "nome", "modalidade", "data", "hora", "laudo_pdf", "avaliacao_pdf", "status", "observacoes")) for r in cur.fetchall()]
	except Exception:
		return []


def contar_aniversariantes(dia: int, mes: int) -> int:
	"""Conta pacientes que fazem aniversário em determinada data."""
	try:
		query = """
		SELECT COUNT(*) AS total FROM pacientes
		WHERE ativo = 1 AND data_nascimento IS NOT NULL
		  AND EXTRACT(DAY FROM data_nascimento) = %s
		  AND EXTRACT(MONTH FROM data_nascimento) = %s
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (dia, mes))
			row = cur.fetchone()
			return int(row["total"]) if row else 0
	except Exception:
		return 0


def listar_aniversariantes(dia: int, mes: int) -> List[Dict[str, Any]]:
	try:
		query = """
		SELECT id, nome, telefone, data_nascimento FROM pacientes
		WHERE ativo = 1 AND data_nascimento IS NOT NULL
		  AND EXTRACT(DAY FROM data_nascimento) = %s
		  AND EXTRACT(MONTH FROM data_nascimento) = %s
		ORDER BY nome
		"""
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(query, (dia, mes))
			return [_format_paciente(r) for r in cur.fetchall()]
	except Exception:
		return []


def save_preference(key: str, value: str) -> bool:
	"""Salva ou atualiza uma preferência do usuário no banco (ex: foto de perfil em base64)."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("""
				INSERT INTO user_preferences (pref_key, pref_value, updated_at)
				VALUES (%s, %s, NOW())
				ON CONFLICT (pref_key)
				DO UPDATE SET pref_value = EXCLUDED.pref_value, updated_at = NOW()
			""", (str(key)[:100], value))
		return True
	except Exception:
		return False


def get_preference(key: str, default: Optional[str] = None) -> Optional[str]:
	"""Recupera uma preferência do usuário pelo key. Retorna default se não existir."""
	try:
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute(
				"SELECT pref_value FROM user_preferences WHERE pref_key = %s",
				(str(key)[:100],)
			)
			row = cur.fetchone()
			return row["pref_value"] if row else default
	except Exception:
		return default


def delete_preference(key: str) -> bool:
	"""Remove uma preferência do banco."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM user_preferences WHERE pref_key = %s", (str(key)[:100],))
			return cur.rowcount > 0
	except Exception:
		return False


def salvar_google_tokens(token_json: str) -> bool:
	"""Persiste o JSON de tokens OAuth do Google (refresh token)."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(
				"""
				INSERT INTO google_oauth (id, token_json) VALUES (1, %s)
				ON CONFLICT (id) DO UPDATE SET
					token_json = EXCLUDED.token_json,
					updated_at = CURRENT_TIMESTAMP
				""",
				(token_json,),
			)
		return True
	except Exception:
		return False


def obter_google_tokens() -> Optional[str]:
	"""Recupera o JSON de tokens OAuth do Google, ou None."""
	try:
		with _connection_scope(commit=False) as conn:
			cur = _get_cursor(conn)
			cur.execute("SELECT token_json FROM google_oauth WHERE id = 1")
			row = cur.fetchone()
			return row["token_json"] if row else None
	except Exception:
		return None


def limpar_google_tokens() -> bool:
	"""Remove os tokens OAuth do Google do banco."""
	try:
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute("DELETE FROM google_oauth WHERE id = 1")
			return cur.rowcount > 0
	except Exception:
		return False



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
	# Sanitização Sênior: strip() e limites de tamanho no DB para segurança extra
	params = (
		str(empresa).strip()[:255], 
		str(nome).strip()[:255], 
		str(modalidade).strip()[:100], 
		data,  # Objeto date (PSQL DATE)
		hora,  # Objeto time (PSQL TIME)
		laudo_pdf, 
		avaliacao_pdf, 
		str(observacoes or "").strip(), 
		str(status or "").strip()[:50]
	)
	with _connection_scope() as conn:
		cur = _get_cursor(conn)
		cur.execute(query, params)
		result = cur.fetchone()
		new_id = int(result["id"]) if result else 0
		try:
			# LGPD: Registrar apenas ID, não dados sensíveis como {nome} ou {empresa}
			registrar_auditoria("CREATE", "atendimentos", new_id, f"Novo registro criado (ID {new_id})")
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
				# LGPD: Apenas status, sem PII
				registrar_auditoria("STATUS", "atendimentos", atendimento_id, f"Status alterado para: {status}")
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
	"""Salva um arquivo (PDF) no banco e retorna o id gerado.
	Limita o tamanho no backend para 50MB para proteção de memória do banco.
	"""
	# Limite de segurança: 50MB (50 * 1024 * 1024)
	MAX_SIZE_BYTES = 52428800 
	if len(content) > MAX_SIZE_BYTES:
		raise ValueError(f"Arquivo '{filename}' excede o limite de segurança de 50MB.")

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
		# Se o usuário não for passado, tenta pegar do session_state do Streamlit
		if not usuario and st and hasattr(st, "session_state"):
			usuario = st.session_state.get("user_name", "system")
			
		with _connection_scope() as conn:
			cur = _get_cursor(conn)
			cur.execute(
				"INSERT INTO auditoria (acao, entidade, entidade_id, detalhes, usuario) VALUES (%s, %s, %s, %s, %s)",
				(acao, entidade, entidade_id, detalhes, usuario),
			)
	except Exception:
		pass


def exportar_dados_seguranca() -> bytes:
	"""Gera um backup completo do banco em formato JSON (mais robusto para restauração)."""
	backup_data = {
		"timestamp": str(Path(__file__).stat().st_mtime), # Simplificado
		"tables": {}
	}
	
	tabels_to_backup = ["atendimentos", "notas", "arquivos", "auditoria"]
	
	with _connection_scope(commit=False) as conn:
		cur = _get_cursor(conn)
		for table in tabels_to_backup:
			try:
				cur.execute(f"SELECT * FROM {table}")
				rows = cur.fetchall()
				# Converter rows (RealDictRow) para lista de dicts puros
				backup_data["tables"][table] = [dict(r) for r in rows]
			except Exception:
				backup_data["tables"][table] = []
				
	# Retorna os bytes do JSON (pode ser zipado depois se crescer muito)
	return json.dumps(backup_data, indent=2, default=str).encode("utf-8")


def listar_auditoria(limit: int = 100) -> List[Dict[str, Any]]:
	"""Lista últimas entradas de auditoria."""
	limit = max(1, min(int(limit or 100), 1000))
	with _connection_scope(commit=False) as conn:
		cur = _get_cursor(conn)
		cur.execute("SELECT id, acao, entidade, entidade_id, detalhes, usuario, criado_em FROM auditoria ORDER BY id DESC LIMIT %s", (limit,))
		rows = cur.fetchall()
		return [dict(r) for r in rows]



# As credenciais admin devem ser configuradas via variáveis de ambiente (.env) ou Secrets do Streamlit Cloud.
# Não armazene senhas diretamente no código fonte.
def _get_admin_config(key: str, default: Optional[str] = None) -> Optional[str]:
	try:
		if st and hasattr(st, "secrets") and key in st.secrets:
			return st.secrets[key]
	except Exception:
		pass
	return os.getenv(key, default)

APP_ADMIN_USER = _get_admin_config("APP_ADMIN_USER")
APP_ADMIN_PASS = _get_admin_config("APP_ADMIN_PASS")
APP_REQUIRE_AUTH = (_get_admin_config("APP_REQUIRE_AUTH", "true") or "true").lower() == "true"