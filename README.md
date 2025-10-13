# JULIANA - Gestão Clínica (MVP)

Aplicação Streamlit para gestão clínica com autenticação simples e PostgreSQL.

## Requisitos
- Python 3.12
- PostgreSQL 18 (serviço: `postgresql-x64-18`)

## Configuração
1. Crie o virtualenv e instale dependências:
   - pip install -r requirements.txt
2. Configure o `.env` (já incluso):
   - APP_ADMIN_USER=admin
   - APP_ADMIN_PASS=admin123
   - DATABASE_URL=postgresql://admin:MinhaSenhaSegura123@127.0.0.1:5432/gestao_clinica
3. Banco de dados:
   - O sistema tenta criar automaticamente o banco `gestao_clinica` na primeira execução (se houver permissão).
   - Alternativa: criar manualmente no pgAdmin: `CREATE DATABASE gestao_clinica;`

## Como iniciar
- Duplo clique em `INICIAR_SISTEMA.bat`
- Ou: `python -m streamlit run app.py`

## Login
- Usuário: admin
- Senha: admin123

## Estrutura
- app.py → App Streamlit (clássico)
- db.py → Acesso ao banco (PostgreSQL com fallback para SQLite)
- security.py → Utilitários
- uploads/ → PDFs enviados

## Notas
- O app inicia mesmo sem o banco conectado e exibe aviso.
- Encoding ajustado para Windows/UTF-8.
