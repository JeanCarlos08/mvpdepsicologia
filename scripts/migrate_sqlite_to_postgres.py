"""Script de migração de dados de SQLite para Postgres (Neon).
Uso:
  1. Configure .env com DATABASE_URL apontando para Postgres.
  2. Execute: python scripts/migrate_sqlite_to_postgres.py
O script:
  - Cria tabelas no Postgres (se não existirem)
  - Copia dados das tabelas atendimentos, notas, notas_historico
  - Evita duplicações simples verificando IDs existentes
"""
from __future__ import annotations
import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.path.join(os.path.dirname(__file__), '..', 'gestao_clinica.db')
SQLITE_PATH = os.path.abspath(SQLITE_PATH)
DATABASE_URL = os.getenv('DATABASE_URL')

SCHEMA_STATEMENTS = [
    """
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
        observacoes TEXT,
        data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_at_data ON atendimentos(data)",
    "CREATE INDEX IF NOT EXISTS idx_at_empresa ON atendimentos(empresa)",
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_notas_titulo ON notas(titulo)",
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
    """,
]

TABLES = [
    ('atendimentos', 'id, empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, status, observacoes, data_criacao, data_atualizacao'),
    ('notas', 'id, titulo, conteudo, tags, favorita, data_criacao, data_atualizacao'),
    ('notas_historico', 'id, nota_id, titulo, conteudo, tags, favorita, data_versao'),
]

def ensure_postgres_schema(conn):
    cur = conn.cursor()
    for stmt in SCHEMA_STATEMENTS:
        cur.execute(stmt)
    conn.commit()


def fetch_sqlite(table: str, cols: str):
    con = sqlite3.connect(SQLITE_PATH)
    try:
        cur = con.cursor()
        cur.execute(f"SELECT {cols} FROM {table}")
        rows = cur.fetchall()
        return rows
    finally:
        con.close()


def existing_ids_pg(conn, table: str) -> set[int]:
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT id FROM {table}")
        return {r[0] for r in cur.fetchall()}
    except Exception:
        return set()


def insert_rows(conn, table: str, cols: str, rows):
    if not rows:
        return 0
    col_list = [c.strip() for c in cols.split(',')]
    placeholders = ','.join(['%s'] * len(col_list))
    sql = f"INSERT INTO {table} ({','.join(col_list)}) VALUES ({placeholders})"
    cur = conn.cursor()
    execute_batch(cur, sql, rows, page_size=500)
    return len(rows)


def main():
    if not DATABASE_URL:
        print("DATABASE_URL não definido no .env")
        return
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite não encontrado: {SQLITE_PATH}")
        return
    print(f"Conectando em Postgres: {DATABASE_URL}")
    pg = psycopg2.connect(DATABASE_URL)
    ensure_postgres_schema(pg)

    for table, cols in TABLES:
        print(f"Migrando {table} ...")
        rows = fetch_sqlite(table, cols)
        if not rows:
            print("  (vazio)")
            continue
        ids_pg = existing_ids_pg(pg, table)
        # Filtra linhas cujo id já existe
        filtered = [r for r in rows if r[0] not in ids_pg]
        if not filtered:
            print("  Nenhuma nova linha.")
            continue
        inserted = insert_rows(pg, table, cols, filtered)
        pg.commit()
        print(f"  Inseridos {inserted} registros.")

    pg.close()
    print("Migração concluída.")

if __name__ == "__main__":
    main()
