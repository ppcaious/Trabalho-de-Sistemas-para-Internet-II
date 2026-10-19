#!/bin/bash
# ============================================================================
# Importação automática dos arquivos do dados.gov.br no primeiro
# `docker compose up`. Roda dentro do contêiner db, via docker-entrypoint.
#
# Lê todos os arquivos de /dados (montado de ./db/data):
#   APOSENTADOS_*.csv  -> situacao = 'APOSENTADO'
#   CARREIRA_*.txt     -> situacao = 'ATIVO'
#
# Etapas (tratamento e limpeza):
#   1. COPY do arquivo bruto (latin-1) para uma tabela de staging só com texto
#   2. Limpeza: trim, remoção de acentos, maiúsculas, datas/valores inválidos
#      viram NULL, linhas de rodapé ("TOTAL GERAL") e vazias são descartadas
#   3. Normalização: cargos e órgãos vão para suas tabelas; servidores recebe
#      as chaves estrangeiras
# ============================================================================
set -euo pipefail

DADOS_DIR="${DADOS_DIR:-/dados}"
PSQL=(psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -q)

# O servidor sobe com statement_timeout (proteção para as consultas da API),
# mas a carga inicial de 1,5 milhão de linhas pode levar minutos: sem limite aqui.
export PGOPTIONS="-c statement_timeout=0 -c idle_in_transaction_session_timeout=0"

log() { echo "[importar] $(date +%H:%M:%S) $*"; }

shopt -s nullglob nocaseglob
ARQ_APOS=("$DADOS_DIR"/APOSENTADOS_*.csv)
ARQ_CARR=("$DADOS_DIR"/CARREIRA_*.txt)
shopt -u nocaseglob

