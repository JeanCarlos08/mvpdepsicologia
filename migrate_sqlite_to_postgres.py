"""
Script de migração: copia dados do SQLite local (gestao_clinica.db) para um Postgres
Configuração: definir a variável de ambiente DATABASE_URL apontando para o Postgres alvo.

Uso:
  powershell:
    $env:DATABASE_URL = "postgresql://user:pass@host:5432/dbname"
    python migrate_sqlite_to_postgres.py

O script copia as tabelas `atendimentos` e `notas` se existirem.
"""
import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from db import metadata, atendimentos_table, notas_table, DATABASE_URL


SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'gestao_clinica.db')
if not os.path.exists(SQLITE_PATH):
    print(f"Arquivo SQLite não encontrado em: {SQLITE_PATH}")
    raise SystemExit(1)

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("Defina a variável de ambiente DATABASE_URL para o Postgres alvo.")
    raise SystemExit(1)

# Engines
src_conn = sqlite3.connect(SQLITE_PATH)
dst_engine = create_engine(DATABASE_URL, future=True)
dst_meta = metadata


def copy_table(table_name: str, columns: list):
    cur = src_conn.cursor()
    cur.execute(f"SELECT {', '.join(columns)} FROM {table_name}")
    rows = cur.fetchall()
    if not rows:
        print(f"Nenhum dado para {table_name}")
        return

    # Cria as tabelas no destino se necessário (usa a metadata definida em db.py)
    dst_meta.create_all(bind=dst_engine)
    dst_meta.reflect(bind=dst_engine)
    if table_name not in dst_meta.tables:
        print(f"Tabela {table_name} não existe no destino mesmo após create_all: {table_name}")
        return

    table = dst_meta.tables[table_name]
    with dst_engine.begin() as conn:
        for row in rows:
            data = {col: val for col, val in zip(columns, row)}
            conn.execute(table.insert().values(**data))
    print(f"Copiados {len(rows)} registros para {table_name}")


def main():
    # Atendimentos
    try:
        cur = src_conn.cursor()
        cur.execute("PRAGMA table_info(atendimentos)")
        cols = [r[1] for r in cur.fetchall()]
        if cols:
            copy_table('atendimentos', cols)
    except Exception as e:
        print(f"Pular atendimentos: {e}")

    try:
        cur = src_conn.cursor()
        cur.execute("PRAGMA table_info(notas)")
        cols = [r[1] for r in cur.fetchall()]
        if cols:
            copy_table('notas', cols)
    except Exception as e:
        print(f"Pular notas: {e}")

    print("Migração concluída")


if __name__ == '__main__':
    main()
