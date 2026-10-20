"""Tratamento centralizado de erros: toda resposta de erro é JSON com código HTTP adequado.

Códigos usados:
  400 - parâmetro inválido (string inválida, UF inválida, possível SQL injection...)
  404 - nada encontrado (nome, cargo, órgão, página inexistente, rota inexistente)
  405 - método não permitido
  429 - excesso de requisições do mesmo cliente (rate limit)
  503 - banco indisponível ou pool de conexões esgotado (excesso de buscas simultâneas)
  504 - consulta excedeu o tempo limite (statement_timeout)
  500 - erro inesperado
"""
import logging

import psycopg
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

from .db import BancoOcupado

log = logging.getLogger(__name__)


class ErroAPI(Exception):
    """Erro de negócio/validação que vira uma resposta JSON."""

    def __init__(self, status: int, mensagem: str, detalhes=None):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem
        self.detalhes = detalhes


def resposta_erro(status: int, mensagem: str, detalhes=None):
    corpo = {"erro": mensagem, "status": status, "caminho": request.path}
    if detalhes is not None:
        corpo["detalhes"] = detalhes
    return jsonify(corpo), status


def registrar_handlers(app):
    @app.errorhandler(ErroAPI)
    def _erro_api(e: ErroAPI):
        return resposta_erro(e.status, e.mensagem, e.detalhes)

    @app.errorhandler(404)
    def _nao_encontrado(e):
        return resposta_erro(404, "Rota não encontrada", {"dica": "A API fica em /api/servidores"})

    @app.errorhandler(405)
    def _metodo(e):
        return resposta_erro(405, "Método não permitido")

    @app.errorhandler(BancoOcupado)
    def _ocupado(e):
        return resposta_erro(
            503,
            "Servidor ocupado: muitas buscas simultâneas. Tente novamente em alguns segundos.",
        )

    @app.errorhandler(psycopg.errors.QueryCanceled)
    def _timeout(e):
        return resposta_erro(
            504,
            "A busca excedeu o tempo limite. Refine os filtros e tente novamente.",
            {"timeout_ms": app.config["STATEMENT_TIMEOUT_MS"]},
        )

    @app.errorhandler(psycopg.OperationalError)
    def _banco_indisponivel(e):
        log.error("Banco indisponível: %s", e)
        return resposta_erro(503, "Banco de dados indisponível no momento.")

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        return resposta_erro(e.code or 500, e.name)

    @app.errorhandler(Exception)
    def _inesperado(e):
        log.exception("Erro inesperado")
        return resposta_erro(500, "Erro interno inesperado.")
