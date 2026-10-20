"""Limitador de requisições por cliente (rate limit), compartilhado entre os
processos do Gunicorn.

Por que não um contador em memória? O Gunicorn roda vários processos
(workers); um contador em memória seria por processo e o limite real ficaria
multiplicado pelo nº de workers. Aqui o contador fica num SQLite local do
contêiner (modo WAL), que todos os workers enxergam, sem precisar de um
serviço extra como Redis.

Algoritmo: janela fixa. Para cada IP conta-se quantas requisições chegaram na
janela atual (ex.: 300 por 60 s). Passou do limite -> HTTP 429 com o tempo
até a janela reabrir. As respostas levam os cabeçalhos X-RateLimit-*.
"""
import random
import re
import sqlite3
import threading
import time
from functools import wraps

from flask import g, request

from .errors import ErroAPI

_PERIODOS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


class LimitadorTaxa:
    def __init__(self):
        self.maximo = 300
        self.segundos = 60
        self.caminho = "/tmp/api_ratelimit.sqlite"
        self._local = threading.local()

    # ------------------------------------------------------------------ setup
    def init_app(self, app):
        self.maximo, self.segundos = self._interpretar(app.config.get("RATE_LIMIT", "300/minute"))
        self.caminho = app.config.get("RATE_LIMIT_DB", self.caminho)
        with self._conexao() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS janelas ("
                " chave TEXT NOT NULL, janela INTEGER NOT NULL, n INTEGER NOT NULL,"
                " PRIMARY KEY (chave, janela))"
            )
        app.after_request(self._cabecalhos)
        app.extensions["limitador"] = self

    @staticmethod
    def _interpretar(texto: str) -> tuple[int, int]:
        """'120/minute' -> (120, 60); '10 per second' -> (10, 1)."""
        m = re.fullmatch(r"\s*(\d+)\s*(?:/|per)\s*(\d+)?\s*(second|minute|hour|day)s?\s*", texto)
        if not m:
            raise ValueError(f"RATE_LIMIT inválido: {texto!r} (ex.: '120/minute')")
        return int(m.group(1)), int(m.group(2) or 1) * _PERIODOS[m.group(3)]

    def _conexao(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.caminho, timeout=2, isolation_level=None, check_same_thread=False)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=OFF")
            self._local.conn = c
        return c

    # ------------------------------------------------------------------ núcleo
    def registrar(self, chave: str) -> tuple[bool, int, int]:
        """Conta uma requisição. Devolve (permitido, restantes, segundos_para_reabrir)."""
        agora = int(time.time())
        janela = agora - agora % self.segundos
        c = self._conexao()
        try:
            n = c.execute(
                "INSERT INTO janelas (chave, janela, n) VALUES (?, ?, 1) "
                "ON CONFLICT (chave, janela) DO UPDATE SET n = n + 1 RETURNING n",
                (chave, janela),
            ).fetchone()[0]
            if random.random() < 0.01:  # limpeza ocasional de janelas antigas
                c.execute("DELETE FROM janelas WHERE janela < ?", (janela - self.segundos,))
        except sqlite3.OperationalError:
            # Banco local travado por mais de 2 s: não derruba a API, apenas deixa passar.
            return True, self.maximo, self.segundos
        return n <= self.maximo, max(0, self.maximo - n), janela + self.segundos - agora

    def limitar(self, func):
        """Decorator de rota: aplica o limite por IP do cliente."""

        @wraps(func)
        def envolto(*args, **kwargs):
            ip = request.remote_addr or "desconhecido"
            permitido, restantes, reabre = self.registrar(ip)
            g.ratelimit = (restantes, reabre)
            if not permitido:
                raise ErroAPI(
                    429,
                    "Excesso de requisições. Aguarde um instante e tente novamente.",
                    {"limite": f"{self.maximo} requisições a cada {self.segundos} s", "tente_em_s": reabre},
                )
            return func(*args, **kwargs)

        return envolto

    def _cabecalhos(self, resposta):
        info = g.pop("ratelimit", None)
        if info:
            resposta.headers["X-RateLimit-Limit"] = str(self.maximo)
            resposta.headers["X-RateLimit-Remaining"] = str(info[0])
            resposta.headers["X-RateLimit-Reset"] = str(info[1])
            if resposta.status_code == 429:
                resposta.headers["Retry-After"] = str(info[1])
        return resposta
