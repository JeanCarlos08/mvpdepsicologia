# 🧠 JULIANA - Gestão Clínica (MVP)

Aplicação Streamlit para gestão de atendimentos, laudos e notas clínicas. O backend agora utiliza **exclusivamente PostgreSQL** via `psycopg2`, com configuração feita por variáveis de ambiente ou `st.secrets` (quando publicado no Streamlit Cloud).

---
## ⚙️ Pré-requisitos
- Python 3.10+
- Servidor PostgreSQL (local, Docker, ou serviço gerenciado como Neon/Render/Railway)

---
## � Configuração do banco
1. Copie o arquivo `.env.example` para `.env` e preencha com os valores do seu ambiente.
2. As variáveis aceitas são:
	- `DB_HOST`
	- `DB_PORT`
	- `DB_NAME`
	- `DB_USER`
	- `DB_PASSWORD`
3. Como alternativa, use uma única `DATABASE_URL` (ou `POSTGRES_URL`) no formato `postgresql://usuario:senha@host:porta/banco`.
4. Em produção (Streamlit Cloud), configure os mesmos valores em **st.secrets**.

> **Erro comum**: “Variável 'db_host' não configurada. Defina em um arquivo .env ou em st.secrets.”  
> ✅ Solução: verifique se copiou `.env.example` para `.env` e se o app foi reiniciado após ajustar as credenciais.

---
## 🚀 Execução local
```powershell
pip install -r requirements.txt
streamlit run app.py
```
O app carrega o esquema automaticamente na primeira execução.

---
## 🔐 Autenticação (opcional, recomendado)
Defina no `.env` (ou em st.secrets):
```env
APP_ADMIN_USER=seu_usuario
APP_ADMIN_PASS=sua_senha
```
Sem essas variáveis o app inicia em modo aberto (apenas para desenvolvimento).

---
## 🔄 Migração do SQLite legado
Se ainda possuir dados no arquivo `gestao_clinica.db`, utilize o script `migrate_sqlite_to_postgres.py`:
1. Garanta que o PostgreSQL esteja acessível e configurado nas variáveis de ambiente.
2. (Opcional) Faça backup do arquivo SQLite original.
3. Execute:
```powershell
python migrate_sqlite_to_postgres.py
```
4.Confira no Postgres: `SELECT COUNT(*) FROM atendimentos;` (etc.).

O script cria o schema, copia registros e evita duplicidades.

---
## 📂 Estrutura principal
| Arquivo | Descrição |
|---------|-----------|
| `app.py` | Interface Streamlit |
| `db.py` | Camada de acesso ao Postgres (`psycopg2`) |
| `security.py` | Sanitização, uploads e logs |
| `migrate_sqlite_to_postgres.py` | Migração de dados legado |
| `requirements.txt` | Dependências do projeto |
| `.env.example` | Modelo de variáveis de ambiente |

Uploads (`uploads/`) e o banco legado (`*.db`) continuam ignorados pelo Git.

---
## 🛡️ Boas práticas
- Logs de acesso: `logs/access.log`
- Sanitização de entradas e validação de PDFs embutidas
- Limpeza de cache Streamlit (quando necessário):
```powershell
streamlit cache clear
```

---
## 🐳 Executando com Docker
```powershell
docker build -t gestao-clinica .
docker run -p 8501:8501 --env-file .env gestao-clinica
```

---
## ✅ Checklist rápido de deploy
1. Provisionar Postgres e obter a URL de conexão.
2. Definir as variáveis no ambiente de execução (ou st.secrets).
3. Executar `migrate_sqlite_to_postgres.py` se houver dados legados.
4. Subir a aplicação (`streamlit run app.py`, Procfile, Docker etc.).
5. Validar badge “Postgres” no dashboard e testar CRUD/Uploads.

---
## 🆘 Suporte
1. Verifique se o banco está acessível (`st.sidebar` mostra status de conexão).
2. Confira as variáveis de ambiente e o `.env`.
3. Consulte os logs em `logs/access.log`.

---
_Atualizado para o fluxo pós-migração para PostgreSQL._
