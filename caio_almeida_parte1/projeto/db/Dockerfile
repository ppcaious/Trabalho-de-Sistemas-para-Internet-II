FROM postgres:16-alpine

# Os scripts em /docker-entrypoint-initdb.d são executados em ordem
# alfabética apenas na PRIMEIRA inicialização do volume de dados:
#   01_schema.sql    -> extensões (pg_trgm, unaccent), tabelas e funções
#   20_importar.sh   -> lê os arquivos de /dados (CSV/TXT do dados.gov.br)
#   30_indices.sql   -> índices btree e GIN (pg_trgm) + ANALYZE
COPY init/ /docker-entrypoint-initdb.d/
# (find em vez de *.sh para não falhar enquanto ainda não existe script .sh)
RUN find /docker-entrypoint-initdb.d -name '*.sh' -exec chmod +x {} +

# Ajustes de desempenho razoáveis para uma máquina de desenvolvimento.
# statement_timeout protege o banco de consultas que travariam o servidor.
CMD ["postgres", \
     "-c", "shared_buffers=256MB", \
     "-c", "work_mem=32MB", \
     "-c", "maintenance_work_mem=256MB", \
     "-c", "max_connections=100", \
     "-c", "statement_timeout=10000", \
     "-c", "idle_in_transaction_session_timeout=30000"]
