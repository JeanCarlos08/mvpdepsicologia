## Resumo rápido

Este repo é um MVP de uma aplicação Streamlit chamada "JULIANA - Gestão Clínica". A interface está em `app.py`. A persistência tem duas camadas:

- SQLite (padrão): `db.py`, arquivo local `gestao_clinica.db`.
- Camada unificada: `db_unified.py` — tenta usar Postgres via `DATABASE_URL` (.env + psycopg2) e faz fallback para `db.py` se necessário.

Agentes: concentrem-se em `app.py`, `core/services.py`, `db_unified.py` e `security.py` para mudanças que afetam comportamento, validação e persistência.

## Como executar (desenvolvimento)

1. Instale dependências:

```powershell
pip install -r requirements.txt
```

2. Rodar local (Streamlit + SQLite):

```powershell
streamlit run app.py
```

3. Para usar Postgres (Neon ou similar), crie um `.env` na raiz com:

```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require
APP_ADMIN_USER=seu_usuario
APP_ADMIN_PASS=sua_senha
```

4. Migração de dados SQLite -> Postgres (script existente):

```powershell
python scripts/migrate_sqlite_to_postgres.py
```

## Convenções e padrões do projeto

- API de persistência: as funções públicas usadas por `core/services.py` e `app.py` seguem nomes/assinaturas como `inserir_atendimento(...)`, `listar_atendimentos()`, `atualizar_atendimento(id, **campos)`, `excluir_atendimento(id)`.
- Retorno: muitas funções retornam boolean (True/False) ou listas/tuplas; raramente lançam exceções — trate verificando valores de retorno.
- SQLite retorna tuplas (ordem fixa de colunas). `core/services.py` normaliza para dicionários quando necessário; ao modificar o schema, atualize essa normalização.
- `db_unified.py` controla a escolha de backend. Não suprimir o fallback: preserve a lógica que tenta Postgres (quando `DATABASE_URL` válido + psycopg2) e, se falhar, recai para SQLite.
- Segurança: `security.py` contém helpers para sanitização (`sanitize_input`), geração de nome de arquivo seguro (`generate_safe_filename`) e logging (`log_access`). Use essas funções ao lidar com uploads/inputs.
- Uploads são salvos em `uploads/` com nomes seguros (veja `security.generate_safe_filename` e `save_uploaded_pdf` em `app.py`).

## Arquivos/chaves para mudanças frequentes

- `app.py` — UI Streamlit, constantes de formato (`DATE_FORMAT`, `TIME_FORMAT`) e estilos CSS. Pequenas regras de UI e fluxo de criação de atendimentos estão aqui.
- `core/services.py` — regras de negócio; preferir colocar lógica aqui em vez de diretamente em `app.py` para manter a separação.
- `db_unified.py` — lógica de conexão ao Postgres, criação de schema Postgres e ponte para `db.py`. Atualize ao adicionar novas tabelas/colunas (atualize `_pg_init_schema()` e as funções públicas correspondentes).
- `db.py` — implementações SQLite (CRUD). Se criar novas colunas em PostgreSQL, mantenha `db.py` compatível para fallback.
- `security.py` — sanitização, validação de uploads e logging. Use para todas as entradas externas.
- `scripts/migrate_sqlite_to_postgres.py` — script de migração; segue a mesma estrutura de tabelas que `db_unified.py`.

## Mudanças de banco de dados — checklist para agentes

1. Ao adicionar/alterar uma tabela: atualizar `db_unified._pg_init_schema()` (SQL CREATE/ALTER) e `init_db.py` (SQLite) para que ambos backends suportem o esquema.
2. Verifique funções utilitárias em `db.py` e `db_unified.py` (nomes/ordem de colunas). Tests e `core/services.py` podem depender da forma dos resultados (tupla vs dict).
3. Se mudar um campo usado pela UI, atualize `app.py` (formulários, `AtendimentoData` constructor e lugares que formatam data/hora).

## Perfis e práticas que agentes devem seguir

- Evite mudanças que removam o fallback SQLite; mantenha compatibilidade reversa.
- Prefira adicionar lógica a `core/services.py` em vez de diretamente em `app.py`.
- Ao tocar migrations ou schema, atualize também `scripts/migrate_sqlite_to_postgres.py` para manter o caminho de migração funcional.
- Logging: escreva logs de auditoria via `security.log_access(...)` (gera entry em `logs/security.log`).

## Pontos de atenção (armadilhas comuns)

- `db_unified.USE_PG` depende de `psycopg2` e do prefixo `DATABASE_URL`. Em CI/environments sem psycopg2 o fallback é esperado.
- SQLite retorna tuplas completas; `core/services.py` faz uma heurística baseada em comprimento da tupla para mapear chaves. Ao reordenar colunas, essa heurística pode quebrar.
- Muitos métodos retornam True/False em vez de lançar exceção — as UIs normalmente verificam e exibem mensagens de erro com `st.error(...)`.
- Arquivo de banco local `gestao_clinica.db` é parte do fluxo dev; não commitar grandes dumps e preferir `backups/` para cópias manuais.

## Exemplos rápidos (referências de código)

- Inserção de atendimento (DB layer): inserir_atendimento(empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes)
- Normalização na camada de serviços (exemplo): `core/services.py` converte tuplas SQLite para dict com chaves ["id","empresa","nome","modalidade","data","hora","laudo_pdf","avaliacao_pdf","status","observacoes"].

## Se precisar executar tarefas do projeto (terminal)

Use os comandos do README para build/run. Exemplos úteis:

```powershell
# instalar dependências
pip install -r requirements.txt
# rodar app local com SQLite
streamlit run app.py --server.port 8510
# migrar para Postgres após definir DATABASE_URL
python scripts/migrate_sqlite_to_postgres.py
```

## Perguntas que devo fazer antes de grandes mudanças

1. Vamos precisar migrar dados existentes? (Se sim, atualize `scripts/migrate_sqlite_to_postgres.py`.)
2. A mudança afeta o schema (SQLite e Postgres)? Atualize ambos lugares.
3. É necessário adicionar testes ou validações em `core/services.py` e `security.py`?

---

Se quiser, faço uma segunda versão reduzida/expandida ou adiciono exemplos de PRs e templates de commits para este projeto.