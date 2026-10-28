"""Special and extraordinary portability, from the gov.br page snapshot.

The page has one `<table>` after each `<h3>` (vigentes, encerradas, extraordinárias encerradas);
each row has the DOU date, the operator name, the RO number and a link. There is no ANS
registration number, so it is matched by name against the CADOP. The RO number comes from its own
column, never from the link text, which is sometimes wrong (the row of RO 2413 says "RO 2312").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

from . import eventos, snapshots
from .eventos import Evento

PAGINA = "portabilidade-especial.html"
SITUACOES = {
    "Portabilidades Especiais Vigentes": "vigente",
    "Portabilidades Especiais Encerradas": "encerrada",
    "Portabilidades Extraordinárias Encerradas": "extraordinária encerrada",
}
SUFIXOS = re.compile(r"\b(LTDA|EIRELI|EPP|ME|S A|SA|S S)\b")
# "(SP)", "(Golden Cross)" on the page; " - EM LIQUIDAÇÃO EXTRAJUDICIAL" and the like in the CADOP.
ACRESCIMOS = re.compile(r"\([^)]*\)|\s+-\s+EM\s+(LIQUIDA|RECUPERA|REGIME|DIRE).*$", re.I)


@dataclass
class Linha:
    situacao: str
    data: date
    operadora: str
    ro: str
    link: str


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.linhas: list[Linha] = []
        self.atualizado: datetime | None = None
        self._h3: list[str] | None = None
        self._situacao: str | None = None
        self._in_tbody = False
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._href = ""
        self._modified = 0  # depth inside span.documentModified
        self._value: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "h3":
            self._h3 = []
        elif tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._row, self._href = [], ""
        elif tag == "td" and self._row is not None:
            self._cell = []
        elif tag == "a" and self._cell is not None and not self._href:
            self._href = (a.get("href") or "").strip()
        elif tag == "span":
            if self._modified:
                self._modified += 1
                if "value" in (a.get("class") or "").split():
                    self._value = []
            elif "documentModified" in (a.get("class") or "").split():
                self._modified = 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self._h3 is not None:
            self._situacao = SITUACOES.get(" ".join("".join(self._h3).split()))
            self._h3 = None
        elif tag == "tbody":
            self._in_tbody = False
        elif tag == "td" and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._situacao and len(self._row) >= 3 and self._row[2].isdigit():
                dia = datetime.strptime(self._row[0], "%d/%m/%Y").date()
                self.linhas.append(
                    Linha(self._situacao, dia, self._row[1], self._row[2], self._href)
                )
            self._row = None
        elif tag == "span" and self._modified:
            if self._value is not None:
                texto = " ".join("".join(self._value).split())
                self.atualizado = datetime.strptime(texto, "%d/%m/%Y %Hh%M")
                self._value = None
            self._modified -= 1

    def handle_data(self, data: str) -> None:
        for buf in (self._h3, self._cell, self._value):
            if buf is not None:
                buf.append(data)


def ler(path: Path) -> tuple[list[Linha], datetime | None]:
    p = _Parser()
    p.feed(path.read_text(encoding="utf-8"))
    p.close()
    return p.linhas, p.atualizado


def normalizar(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", ACRESCIMOS.sub(" ", nome)).encode("ascii", "ignore")
    sem_acento = sem_acento.decode()
    texto = re.sub(r"[^A-Z0-9]+", " ", sem_acento.upper())
    return " ".join(SUFIXOS.sub(" ", texto).split())


def indice_cadop(root: Path) -> tuple[dict[str, str | None], dict[str, str | None]]:
    """Normalized legal name and trade name → registration; None when two registrations share it."""
    razao: dict[str, str | None] = {}
    fantasia: dict[str, str | None] = {}
    for name in (eventos.ATIVAS, eventos.CANCELADAS):
        path = snapshots.latest(root, name)
        for r in eventos.rows(path) if path else []:
            reg = eventos.registro(r["REGISTRO_OPERADORA"])
            for indice, campo in ((razao, "RAZAO_SOCIAL"), (fantasia, "NOME_FANTASIA")):
                chave = normalizar(r[campo])
                if chave:
                    indice[chave] = reg if indice.get(chave, reg) == reg else None
    return razao, fantasia


REGISTRO_NO_NOME = re.compile(r"registro ANS n[ºo°]?\s*(\d{2}\.?\d{3}-?\d)", re.I)


def casar(nome: str, razao: dict[str, str | None], fantasia: dict[str, str | None]) -> str | None:
    """Registration written in the name, else exact match on the normalized legal name, then on the
    trade name; never fuzzy."""
    escrito = REGISTRO_NO_NOME.search(nome)
    if escrito:
        return eventos.registro(re.sub(r"\D", "", escrito.group(1)))
    chave = normalizar(nome)
    return razao[chave] if chave in razao else fantasia.get(chave)


def _chave(linha: Linha) -> str:
    return f"{linha.ro}|{linha.situacao}"


def portabilidades(root: Path) -> tuple[list[Evento], datetime | None]:
    path = snapshots.latest(root, PAGINA)
    if not path:
        return [], None
    linhas, atualizado = ler(path)
    if not linhas:  # a redesigned page reads as no operator at all: the warnings would vanish
        versoes = snapshots.versions(root, PAGINA)
        if len(versoes) > 1 and ler(versoes[-2][1])[0]:
            raise RuntimeError(
                f"{PAGINA} of {versoes[-1][0]}: no rows, while the version of {versoes[-2][0]} "
                "had some; the page probably changed layout and portabilidade.ler needs a fix"
            )
    razao, fantasia = indice_cadop(root)
    seen = snapshots.first_seen(root, PAGINA, lambda p: map(_chave, ler(p)[0]))
    fonte = eventos.source_url(root, PAGINA)
    out = []
    for linha in linhas:
        tipo = (
            "Portabilidade extraordinária"
            if "extraordinária" in linha.situacao
            else ("Portabilidade especial")
        )
        visto = seen.get(_chave(linha))
        out.append(
            Evento(
                tipo="portabilidade",
                chave=linha.ro,
                data=linha.data,
                titulo=f"{tipo}: {linha.operadora} (RO {linha.ro}, {linha.situacao})",
                nome=linha.operadora,
                registro=casar(linha.operadora, razao, fantasia),
                detalhes={
                    "Situação": linha.situacao,
                    "Resolução Operacional": linha.ro,
                    "Publicação no DOU": linha.data.strftime("%d/%m/%Y"),
                },
                fonte=fonte,
                link=linha.link or None,
                visto_em=visto[1] if visto else None,
            )
        )
    return out, atualizado
