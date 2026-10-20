"""Teste de sobrecarga paralela da API (sem dependências externas).

Dispara N requisições simultâneas por rodada e mede latência e códigos de
resposta. Serve para encontrar o ponto em que a API começa a responder 429
(rate limit), 503 (pool esgotado) ou 504 (timeout) em vez de travar.

Uso:
    python teste_carga.py --url http://localhost:8000 --concorrencia 50 --total 500

Para um teste mais completo com gráficos, use o locust (locustfile.py).
"""
import argparse
import random
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

CONSULTAS = [
    {"uf": "DF"},
    {"uf": "RS", "per_page": 50},
    {"cargo": "ANALISTA"},
    {"cargo": "AUDITOR", "uf": "SP"},
    {"orgao": "UNIVERSIDADE"},
    {"orgao": "MINISTERIO", "uf": "DF", "page": 2},
    {"similar": "%MARIA%SILVA%", "limit": 100},
    {"similar": "JOSE%", "limit": 50},
    {"situacao": "APOSENTADO", "per_page": 100},
    {"nome": "JOAO DA SILVA"},
]


def requisitar(base: str, params: dict):
    url = f"{base}/api/servidores?{urllib.parse.urlencode(params)}"
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:  # noqa: BLE001
        status = 0  # conexão recusada / timeout do cliente
    return status, (time.perf_counter() - inicio) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--concorrencia", type=int, default=50, help="requisições simultâneas")
    ap.add_argument("--total", type=int, default=500, help="total de requisições")
    args = ap.parse_args()

    print(f"Alvo: {args.url}  concorrência={args.concorrencia}  total={args.total}")
    codigos: Counter = Counter()
    latencias: list[float] = []
    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concorrencia) as ex:
        futs = [ex.submit(requisitar, args.url, random.choice(CONSULTAS)) for _ in range(args.total)]
        for f in as_completed(futs):
            status, ms = f.result()
            codigos[status] += 1
            latencias.append(ms)
    duracao = time.perf_counter() - inicio

    latencias.sort()
    p = lambda q: latencias[min(len(latencias) - 1, int(len(latencias) * q))]  # noqa: E731
    print(f"\nDuração total: {duracao:.1f}s  ->  {args.total / duracao:.1f} req/s")
    print("Códigos de resposta:")
    nomes = {200: "OK", 404: "não encontrado", 400: "parâmetro inválido", 429: "rate limit",
             503: "servidor ocupado", 504: "timeout da consulta", 0: "falha de conexão"}
    for c, n in sorted(codigos.items()):
        print(f"  {c:>3} {nomes.get(c, ''):<20} {n:>6}")
    print(f"Latência (ms): média={statistics.mean(latencias):.0f}  p50={p(.5):.0f}  p90={p(.9):.0f}  p99={p(.99):.0f}  max={latencias[-1]:.0f}")
    falhas = codigos[0]
    print("\nResultado:", "API respondeu a todas as requisições (sem colapso)." if falhas == 0 else f"{falhas} conexões falharam.")


if __name__ == "__main__":
    main()
