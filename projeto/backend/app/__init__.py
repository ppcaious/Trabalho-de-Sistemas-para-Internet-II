"""Fábrica da aplicação Flask.

Uso: `from app import create_app; app = create_app()`
"""
from flask import Flask, jsonify

from .config import Config
from . import db


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.json.ensure_ascii = False  # acentos legíveis no JSON

    db.init_app(app)

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
