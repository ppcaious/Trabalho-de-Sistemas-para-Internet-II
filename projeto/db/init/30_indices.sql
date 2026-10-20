-- ============================================================================
-- Índices para busca indexada e por similaridade.
-- Criados DEPOIS da importação: inserir em tabela sem índices é muito mais
-- rápido do que manter os índices a cada linha.
-- ============================================================================

-- Criar índices GIN em 1,5 milhão de linhas pode passar do statement_timeout
-- do servidor; nesta sessão de inicialização não há limite.
SET statement_timeout = 0;

-- Busca exata por nome (?nome=) e ordenação dos resultados
CREATE INDEX idx_servidores_nome ON servidores (nome);

-- Busca por similaridade (?similar=%JOAO%SILVA%): o índice GIN com trigramas
-- acelera ILIKE '%...%' e a função similarity() do pg_trgm.
CREATE INDEX idx_servidores_nome_trgm ON servidores USING GIN (nome gin_trgm_ops);

-- Filtros
CREATE INDEX idx_servidores_uf       ON servidores (uf);
CREATE INDEX idx_servidores_cargo    ON servidores (cargo_id);
CREATE INDEX idx_servidores_orgao    ON servidores (orgao_id);
CREATE INDEX idx_servidores_situacao ON servidores (situacao);

-- Combinações frequentes (cargo+UF, órgão+UF)
CREATE INDEX idx_servidores_cargo_uf ON servidores (cargo_id, uf);
CREATE INDEX idx_servidores_orgao_uf ON servidores (orgao_id, uf);

-- Busca parcial de cargo/órgão (ILIKE '%AUDITOR%') nas tabelas de domínio
CREATE INDEX idx_cargos_nome_trgm ON cargos USING GIN (nome gin_trgm_ops);
CREATE INDEX idx_orgaos_nome_trgm ON orgaos USING GIN (nome gin_trgm_ops);

-- Estatísticas para o planejador escolher os índices certos
ANALYZE servidores;
ANALYZE cargos;
ANALYZE orgaos;
