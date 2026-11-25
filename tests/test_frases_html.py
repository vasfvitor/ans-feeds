"""The phrases of frases-proibidas.txt stay out of the built pages, not only out of the source
strings: a sentence put together at build time (a date, a source name, a reason) is checked here as
the visitor reads it. Uses the scanner of test_frases_proibidas.py as it is.

The pages come from the frozen tree (conftest.py), with and without failed sources, so the failure
notices and the portability box are read in both forms.
"""

from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_frases_proibidas import achados


class _Texto(HTMLParser):
    """The text a visitor reads: element text (style and script left out), the title, and the
    description and alt texts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._fora = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script"):
            self._fora += 1
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "description" or tag == "img":
            self.partes.append(a.get("content") or a.get("alt") or "")
        self.partes.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script"):
            self._fora -= 1
        self.partes.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._fora:
            self.partes.append(data)


def texto(html: str) -> str:
    p = _Texto()
    p.feed(html)
    p.close()
    return "".join(p.partes)


def achados_html(site: Path) -> list[str]:
    out = []
    for path in sorted(site.glob("*.html")):
        corpo = texto(path.read_text(encoding="utf-8"))
        out += achados(path.name, [[(1, corpo)]])
    return out


def test_the_text_is_read_across_tags_and_without_the_css():
    html = (
        '<html><head><meta name="description" content="Dados em tempo real">'
        "<style>.todo-dia{}</style></head><body><p>Saiba <b>mais</b></p></body></html>"
    )
    assert achados("x.html", [[(1, texto(html))]]) == [
        "x.html:1: saiba mais",
        "x.html:1: em tempo real",
    ]


@pytest.mark.parametrize("fixture", ["site_congelado", "site_falhas"])
def test_no_banned_phrase_in_the_built_pages(fixture, request):
    site = request.getfixturevalue(fixture)
    assert sorted(site.glob("*.html")), "the build wrote no page"
    hits = achados_html(site)
    assert not hits, "\n".join(hits)
