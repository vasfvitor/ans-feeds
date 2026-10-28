"""Operator events read from the latest version of each snapshot file.

Every event carries the date of the act itself (cancellation, registration, RO publication), so the
whole history comes out of the current files. The snapshot series only adds `visto_em`: when the
event first showed up in a collection, which measures how late the ANS publishes it.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import snapshots

ATIVAS = "Relatorio_cadop.csv"
CANCELADAS = "Relatorio_cadop_canceladas.csv"
DIRECAO_TECNICA = "pda-040-regimes_especiais_direcao_tecnica.csv"
LIQUIDACAO = "Liquidação Extrajudicial"
BRASILIA = timezone(timedelta(hours=-3))


@dataclass
class Evento:
    tipo: str
    chave: str
    data: date
    titulo: str
    nome: str
    registro: str | None
    detalhes: dict[str, str] = field(default_factory=dict)
    fonte: str = ""
    link: str | None = None
    destaque: bool = False
    visto_em: datetime | None = None

    @property
    def id(self) -> str:
        return f"{self.tipo}/{self.chave}"

    @property
    def updated(self) -> datetime:
        if self.visto_em:
            return self.visto_em
        return datetime(self.data.year, self.data.month, self.data.day, tzinfo=BRASILIA)


def registro(valor: str) -> str | None:
    """ANS registration number with 6 digits; None for codes that are not one (`X00002`)."""
    valor = valor.strip()
    return valor.zfill(6) if valor.isdigit() else None


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def source_url(root: Path, name: str) -> str:
    cols = snapshots.estado(root, name)
    return cols[1] if cols and len(cols) > 1 else ""


def _with_seen(
    root: Path, name: str, eventos: list[Evento], chave: Callable[[dict[str, str]], str | None]
) -> list[Evento]:
    def keys(path: Path) -> Iterable[str]:
        return (k for k in map(chave, rows(path)) if k)

    seen = snapshots.first_seen(root, name, keys)
    for e in eventos:
        if e.chave in seen:
            e.visto_em = seen[e.chave][1]
    return eventos


def _cadop_detalhes(r: dict[str, str]) -> dict[str, str]:
    return {
        "Modalidade": r["MODALIDADE"],
        "Município": f"{r['CIDADE']}/{r['UF']}" if r["CIDADE"] else r["UF"],
        "CNPJ": r["CNPJ"],
    }


def _cancel_chave(r: dict[str, str]) -> str | None:
    reg, dia = registro(r["REGISTRO_OPERADORA"]), r["DATA_DESCREDENCIAMENTO"].strip()
    return f"{reg}/{dia}" if reg and dia else None


def cancelamentos(root: Path) -> list[Evento]:
    path = snapshots.latest(root, CANCELADAS)
    if not path:
        return []
    fonte = source_url(root, CANCELADAS)
    out = []
    for r in rows(path):
        chave = _cancel_chave(r)
        if not chave:
            continue
        motivo = r["MOTIVO_DO_DESCREDENCIAMENTO"].strip()
        out.append(
            Evento(
                tipo="cancelamento",
                chave=chave,
                data=date.fromisoformat(r["DATA_DESCREDENCIAMENTO"].strip()),
                titulo=f"Cancelamento: {r['RAZAO_SOCIAL'].strip()} ({motivo})",
                nome=r["RAZAO_SOCIAL"].strip(),
                registro=registro(r["REGISTRO_OPERADORA"]),
                detalhes={
                    "Motivo": motivo,
                    **_cadop_detalhes(r),
                    "Registro na ANS desde": r["DATA_REGISTRO_ANS"],
                },
                fonte=fonte,
                destaque=motivo == LIQUIDACAO,
            )
        )
    return _with_seen(root, CANCELADAS, out, _cancel_chave)


def _registro_chave(r: dict[str, str]) -> str | None:
    return registro(r["REGISTRO_OPERADORA"]) if r["DATA_REGISTRO_ANS"].strip() else None


def registros(root: Path) -> list[Evento]:
    """Registrations of active and cancelled operators; new ones show up in the active list."""
    out = []
    for name, situacao in ((ATIVAS, "ativa"), (CANCELADAS, "cancelada")):
        path = snapshots.latest(root, name)
        if not path:
            continue
        fonte = source_url(root, name)
        for r in rows(path):
            chave = _registro_chave(r)
            if not chave:
                continue
            out.append(
                Evento(
                    tipo="registro",
                    chave=chave,
                    data=date.fromisoformat(r["DATA_REGISTRO_ANS"].strip()),
                    titulo=f"Novo registro: {r['RAZAO_SOCIAL'].strip()}",
                    nome=r["RAZAO_SOCIAL"].strip(),
                    registro=chave,
                    detalhes={**_cadop_detalhes(r), "Situação hoje": situacao},
                    fonte=fonte,
                )
            )
    return _with_seen(root, ATIVAS, out, _registro_chave)


def _dt_chave(r: dict[str, str]) -> str | None:
    ro, reg = r["RESOLUCAO_OPERACIONAL"].strip(), r["REGISTRO_OPERADORA"].strip()
    return f"{ro}/{reg}" if ro and reg else None


def direcao_tecnica(root: Path) -> list[Evento]:
    path = snapshots.latest(root, DIRECAO_TECNICA)
    if not path:
        return []
    fonte = source_url(root, DIRECAO_TECNICA)
    out = []
    for r in rows(path):
        chave = _dt_chave(r)
        if not chave:
            continue
        ro = r["RESOLUCAO_OPERACIONAL"].strip()
        out.append(
            Evento(
                tipo="direcao-tecnica",
                chave=chave,
                data=date.fromisoformat(r["DATA_PUBLICACAO"].strip()),
                titulo=f"Direção técnica: {r['RAZAO_SOCIAL'].strip()} (RO {ro})",
                nome=r["RAZAO_SOCIAL"].strip(),
                registro=registro(r["REGISTRO_OPERADORA"]),
                detalhes={"Resolução Operacional": ro, "UF": r["UF"].strip()},
                fonte=fonte,
            )
        )
    return _with_seen(root, DIRECAO_TECNICA, out, _dt_chave)
