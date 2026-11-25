import json
import re
from collections import Counter
from xml.etree import ElementTree as ET

import pytest
from conftest import OPTS, SNAPSHOTS

from ans_feeds.cli import BASE_TAG, BASE_URL, PORTAL_URL
from ans_feeds.site import (
    RELATO_EMAIL,
    SCHEMA_VERSION,
    TIPOS,
    build_site,
    feed_bytes,
    motivo_legivel,
)

A = "{http://www.w3.org/2005/Atom}"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Built from today's snapshots: only invariants are checked on it."""
    out = tmp_path_factory.mktemp("site")
    build_site(SNAPSHOTS, out, base_url=BASE_URL, base_tag=BASE_TAG, **OPTS)
    return out


def entries(path):
    return ET.parse(path).getroot().findall(f"{A}entry")


def test_every_xml_parses_and_ids_are_clean(site):
    for path in site.rglob("*.xml"):
        ET.parse(path)
    geral = entries(site / "geral.xml")
    assert len(geral) == 100
    ids = [e.findtext(f"{A}id") for e in geral]
    assert not [i for i, n in Counter(ids).items() if n > 1]
    assert all(i.startswith(f"tag:{BASE_TAG}:") and "//" not in i for i in ids)
    for tipo in TIPOS:
        assert 0 < len(entries(site / f"{tipo}.xml")) <= 50


def test_every_entry_link_has_its_anchor(site):
    paginas = {t: (site / f"{t}.html").read_text(encoding="utf-8") for t in TIPOS}
    for xml in ["geral.xml", *(f"{t}.xml" for t in TIPOS)]:
        for e in entries(site / xml):
            href = e.find(f"{A}link").get("href")
            pagina, ancora = href.removeprefix(f"{BASE_URL}/").split("#")
            assert f'id="{ancora}"' in paginas[pagina.removesuffix(".html")], href


def test_internal_links_point_to_files(site):
    for path in site.glob("*.html"):
        for href in re.findall(r'href="([^"]+)"', path.read_text(encoding="utf-8")):
            if ":" in href or href.startswith("#"):
                continue  # external
            assert (site / href.split("#")[0]).is_file(), (path.name, href)


def test_build_is_idempotent(site, tmp_path):
    again = tmp_path / "again"
    build_site(SNAPSHOTS, again, base_url=BASE_URL, base_tag=BASE_TAG, **OPTS)
    um = sorted(p.relative_to(site) for p in site.rglob("*") if p.is_file())
    dois = sorted(p.relative_to(again) for p in again.rglob("*") if p.is_file())
    assert um == dois
    assert all((site / p).read_bytes() == (again / p).read_bytes() for p in um)


def test_operator_data_is_published(site):
    idx = json.loads((site / "dados" / "operadoras.json").read_text(encoding="utf-8"))
    assert len(idx) > 1000  # a parse that came out empty or cut short fails here
    for o in idx[:20]:
        rec = json.loads((site / "dados" / "operadora" / f"{o['registro']}.json").read_text())
        assert rec["registro"] == o["registro"] and rec["nome"] == o["nome"]
    assert (site / "dados" / "schema.md").is_file()


def test_todas_holds_the_same_operators_as_the_files(site):
    dados = site / "dados"
    idx = json.loads((dados / "operadoras.json").read_text(encoding="utf-8"))
    todas = json.loads((dados / "todas.json").read_text(encoding="utf-8"))
    meta = json.loads((site / "meta.json").read_text(encoding="utf-8"))
    assert todas["date"] == meta["date"]
    assert todas["schema_version"] == meta["schema_version"] == SCHEMA_VERSION
    assert [o["registro"] for o in todas["operadoras"]] == [o["registro"] for o in idx]
    for o in todas["operadoras"]:
        arquivo = dados / "operadora" / f"{o['registro']}.json"
        assert o == json.loads(arquivo.read_text(encoding="utf-8"))


def test_known_events(site_congelado):
    def text(name):
        return (site_congelado / name).read_text(encoding="utf-8")

    assert f"tag:{BASE_TAG}:cancelamento/423122/2026-10-09" in text("cancelamento.xml")
    assert f"tag:{BASE_TAG}:direcao-tecnica/3077/422681" in text("direcao-tecnica.xml")
    assert 'id="registro-425010"' in text("registro.html")
    assert f"tag:{BASE_TAG}:portabilidade/3094<" in text("portabilidade.xml")
    assert "24/02/2026" in text("portabilidade.html")


