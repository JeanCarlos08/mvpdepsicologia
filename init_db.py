import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'gestao_clinica.db')

def initialize_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Tabela de atendimentos
        cur.execute('''CREATE TABLE IF NOT EXISTS atendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            nome TEXT,
            modalidade TEXT,
            data TEXT,
            hora TEXT,
            laudo_pdf TEXT,
            avaliacao_pdf TEXT,
            observacoes TEXT
        )''')
        # Tabela de notas
        cur.execute('''CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            conteudo TEXT,
            tags TEXT,
            favorita INTEGER DEFAULT 0
        )''')
        conn.commit()

if __name__ == "__main__":
    initialize_db()
    print("Banco de dados inicializado com sucesso!")
