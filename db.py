"""
JULIANA - Gestão Clínica (Banco SQLite simplificado)

Este módulo fornece um DatabaseManager leve para uso local com SQLite.
"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Any, Optional


class DatabaseManager:
    def __init__(self, db_path: str = "juliana_clinica.db"):
        self.db_path = db_path
        self._ensure_dir()
        self.init_database()

    def _ensure_dir(self):
        base = os.path.dirname(self.db_path)
        if base and not os.path.exists(base):
            os.makedirs(base, exist_ok=True)

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                tags TEXT,
                favorita BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_atendimentos_data ON atendimentos(data)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_atendimentos_empresa ON atendimentos(empresa)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notas_titulo ON notas(titulo)")
        conn.commit()
        conn.close()

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()
        return rows

    def execute_update(self, query: str, params: tuple = ()) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print("DB ERROR:", e)
            return False

    def get_all_appointments(self) -> List[Dict[str, Any]]:
        return self.execute_query("SELECT * FROM atendimentos ORDER BY data DESC, hora DESC")

    def add_appointment(self, data) -> bool:
        query = """
            INSERT INTO atendimentos (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, status, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (data.empresa, data.nome, data.modalidade, data.data, data.hora, data.laudo_pdf, data.avaliacao_pdf, data.status, data.observacoes)
        return self.execute_update(query, params)

    def update_appointment(self, apt_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        kwargs['updated_at'] = datetime.now().isoformat()
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        params = tuple(list(kwargs.values()) + [apt_id])
        query = f"UPDATE atendimentos SET {set_clause} WHERE id = ?"
        return self.execute_update(query, params)

    def delete_appointment(self, apt_id: int) -> bool:
        return self.execute_update("DELETE FROM atendimentos WHERE id = ?", (apt_id,))

    def get_all_notes(self) -> List[Dict[str, Any]]:
        return self.execute_query("SELECT * FROM notas ORDER BY created_at DESC")

    def add_note(self, data) -> bool:
        query = "INSERT INTO notas (titulo, conteudo, tags, favorita) VALUES (?, ?, ?, ?)"
        params = (data.titulo, data.conteudo, data.tags, int(bool(data.favorita)))
        return self.execute_update(query, params)

    def delete_note(self, note_id: int) -> bool:
        return self.execute_update("DELETE FROM notas WHERE id = ?", (note_id,))

    def get_stats(self) -> Dict[str, Any]:
        stats = {}
        r = self.execute_query("SELECT COUNT(*) as total FROM atendimentos")
        stats['total_atendimentos'] = r[0]['total'] if r else 0
        r = self.execute_query("SELECT COUNT(DISTINCT empresa) as total FROM atendimentos")
        stats['total_empresas'] = r[0]['total'] if r else 0
        r = self.execute_query("SELECT COUNT(*) as total FROM atendimentos WHERE laudo_pdf IS NULL OR laudo_pdf = ''")
        stats['pendentes_laudo'] = r[0]['total'] if r else 0
        r = self.execute_query("SELECT COUNT(*) as total FROM atendimentos WHERE avaliacao_pdf IS NULL OR avaliacao_pdf = ''")
        stats['pendentes_avaliacao'] = r[0]['total'] if r else 0
        r = self.execute_query("SELECT COUNT(*) as total FROM notas")
        stats['total_notas'] = r[0]['total'] if r else 0
        r = self.execute_query("SELECT COUNT(*) as total FROM notas WHERE favorita = 1")
        stats['notas_favoritas'] = r[0]['total'] if r else 0
        return stats


_instance: Optional[DatabaseManager] = None


def get_database(db_path: str = "juliana_clinica.db") -> DatabaseManager:
    global _instance
    if _instance is None:
        _instance = DatabaseManager(db_path)
    return _instance


# --- Compat layer: funções legadas esperadas por db_unified.py e testes ---
def init_db() -> bool:
    """Compat: inicializa o DB. Retorna True em sucesso."""
    try:
        get_database().init_database()
        return True
    except Exception:
        return False


def verificar_conexao() -> bool:
    try:
        # tenta abrir e executar um select simples
        db = get_database()
        db.execute_query("SELECT 1")
        return True
    except Exception:
        return False


def inserir_atendimento(empresa: str, nome: str, modalidade: str, data: str, hora: str,
                         laudo_pdf: Optional[str] = None, avaliacao_pdf: Optional[str] = None,
                         observacoes: Optional[str] = None) -> bool:
    from types import SimpleNamespace
    ap = SimpleNamespace(empresa=empresa, nome=nome, modalidade=modalidade, data=data, hora=hora,
                         laudo_pdf=laudo_pdf, avaliacao_pdf=avaliacao_pdf, status='Agendado', observacoes=observacoes)
    return get_database().add_appointment(ap)


def listar_atendimentos() -> List[tuple]:
    rows = get_database().get_all_appointments()
    # converter dicts para tuplas de forma compatível com código legado
    if not rows:
        return []
    cols = sorted(rows[0].keys())
    result = []
    for r in rows:
        result.append(tuple(r.get(c) for c in cols))
    return result


def atualizar_atendimento(id_atendimento: int, **campos) -> bool:
    return get_database().update_appointment(id_atendimento, **campos)


def excluir_atendimento(id_atendimento: int) -> bool:
    return get_database().delete_appointment(id_atendimento)


def obter_estatisticas() -> Dict[str, Any]:
    return get_database().get_stats()


# ===== Notas (compat) =====
def inserir_nota(titulo: str, conteudo: str, tags: Optional[str] = None, favorita: bool = False) -> bool:
    from types import SimpleNamespace
    n = SimpleNamespace(titulo=titulo, conteudo=conteudo, tags=tags, favorita=favorita)
    return get_database().add_note(n)


def listar_notas() -> List[tuple]:
    rows = get_database().get_all_notes()
    if not rows:
        return []
    cols = sorted(rows[0].keys())
    result = []
    for r in rows:
        result.append(tuple(r.get(c) for c in cols))
    return result


def atualizar_nota(id_nota: int, **campos) -> bool:
    # campos: titulo, conteudo, tags, favorita
    return get_database().execute_update(
        f"UPDATE notas SET {', '.join([f'{k} = ?' for k in campos.keys()])}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        tuple(list(campos.values()) + [id_nota])
    )


def excluir_nota(id_nota: int) -> bool:
    return get_database().delete_note(id_nota)


def inserir_historico_nota(nota_id: int, titulo: str, conteudo: str, tags: Optional[str], favorita: int) -> bool:
    # Implementação simples: inserir na tabela notas_historico se existir
    try:
        query = "INSERT INTO notas_historico (nota_id, titulo, conteudo, tags, favorita) VALUES (?, ?, ?, ?, ?)"
        return get_database().execute_update(query, (nota_id, titulo, conteudo, tags, favorita))
    except Exception:
        return False


def listar_historico_nota(nota_id: int) -> List[tuple]:
    try:
        rows = get_database().execute_query("SELECT id, nota_id, titulo, conteudo, tags, favorita, data_versao FROM notas_historico WHERE nota_id = ? ORDER BY data_versao DESC, id DESC", (nota_id,))
        if not rows:
            return []
        cols = sorted(rows[0].keys())
        result = []
        for r in rows:
            result.append(tuple(r.get(c) for c in cols))
        return result
    except Exception:
        return []