def test_pages_show_the_notice_and_no_contact_data(site):
    for path in site.glob("*.html"):
        html = path.read_text(encoding="utf-8")
        if path.name != "404.html":
            assert "Coleta falhou." in html
        # the site's own report address is the one e-mail a page may show
        sem_relato = html.replace(RELATO_EMAIL, "")
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", sem_relato), path.name
    assert 'class="box warn"' in (site / "portabilidade.html").read_text(encoding="utf-8")


def test_every_operator_has_a_feed_that_links_to_the_portal(site):
    todas = json.loads((site / "dados" / "todas.json").read_text(encoding="utf-8"))
    geral = {e.findtext(f"{A}id") for e in entries(site / "geral.xml")}
    compartilhados = 0
    for o in todas["operadoras"]:
        reg = o["registro"]
        assert o["feed"] == f"{BASE_URL}/operadora/{reg}.xml"
        path = site / "operadora" / f"{reg}.xml"
        assert path.read_bytes().splitlines()[1] == (
            b'<?xml-stylesheet type="text/xsl" href="../feed.xsl"?>'
        )
        root = ET.parse(path).getroot()
        assert root.find(f"{A}link[@rel='alternate']").get("href") == f"{PORTAL_URL}/plano/{reg}/"
        ids = [e.findtext(f"{A}id") for e in root.findall(f"{A}entry")]
        assert 0 < len(ids) <= 50 and len(set(ids)) == len(ids), reg
        assert all(
            e.find(f"{A}link").get("href") == f"{PORTAL_URL}/plano/{reg}/"
            for e in root.findall(f"{A}entry")
        )
        compartilhados += len(geral & set(ids))
    assert compartilhados > 0  # same ids as the general feed: a reader shows the entry once
    assert len(list((site / "operadora").iterdir())) == len(todas["operadoras"])


def test_operator_feed_has_complaints_and_score(site_congelado):
    text = (site_congelado / "operadora" / "005711.xml").read_text(encoding="utf-8")
    assert f"tag:{BASE_TAG}:idss/005711/2025_2024<" in text
    assert f"tag:{BASE_TAG}:reclamacoes/005711/3T2026<" in text
    assert "Reclamações de julho a setembro de 2026: " in text


def test_a_failed_source_is_named_on_the_pages_built_from_it(site_falhas):
    def text(name):
        return (site_falhas / name).read_text(encoding="utf-8")

    rn623 = "Página da ANS com as listas da Resolução Normativa (RN) 623: a coleta deste site falha"
    port = "Página da ANS de operadoras em portabilidade especial</a>: a coleta deste site falha"
    cadop = (
        "Cadastro de operadoras ativas da ANS (CADOP)</a>: a coleta deste site falhou em 07/11/2026"
        " (o site da ANS respondeu com o erro HTTP 503). O que vem dessa fonte é a cópia da coleta"
        " de 05/11/2026, a última versão baixada."
    )
    index = text("index.html")
    assert rn623 in index and port in index and cadop in index
    # the lists: the newest PDF stored; no cause recorded, so it is not guessed
    assert (
        " desde 05/11/2026 (em 07/11/2026, a coleta não conseguiu abrir a página da ANS). O que vem"
        " dessa fonte é a cópia da coleta de 22/10/2026, a última versão baixada." in index
    )
    assert (
        " desde 05/11/2026 (em 07/11/2026, a conexão segura com o site da ANS foi interrompida"
        " (erro 35 do curl)). O que vem dessa fonte é a cópia da coleta de 04/11/2026," in index
    )
    assert cadop in text("registro.html") and rn623 not in text("registro.html")
    for name in ("cancelamento.html", "direcao-tecnica.html", "404.html"):
        assert "a coleta deste site" not in text(name), name
    # the portability page says it once, in the box above the list, with the page's own date; the
    # CADOP is named too, since it matches each operator on the page to its registration
    portabilidade = text("portabilidade.html")
    assert port not in portabilidade and rn623 not in portabilidade and cadop in portabilidade
    assert "não consegue baixar a <a href=" in portabilidade
    assert "página de portabilidade da ANS</a> desde 05/11/2026 (em 07/11/2026," in portabilidade
    assert "A versão usada aqui é a cópia da coleta de 04/11/2026; nela, a ANS" in portabilidade
    assert "só aparecem aqui quando a ANS atualizar" not in portabilidade
    meta = json.loads(text("meta.json"))
    assert [(f["assunto"], f["desde"], f.get("ultima_copia")) for f in meta["falhas"]] == [
        ("rn623", "2026-11-05", "2026-10-22"),
        ("portabilidade", "2026-11-05", "2026-11-04"),
        ("cadastro", "2026-11-07", "2026-11-05"),
        (None, "2026-11-06", None),
    ]


