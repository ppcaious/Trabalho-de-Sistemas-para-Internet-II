"""Validação dos parâmetros de busca.

Tudo que chega pela query string passa por aqui antes de virar SQL.
"""
import re
import unicodedata

from flask import current_app

from .errors import ErroAPI

UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}

SITUACOES = {"ATIVO", "APOSENTADO"}

PARAMETROS_PERMITIDOS = {
    "nome", "similar", "limit", "cargo", "uf", "orgao", "situacao", "page", "per_page",
}


def normalizar(texto: str) -> str:
    """Remove acentos, colapsa espaços e põe em maiúsculas (formato da base)."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return " ".join(sem_acento.split()).upper()


def _texto(valor: str, campo: str, permitir_curinga: bool = False) -> str:
    valor = (valor or "").strip()
    max_len = current_app.config["MAX_PARAM_LEN"]
    if not valor:
        raise ErroAPI(400, f"Parâmetro '{campo}' não pode ser vazio.")
    if len(valor) > max_len:
        raise ErroAPI(400, f"Parâmetro '{campo}' excede {max_len} caracteres.")
    return normalizar(valor)


def _inteiro(valor: str, campo: str, minimo: int, maximo: int, padrao: int) -> int:
    if valor is None or valor == "":
        return padrao
    if not re.fullmatch(r"\d{1,9}", valor.strip()):
        raise ErroAPI(400, f"Parâmetro '{campo}' deve ser um número inteiro positivo.", {"valor": valor})
    n = int(valor)
    if n < minimo or n > maximo:
        raise ErroAPI(400, f"Parâmetro '{campo}' deve estar entre {minimo} e {maximo}.", {"valor": n})
    return n


def validar_busca(args) -> dict:
    """Valida a query string de GET /api/servidores e devolve um dict limpo.

    Levanta ErroAPI(400) para qualquer parâmetro inválido.
    """
    cfg = current_app.config
    desconhecidos = sorted(set(args.keys()) - PARAMETROS_PERMITIDOS)
    if desconhecidos:
        raise ErroAPI(
            400,
            "Parâmetro(s) de busca inválido(s): " + ", ".join(desconhecidos),
            {"permitidos": sorted(PARAMETROS_PERMITIDOS)},
        )
    p: dict = {}

    if args.get("nome") is not None:
        p["nome"] = _texto(args.get("nome"), "nome")

    if args.get("similar") is not None:
        s = _texto(args.get("similar"), "similar", permitir_curinga=True)
        if s.replace("%", "").replace("_", "").strip() == "":
            raise ErroAPI(400, "Parâmetro 'similar' precisa conter ao menos uma letra.")
        if "%" not in s:
            s = f"%{s}%"  # sem curinga explícito, procura em qualquer posição
        p["similar"] = s

    if args.get("cargo") is not None:
        p["cargo"] = _texto(args.get("cargo"), "cargo")

    if args.get("orgao") is not None:
        p["orgao"] = _texto(args.get("orgao"), "orgao")

    if args.get("uf") is not None:
        uf = (args.get("uf") or "").strip().upper()
        if uf not in UFS:
            raise ErroAPI(400, f"UF inválida: '{args.get('uf')}'.", {"ufs_validas": sorted(UFS)})
        p["uf"] = uf

    if args.get("situacao") is not None:
        sit = normalizar(args.get("situacao") or "")
        if sit not in SITUACOES:
            raise ErroAPI(400, f"Situação inválida: '{args.get('situacao')}'.", {"validas": sorted(SITUACOES)})
        p["situacao"] = sit

    p["limit"] = _inteiro(args.get("limit"), "limit", 1, cfg["MAX_LIMIT"], cfg["MAX_LIMIT"])
    p["page"] = _inteiro(args.get("page"), "page", 1, 1_000_000, 1)
    p["per_page"] = _inteiro(args.get("per_page"), "per_page", 1, cfg["MAX_PER_PAGE"], cfg["DEFAULT_PER_PAGE"])

    if not any(k in p for k in ("nome", "similar", "cargo", "orgao", "uf", "situacao")):
        raise ErroAPI(
            400,
            "Informe pelo menos um critério de busca.",
            {"criterios": ["nome", "similar", "cargo", "uf", "orgao", "situacao"]},
        )
    return p


def validar_texto_simples(valor: str, campo: str) -> str:
    """Para ?q= em /api/cargos e /api/orgaos."""
    return _texto(valor, campo)
