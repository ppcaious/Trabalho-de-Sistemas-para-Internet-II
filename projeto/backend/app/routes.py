"""Rotas da API.

GET /api           -> descrição dos endpoints
GET /api/health    -> status da API e do banco
"""
from flask import Blueprint, jsonify

from . import db

bp = Blueprint("api", __name__)


@bp.get("")
@bp.get("/")
def indice():
    return jsonify({
        "endpoints": {
            "GET /api/health": "status da API e do banco",
            "GET /api/servidores": "busca de servidores (em desenvolvimento)",
        }
    })


@bp.get("/health")
def health():
    try:
        info = db.verificar()
    except Exception as exc:  # noqa: BLE001 - qualquer falha do banco vira 503
        return jsonify({"status": "degradado", "banco": "indisponivel", "detalhe": str(exc)[:200]}), 503
    return jsonify({
        "status": "ok",
        "banco": "ok",
        "total_servidores": info.get("total"),
        "ativos": info.get("ativos"),
        "aposentados": info.get("aposentados"),
        "pool": db.estatisticas_pool(),
    })
