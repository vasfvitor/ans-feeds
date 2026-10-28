"""One Atom feed per operator, for the portal's "Acompanhar esta operadora".

Entries: the operator's events (same ids as the general feeds, so a reader that follows both sees
one entry), plus one entry per closed complaint quarter and one per ANS score (IDSS) year, so a
feed does not sit still for years. Quarters and years are dated by the collection that first held
them; those already in the first stored version get that version's collection time. Facts with
their base only: the reading of the numbers is the portal's.
"""

from __future__ import annotations

import csv
import html
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path

from . import eventos as ev
from . import operadoras, snapshots
from .atom import Entry, tag_uri

LIMIT = 50
MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def q(s: str) -> str:
    return html.escape(s, quote=True)


def trimestre_extenso(tri: str) -> str:
    """ "3T2026" → "julho a setembro de 2026"."""
    n, ano = int(tri[0]), tri[2:]
    return f"{MESES[3 * n - 3]} a {MESES[3 * n - 1]} de {ano}"


def inteiro(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def dec(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def _vistos(root: Path, name: str, keys: Callable[[Path], Iterable[str]]) -> dict[str, datetime]:
    """When each key first showed up in `name`; baseline keys get the first collection time."""
    versoes = snapshots.versions(root, name)
    if not versoes:
        return {}

    def quando(dia: str, at: datetime | None) -> datetime:
        return at or datetime.fromisoformat(dia).replace(tzinfo=ev.BRASILIA)

    dia0, path0 = versoes[0]
    base = quando(dia0, snapshots.collected_at(root, dia0, name))
    out = dict.fromkeys(keys(path0), base)
    for key, (dia, at) in snapshots.first_seen(root, name, keys).items():
        out[key] = quando(dia, at)
    return out


def _trimestres(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as f:
        competencias = {r["COMPETENCIA"] for r in csv.DictReader(f, delimiter=";")}
    return set(operadoras.trimestres_fechados(competencias))


def _anos_idss(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as f:
        header = next(csv.reader(f, delimiter=";"), [])
    return {c.split("_", 1)[1] for c in header if c.startswith("IDSS_")}


def vistos(root: Path) -> tuple[dict[str, datetime], dict[str, datetime]]:
    """(complaint quarter → first seen, IDSS "ano_base" suffix → first seen)."""
    return _vistos(root, operadoras.IGR, _trimestres), _vistos(root, operadoras.IDSS, _anos_idss)


def _reclamacoes(
    o: dict, quando: dict[str, datetime], base_tag: str, link: str
) -> list[tuple[date, Entry]]:
    por_tri: dict[str, list[tuple[str, dict]]] = {}
    for r in o["reclamacoes"]:
        for s in r["serie"]:
            por_tri.setdefault(s["trimestre"], []).append((r["cobertura"], s))
    out = []
    for tri, linhas in por_tri.items():
        if tri not in quando:
            continue
        total = sum(s["reclamacoes"] for _, s in linhas)
        partes = []
        for cobertura, s in linhas:
            texto = f"Plano {cobertura}: {inteiro(s['reclamacoes'])} reclamações"
            if s["indice"] is not None:
                texto += (
                    f"; {dec(s['indice'])} por mês para cada 100 mil beneficiários (índice da ANS)"
                )
            partes.append(f"<li>{q(texto)}.</li>")
        fonte = o["fontes"]["reclamacoes"]
        visto = quando[tri].isoformat()
        fim = date(int(tri[2:]), 3 * int(tri[0]), 1)
        out.append(
            (
                fim,
                Entry(
                    id=tag_uri(base_tag, "reclamacoes", o["registro"], tri),
                    title=f"Reclamações de {trimestre_extenso(tri)}: {inteiro(total)}",
                    updated=visto,
                    published=visto,
                    link=link,
                    content=f"<ul>{''.join(partes)}</ul>"
                    + (f'<p><a href="{q(fonte)}">fonte</a></p>' if fonte else ""),
                ),
            )
        )
    return out


def _idss(
    o: dict, quando: dict[str, datetime], base_tag: str, link: str
) -> list[tuple[date, Entry]]:
    nota = o["idss"]
    sufixo = f"{nota['ano']}_{nota['ano_base']}" if nota else ""
    if not nota or sufixo not in quando:
        return []
    valor = dec(nota["valor"]) if nota["valor"] is not None else "não divulgada"
    linhas = [
        f"<li>{q(d['nome'])}: {dec(d['valor'])}</li>"
        for d in nota["dimensoes"].values()
        if d["valor"] is not None
    ]
    partes = [
        f"<p>Índice de Desempenho da Saúde Suplementar (IDSS) publicado em {nota['ano']},"
        f" referente a {nota['ano_base']}, numa escala de 0 a 1.</p>"
    ]
    if linhas:
        partes.append(f"<ul>{''.join(linhas)}</ul>")
    if nota["mediana_mesma_modalidade"] is not None:
        partes.append(
            f"<p>Mediana das {nota['operadoras_mesma_modalidade']} operadoras da mesma"
            f" modalidade: {dec(nota['mediana_mesma_modalidade'])}.</p>"
        )
    if o["fontes"]["idss"]:
        partes.append(f'<p><a href="{q(o["fontes"]["idss"])}">fonte</a></p>')
    visto = quando[sufixo].isoformat()
    return [
        (
            date(nota["ano"], 1, 1),
            Entry(
                id=tag_uri(base_tag, "idss", o["registro"], sufixo),
                title=f"Nota da ANS de {nota['ano']} (referente a {nota['ano_base']}): {valor}",
                updated=visto,
                published=visto,
                link=link,
                content="".join(partes),
            ),
        )
    ]


def entradas(
    o: dict,
    eventos: list[tuple[date, Entry]],
    *,
    trimestres: dict[str, datetime],
    anos: dict[str, datetime],
    base_tag: str,
    link: str,
) -> list[Entry]:
    """Every entry of one operator's feed, newest first, at most LIMIT. Each comes with the date it
    refers to (the act, the end of the quarter, the score year), which orders entries published at
    the same time."""
    todas = eventos + _reclamacoes(o, trimestres, base_tag, link) + _idss(o, anos, base_tag, link)
    todas.sort(key=lambda t: (datetime.fromisoformat(t[1].published), t[0], t[1].id), reverse=True)
    return [entry for _, entry in todas[:LIMIT]]
