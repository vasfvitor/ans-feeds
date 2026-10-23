import filecmp
import re
from collections import Counter
from xml.etree import ElementTree as ET

import pytest
from conftest import SNAPSHOTS

from ans_feeds.cli import BASE_TAG, BASE_URL
from ans_feeds.site import TIPOS, build_site

A = "{http://www.w3.org/2005/Atom}"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    build_site(SNAPSHOTS, out, base_url=BASE_URL, base_tag=BASE_TAG, notice="Coleta falhou.")
    return out


def entries(path):
    return ET.parse(path).getroot().findall(f"{A}entry")


def test_every_xml_parses_and_ids_are_clean(site):
    for path in site.glob("*.xml"):
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
    build_site(SNAPSHOTS, again, base_url=BASE_URL, base_tag=BASE_TAG, notice="Coleta falhou.")
    cmp = filecmp.dircmp(site, again)
    assert not cmp.left_only and not cmp.right_only
    assert filecmp.cmpfiles(site, again, cmp.common_files, shallow=False)[1] == []


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
