"""
Camada unificada de acesso a dados.
- Usa PostgreSQL se DATABASE_URL estiver definido e válido.
- Caso contrário, recorre ao SQLite via módulo original `db`.
Mantém a mesma API utilizada em `app.py` para não quebrar o fluxo.
"""
from __future__ import annotations
import os
from typing import List, Tuple, Dict, Optional

# Carrega .env (se existir) para permitir DATABASE_URL sem alterar app principal
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

USE_PG = False
_DB_URL = os.getenv("DATABASE_URL", "").strip()

_pg_conn = None

# Tenta carregar psycopg2 se URL indicar postgres
if _DB_URL.lower().startswith("postgres://") or _DB_URL.lower().startswith("postgresql://"):
    try:
        import psycopg2  # type: ignore
        USE_PG = True
    except Exception:
        USE_PG = False

# Importa sempre o módulo SQLite como fallback
import db as sqlite_db  # type: ignore

# ---------------- PostgreSQL Helpers ----------------
def _pg_connect():
    global _pg_conn
    if _pg_conn is not None:
        try:
            _pg_conn.cursor().execute("SELECT 1")
            return _pg_conn
        except Exception:
            _pg_conn = None
    if not _DB_URL:
        return None
    try:
        _pg_conn = psycopg2.connect(_DB_URL, connect_timeout=10)
        _pg_conn.autocommit = True
        return _pg_conn
    except Exception:
        return None

_PG_TABLES_CREATED = False

