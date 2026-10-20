"""Testes de integração da API (rodam contra a aplicação no ar).

Uso:
    cd projeto/backend
    pip install pytest requests
    BASE_URL=http://localhost:8000 pytest -v tests/

Cobrem os cenários exigidos no enunciado: strings inválidas, SQL injection,
nome não encontrado, múltiplos registros (paginação), cargo/UF/órgão
inválidos, página inexistente, parâmetros inválidos e rate limit.
"""
import os
import time

import pytest
import requests

BASE = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
API = BASE + "/api"


def get(caminho, **params):
    return requests.get(API + caminho, params=params, timeout=15)


def _aguardar_rate_limit():
    """Se uma execução anterior (test_rate_limit) esgotou a cota deste IP,
    espera a janela reabrir para os outros testes não receberem 429."""
    r = get("/servidores", uf="DF", per_page=1)
    if r.status_code == 429:
        espera = int(r.headers.get("Retry-After", "60")) + 1
        print(f"\nrate limit ativo de execução anterior; aguardando {espera}s")
        time.sleep(espera)


@pytest.fixture(scope="session", autouse=True)
def api_no_ar():
    for _ in range(30):
        try:
            if requests.get(API + "/health", timeout=3).status_code == 200:
                _aguardar_rate_limit()
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    pytest.fail("API não respondeu em /api/health")


@pytest.fixture(scope="session")
def amostra():
    """Um servidor qualquer da base, para montar buscas que existem."""
    r = get("/servidores", uf="DF", per_page=1)
    if r.status_code != 200:
        r = get("/servidores", situacao="APOSENTADO", per_page=1)
    assert r.status_code == 200, r.text
    return r.json()["itens"][0]


# --- saúde e documentação ----------------------------------------------------
def test_health():
    r = get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok" and d["banco"] == "ok"
    assert d["total_servidores"] > 0


def test_indice_documenta_endpoints():
    d = get("").json()
    assert "GET /api/servidores" in d["endpoints"]


# --- buscas que funcionam ----------------------------------------------------
def test_busca_por_nome_exato(amostra):
    r = get("/servidores", nome=amostra["nome"])
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
    assert all(i["nome"] == amostra["nome"] for i in d["itens"])


def test_nome_ignora_acentos_e_caixa(amostra):
    nome = amostra["nome"].lower()
    r = get("/servidores", nome=nome)
    assert r.status_code == 200


def test_busca_por_similaridade(amostra):
    partes = amostra["nome"].split()
    padrao = f"%{partes[0]}%{partes[-1]}%"
    r = get("/servidores", similar=padrao, limit=10)
    assert r.status_code == 200
    d = r.json()
    assert 1 <= d["total"] <= 10
    assert "similaridade" in d["itens"][0]


def test_similar_sem_curinga_procura_em_qualquer_posicao(amostra):
    r = get("/servidores", similar=amostra["nome"].split()[0])
    assert r.status_code == 200


def test_busca_por_cargo(amostra):
    r = get("/servidores", cargo=amostra["cargo"].split()[0])
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_busca_por_uf():
    r = get("/servidores", uf="df")
    assert r.status_code == 200
    assert all(i["uf"] == "DF" for i in r.json()["itens"])


def test_busca_por_orgao(amostra):
    r = get("/servidores", orgao=amostra["orgao"].split()[0])
    assert r.status_code == 200


def test_busca_combinada(amostra):
    r = get("/servidores", cargo=amostra["cargo"].split()[0], uf=amostra["uf"] or "DF")
    assert r.status_code in (200, 404)


