# 🧠 JULIANA - Gestão Clínica (MVP)

Aplicação Streamlit para gestão básica de atendimentos, laudos e notas clínicas.
Suporta dois backends de banco de dados:

- SQLite (padrão, zero-config)
- PostgreSQL (Neon ou local) via `db_unified.py` (fallback automático)

---
## 🚀 Execução local (SQLite padrão)
```powershell
pip install -r requirements.txt
streamlit run app.py
```
Acesse: http://localhost:8501 (ou porta exibida).

---
## 🐘 Usando PostgreSQL / Neon
1. Criar `.env` na raiz:
```env
DATABASE_URL=postgresql://usuario:senha@host:5432/nome_banco?sslmode=require
```
2. Instalar dependências (já listadas): `psycopg2-binary` e `python-dotenv`.
3. Rodar normalmente: `streamlit run app.py`.
4. O app detecta automaticamente e mostra badge “Postgres”.
5. Se a URL estiver ausente ou inválida, cai em SQLite sem quebrar.

### Estrutura esperada de tabelas (Postgres)
`atendimentos`, `notas`, `notas_historico` (FK automática em `notas_historico.nota_id`).

---
## 🔄 Migração SQLite → Postgres
Script: `scripts/migrate_sqlite_to_postgres.py`

Passos:
1. Garanta `.env` com `DATABASE_URL` válido.
2. (Opcional) Faça backup: copie `gestao_clinica.db` para `backups/gestao_clinica_<data>.db`.
3. Execute:
```powershell
python scripts/migrate_sqlite_to_postgres.py
```
4. Verifique contagens no Postgres (psql):
```sql
SELECT COUNT(*) FROM atendimentos; SELECT COUNT(*) FROM notas; SELECT COUNT(*) FROM notas_historico;
```
5. Abra o app e confirme badge “Postgres”.

O script:
- Cria o schema se necessário
- Copia dados sem sobrescrever IDs existentes
- Ignora tabelas vazias

---
## 🧩 Principais arquivos
| Arquivo | Função |
|---------|--------|
| `app.py` | Interface Streamlit principal |
| `db.py` | Implementação original SQLite |
| `db_unified.py` | Camada unificada (Postgres + fallback) |
| `security.py` | Sanitização, validação de uploads e logging |
| `scripts/migrate_sqlite_to_postgres.py` | Migração de dados |
| `requirements.txt` | Dependências |
| `Dockerfile` | Build container |
| `Procfile` | Deploy em plataformas tipo Heroku/Render |

Uploads e banco local são ignorados no Git (`uploads/`, `*.db`).

---
## 🛡️ Segurança / Logs
- Logs em `logs/security.log`.
- Sanitização básica de entradas (remoção de caracteres perigosos).
- Validação de PDF por extensão e tamanho.

---
## 🗄️ Fallback Inteligente
| Situação | Ação |
|----------|------|
| `DATABASE_URL` definido e driver ok | Usa Postgres |
| URL inválida ou driver ausente | Reverte para SQLite |
| Erro de conexão Posterior | Mantém SQLite para continuidade |

---
## 🔧 Manutenção
Limpar caches Streamlit (em Configurações ou manual):
```powershell
streamlit cache clear
```

Reinicializar (cria tabelas SQLite se faltarem) via botão em ⚙️ Configurações.

---
## 🐳 Docker
```powershell
docker build -t gestao-clinica .
docker run -p 8501:8501 gestao-clinica
```
Definir variável em runtime (Postgres):
```powershell
docker run -e DATABASE_URL="postgresql://..." -p 8501:8501 gestao-clinica
```

---
## ✅ Checklist de Deploy (Neon)
1. Criar projeto Neon e copiar URL.
2. Definir `DATABASE_URL` em variáveis de ambiente da plataforma.
3. Executar migração (local ou container one-off).
4. Subir container / app (Procfile ou Dockerfile).
5. Testar CRUD + uploads.
6. Verificar logs e badge de backend.
7. Fazer backup periódico (dump SQL ou export CSV).

---
## 🛠️ Próximas evoluções sugeridas
- Agenda semanal visual
- Painel de pendências (laudo/avaliação faltantes)
- Notificações (WhatsApp / e-mail)
- Export PDF consolidado
- Busca fuzzy/acento-insensível
- OCR de PDFs (indexação)

---
## Licença
Uso interno clínico (MVP). Definir licença formal posteriormente.

---
## Suporte
Em caso de erro, verificar primeiro:
1. Badge de backend (Postgres ou SQLite)
2. Log: `logs/security.log`
3. Conexão: botão “Testar Backend” em ⚙️ Configurações.

---
_Este README foi gerado automaticamente para refletir o estado atual do projeto._
