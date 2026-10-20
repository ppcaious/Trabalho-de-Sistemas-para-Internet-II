"""Teste de carga com Locust.

    pip install locust
    locust -f locustfile.py --host http://localhost:8000
    # abra http://localhost:8089, defina usuários e taxa de criação

Modo sem interface:
    locust -f locustfile.py --host http://localhost:8000 --headless -u 100 -r 20 -t 60s
"""
import random

from locust import HttpUser, between, task

PADROES = ["%MARIA%SILVA%", "JOSE%", "%SANTOS", "ANA%SOUZA%", "%OLIVEIRA%"]
CARGOS = ["ANALISTA", "AUDITOR", "TECNICO", "PROFESSOR", "AGENTE"]
UFS = ["DF", "RS", "SP", "RJ", "MG", "BA", "PE"]
ORGAOS = ["UNIVERSIDADE", "MINISTERIO", "INSTITUTO", "FUNDACAO"]


class Usuario(HttpUser):
    wait_time = between(0.1, 1.0)

    @task(3)
    def por_uf(self):
        self.client.get("/api/servidores", params={"uf": random.choice(UFS), "per_page": 20}, name="/api/servidores?uf")

    @task(3)
    def por_cargo(self):
        self.client.get("/api/servidores", params={"cargo": random.choice(CARGOS)}, name="/api/servidores?cargo")

    @task(2)
    def combinada(self):
        self.client.get("/api/servidores", params={"orgao": random.choice(ORGAOS), "uf": random.choice(UFS)}, name="/api/servidores?orgao&uf")

    @task(2)
    def similar(self):
        self.client.get("/api/servidores", params={"similar": random.choice(PADROES), "limit": 100}, name="/api/servidores?similar")

    @task(1)
    def health(self):
        self.client.get("/api/health")
