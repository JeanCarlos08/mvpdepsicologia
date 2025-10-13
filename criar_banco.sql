-- Script SQL para criar o banco e a tabela
-- Execute este script no pgAdmin ou psql

-- Criar banco (se não existir)
CREATE DATABASE gestao_clinica;

-- Conectar ao banco gestao_clinica e criar tabela
\c gestao_clinica

CREATE TABLE IF NOT EXISTS atendimentos (
    id SERIAL PRIMARY KEY,
    empresa TEXT NOT NULL,
    nome TEXT NOT NULL,
    modalidade TEXT NOT NULL,
    data TEXT NOT NULL,
    hora TEXT NOT NULL,
    laudo_pdf TEXT,
    avaliacao_pdf TEXT,
    status TEXT DEFAULT 'Agendado',
    observacoes TEXT
);

-- Dar permissões ao usuário admin
GRANT ALL PRIVILEGES ON DATABASE gestao_clinica TO admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin;

-- Verificar
SELECT 'Banco configurado com sucesso!' AS status;
SELECT COUNT(*) AS total_registros FROM atendimentos;