def test_paginacao():
    r1 = get("/servidores", situacao="ATIVO", per_page=5, page=1)
    r2 = get("/servidores", situacao="ATIVO", per_page=5, page=2)
    assert r1.status_code == r2.status_code == 200
    d1, d2 = r1.json(), r2.json()
    assert d1["page"] == 1 and d2["page"] == 2
    assert len(d1["itens"]) == 5
    assert d1["total_paginas"] == -(-d1["total"] // 5)
    assert [i["id"] for i in d1["itens"]] != [i["id"] for i in d2["itens"]]


def test_registro_unico_por_id(amostra):
    r = get(f"/servidores/{amostra['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == amostra["id"]


@pytest.mark.parametrize("limit", ["0", "abc", "500"])
def test_cargos_limit_invalido(limit):
    r = get("/cargos", q="AN", limit=limit)
    assert r.status_code == 400


def test_listas_auxiliares():
    assert get("/ufs").status_code == 200
    assert len(get("/ufs").json()["itens"]) == 27
    assert get("/cargos", q="AN").status_code == 200
    assert get("/orgaos", q="MIN").status_code == 200
    assert get("/estatisticas").status_code == 200


# --- tratamento de erros -----------------------------------------------------
def test_nome_nao_encontrado():
    r = get("/servidores", nome="FULANO INEXISTENTE XYZ")
    assert r.status_code == 404
    assert "não encontrado" in r.json()["erro"].lower()


def test_cargo_invalido():
    r = get("/servidores", cargo="CARGOQUENAOEXISTE")
    assert r.status_code == 404
    assert "cargo" in r.json()["erro"].lower()


def test_orgao_invalido():
    r = get("/servidores", orgao="ORGAOQUENAOEXISTE")
    assert r.status_code == 404


@pytest.mark.parametrize("uf", ["XX", "D", "RSS", "12"])
def test_uf_invalida(uf):
    r = get("/servidores", uf=uf)
    assert r.status_code == 400
    assert "uf" in r.json()["erro"].lower()


def test_pagina_inexistente():
    r = get("/servidores", situacao="ATIVO", per_page=100, page=999999)
    assert r.status_code == 404
    assert "página" in r.json()["erro"].lower()


@pytest.mark.parametrize("params", [
    {"page": "abc"}, {"page": "0"}, {"per_page": "1000"}, {"limit": "0"}, {"limit": "-5"},
])
def test_parametros_numericos_invalidos(params):
    r = get("/servidores", situacao="ATIVO", **params)
    assert r.status_code == 400


def test_parametro_desconhecido():
    r = get("/servidores", nomee="X")
    assert r.status_code == 400
    assert "inválido" in r.json()["erro"].lower()


def test_sem_criterio():
    r = get("/servidores")
    assert r.status_code == 400


def test_nome_e_similar_juntos():
    r = get("/servidores", nome="A", similar="A")
    assert r.status_code == 400


@pytest.mark.parametrize("valor", [
    "' OR 1=1 --", "'; DROP TABLE servidores; --", "MARIA UNION SELECT 1", "x\"); SELECT pg_sleep(10); --",
])
def test_sql_injection_bloqueado(valor):
    r = get("/servidores", nome=valor)
    assert r.status_code == 400
    # e a base continua íntegra
    assert get("/health").json()["total_servidores"] > 0


@pytest.mark.parametrize("valor", ["<script>", "\x00abc", "a" * 200, "   ", "nome=ç§"])
def test_strings_invalidas(valor):
    r = get("/servidores", nome=valor)
    assert r.status_code == 400


def test_rota_inexistente_retorna_json():
    r = requests.get(API + "/nao-existe", timeout=10)
    assert r.status_code == 404
    assert r.headers["Content-Type"].startswith("application/json")


def test_metodo_nao_permitido():
    r = requests.post(API + "/servidores", timeout=10)
    assert r.status_code == 405


def test_rate_limit():
    """Dispara mais requisições que o limite por minuto e espera um 429."""
    codigos = set()
    for _ in range(500):
        codigos.add(get("/servidores", uf="DF", per_page=1).status_code)
        if 429 in codigos:
            break
    assert 429 in codigos, "rate limit não foi acionado"
