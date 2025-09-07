"""
JULIANA - Gestão Clínica (Banco SQLite)
"""
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from contextlib import contextmanager

DATABASE_NAME = "gestao_clinica.db"
DATABASE_PATH = os.path.join(os.path.dirname(__file__), DATABASE_NAME)

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> bool:
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
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
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_at_data ON atendimentos(data)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_at_empresa ON atendimentos(empresa)"
            )
            # Tabela de notas (bloco de notas)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS notas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    tags TEXT,
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_notas_titulo ON notas(titulo)"
            )
            # Garantir coluna 'favorita' (migração leve)
            try:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(notas)").fetchall()]
                if 'favorita' not in cols:
                    cur.execute("ALTER TABLE notas ADD COLUMN favorita INTEGER DEFAULT 0")
            except Exception:
                pass
            # Histórico de versões das notas
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS notas_historico (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nota_id INTEGER NOT NULL,
                    titulo TEXT,
                    conteudo TEXT,
                    tags TEXT,
                    favorita INTEGER,
                    data_versao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        return True
    except Exception:
        return False

def inserir_atendimento(empresa: str, nome: str, modalidade: str, data: str, hora: str,
                         laudo_pdf: Optional[str] = None, avaliacao_pdf: Optional[str] = None,
                         observacoes: Optional[str] = None) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO atendimentos (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes),
            )
        return True
    except Exception:
        return False

def listar_atendimentos() -> List[Tuple]:
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, status, observacoes FROM atendimentos ORDER BY data DESC, hora DESC"
            ).fetchall()
            return [tuple(r) for r in rows]
    except Exception:
        return []

def atualizar_atendimento(id_atendimento: int, **campos) -> bool:
    if not campos:
        return False
    allowed = ["empresa", "nome", "modalidade", "data", "hora", "laudo_pdf", "avaliacao_pdf", "status", "observacoes"]
    sets = []
    vals = []
    for k, v in campos.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    vals.append(id_atendimento)
    try:
        with get_db_connection() as conn:
            conn.execute(
                f"UPDATE atendimentos SET {', '.join(sets)}, data_atualizacao = CURRENT_TIMESTAMP WHERE id = ?",
                vals,
            )
        return True
    except Exception:
        return False

def excluir_atendimento(id_atendimento: int) -> bool:
    try:
        with get_db_connection() as conn:
            cur = conn.execute("DELETE FROM atendimentos WHERE id = ?", (id_atendimento,))
            return cur.rowcount > 0
    except Exception:
        return False

def obter_estatisticas() -> Dict:
    stats: Dict = {}
    try:
        with get_db_connection() as conn:
            stats["total_atendimentos"] = conn.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0]
            stats["total_empresas"] = conn.execute("SELECT COUNT(DISTINCT empresa) FROM atendimentos").fetchone()[0]
            stats["laudos_enviados"] = conn.execute("SELECT COUNT(*) FROM atendimentos WHERE laudo_pdf IS NOT NULL").fetchone()[0]
            stats["avaliacoes_enviadas"] = conn.execute("SELECT COUNT(*) FROM atendimentos WHERE avaliacao_pdf IS NOT NULL").fetchone()[0]
            rows = conn.execute("SELECT modalidade, COUNT(*) FROM atendimentos GROUP BY modalidade ORDER BY 2 DESC").fetchall()
            stats["modalidades"] = {r[0]: r[1] for r in rows}

        # Remover campos vazios ou desnecessários
        stats = {k: v for k, v in stats.items() if v}
    except Exception:
        pass
    return stats

def verificar_conexao() -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1")
            return True
    except Exception:
        return False

# ===== CRUD Notas =====
def inserir_nota(titulo: str, conteudo: str, tags: Optional[str] = None, favorita: bool = False) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO notas (titulo, conteudo, tags, favorita)
                VALUES (?, ?, ?, ?)
                """,
                (titulo, conteudo, tags, 1 if favorita else 0),
            )
        return True
    except Exception:
        return False

def listar_notas() -> List[Tuple]:
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, titulo, conteudo, tags, data_criacao, data_atualizacao, COALESCE(favorita,0) as favorita FROM notas ORDER BY favorita DESC, data_atualizacao DESC, id DESC"
            ).fetchall()
            return [tuple(r) for r in rows]
    except Exception:
        return []

def atualizar_nota(id_nota: int, **campos) -> bool:
    if not campos:
        return False
    allowed = ["titulo", "conteudo", "tags", "favorita"]
    sets = []
    vals = []
    for k, v in campos.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    vals.append(id_nota)
    try:
        with get_db_connection() as conn:
            conn.execute(
                f"UPDATE notas SET {', '.join(sets)}, data_atualizacao = CURRENT_TIMESTAMP WHERE id = ?",
                vals,
            )
        return True
    except Exception:
        return False

def excluir_nota(id_nota: int) -> bool:
    try:
        with get_db_connection() as conn:
            cur = conn.execute("DELETE FROM notas WHERE id = ?", (id_nota,))
            return cur.rowcount > 0
    except Exception:
        return False

def inserir_historico_nota(nota_id: int, titulo: str, conteudo: str, tags: Optional[str], favorita: int) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO notas_historico (nota_id, titulo, conteudo, tags, favorita)
                VALUES (?, ?, ?, ?, ?)
                """,
                (nota_id, titulo, conteudo, tags, favorita),
            )
        return True
    except Exception:
        return False

def listar_historico_nota(nota_id: int) -> List[Tuple]:
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, nota_id, titulo, conteudo, tags, favorita, data_versao FROM notas_historico WHERE nota_id = ? ORDER BY data_versao DESC, id DESC",
                (nota_id,),
            ).fetchall()
            return [tuple(r) for r in rows]
    except Exception:
        return []