if [ ${#ARQ_APOS[@]} -eq 0 ] && [ ${#ARQ_CARR[@]} -eq 0 ]; then
    log "AVISO: nenhum arquivo encontrado em $DADOS_DIR. O banco ficará vazio."
    exit 0
fi

# ---------------------------------------------------------------------------
# Tabelas de staging (texto puro, sem restrições) - descartadas no final
# ---------------------------------------------------------------------------
"${PSQL[@]}" <<'SQL'
CREATE UNLOGGED TABLE stg_aposentados (
    nome TEXT, cpf TEXT, matricula TEXT, orgao TEXT, sigla_orgao TEXT, orgao_vinc TEXT,
    cargo TEXT, classe TEXT, padrao TEXT, referencia TEXT, nivel TEXT,
    tipo_apos TEXT, fund_legal TEXT, portaria TEXT, dt_inatividade TEXT,
    nome_ocorrencia TEXT, dt_ingresso TEXT, valor TEXT, arquivo TEXT
);
CREATE UNLOGGED TABLE stg_carreira (
    nome TEXT, cpf TEXT, cod_carreira TEXT, cargo TEXT, uf TEXT, orgao TEXT,
    mes_ref TEXT, valor TEXT, arquivo TEXT
);
SQL

mes_do_arquivo() {  # APOSENTADOS_052026_FULL.csv -> 05/2026
    local b; b=$(basename "$1")
    if [[ "$b" =~ ([0-9]{2})([0-9]{4}) ]]; then echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"; else echo ""; fi
}

# ---------------------------------------------------------------------------
# 1. Aposentados: 18 colunas; o arquivo _FULL tem cabeçalho, os mensais não.
# ---------------------------------------------------------------------------
for f in "${ARQ_APOS[@]}"; do
    mes=$(mes_do_arquivo "$f")
    log "lendo $(basename "$f") (aposentados, ref. $mes)"
    if head -c 5 "$f" | grep -qi '^Nome'; then pular=2; else pular=1; fi
    tail -n +"$pular" "$f" \
      | tr -d '\r' \
      | cut -d';' -f1-18 \
      | awk -v m="$mes" -F';' 'NF>=18 && $1 !~ /^ *$/ { print $0 ";" m }' \
      | "${PSQL[@]}" -c "\\copy stg_aposentados FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE E'\\x01', ENCODING 'LATIN1', NULL '')"
done

# ---------------------------------------------------------------------------
# 2. Carreiras/Cargos (ativos): 2 linhas de cabeçalho, 8 colunas + ';' final,
#    rodapé com linhas em branco e "TOTAL GERAL".
# ---------------------------------------------------------------------------
for f in "${ARQ_CARR[@]}"; do
    mes=$(mes_do_arquivo "$f")
    log "lendo $(basename "$f") (ativos, ref. $mes)"
    tail -n +3 "$f" \
      | tr -d '\r' \
      | cut -d';' -f1-8 \
      | awk -v m="$mes" -F';' 'NF>=8 && $1 !~ /^ *$/ && $1 !~ /^TOTAL/ { print $0 ";" m }' \
      | "${PSQL[@]}" -c "\\copy stg_carreira FROM STDIN WITH (FORMAT csv, DELIMITER ';', QUOTE E'\\x01', ENCODING 'LATIN1', NULL '')"
done

# ---------------------------------------------------------------------------
# 3. Limpeza + normalização -> tabelas finais
# ---------------------------------------------------------------------------
log "normalizando cargos e órgãos"
"${PSQL[@]}" <<'SQL'
INSERT INTO cargos (nome)
SELECT DISTINCT texto_limpo(cargo) FROM stg_aposentados WHERE texto_limpo(cargo) IS NOT NULL
UNION
SELECT DISTINCT texto_limpo(cargo) FROM stg_carreira WHERE texto_limpo(cargo) IS NOT NULL
ON CONFLICT (nome) DO NOTHING;

INSERT INTO orgaos (nome, sigla)
SELECT nome, max(sigla) FROM (
    SELECT texto_limpo(orgao) AS nome, texto_limpo(sigla_orgao) AS sigla FROM stg_aposentados
    UNION ALL
    SELECT texto_limpo(orgao), NULL FROM stg_carreira
) t
WHERE nome IS NOT NULL
GROUP BY nome
ON CONFLICT (nome) DO NOTHING;
SQL

log "inserindo aposentados"
"${PSQL[@]}" <<'SQL'
INSERT INTO servidores (nome, cpf, matricula, situacao, cargo_id, orgao_id, uf,
                        classe, padrao, referencia, nivel, tipo_aposentadoria,
                        fundamento_legal, diploma_legal, data_inatividade,
                        ocorrencia_ingresso, data_ingresso, valor, mes_referencia)
SELECT texto_limpo(s.nome),
       NULLIF(btrim(s.cpf), ''),
       NULLIF(btrim(s.matricula), ''),
       'APOSENTADO',
       c.id,
       o.id,
       NULL,
       NULLIF(btrim(s.classe), ''), NULLIF(btrim(s.padrao), ''),
       NULLIF(btrim(s.referencia), ''), NULLIF(btrim(s.nivel), ''),
       texto_limpo(s.tipo_apos),
       texto_limpo(s.fund_legal),
       texto_limpo(s.portaria),
       data_segura(s.dt_inatividade),
       texto_limpo(s.nome_ocorrencia),
       data_segura(s.dt_ingresso),
       valor_seguro(s.valor),
       s.arquivo
FROM stg_aposentados s
LEFT JOIN cargos c ON c.nome = texto_limpo(s.cargo)
LEFT JOIN orgaos o ON o.nome = texto_limpo(s.orgao)
WHERE texto_limpo(s.nome) IS NOT NULL;
SQL

log "inserindo ativos"
"${PSQL[@]}" <<'SQL'
INSERT INTO servidores (nome, cpf, situacao, cargo_id, orgao_id, uf, codigo_carreira, valor, mes_referencia)
SELECT texto_limpo(s.nome),
       NULLIF(btrim(s.cpf), ''),
       'ATIVO',
       c.id,
       o.id,
       u.sigla,
       NULLIF(btrim(s.cod_carreira), ''),
       valor_seguro(s.valor),
       s.arquivo
FROM stg_carreira s
LEFT JOIN cargos c ON c.nome = texto_limpo(s.cargo)
LEFT JOIN orgaos o ON o.nome = texto_limpo(s.orgao)
LEFT JOIN ufs u ON u.sigla = upper(btrim(s.uf))
WHERE texto_limpo(s.nome) IS NOT NULL;

DROP TABLE stg_aposentados;
DROP TABLE stg_carreira;
SQL

"${PSQL[@]}" -At -c "SELECT 'servidores=' || count(*) || ' ativos=' || count(*) FILTER (WHERE situacao='ATIVO') || ' aposentados=' || count(*) FILTER (WHERE situacao='APOSENTADO') FROM servidores" \
  | while read -r l; do log "concluído: $l"; done
