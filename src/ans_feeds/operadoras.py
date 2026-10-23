"""One record per operator for the public portal: registry, complaints compared with peers, quality
score, SUS reimbursement and events. Facts with their base and source only, no score of our own.

Left out on purpose: the prudential class S1-S4 (a size and risk segment for capital rules, not a
financial health grade), PORCENTAGEM_HC (meaning not verified), and the series the ANS stopped
updating (resolution rate up to 2019-10, coverage guarantee up to 4Q2024, penalties up to 03/2025).
"""

from __future__ import annotations

import csv
import re
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from . import eventos as ev
from . import snapshots
from .eventos import Evento

SCHEMA = Path(__file__).with_name("dados_schema.md")
IGR = "pda-023-igr.csv"
IDSS = "pda-020-historico-idss-2016_2025.csv"
RESSARCIMENTO = re.compile(r"^\d{6}_Indice_de_Efetivo_Pagamento\.csv$")
COBERTURAS = {
    "Assistência médica": "médico-hospitalar",
    "Exclusivamente odontológica": "odontológica",
}
SERIE_TRIMESTRES = 8
CANCELADAS_ANOS = 5
IDSS_DIMENSOES = {
    "IDQS": "qualidade da atenção à saúde",
    "IDGA": "garantia de acesso",
    "IDSM": "sustentabilidade no mercado",
    "IDGR": "gestão de processos e regulação",
}
FORA = [
    "Taxa de resolutividade: a ANS não atualiza desde 2019-10.",
    "Garantia de atendimento: a ANS não atualiza desde o 4º trimestre de 2024.",
    "Penalidades aplicadas: a ANS não atualiza desde 03/2025.",
]


def numero(valor: str) -> float | None:
    valor = valor.strip().rstrip("%").replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return None


def trimestre(competencia: str) -> str:
    ano, mes = competencia.split("-")
    return f"{(int(mes) - 1) // 3 + 1}T{ano}"


def _ordem_tri(t: str) -> tuple[int, int]:
    return int(t[2:]), int(t[0])


def mediana(valores: list[float]) -> float | None:
    return round(statistics.median(valores), 2) if valores else None


