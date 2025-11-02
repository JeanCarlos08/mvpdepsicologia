import psycopg2
import sys

HOST = 'localhost'
PORT = 5432
USER = 'postgres'
PASSWORD = '845207'
DBNAME = 'gestao_clinica'

try:
    conn = psycopg2.connect(host=HOST, port=PORT, user=USER, password=PASSWORD, dbname='postgres')
except Exception as e:
    print(f"Falha ao conectar no banco 'postgres' como {USER}: {e}")
    sys.exit(1)

conn.autocommit = True
cur = conn.cursor()
try:
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DBNAME,))
    exists = cur.fetchone() is not None
    if exists:
        print(f"Banco '{DBNAME}' já existe. Nada a fazer.")
    else:
        cur.execute(f"CREATE DATABASE {DBNAME} OWNER {USER}")
        print(f"Banco '{DBNAME}' criado com sucesso, owner={USER}.")
finally:
    cur.close()
    conn.close()
