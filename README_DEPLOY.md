# Deploy Rápido (Streamlit)

Arquivos essenciais:
- app.py (aplicativo)
- db.py (PostgreSQL)
- requirements.txt
- runtime.txt (python-3.12)
- .streamlit/config.toml

Antes de subir ao Streamlit Cloud:
1. Garanta que o banco está acessível na internet (RDS, Neon, Render etc.).
2. Configure Secrets no Streamlit Cloud:
   - DATABASE_URL=postgresql://usuario:senha@host:5432/gestao_clinica
   - APP_ADMIN_USER=seu_usuario
   - APP_ADMIN_PASS=sua_senha
3. Aponte o app para gestao_clinica/app.py.

Locally:
- INICIAR_SISTEMA.bat (abre navegador e inicia Streamlit)
- Crie o DB: CREATE DATABASE gestao_clinica; e execute sql/create_app_user.sql
