"""Rotas da API.

GET /api                      -> descrição dos endpoints
GET /api/health               -> status da API e do banco
GET /api/servidores           -> busca com filtros, similaridade e paginação
GET /api/servidores/<id>      -> um registro
GET /api/cargos?q=            -> lista de cargos (autocompletar)
GET /api/orgaos?q=            -> lista de órgãos (autocompletar)
GET /api/ufs                  -> lista de UFs válidas
GET /api/estatisticas         -> totais por situação / UF
"""
import math

from flask import Blueprint, current_app, jsonify, request

from . import db, limitador
from .errors import ErroAPI
from .validators import UFS, validar_busca, validar_inteiro, validar_texto_simples

bp = Blueprint("api", __name__)

# Colunas devolvidas em cada registro de servidor
_COLUNAS = """
    s.id, s.nome, s.cpf, s.matricula, s.situacao,
    c.nome AS cargo, o.nome AS orgao, o.sigla AS orgao_sigla, s.uf,
    s.codigo_carreira, s.classe, s.padrao, s.referencia, s.nivel,
    s.tipo_aposentadoria, s.fundamento_legal, s.diploma_legal,
    s.data_inatividade, s.ocorrencia_ingresso, s.data_ingresso,
    s.valor, s.mes_referencia
"""
_FROM = """
    FROM servidores s
    LEFT JOIN cargos c ON c.id = s.cargo_id
    LEFT JOIN orgaos o ON o.id = s.orgao_id
"""


def _serializar(linha: dict) -> dict:
    """Converte tipos do Postgres (Decimal, date) para JSON."""
    r = dict(linha)
    for k in ("data_inatividade", "data_ingresso"):
        if r.get(k) is not None:
            r[k] = r[k].isoformat()
    if r.get("valor") is not None:
        r["valor"] = float(r["valor"])
    return r


# ---------------------------------------------------------------------------
@bp.get("")
@bp.get("/")
def indice():
    return jsonify({
        "endpoints": {
            "GET /api/health": "status da API e do banco",
            "GET /api/servidores": {
                "descricao": "busca de servidores ativos e aposentados",
                "parametros": {
                    "nome": "busca exata pelo nome completo (ignora acentos/maiúsculas)",
                    "similar": "busca por similaridade, aceita %: ?similar=%JOAO%SILVA%",
                    "limit": f"máximo de nomes similares (1..{current_app.config['MAX_LIMIT']}, padrão {current_app.config['MAX_LIMIT']})",
                    "cargo": "cargo/profissão (busca parcial)",
                    "uf": "unidade federativa, ex.: RS",
                    "orgao": "instituição/órgão (busca parcial)",
                    "situacao": "ATIVO ou APOSENTADO",
                    "page": "página (padrão 1)",
                    "per_page": f"itens por página (1..{current_app.config['MAX_PER_PAGE']}, padrão {current_app.config['DEFAULT_PER_PAGE']})",
                },
                "exemplos": [
                    "/api/servidores?cargo=AUDITOR&uf=DF",
                    "/api/servidores?similar=%MARIA%SILVA%&limit=50",
                    "/api/servidores?orgao=UNIVERSIDADE&uf=RS&page=2&per_page=10",
                ],
            },
            "GET /api/servidores/<id>": "um registro pelo id",
            "GET /api/cargos?q=": "cargos (para autocompletar)",
            "GET /api/orgaos?q=": "órgãos (para autocompletar)",
            "GET /api/ufs": "UFs válidas",
            "GET /api/estatisticas": "totais da base",
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
        "statement_timeout": info.get("statement_timeout"),
        "pool": db.estatisticas_pool(),
    })


# ---------------------------------------------------------------------------
def _montar_filtros(p: dict):
    """Devolve (cláusulas WHERE, parâmetros) a partir dos filtros validados."""
    where = []
    params: dict = {}

    if "nome" in p:
        where.append("s.nome = %(nome)s")
        params["nome"] = p["nome"]
    if "similar" in p:
        where.append("s.nome ILIKE %(similar)s")
        params["similar"] = p["similar"]
        # texto sem curingas, usado para ordenar por similaridade (pg_trgm)
        params["similar_txt"] = p["similar"].replace("%", " ").replace("_", " ").strip()
    if "cargo" in p:
        where.append("c.nome ILIKE %(cargo)s")
        params["cargo"] = f"%{p['cargo']}%"
    if "orgao" in p:
        where.append("(o.nome ILIKE %(orgao)s OR o.sigla ILIKE %(orgao_sigla)s)")
        params["orgao"] = f"%{p['orgao']}%"
        params["orgao_sigla"] = p["orgao"]
    if "uf" in p:
        where.append("s.uf = %(uf)s")
        params["uf"] = p["uf"]
    if "situacao" in p:
        where.append("s.situacao = %(situacao)s")
        params["situacao"] = p["situacao"]
    return " AND ".join(where), params


def _verificar_dominio(p: dict):
    """Cargo/órgão que não existem na base => 404 com mensagem específica."""
    if "cargo" in p:
        existe = db.consultar_um(
            "SELECT 1 FROM cargos WHERE nome ILIKE %(q)s LIMIT 1", {"q": f"%{p['cargo']}%"}
        )
        if not existe:
            raise ErroAPI(404, f"Cargo inválido ou não encontrado: '{p['cargo']}'.",
                          {"dica": "Consulte /api/cargos?q=<texto> para ver os cargos existentes."})
    if "orgao" in p:
        existe = db.consultar_um(
            "SELECT 1 FROM orgaos WHERE nome ILIKE %(q)s OR sigla ILIKE %(s)s LIMIT 1",
            {"q": f"%{p['orgao']}%", "s": p["orgao"]},
        )
        if not existe:
            raise ErroAPI(404, f"Instituição/órgão inválido ou não encontrado: '{p['orgao']}'.",
                          {"dica": "Consulte /api/orgaos?q=<texto> para ver os órgãos existentes."})


@bp.get("/servidores")
@limitador.limitar
def buscar_servidores():
    p = validar_busca(request.args)
    _verificar_dominio(p)

    where, params = _montar_filtros(p)
    page, per_page = p["page"], p["per_page"]
    params.update({"offset": (page - 1) * per_page, "per_page": per_page, "limit": p["limit"]})

    universo = None
    if "similar" in p:
        # Universo = os `limit` nomes mais parecidos (no máximo MAX_LIMIT linhas).
        # A consulta com similarity() é a mais cara da API, então roda uma única
        # vez: traz o universo inteiro e a paginação é feita aqui em memória.
        universo = db.consultar(f"""
            SELECT {_COLUNAS}, similarity(s.nome, %(similar_txt)s) AS similaridade
            {_FROM}
            WHERE {where}
            ORDER BY similaridade DESC, s.nome, s.id
            LIMIT %(limit)s
        """, params)
        total = len(universo)
    else:
        total = db.consultar_um(f"SELECT count(*) AS n {_FROM} WHERE {where}", params)["n"]
        sql_itens = f"""
            SELECT {_COLUNAS} {_FROM}
            WHERE {where}
            ORDER BY s.nome, s.id
            OFFSET %(offset)s LIMIT %(per_page)s
        """

    if total == 0:
        if "nome" in p:
            msg = f"Nome não encontrado: '{p['nome']}'."
            dica = "Tente a busca por similaridade: ?similar=%PARTE%DO%NOME%"
        elif "similar" in p:
            msg = f"Nenhum nome parecido com '{p['similar']}'."
            dica = "Use % como curinga, ex.: ?similar=MARIA%SILVA"
        else:
            msg = "Nenhum servidor encontrado com os filtros informados."
            dica = "Remova ou altere algum filtro."
        raise ErroAPI(404, msg, {"filtros": {k: v for k, v in p.items() if k not in ("page", "per_page", "limit")}, "dica": dica})

    total_paginas = max(1, math.ceil(total / per_page))
    if page > total_paginas:
        raise ErroAPI(404, f"Página inexistente: {page}. A busca tem {total_paginas} página(s).",
                      {"total": total, "total_paginas": total_paginas, "per_page": per_page})

    if universo is not None:
        linhas = universo[params["offset"]:params["offset"] + per_page]
    else:
        linhas = db.consultar(sql_itens, params)
    itens = [_serializar(l) for l in linhas]
    if "similar" in p:
        for it in itens:
            it["similaridade"] = round(float(it.pop("similaridade", 0) or 0), 3)

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_paginas": total_paginas,
        "registro_unico": total == 1,
        "filtros": {k: v for k, v in p.items() if k not in ("page", "per_page")},
        "itens": itens,
    })