def reclamacoes(root: Path) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Quarterly complaint index (RN 623 formula: complaints per month per 100,000 beneficiaries),
    per operator and coverage, with the median of operators of the same size and coverage in the
    latest closed quarter. Also returns the beneficiaries in the latest month."""
    path = snapshots.latest(root, IGR)
    if not path:
        return {}, {}
    meses: dict[tuple[str, str, str], list[tuple[str, int, int, str]]] = defaultdict(list)
    competencias: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            reg, cob = ev.registro(r["REGISTRO_OPERADORA"]), COBERTURAS.get(r["COBERTURA"])
            if not reg or not cob or not r["COMPETENCIA"]:
                continue
            competencias.add(r["COMPETENCIA"])
            meses[(reg, cob, trimestre(r["COMPETENCIA"]))].append(
                (
                    r["COMPETENCIA"],
                    int(r["QTD_RECLAMACOES"] or 0),
                    int(r["QTD_BENEFICIARIOS"] or 0),
                    r["PORTE_OPERADORA"],
                )
            )
    fechados = sorted({trimestre(c) for c in competencias}, key=_ordem_tri)
    fechados = [t for t in fechados if sum(trimestre(c) == t for c in competencias) == 3]
    serie_tris = fechados[-SERIE_TRIMESTRES:]
    ultimo = fechados[-1] if fechados else None

    def calc(lst):
        if len(lst) != 3:
            return None
        nips = sum(n for _, n, _, _ in lst)
        benef = sum(b for _, _, b, _ in lst) / 3
        porte = max(lst)[3]
        igr = round((nips / 3) / benef * 100000, 2) if benef else None
        return {"nips": nips, "beneficiarios_media": round(benef), "porte": porte, "igr": igr}

    por_op: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for (reg, cob, tri), lst in meses.items():
        if tri in serie_tris:
            c = calc(lst)
            if c:
                por_op[(reg, cob)][tri] = c
    pares: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (_, cob), tris in por_op.items():
        c = tris.get(ultimo)
        if c and c["igr"] is not None:
            pares[(cob, c["porte"])].append(c["igr"])

    out: dict[str, list[dict]] = defaultdict(list)
    for (reg, cob), tris in sorted(por_op.items()):
        c = tris.get(ultimo)
        if not c:
            continue
        grupo = pares[(cob, c["porte"])]
        out[reg].append(
            {
                "cobertura": cob,
                "trimestre": ultimo,
                "indice": c["igr"],
                "reclamacoes": c["nips"],
                "beneficiarios_media": c["beneficiarios_media"],
                "porte": c["porte"],
                "mediana_mesmo_porte": mediana(grupo),
                "operadoras_mesmo_porte": len(grupo),
                "serie": [
                    {"trimestre": t, "indice": tris[t]["igr"], "reclamacoes": tris[t]["nips"]}
                    for t in serie_tris
                    if t in tris
                ],
            }
        )
    ultima_comp = max(competencias) if competencias else None
    beneficiarios: dict[str, int] = defaultdict(int)
    for (reg, _, _tri), lst in meses.items():
        for comp, _, b, _ in lst:
            if comp == ultima_comp:
                beneficiarios[reg] += b
    return dict(out), dict(beneficiarios)


def idss(root: Path) -> tuple[dict[str, dict], str | None]:
    path = snapshots.latest(root, IDSS)
    if not path:
        return {}, None
    rows = ev.rows(path)
    anos = sorted({c.split("_", 1)[1] for c in rows[0] if c.startswith("IDSS_")} if rows else set())
    if not anos:
        return {}, None
    sufixo = anos[-1]  # e.g. "2025_2024": published in 2025, base year 2024
    por_modalidade: dict[str, list[float]] = defaultdict(list)
    valores: dict[str, tuple[str, float | None, dict]] = {}
    for r in rows:
        reg = ev.registro(r["REGISTRO_OPERADORA"])
        if not reg:
            continue
        valor = numero(r[f"IDSS_{sufixo}"])
        dims = {k: numero(r.get(f"{k}_{sufixo}", "")) for k in IDSS_DIMENSOES}
        valores[reg] = (r["MODALIDADE"], valor, dims)
        if valor is not None:
            por_modalidade[r["MODALIDADE"]].append(valor)
    ano, base = sufixo.split("_")
    out = {}
    for reg, (modalidade, valor, dims) in valores.items():
        grupo = por_modalidade[modalidade]
        out[reg] = {
            "ano": int(ano),
            "ano_base": int(base),
            "valor": valor,
            "motivo": None if valor is not None else "não divulgado pela ANS",
            "dimensoes": {k: {"nome": IDSS_DIMENSOES[k], "valor": v} for k, v in dims.items()},
            "mediana_mesma_modalidade": mediana(grupo),
            "operadoras_mesma_modalidade": len(grupo),
        }
    return out, sufixo


def ressarcimento(root: Path) -> tuple[dict[str, dict], str | None]:
    nomes = sorted(
        {
            p.name
            for d in snapshots.days(root)
            for p in (root / d).iterdir()
            if RESSARCIMENTO.match(p.name)
        }
    )
    if not nomes:
        return {}, None
    path = snapshots.latest(root, nomes[-1])
    out = {}
    for r in ev.rows(path):
        reg = ev.registro(r["CODIGO_OPERADORA"])
        if not reg:
            continue
        out[reg] = {
            "competencia": r["COMPETENCIA"],
            "indice_pagamento": numero(r["INDICE_ADIMPLENCIA"]),
            "indice_pagamento_5anos": numero(r["INDICE_ADIMPLENCIA_5ANOS"]),
            "valor_cobrado": numero(r["VALOR_COBRADO_ACUMULADO"]),
            "valor_pago": numero(r["VALOR_PAGO_ACUMULADO"]),
        }
    return out, nomes[-1]


def _evento_curto(e: Evento) -> dict:
    return {"tipo": e.tipo, "id": e.id, "data": e.data.isoformat(), "titulo": e.titulo}


def operadoras(root: Path, todos: list[Evento]) -> list[dict]:
    """Active operators plus those cancelled in the last five years."""
    hoje = date.fromisoformat(snapshots.days(root)[-1])
    limite = hoje - timedelta(days=365 * CANCELADAS_ANOS)
    recl, beneficiarios = reclamacoes(root)
    notas, _ = idss(root)
    ress, ress_arquivo = ressarcimento(root)
    por_reg: dict[str, list[Evento]] = defaultdict(list)
    for e in todos:
        if e.registro:
            por_reg[e.registro].append(e)

    fontes = {
        "cadastro": ev.source_url(root, ev.ATIVAS),
        "cancelamentos": ev.source_url(root, ev.CANCELADAS),
        "reclamacoes": ev.source_url(root, IGR),
        "idss": ev.source_url(root, IDSS),
        "ressarcimento": ev.source_url(root, ress_arquivo) if ress_arquivo else "",
    }
    out = []
    for name, situacao in ((ev.ATIVAS, "ativa"), (ev.CANCELADAS, "cancelada")):
        path = snapshots.latest(root, name)
        for r in ev.rows(path) if path else []:
            reg = ev.registro(r["REGISTRO_OPERADORA"])
            if not reg:
                continue
            cancelamento = None
            if situacao == "cancelada":
                dia = r["DATA_DESCREDENCIAMENTO"].strip()
                if not dia or date.fromisoformat(dia) < limite:
                    continue
                cancelamento = {"data": dia, "motivo": r["MOTIVO_DO_DESCREDENCIAMENTO"].strip()}
            eventos_op = sorted(por_reg.get(reg, []), key=lambda e: (e.data, e.id), reverse=True)
            vigentes = [
                e
                for e in eventos_op
                if e.tipo == "portabilidade" and e.detalhes.get("Situação") == "vigente"
            ]
            out.append(
                {
                    "registro": reg,
                    "nome": r["RAZAO_SOCIAL"].strip(),
                    "fantasia": r["NOME_FANTASIA"].strip() or None,
                    "cnpj": r["CNPJ"].strip(),
                    "modalidade": r["MODALIDADE"].strip(),
                    "municipio": r["CIDADE"].strip() or None,
                    "uf": r["UF"].strip() or None,
                    "registrada_em": r["DATA_REGISTRO_ANS"].strip() or None,
                    "situacao": situacao,
                    "cancelamento": cancelamento,
                    "beneficiarios": beneficiarios.get(reg),
                    "reclamacoes": recl.get(reg, []),
                    "idss": notas.get(reg),
                    "ressarcimento": ress.get(reg),
                    "portabilidade_vigente": [
                        {"ro": e.chave, "data": e.data.isoformat(), "link": e.link}
                        for e in vigentes
                    ],
                    "eventos": [_evento_curto(e) for e in eventos_op],
                    "fontes": fontes,
                    "fora": FORA,
                }
            )
    out.sort(key=lambda o: o["registro"])
    return out


def indice(registros: list[dict]) -> list[dict]:
    """Small search index for the portal: name, trade name, place and size."""
    return [
        {
            "registro": o["registro"],
            "nome": o["nome"],
            "fantasia": o["fantasia"],
            "uf": o["uf"],
            "municipio": o["municipio"],
            "modalidade": o["modalidade"],
            "situacao": o["situacao"],
            "beneficiarios": o["beneficiarios"],
        }
        for o in registros
    ]
