"""Tratamento centralizado de erros: toda resposta de erro é JSON com código HTTP adequado."""
import logging

import psycopg
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

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
