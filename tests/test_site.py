import json
import re
from collections import Counter
from xml.etree import ElementTree as ET

import pytest
from conftest import SNAPSHOTS

from ans_feeds.cli import BASE_TAG, BASE_URL, PORTAL_URL
from ans_feeds.site import TIPOS, build_site

A = "{http://www.w3.org/2005/Atom}"
OPTS = {"portal_url": PORTAL_URL, "notice": "Coleta falhou."}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
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
    assert len(idx) > 1106
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
    assert [o["registro"] for o in todas["operadoras"]] == [o["registro"] for o in idx]
    for o in todas["operadoras"]:
        arquivo = dados / "operadora" / f"{o['registro']}.json"
        assert o == json.loads(arquivo.read_text(encoding="utf-8"))


def test_known_events(site):
    def text(name):
        return (site / name).read_text(encoding="utf-8")

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
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", html), path.name
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


def test_operator_feed_has_complaints_and_score(site):
    text = (site / "operadora" / "005711.xml").read_text(encoding="utf-8")
    assert f"tag:{BASE_TAG}:idss/005711/2025_2024<" in text
    assert f"tag:{BASE_TAG}:reclamacoes/005711/3T2026<" in text
    assert "Reclamações de julho a setembro de 2026: " in text
