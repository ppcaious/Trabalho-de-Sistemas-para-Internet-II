"""Ponto de entrada WSGI usado pelo Gunicorn: `gunicorn wsgi:app`."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Execução direta (desenvolvimento, sem Gunicorn): python wsgi.py
    app.run(host="0.0.0.0", port=8000, debug=True)
