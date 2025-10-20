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
   - DATABASE_URL=postgresql://admin:admin123@127.0.0.1:5432/gestao_clinica
3. Banco de dados:
   - O app exige PostgreSQL ativo e credenciais válidas.
   - Crie o banco previamente no pgAdmin/psql: `CREATE DATABASE gestao_clinica;`

## Como iniciar
- Duplo clique em `INICIAR_SISTEMA.bat`
- Ou: `python -m streamlit run app.py`

## Login
- Usuário: admin
- Senha: admin123

## Estrutura
- app.py → App Streamlit (clássico)
- db.py → Acesso ao banco (PostgreSQL)
- uploads/ → Compatibilidade para PDFs antigos (novo padrão usa Postgres)

## Anexos (PDFs) no Banco de Dados
- PDFs são armazenados no PostgreSQL (tabela `arquivos`).
- Ao enviar um PDF (em Atendimentos ou na página Upload), o arquivo é salvo como `BYTEA` e o sistema registra um marcador `db:<id>`.
- Downloads são feitos diretamente do banco, inclusive na lista de atendimentos.

Observação: existe compatibilidade para caminhos em disco legados, mas o padrão e recomendado é sempre o banco.

## Deploy no Streamlit Cloud
1. Suba este repositório para o GitHub (branch main).
2. No Streamlit Cloud, crie um novo app apontando para `gestao_clinica/app.py`.
3. Em Settings → Secrets, defina as variáveis (um por linha):
   - `DATABASE_URL=postgresql://usuario:senha@host:5432/gestao_clinica`
   - `APP_ADMIN_USER=seu_usuario`
   - `APP_ADMIN_PASS=sua_senha_forte`
4. Opcional: ajuste o tamanho máximo de upload pelo `config.toml` se necessário (o padrão aqui é 50MB).

Importante: nunca coloque senhas no repositório. Use Secrets no Streamlit Cloud ou `.env` local (não versionado). O arquivo `.env.example` mostra o formato esperado.

## Notas
- O app exige PostgreSQL configurado e ativo.
- Encoding ajustado para Windows/UTF-8.
