import json
import sys

try:
    import psycopg2
except Exception as e:
    print(json.dumps({"ok": False, "error": f"psycopg2 não encontrado: {e}", "hint": "Instale as dependências do projeto (psycopg2-binary)"}, ensure_ascii=False))
    sys.exit(0)

params = dict(host='localhost', port=5432, user='postgres', password='845207')
try_dbs = ['gestao_clinica', 'postgres']
res = {"ok": False, "tried": [], "connected_to": None, "current_user": None, "databases": [], "roles": []}

for db in try_dbs:
    try:
        conn = psycopg2.connect(dbname=db, **params)
        cur = conn.cursor()
        cur.execute("SELECT current_database(), current_user")
        dbname, user = cur.fetchone()
        res["ok"] = True
        res["connected_to"] = dbname
        res["current_user"] = user
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate=FALSE ORDER BY 1")
        res["databases"] = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT rolname FROM pg_roles ORDER BY 1")
        res["roles"] = [r[0] for r in cur.fetchall()]
        conn.close()
        break
    except Exception as e:
        res["tried"].append({"db": db, "error": str(e)})

print(json.dumps(res, ensure_ascii=False))
