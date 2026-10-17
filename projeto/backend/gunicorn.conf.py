"""Configuração do Gunicorn (servidor WSGI).

Multi-processo + multi-thread: cada worker é um processo e cada processo
atende várias requisições em paralelo com threads (worker_class gthread).
Os valores podem ser ajustados por variáveis de ambiente no docker-compose.
"""
import multiprocessing
import os

bind = "0.0.0.0:8000"

# Nº de processos. Regra comum: 2*CPUs+1, limitado para não estourar a
# memória da máquina de avaliação.
workers = int(os.getenv("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 8)))

# Threads por processo (atende mais requisições simultâneas, útil porque a
# API passa a maior parte do tempo esperando o banco).
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", 8))

# Tempo máximo de uma requisição antes do worker ser reiniciado.
timeout = int(os.getenv("GUNICORN_TIMEOUT", 30))
graceful_timeout = 15
keepalive = 5

# Recicla workers periodicamente (evita vazamento de memória em execuções longas)
max_requests = 2000
max_requests_jitter = 200

# Logs no stdout/stderr para o `docker compose logs`
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Cada worker carrega a aplicação após o fork, assim cada processo cria o
# seu próprio pool de conexões com o banco (sockets não são compartilhados).
preload_app = False
