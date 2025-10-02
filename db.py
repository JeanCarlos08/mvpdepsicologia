import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'gestao_clinica.db')

def conectar():
	return sqlite3.connect(DATABASE_PATH)

def verificar_conexao():
	try:
		with conectar() as conn:
			conn.execute('SELECT 1')
		return True
	except Exception:
		return False

def inserir_atendimento(empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes=None):
	with conectar() as conn:
		cur = conn.cursor()
		cur.execute('''INSERT INTO atendimentos (empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes)
					  VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
					(empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes))
		conn.commit()
		return cur.lastrowid

def listar_atendimentos():
	with conectar() as conn:
		cur = conn.cursor()
		cur.execute('SELECT * FROM atendimentos')
		return cur.fetchall()

def excluir_atendimento(atendimento_id):
	with conectar() as conn:
		cur = conn.cursor()
		cur.execute('DELETE FROM atendimentos WHERE id = ?', (atendimento_id,))
		conn.commit()
		return cur.rowcount > 0

def atualizar_atendimento(atendimento_id, **kwargs):
	campos = []
	valores = []
	for k, v in kwargs.items():
		campos.append(f"{k} = ?")
		valores.append(v)
	valores.append(atendimento_id)
	with conectar() as conn:
		cur = conn.cursor()
		cur.execute(f'UPDATE atendimentos SET {", ".join(campos)} WHERE id = ?', valores)
		conn.commit()
		return cur.rowcount > 0

# Funções para notas (bloco de notas)
def inserir_nota(titulo, conteudo, tags, favorita=0):
	with conectar() as conn:
		cur = conn.cursor()
		cur.execute('''INSERT INTO notas (titulo, conteudo, tags, favorita)
					  VALUES (?, ?, ?, ?)''', (titulo, conteudo, tags, favorita))
		conn.commit()
		return cur.lastrowid

def listar_notas():
	with conectar() as conn:
		cur = conn.cursor()
		cur.execute('SELECT * FROM notas')
		return cur.fetchall()

def atualizar_nota(nota_id, **kwargs):
	campos = []
	valores = []
	for k, v in kwargs.items():
		campos.append(f"{k} = ?")
		valores.append(v)
	valores.append(nota_id)
	with conectar() as conn:
		cur = conn.cursor()
		cur.execute(f'UPDATE notas SET {", ".join(campos)} WHERE id = ?', valores)
		conn.commit()
		return cur.rowcount > 0

def excluir_nota(nota_id):
	with conectar() as conn:
		cur = conn.cursor()
		cur.execute('DELETE FROM notas WHERE id = ?', (nota_id,))
		conn.commit()
		return cur.rowcount > 0

# Diagnóstico simples
def get_db_diagnostics():
	try:
		with conectar() as conn:
			cur = conn.cursor()
			cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
			tables = [r[0] for r in cur.fetchall()]
			return {"tables": tables, "db_path": DATABASE_PATH}
	except Exception as e:
		return {"error": str(e)}