def _pg_init_schema():
    global _PG_TABLES_CREATED
    if _PG_TABLES_CREATED:
        return
    conn = _pg_connect()
    if not conn:
        return
    try:
        cur = conn.cursor()
        # Usa DATE e TIME nativos quando em Postgres
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS atendimentos (
                id SERIAL PRIMARY KEY,
                empresa TEXT NOT NULL,
                nome TEXT NOT NULL,
                modalidade TEXT NOT NULL,
                data DATE NOT NULL,
                hora TIME NOT NULL,
                laudo_pdf TEXT,
                avaliacao_pdf TEXT,
                status TEXT DEFAULT 'Agendado',
                observacoes TEXT,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_at_data ON atendimentos(data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_at_empresa ON atendimentos(empresa)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notas (
                id SERIAL PRIMARY KEY,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                tags TEXT,
                favorita INT DEFAULT 0,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_notas_titulo ON notas(titulo)")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notas_historico (
                id SERIAL PRIMARY KEY,
                nota_id INT NOT NULL,
                titulo TEXT,
                conteudo TEXT,
                tags TEXT,
                favorita INT,
                data_versao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Garantir FK suave (tenta adicionar; ignora erro se já existir)
        try:
            cur.execute("ALTER TABLE notas_historico ADD CONSTRAINT fk_nota FOREIGN KEY (nota_id) REFERENCES notas(id) ON DELETE CASCADE")
        except Exception:
            pass
        _PG_TABLES_CREATED = True
    except Exception:
        pass

if USE_PG:
    _pg_init_schema()

# ---------------- API Unificada ----------------

def init_db() -> bool:
    """Mantém compatibilidade com chamadas existentes em app.py.
    Para Postgres apenas garante que o schema foi inicializado;
    para SQLite delega para o módulo original.
    """
    if USE_PG:
        try:
            _pg_init_schema()
            # Se chegou aqui sem exceção consideramos sucesso
            return True
        except Exception:
            return False
    # Fallback / modo SQLite
    try:
        return bool(getattr(sqlite_db, "init_db")())
    except Exception:
        return False

def verificar_conexao() -> bool:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            return True
        except Exception:
            return False
    else:
        return sqlite_db.verificar_conexao()

# ---- Atendimentos ----

def inserir_atendimento(empresa: str, nome: str, modalidade: str, data: str, hora: str,
                        laudo_pdf: Optional[str] = None, avaliacao_pdf: Optional[str] = None,
                        observacoes: Optional[str] = None) -> bool:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO atendimentos (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes)
            )
            return True
        except Exception:
            return False
    return sqlite_db.inserir_atendimento(empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes)

def listar_atendimentos() -> List[Tuple]:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return []
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, empresa, nome, modalidade, TO_CHAR(data,'YYYY-MM-DD') as data, TO_CHAR(hora,'HH24:MI') as hora, laudo_pdf, avaliacao_pdf, status, observacoes FROM atendimentos ORDER BY data DESC, hora DESC")
            rows = cur.fetchall()
            return list(rows)
        except Exception:
            return []
    return sqlite_db.listar_atendimentos()

def atualizar_atendimento(id_atendimento: int, **campos) -> bool:
    if USE_PG:
        allowed = ["empresa", "nome", "modalidade", "data", "hora", "laudo_pdf", "avaliacao_pdf", "status", "observacoes"]
        sets = []
        vals = []
        for k, v in campos.items():
            if k in allowed:
                sets.append(f"{k}=%s")
                vals.append(v)
        if not sets:
            return False
        vals.append(id_atendimento)
        conn = _pg_connect()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE atendimentos SET {', '.join(sets)}, data_atualizacao=CURRENT_TIMESTAMP WHERE id=%s", vals)
            return True
        except Exception:
            return False
    return sqlite_db.atualizar_atendimento(id_atendimento, **campos)

def excluir_atendimento(id_atendimento: int) -> bool:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM atendimentos WHERE id=%s", (id_atendimento,))
            return cur.rowcount > 0
        except Exception:
            return False
    return sqlite_db.excluir_atendimento(id_atendimento)

def obter_estatisticas() -> Dict:
    if USE_PG:
        stats: Dict = {}
        conn = _pg_connect()
        if not conn:
            return stats
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM atendimentos")
            stats["total_atendimentos"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT empresa) FROM atendimentos")
            stats["total_empresas"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM atendimentos WHERE laudo_pdf IS NOT NULL")
            stats["laudos_enviados"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM atendimentos WHERE avaliacao_pdf IS NOT NULL")
            stats["avaliacoes_enviadas"] = cur.fetchone()[0]
            cur.execute("SELECT modalidade, COUNT(*) FROM atendimentos GROUP BY modalidade ORDER BY 2 DESC")
            stats["modalidades"] = {r[0]: r[1] for r in cur.fetchall()}
            return {k: v for k, v in stats.items() if v}
        except Exception:
            return {}
    return sqlite_db.obter_estatisticas()

# ---- Utilidades adicionais ----

def get_backend_info() -> Dict[str, str]:
    """Retorna metadados do backend atual para exibição/diagnóstico."""
    if USE_PG:
        return {"engine": "Postgres", "url_present": "yes" if bool(_DB_URL) else "no"}
    return {"engine": "SQLite", "url_present": "no"}

# ---- Notas ----

def inserir_nota(titulo: str, conteudo: str, tags: Optional[str] = None, favorita: bool = False) -> bool:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO notas (titulo, conteudo, tags, favorita) VALUES (%s,%s,%s,%s)",
                (titulo, conteudo, tags, 1 if favorita else 0)
            )
            return True
        except Exception:
            return False
    return sqlite_db.inserir_nota(titulo, conteudo, tags, favorita)

def listar_notas() -> List[Tuple]:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return []
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, titulo, conteudo, tags, data_criacao, data_atualizacao, COALESCE(favorita,0) as favorita FROM notas ORDER BY favorita DESC, data_atualizacao DESC, id DESC")
            return cur.fetchall()
        except Exception:
            return []
    return sqlite_db.listar_notas()

def atualizar_nota(id_nota: int, **campos) -> bool:
    if USE_PG:
        allowed = ["titulo", "conteudo", "tags", "favorita"]
        sets = []
        vals = []
        for k, v in campos.items():
            if k in allowed:
                sets.append(f"{k}=%s")
                vals.append(v)
        if not sets:
            return False
        vals.append(id_nota)
        conn = _pg_connect()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute(f"UPDATE notas SET {', '.join(sets)}, data_atualizacao=CURRENT_TIMESTAMP WHERE id=%s", vals)
            return True
        except Exception:
            return False
    return sqlite_db.atualizar_nota(id_nota, **campos)

def excluir_nota(id_nota: int) -> bool:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM notas WHERE id=%s", (id_nota,))
            return cur.rowcount > 0
        except Exception:
            return False
    return sqlite_db.excluir_nota(id_nota)

def inserir_historico_nota(nota_id: int, titulo: str, conteudo: str, tags: Optional[str], favorita: int) -> bool:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO notas_historico (nota_id, titulo, conteudo, tags, favorita) VALUES (%s,%s,%s,%s,%s)",
                (nota_id, titulo, conteudo, tags, favorita)
            )
            return True
        except Exception:
            return False
    return sqlite_db.inserir_historico_nota(nota_id, titulo, conteudo, tags, favorita)

def listar_historico_nota(nota_id: int) -> List[Tuple]:
    if USE_PG:
        conn = _pg_connect()
        if not conn:
            return []
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, nota_id, titulo, conteudo, tags, favorita, data_versao FROM notas_historico WHERE nota_id=%s ORDER BY data_versao DESC, id DESC", (nota_id,))
            return cur.fetchall()
        except Exception:
            return []
    return sqlite_db.listar_historico_nota(nota_id)