@bp.get("/servidores/<int:id_servidor>")
@limitador.limitar
def obter_servidor(id_servidor: int):
    linha = db.consultar_um(f"SELECT {_COLUNAS} {_FROM} WHERE s.id = %(id)s", {"id": id_servidor})
    if not linha:
        raise ErroAPI(404, f"Servidor com id {id_servidor} não encontrado.")
    return jsonify(_serializar(linha))


# ---------------------------------------------------------------------------
def _listar_dominio(tabela: str, extra_cols: str = ""):
    q = request.args.get("q")
    limite = validar_inteiro(request.args.get("limit"), "limit", 1, 100, 20)
    if q:
        qn = validar_texto_simples(q, "q")
        linhas = db.consultar(
            f"SELECT id, nome{extra_cols} FROM {tabela} WHERE nome ILIKE %(q)s "
            f"ORDER BY similarity(nome, %(qt)s) DESC, nome LIMIT %(lim)s",
            {"q": f"%{qn}%", "qt": qn, "lim": limite},
        )
    else:
        linhas = db.consultar(f"SELECT id, nome{extra_cols} FROM {tabela} ORDER BY nome LIMIT %(lim)s", {"lim": limite})
    return jsonify({"total": len(linhas), "itens": linhas})


@bp.get("/cargos")
@limitador.limitar
def cargos():
    return _listar_dominio("cargos")


@bp.get("/orgaos")
@limitador.limitar
def orgaos():
    return _listar_dominio("orgaos", ", sigla")


@bp.get("/ufs")
def ufs():
    return jsonify({"itens": [{"sigla": s, "nome": n} for s, n in sorted(UFS.items())]})


@bp.get("/estatisticas")
@limitador.limitar
def estatisticas():
    totais = db.verificar()
    por_uf = db.consultar(
        "SELECT uf, count(*) AS total FROM servidores WHERE uf IS NOT NULL GROUP BY uf ORDER BY total DESC"
    )
    return jsonify({
        "total": totais.get("total"),
        "ativos": totais.get("ativos"),
        "aposentados": totais.get("aposentados"),
        "por_uf": por_uf,
    })
