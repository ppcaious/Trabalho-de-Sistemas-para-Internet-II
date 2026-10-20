"""Configuração da API lida de variáveis de ambiente (definidas no docker-compose)."""
import os


def _int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, padrao))
    except ValueError:
        return padrao


class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://app:app@localhost:5432/servidores")

    # Tempo máximo de uma consulta SQL (ms). Acima disso o Postgres cancela e a
    # API responde 504.
    STATEMENT_TIMEOUT_MS = _int("STATEMENT_TIMEOUT_MS", 5000)

    # Pool de conexões. Se todas estiverem ocupadas por mais de POOL_TIMEOUT_S
    # segundos, a API responde 503 (servidor ocupado) em vez de travar.
    POOL_MAX = _int("POOL_MAX", 16)
    POOL_MIN = min(_int("POOL_MIN", 4), POOL_MAX)
    POOL_TIMEOUT_S = float(os.getenv("POOL_TIMEOUT_S", "5"))

    # Limite de requisições por cliente (app/ratelimit.py). Ex.: "300/minute".
    RATE_LIMIT = os.getenv("RATE_LIMIT", "300/minute")

    # Limites de paginação / similaridade
    MAX_LIMIT = _int("MAX_LIMIT", 100)        # ?limit= máximo na busca por similaridade
    MAX_PER_PAGE = _int("MAX_PER_PAGE", 100)  # ?per_page= máximo
    DEFAULT_PER_PAGE = _int("DEFAULT_PER_PAGE", 20)

    # Tamanho máximo aceito para parâmetros textuais
    MAX_PARAM_LEN = _int("MAX_PARAM_LEN", 80)
