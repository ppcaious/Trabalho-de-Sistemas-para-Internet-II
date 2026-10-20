"""Acesso ao PostgreSQL com pool de conexões (psycopg 3).

- Todas as consultas usam parâmetros (%(nome)s), nunca concatenação de
  strings: é isso que impede SQL injection.
- Cada conexão é aberta com statement_timeout, então uma consulta lenta é
  cancelada pelo próprio banco e vira um erro tratado (504).
- O pool tem tamanho máximo; se estiver esgotado por mais de POOL_TIMEOUT_S
  segundos a requisição recebe 503 em vez de enfileirar sem fim.
"""
import threading
from contextlib import contextmanager

from flask import current_app
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

_pool: ConnectionPool | None = None
_pool_aberto = False
_lock = threading.Lock()


def init_app(app):
    global _pool
    cfg = app.config
    _pool = ConnectionPool(
        conninfo=cfg["DATABASE_URL"],
        min_size=cfg["POOL_MIN"],
        max_size=cfg["POOL_MAX"],
        timeout=cfg["POOL_TIMEOUT_S"],
        kwargs={
            "row_factory": dict_row,
            "options": f"-c statement_timeout={cfg['STATEMENT_TIMEOUT_MS']}",
            "application_name": "api-servidores",
        },
        open=False,
    )
    # O pool é aberto de forma preguiçosa na primeira consulta de cada
    # processo do Gunicorn (abrir antes do fork compartilharia sockets).


def _abrir_pool():
    global _pool_aberto
    if _pool_aberto:
        return
    with _lock:
        if not _pool_aberto:
            _pool.open(wait=False)
            _pool_aberto = True


class BancoOcupado(Exception):
    """Pool de conexões esgotado (excesso de buscas simultâneas)."""


@contextmanager
def conexao():
    """Entrega uma conexão do pool e devolve ao final (commit/rollback automático)."""
    _abrir_pool()
    try:
        with _pool.connection() as conn:
            yield conn
    except PoolTimeout as exc:
        raise BancoOcupado() from exc


def consultar(sql: str, params: dict | None = None) -> list[dict]:
    """Executa um SELECT parametrizado e devolve a lista de linhas (dicts)."""
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchall()


def consultar_um(sql: str, params: dict | None = None) -> dict | None:
    linhas = consultar(sql, params)
    return linhas[0] if linhas else None


def verificar() -> dict:
    """Usado pelo /api/health: confirma que o banco responde e quantos registros tem.

    Uma única passagem pela tabela (count com FILTER) em vez de três subconsultas.
    """
    linha = consultar_um(
        "SELECT count(*) AS total, "
        "       count(*) FILTER (WHERE situacao = 'ATIVO') AS ativos, "
        "       count(*) FILTER (WHERE situacao = 'APOSENTADO') AS aposentados, "
        "       current_setting('statement_timeout') AS statement_timeout "
        "FROM servidores"
    )
    return linha or {}


def estatisticas_pool() -> dict:
    if _pool is None:
        return {}
    st = _pool.get_stats()
    return {
        "tamanho": st.get("pool_size"),
        "disponiveis": st.get("pool_available"),
        "aguardando": st.get("requests_waiting"),
        "max": current_app.config["POOL_MAX"],
    }