def test_a_source_with_no_copy_has_no_copy_day(site_falhas):
    """The penalties file is never stored: meta.json leaves `ultima_copia` out, and the index says
    the data is older than the first failure instead of naming a copy."""
    meta = json.loads((site_falhas / "meta.json").read_text(encoding="utf-8"))
    (pen,) = [f for f in meta["falhas"] if f["fonte"].startswith("penalidades")]
    assert "ultima_copia" not in pen
    index = (site_falhas / "index.html").read_text(encoding="utf-8")
    assert (
        "Arquivo penalidades_aplicadas_a_operadoras.csv da ANS</a>: a coleta deste site falha desde"
        " 06/11/2026 (em 07/11/2026, o site da ANS não respondeu dentro do tempo limite da coleta"
        " (erro 28 do curl)). O que vem dessa fonte é da última coleta que deu certo, antes de"
        " 06/11/2026." in index
    )


def test_the_portability_box_without_a_failure_dates_the_copy(site_congelado):
    """No promise about when a new decree shows up: the day of the copy and the ANS page's own
    date, with the age when the page is older than STALE_DAYS."""
    html = (site_congelado / "portabilidade.html").read_text(encoding="utf-8")
    assert "só aparecem aqui quando" not in html
    assert (
        "página de portabilidade da ANS</a> usada aqui é a cópia da coleta de 04/11/2026; nela, a"
        " ANS diz ter atualizado a página em 24/02/2026 (254 dias antes de 05/11/2026).</div>"
        in html
    )


def test_an_empty_feed_is_dated_by_the_data_not_by_a_fixed_day():
    xml = feed_bytes(
        [],
        feed_id="tag:x,2026:f",
        titulo="t",
        subtitulo="s",
        self_url="https://x/f.xml",
        alt="https://x/f.html",
        vazio="2026-11-24T00:00:00-03:00",
    )
    assert ET.fromstring(xml).findtext(f"{A}updated") == "2026-11-24T00:00:00-03:00"


def test_a_reason_says_the_recorded_cause_and_guesses_none():
    assert motivo_legivel("erro 28 do curl") == (
        "o site da ANS não respondeu dentro do tempo limite da coleta (erro 28 do curl)"
    )
    assert motivo_legivel("erro 23 do curl") == (
        "a coleta não conseguiu abrir a página da ANS (erro 23 do curl)"
    )
    for antigo in ("HTTP 000", "página fora do ar", "diretório fora do ar"):
        assert motivo_legivel(antigo) == "a coleta não conseguiu abrir a página da ANS"
    assert motivo_legivel("HTTP 404") == "o site da ANS respondeu com o erro HTTP 404"
    assert motivo_legivel("HTTP 301") == (
        "o site da ANS respondeu com o código HTTP 301, sem o arquivo"
    )


def test_an_event_names_the_file_it_links_to(site_congelado):
    for tipo, nome in (
        ("cancelamento", "Cadastro de operadoras canceladas da ANS"),
        ("registro", "Cadastro de operadoras ativas da ANS (CADOP)"),
        ("direcao-tecnica", "Arquivo da ANS de regimes especiais de direção técnica"),
        ("portabilidade", "Página da ANS de operadoras em portabilidade especial"),
    ):
        html = (site_congelado / f"{tipo}.html").read_text(encoding="utf-8")
        assert f'">{nome}</a>' in html, tipo
        assert '">fonte</a>' not in html, tipo
