-- Cria usuário de aplicação com privilégios mínimos
-- Ajuste <SENHA_FORTE_AQUI>

-- 1) Conectar como superusuário (ex.: postgres) e rodar:
--    \c gestao_clinica

DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
      CREATE ROLE app_user LOGIN PASSWORD '<SENHA_FORTE_AQUI>';
   END IF;
END$$;

-- 2) Conceder privilégios mínimos nas tabelas existentes
GRANT CONNECT ON DATABASE gestao_clinica TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- Permissões de leitura/escrita nas tabelas do app
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.atendimentos TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.notas TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.arquivos TO app_user;

-- Permissão em sequências (necessário para INSERT com SERIAL)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Opcional: Tornar padrão para futuras tabelas/sequências
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user;
