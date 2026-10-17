-- ============================================================================
-- Schema do banco "servidores" (PostgreSQL 16)
--
-- Fontes (Portal Brasileiro de Dados Abertos - dados.gov.br):
--   * Gestão de Pessoas (Executivo Federal) - Aposentados
--       arquivo APOSENTADOS_MMAAAA[_FULL].csv  (latin-1, separador ';')
--       campos: Nome; CPF; Matricula; Orgao; Sigla Orgao; Orgao vinculacao;
--               Cargo emprego; Classe; Padrao; Referencia; Nivel;
--               Tipo aposentadoria; Fund legal aposentadoria;
--               Portaria aposentadoria; Dt ocorrencia inatividade;
--               Nome ocorrencia; Dt ingresso servico publico; Valor aposentadoria
--   * Gestão de Pessoas (Executivo Federal) - Carreiras / Cargos (servidores ativos)
--       arquivo CARREIRA_MMAAAA.txt (latin-1, separador ';', 2 linhas de cabeçalho)
--       campos: Nome; CPF; Código da carreira; Descrição do cargo emprego;
--               UF da UPAG de vinculação; Denominação do órgão de atuação;
--               Mês de referência; Valor da remuneração
--
-- Modelo: tabela principal `servidores` (ativos + aposentados) normalizada
-- com `cargos` e `orgaos`, mais a tabela de domínio `ufs`.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- busca por similaridade / ILIKE indexado
CREATE EXTENSION IF NOT EXISTS unaccent;   -- normalização de acentos

CREATE TABLE ufs (
    sigla CHAR(2) PRIMARY KEY,
    nome  VARCHAR(30) NOT NULL
);

INSERT INTO ufs (sigla, nome) VALUES
 ('AC','Acre'),('AL','Alagoas'),('AP','Amapá'),('AM','Amazonas'),('BA','Bahia'),
 ('CE','Ceará'),('DF','Distrito Federal'),('ES','Espírito Santo'),('GO','Goiás'),
 ('MA','Maranhão'),('MT','Mato Grosso'),('MS','Mato Grosso do Sul'),('MG','Minas Gerais'),
 ('PA','Pará'),('PB','Paraíba'),('PR','Paraná'),('PE','Pernambuco'),('PI','Piauí'),
 ('RJ','Rio de Janeiro'),('RN','Rio Grande do Norte'),('RS','Rio Grande do Sul'),
 ('RO','Rondônia'),('RR','Roraima'),('SC','Santa Catarina'),('SP','São Paulo'),
 ('SE','Sergipe'),('TO','Tocantins');

CREATE TABLE orgaos (
    id    SERIAL PRIMARY KEY,
    nome  VARCHAR(80) NOT NULL UNIQUE,
    sigla VARCHAR(15)
);

CREATE TABLE cargos (
    id   SERIAL PRIMARY KEY,
    nome VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE servidores (
    id                   BIGSERIAL PRIMARY KEY,
    nome                 VARCHAR(80) NOT NULL,
    cpf                  VARCHAR(14),              -- já vem mascarado: ***123456**
    matricula            VARCHAR(20),
    situacao             VARCHAR(10) NOT NULL CHECK (situacao IN ('ATIVO', 'APOSENTADO')),
    cargo_id             INTEGER REFERENCES cargos (id),
    orgao_id             INTEGER REFERENCES orgaos (id),
    uf                   CHAR(2) REFERENCES ufs (sigla),   -- só existe na base de ativos
    codigo_carreira      VARCHAR(5),
    classe               VARCHAR(5),
    padrao               VARCHAR(5),
    referencia           VARCHAR(5),
    nivel                VARCHAR(5),
    tipo_aposentadoria   VARCHAR(40),
    fundamento_legal     VARCHAR(60),
    diploma_legal        VARCHAR(80),
    data_inatividade     DATE,
    ocorrencia_ingresso  VARCHAR(60),
    data_ingresso        DATE,
    valor                NUMERIC(14,2),            -- remuneração (ativo) ou provento (aposentado)
    mes_referencia       VARCHAR(7)                -- MM/AAAA do arquivo de origem
);

COMMENT ON TABLE servidores IS 'Servidores ativos (Carreiras/Cargos) e aposentados do Executivo Federal';

-- ----------------------------------------------------------------------------
-- Funções auxiliares usadas na importação (tratamento/limpeza dos dados)
-- ----------------------------------------------------------------------------

-- Converte 'DDMMAAAA' em DATE; devolve NULL se a data for inválida/vazia.
CREATE OR REPLACE FUNCTION data_segura(txt TEXT) RETURNS DATE
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF txt IS NULL OR btrim(txt) !~ '^\d{8}$' OR btrim(txt) = '00000000' THEN
        RETURN NULL;
    END IF;
    RETURN to_date(btrim(txt), 'DDMMYYYY');
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END $$;

-- Converte '  1.234,56 ' em NUMERIC; NULL se vazio/inválido.
CREATE OR REPLACE FUNCTION valor_seguro(txt TEXT) RETURNS NUMERIC
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF txt IS NULL OR btrim(txt) = '' THEN
        RETURN NULL;
    END IF;
    RETURN replace(replace(btrim(txt), '.', ''), ',', '.')::NUMERIC;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END $$;

-- Normaliza texto: tira espaços duplicados/extremos, remove acentos, maiúsculas.
-- NULL para vazio.
CREATE OR REPLACE FUNCTION texto_limpo(txt TEXT) RETURNS TEXT
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(upper(unaccent(regexp_replace(btrim(txt), '\s+', ' ', 'g'))), '');
$$;
