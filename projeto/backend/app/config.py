"""Configuração da API lida de variáveis de ambiente (definidas no docker-compose)."""
import os


def _int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, padrao))
    except ValueError:
        return padrao


class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://app:app@localhost:5432/servidores")

    # Pool de conexões com o banco (por processo do Gunicorn)
    POOL_MAX = _int("POOL_MAX", 16)
    POOL_MIN = min(_int("POOL_MIN", 4), POOL_MAX)

    # Limites de paginação / similaridade
    MAX_LIMIT = _int("MAX_LIMIT", 100)        # ?limit= máximo na busca por similaridade
    MAX_PER_PAGE = _int("MAX_PER_PAGE", 100)  # ?per_page= máximo
    DEFAULT_PER_PAGE = _int("DEFAULT_PER_PAGE", 20)

    # Tamanho máximo aceito para parâmetros textuais
    MAX_PARAM_LEN = _int("MAX_PARAM_LEN", 80)

    JSON_SORT_KEYS = False
