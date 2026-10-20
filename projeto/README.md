# Servidores do Executivo Federal — aplicação full stack

Trabalho do 3º bimestre de **Sistemas para Internet II**. Aplicação para
consultar servidores **ativos** e **aposentados** do Poder Executivo Federal
a partir das bases abertas do [dados.gov.br](https://dados.gov.br), com
busca por nome (exata e por similaridade), cargo, UF, órgão e combinações,
resultados paginados em JSON.

| Contêiner | Tecnologia | Porta |
|---|---|---|
| `db` (db-server) | PostgreSQL 16 + pg_trgm | 5432 |
| `backend` | Python 3.12 · Flask · Gunicorn (WSGI, multi-worker/thread) | 8000 |
| `frontend` | HTML/CSS/JS puro servido pelo Nginx (proxy `/api` → backend) | 8080 |

Adicional: aplicação **desktop** em tkinter (`desktop/`), fora do Docker.

## Como executar

Pré-requisito: Docker com o plugin Compose.

```bash
cd projeto
docker compose up --build
```

Na primeira execução o banco é criado e os arquivos de `db/data/` são
importados (≈20 s com a amostra). Depois:

- Interface web: <http://localhost:8080>
- API: <http://localhost:8000/api> (documentação dos endpoints em JSON)
- Saúde: <http://localhost:8000/api/health>

Para parar: `docker compose down`. Para apagar o banco e reimportar:
`docker compose down -v`.

### Base completa

O repositório traz uma **amostra** (~47 mil registros) para a subida ser
rápida. Para usar as bases completas (~1,5 milhão de registros):

```bash
bash db/scripts/baixar_dados_completos.sh
docker compose down -v && docker compose up --build
```

## Estrutura

```
projeto/
├── docker-compose.yml        # orquestra db, backend e frontend
├── backend/                  # API Flask + Gunicorn
│   ├── Dockerfile
│   ├── gunicorn.conf.py      # workers/threads/timeouts
│   ├── wsgi.py               # entrada WSGI
│   ├── app/
│   │   ├── __init__.py       # fábrica da aplicação
│   │   ├── config.py         # variáveis de ambiente
│   │   ├── db.py             # pool de conexões, statement_timeout
│   │   ├── validators.py     # validação dos parâmetros
│   │   ├── ratelimit.py      # limite de requisições por IP
│   │   ├── errors.py         # respostas de erro em JSON
│   │   └── routes.py         # endpoints
│   ├── tests/test_api.py     # testes de integração (pytest)
│   └── loadtest/             # teste de sobrecarga (locust e script simples)
├── db/                       # PostgreSQL
│   ├── Dockerfile
│   ├── init/01_schema.sql    # extensões, tabelas, funções de limpeza
│   ├── init/20_importar.sh   # importação automática dos CSV/TXT
│   ├── init/30_indices.sql   # índices btree + GIN (pg_trgm)
│   ├── data/                 # arquivos do dados.gov.br (amostra)
│   └── scripts/baixar_dados_completos.sh
├── frontend/                 # Nginx + página estática
│   ├── Dockerfile
│   ├── nginx.conf
│   └── public/ (index.html, style.css, app.js)
└── desktop/app_desktop.py    # aplicação desktop (tkinter) - adicional
```

## API

Base: `http://localhost:8000/api`

| Endpoint | Descrição |
|---|---|
| `GET /health` | status da API, do banco e do pool |
| `GET /servidores` | busca (parâmetros abaixo) |
| `GET /servidores/{id}` | um registro |
| `GET /cargos?q=` | cargos existentes (autocompletar) |
| `GET /orgaos?q=` | órgãos existentes (autocompletar) |
| `GET /ufs` | UFs válidas |
| `GET /estatisticas` | totais por situação e por UF |

### `GET /servidores`

| Parâmetro | Descrição |
|---|---|
| `nome` | busca **exata** pelo nome completo (ignora acentos/maiúsculas) |
| `similar` | busca por **similaridade**; `%` é curinga: `%MARIA%SILVA%`, `JOAO SILVA%`, `%SILVA`. Sem `%` procura em qualquer posição |
| `limit` | nº máximo de nomes similares (1–100, padrão 100) |
| `cargo` | cargo/profissão (busca parcial) |
| `uf` | unidade federativa (ex.: `RS`) |
| `orgao` | instituição/órgão (busca parcial, aceita sigla) |
| `situacao` | `ATIVO` ou `APOSENTADO` |
| `page`, `per_page` | paginação (per_page 1–100, padrão 20) |

Os filtros podem ser combinados. Exemplos:

```
/api/servidores?cargo=AUDITOR
/api/servidores?uf=RS
/api/servidores?orgao=UNIVERSIDADE&uf=RS
/api/servidores?nome=MARIA%20DA%20SILVA&cargo=PROFESSOR
/api/servidores?similar=%25MARIA%25SILVA%25&limit=100
/api/servidores?cargo=ANALISTA&uf=DF&page=2&per_page=50
```

Resposta:

```json
{
  "total": 598, "page": 2, "per_page": 2, "total_paginas": 299,
  "registro_unico": false,
  "filtros": {"orgao": "UNIVERSIDADE", "uf": "RS", "limit": 100},
  "itens": [
    {"id": 1234, "nome": "ADENIR SOARES DE OLIVEIRA", "cpf": "***123456**",
     "situacao": "ATIVO", "cargo": "MARCENEIRO",
     "orgao": "UNIVERSIDADE FEDERAL DO RIO GRANDE DO SUL", "orgao_sigla": null,
     "uf": "RS", "valor": 4523.38, "mes_referencia": "08/2026", "...": "..."}
  ]
}
```

### Tratamento de erros (sempre JSON)

| Situação | HTTP |
|---|---|
| parâmetro desconhecido, string inválida, UF inválida, número inválido, sem critério | 400 |
| tentativa de SQL injection (`' OR 1=1 --`, `UNION SELECT`…) | 400 |
| nome não encontrado, cargo/órgão inexistente, página inexistente, id inexistente | 404 |
| método não permitido | 405 |
| excesso de requisições do mesmo cliente (padrão 300/min) | 429 |
| pool de conexões esgotado (excesso de buscas simultâneas) ou banco fora | 503 |
| consulta excedeu o `statement_timeout` (padrão 5 s) | 504 |

Nome com vários registros → lista paginada; com um registro → `registro_unico: true`.

## Mecanismos de proteção

- **SQL injection**: todas as consultas são parametrizadas (psycopg), e os
  parâmetros ainda passam por validação de caracteres e de padrões SQL.
- **Timeout**: cada conexão abre com `statement_timeout`; consulta lenta é
  cancelada pelo Postgres e vira 504.
- **Excesso de buscas simultâneas**: pool de conexões limitado (`POOL_MAX`);
  se não houver conexão livre em `POOL_TIMEOUT_S` segundos a API responde 503
  em vez de enfileirar. Rate limit por IP compartilhado entre os workers do
  Gunicorn (SQLite local), com cabeçalhos `X-RateLimit-*` e `Retry-After`.
  A porta 8000 é publicada só em `127.0.0.1`: de fora, a API é acessada pelo
  Nginx, que informa o IP real do cliente (`X-Forwarded-For`), impedindo que
  alguém forje o cabeçalho para escapar do limite (`API_BIND=0.0.0.0` expõe).
- **Gunicorn**: `WEB_CONCURRENCY` processos × `GUNICORN_THREADS` threads,
  `timeout` de 30 s e reciclagem de workers.

Todos os valores podem ser ajustados por variáveis de ambiente (ver
`docker-compose.yml`), por exemplo `RATE_LIMIT=60/minute docker compose up`.

## Testes

```bash
# testes de integração (API no ar)
pip install pytest requests
BASE_URL=http://localhost:8000 pytest -v backend/tests

# sobrecarga paralela (sem dependências)
python backend/loadtest/teste_carga.py --concorrencia 100 --total 1000

# locust (interface em http://localhost:8089)
pip install locust && locust -f backend/loadtest/locustfile.py --host http://localhost:8000
```

## Equipe

| Integrante | Responsabilidade |
|---|---|
| Thiago Neves (líder técnico) | backend/API Flask + Gunicorn, validação, proteção, testes de carga, relatório |
| Caio Almeida de Souza | banco de dados PostgreSQL, tratamento e importação dos dados, índices, infra Docker |
| Caio Neves Ferreira | frontend web, integração com a API, aplicação desktop |
