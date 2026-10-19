#!/bin/bash
# ============================================================================
# Baixa as bases COMPLETAS do dados.gov.br para ./db/data e remove as amostras.
#
# Por padrão o repositório traz apenas uma AMOSTRA (~47 mil registros) para o
# `docker compose up --build` ficar rápido. Com as bases completas são
# ~1,5 milhão de registros (~370 MB) e a primeira subida leva alguns minutos.
#
# Uso (na pasta projeto/):   bash db/scripts/baixar_dados_completos.sh
# Depois:                    docker compose down -v && docker compose up --build
#   (o -v apaga o volume do banco para a importação rodar de novo)
# ============================================================================
set -euo pipefail

BASE="https://repositorio.dados.gov.br/segrt"
APOS="${APOS:-Aposentados/2026/APOSENTADOS_052026_FULL.csv}"
CARR="${CARR:-Cargos%20e%20Carreiras/2026/CARREIRA_082026.txt}"

DIR="$(cd "$(dirname "$0")/.." && pwd)/data"
mkdir -p "$DIR"

echo "Baixando aposentados (~170 MB)..."
curl -L --progress-bar -A "Mozilla/5.0" -o "$DIR/APOSENTADOS_052026_FULL.csv" "$BASE/$APOS"

echo "Baixando carreiras/cargos - ativos (~200 MB)..."
curl -L --progress-bar -A "Mozilla/5.0" -o "$DIR/CARREIRA_082026.txt" "$BASE/$CARR"

echo "Removendo amostras..."
rm -f "$DIR"/*_amostra.*

echo "Pronto. Agora rode: docker compose down -v && docker compose up --build"
