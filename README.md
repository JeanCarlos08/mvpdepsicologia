# Gestão Clínica (MVP)

[![Deploy to Streamlit](https://img.shields.io/badge/Deploy%20to-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://share.streamlit.io/deploy?repository=JeanCarlos08/mvpdepsicologia&branch=main&mainFilePath=app.py)

Aplicação Streamlit para gestão clínica com PostgreSQL, autenticação simples e diagnósticos embutidos.

## Requisitos
- Python 3.11 (ver `runtime.txt`)
- PostgreSQL disponível (local ou serviço gerenciado)

## Visão rápida (Try it)
1) Crie e ative um ambiente virtual, depois instale as dependências:

```powershell
python -m venv .venv
./.venv/Scripts/Activate
pip install -r requirements.txt
```

2) Configure a conexão ao Postgres (escolha 1 opção):
- Opção A (temporário na sessão):

```powershell
$env:DATABASE_URL = "postgresql://USUARIO:SENHA@HOST:5432/NOME_DO_BANCO?sslmode=require"
```

- Opção B (recomendado): crie o arquivo `.streamlit/secrets.toml` com seu conteúdo real (veja `/.streamlit/secrets.example.toml`).

3) Rode o app:

```powershell
python -m streamlit run app.py
```

Se a conexão estiver correta, a página “🔎 Diagnóstico” mostrará “Conectado” e você poderá “⚡ Criar índices”.

## Configuração (detalhes)
- O app lê `DATABASE_URL` (ex.: `postgresql://user:pass@host:5432/db?sslmode=require`) OU as chaves separadas em Secrets: `db_host`, `db_port`, `db_name`, `db_user`, `db_password` e, se necessário, `db_sslmode` (ex.: `require`).
- Para provedores Cloud (Neon, Render, Supabase, ElephantSQL, etc.), use `sslmode=require` na URL.
- Nunca versione segredos. Use:
  - Local: `.streamlit/secrets.toml` (IGNORADO pelo Git)
  - Cloud: Settings → Secrets do Streamlit Cloud

## Deploy no Streamlit Cloud
1) Aponte para o repo (branch `main`).
2) Main file path: `app.py` (ou `gestao_clinica/app.py` se estiver em subpasta).
3) Em Settings → Secrets, adicione (exemplos):
   - `DATABASE_URL=postgresql://usuario:senha@host:5432/gestao_clinica?sslmode=require`
   - Alternativa com campos separados: `db_host`, `db_port`, `db_name`, `db_user`, `db_password`, `db_sslmode=require`
4) Sem fixar porta/endereço no `config.toml` (já configurado). Upload máx.: 50MB.

### Checklist pós-deploy
- [ ] Definir Secrets no Cloud (use `DATABASE_URL` com `sslmode=require` ou chaves separadas com `db_sslmode=require`).
- [ ] Abrir “⚙️ Configurações → 🔎 Diagnóstico” no app e confirmar “Conectado”.
- [ ] Clicar em “⚡ Criar índices” para acelerar filtros e buscas.
- [ ] Testar login (credenciais definidas nos Secrets) e garantir `APP_REQUIRE_AUTH=true` se quiser exigir autenticação.
- [ ] Testar upload/download/preview de PDF em Atendimentos e no módulo de Upload.

## PDFs no Banco (BYTEA)
- Anexos são gravados na tabela `arquivos` como `BYTEA`, e referenciados como `db:<id>`.
- Registros antigos que usam caminho no disco seguem compatíveis, mas o padrão recomendado é o banco.

## Segurança e autenticação
- O app exige login por padrão. Use Secrets para definir credenciais.
- Fallback (apenas se não houver credenciais nos Secrets): `admin` / `admin123`.
- Ajustes adicionais via variáveis de ambiente/Secrets (ex.: obrigatoriedade de autenticação) são suportados no código.

## Diagnóstico e manutenção
- Página “⚙️ Configurações → 🔎 Diagnóstico”: testa conexão e mostra status.
- Ação “⚡ Criar índices”: cria índices idempotentes úteis para buscas/filtros.

## Estrutura principal
- `app.py` — UI em Streamlit
- `db.py` — Conexão e CRUD no PostgreSQL (com suporte a `sslmode`)
- `.streamlit/config.toml` — Configuração do Streamlit (headless, CORS/XSRF off, uploads)
- `.streamlit/secrets.example.toml` — Modelo de Secrets (não contém credenciais reais)
- `requirements.txt` — Dependências
- `runtime.txt` — Versão do Python para deploy
- `tools/check_pg.py` — Verifica conexão local ao Postgres (opcional)
- `tools/create_db.py` — Cria DB local se necessário (opcional)

## Troubleshooting rápido
- “Falha ao conectar ao PostgreSQL”: verifique host/porta/DB, usuário/senha e `sslmode` exigido pelo provedor.
- “Conectado, mas sem tabelas”: abra o app; o esquema é criado automaticamente na inicialização.
- PDFs não abrem: confirme que o campo guarda `db:<id>` e que a tabela `arquivos` contém conteúdo para o `id` informado.
- No Cloud, “localhost” não funciona — use o host público do seu serviço de banco.

---
Este repositório ignora secrets, logs, uploads e artefatos de build por padrão (veja `.gitignore`).

# Gestão Clínica — Postgres

- Banco: PostgreSQL (apenas)
- Cloud: use DATABASE_URL com sslmode=require

## Rodar local
1) Crie .streamlit/secrets.toml:
   DATABASE_URL = "postgresql://postgres:SENHA@localhost:5432/SEU_BANCO"
2) streamlit run app.py
3) Em Configurações → Diagnóstico, verifique “Conectado”.

## Deploy (Streamlit Cloud)
- Settings → Secrets:
  DATABASE_URL = "postgresql://USUARIO:SENHA@HOST_PUBLICO:5432/NOME_DO_BANCO?sslmode=require"
- Rerun/Deploy e verifique em Diagnóstico.

---

## 🔧 Correções Recentes (v1.1)

### Bugs Corrigidos
- ✅ **Função `save_uploaded_pdf()`** — Retorno inconsistente (None vs "")
  - Solução: Padronizar para retornar `None` em falhas
  
- ✅ **Conversão data/hora em edição** — `.strftime()` incorreto
  - Solução: Passar objetos `date`/`time` direto ao PostgreSQL
  
- ✅ **Tratamento de anexos None** — Validação inadequada
  - Solução: Verificar `if up_laudo else None` antes de processar

### Funcionalidades Validadas
- ✓ Geração de PDF da lista de atendimentos
- ✓ Upload/download de Laudo e Avaliação (PDF)
- ✓ Análise de PDF com IA (Gemini)
- ✓ Visualização em iframe
- ✓ Edição com substituição de anexos
- ✓ Exclusão segura de arquivos
- ✓ Conversão correta de tipos DATE/TIME

### Documentação
- **BUGS_CORRIGIDOS.md** — Relatório técnico detalhado
- **TESTE_PDF_ANEXOS.md** — Guia passo-a-passo para testar

---

## Status
✨ **Sistema pronto para produção** (v1.1)
