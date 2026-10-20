"""Fábrica da aplicação Flask.

Uso: `from app import create_app; app = create_app()`
"""
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from . import db
from .ratelimit import LimitadorTaxa

# Limite de requisições por IP, compartilhado entre os workers do Gunicorn
limitador = LimitadorTaxa()


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.json.ensure_ascii = False  # acentos legíveis no JSON
    app.json.sort_keys = False     # mantém a ordem dos campos das respostas

    # O frontend (Nginx) faz proxy de /api; ProxyFix lê X-Forwarded-For para
    # que o rate limit seja por usuário final e não pelo IP do Nginx.
    # Como qualquer cliente que fale direto com a porta 8000 também poderia
    # enviar esse cabeçalho (e assim escapar do rate limit), o docker-compose
    # publica a 8000 apenas em 127.0.0.1; de fora, só se chega pelo Nginx.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    limitador.init_app(app)

    from .routes import bp
    app.register_blueprint(bp, url_prefix="/api")

    from .errors import registrar_handlers
    registrar_handlers(app)

    @app.get("/")
    def raiz():
        return jsonify({
            "aplicacao": "API de Servidores do Executivo Federal",
            "documentacao": "/api",
        })

    return app
