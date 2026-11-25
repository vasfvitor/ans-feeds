"""The links that report a problem on a page: the prefilled issue form, and an e-mail."""

import re
from urllib.parse import parse_qs, quote, unquote, urlsplit

from ans_feeds.cli import BASE_URL
from ans_feeds.site import (
    ASSUNTO_FEED,
    ASSUNTO_FEED_OPERADORA,
    FEED_XSL_RELATO,
    RELATO_EMAIL,
    REPO_URL,
    q,
    relato_links,
    relato_rodape,
    relato_urls,
)

PAGINA = f"{BASE_URL}/cancelamento.html"


def campos(url: str) -> dict[str, str]:
    """The query of `url`, decoded; a field present but empty stays, as ""."""
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query, keep_blank_values=True).items()}


def test_the_issue_link_prefills_the_form_of_this_repo():
    issue, _ = relato_urls(PAGINA, "Unimed Rio (registro ANS 393321)", "Cancelamentos")
    assert issue.startswith(f"{REPO_URL}/issues/new?template=problema.yml&")
    assert campos(issue) == {
        "template": "problema.yml",
        "title": "Problema em Unimed Rio (registro ANS 393321)",
        "pagina": PAGINA,
        "item": "Unimed Rio (registro ANS 393321)",
    }


def test_without_an_item_the_title_names_the_page_and_the_item_is_empty():
    issue, mailto = relato_urls(PAGINA, "", "Cancelamentos")
    assert campos(issue)["title"] == "Problema em Cancelamentos"
    assert campos(issue)["item"] == ""
    assert "&item=" in issue
    assert campos(mailto)["subject"] == "Problema em Cancelamentos"
    assert "\nItem: \n" in campos(mailto)["body"]


def test_accents_spaces_ampersand_hash_and_newlines_are_escaped():
    item = "Saúde & Vida #1 (registro ANS 000000)"
    issue, mailto = relato_urls(PAGINA, item, "")
    for url in (issue, mailto):
        query = urlsplit(url).query
        assert " " not in url and "#" not in url and "+" not in query and "\n" not in url
        assert "Sa%C3%BAde%20%26%20Vida%20%231" in query
    # the "&" of the item does not split the field
    assert campos(issue)["item"] == item
    assert campos(mailto)["subject"] == f"Problema em {item}"
    assert "%0A" in urlsplit(mailto).query


def test_the_page_url_is_encoded_whole():
    issue, _ = relato_urls(PAGINA, "", "Cancelamentos")
    assert "pagina=https%3A%2F%2F" in issue
    assert campos(issue)["pagina"] == PAGINA


def test_the_email_goes_to_the_report_address_with_the_body_to_fill():
    _, mailto = relato_urls(PAGINA, "Unimed Rio (registro ANS 393321)", "Cancelamentos")
    endereco, _, _ = mailto.partition("?")
    assert endereco == f"mailto:{RELATO_EMAIL}"
    assert unquote(urlsplit(mailto).query.split("body=")[1]) == (
        f"Página: {PAGINA}\nItem: Unimed Rio (registro ANS 393321)\n\n"
        "O que está errado:\n\nO que a fonte oficial mostra (link):\n"
    )


def test_the_footer_sentence_escapes_the_urls_for_html():
    html = relato_rodape(PAGINA, "Cancelamentos")
    assert html.startswith("<p>Encontrou um erro? <a href=")
    assert ">Relato no GitHub</a> ou <a href=" in html
    assert html.endswith(f">{RELATO_EMAIL}</a>.</p>")
    assert "&amp;title=" in html and "?template=problema.yml&title" not in html


def test_every_page_footer_reports_on_its_own_page(site_congelado):
    paginas = sorted(site_congelado.glob("*.html"))
    assert "404.html" in [p.name for p in paginas]
    for path in paginas:
        html = path.read_text(encoding="utf-8")
        rodape = html[html.index("<footer>") :]
        url = f"{BASE_URL}/" if path.name == "index.html" else f"{BASE_URL}/{path.name}"
        if path.name == "404.html":
            url = ""  # served for any missing path: its own address says nothing
        issue, mailto = relato_urls(url, "", html.split("<title>")[1].split("</title>")[0])
        assert "Encontrou um erro?" in rodape, path.name
        assert issue.replace("&", "&amp;") in rodape, path.name
        assert mailto.replace("&", "&amp;") in rodape, path.name


def test_the_404_footer_leaves_the_page_for_the_reader(site_congelado):
    html = (site_congelado / "404.html").read_text(encoding="utf-8")
    issue = re.search(r'href="([^"]*/issues/new[^"]*)"', html).group(1).replace("&amp;", "&")
    mailto = re.search(r'href="(mailto:[^"]*)"', html).group(1).replace("&amp;", "&")
    assert campos(issue)["pagina"] == ""
    assert campos(mailto)["body"].startswith("Página: \nItem: \n")


# what feed.xsl's `troca` template does to the self URL; the only escapes it knows
def troca_xsl(url: str) -> str:
    return url.replace(":", "%3A").replace("/", "%2F")


def test_every_feed_self_url_needs_only_the_escapes_the_xsl_makes(site_congelado):
    """XSLT 1.0 cannot percent-encode: feed.xsl escapes ":" and "/" of the feed's self URL and
    nothing else, so every self URL must hold no other character a query would escape."""
    feeds = sorted(site_congelado.glob("*.xml")) + sorted(site_congelado.glob("operadora/*.xml"))
    assert any(f.parent.name == "operadora" for f in feeds)
    for f in feeds:
        texto = f.read_text(encoding="utf-8")
        if "<feed" not in texto:
            continue  # sitemap
        self_url = re.search(r'<link rel="self" href="([^"]+)"', texto).group(1)
        assert re.fullmatch(r"[A-Za-z0-9._~:/-]+", self_url), f.name


def test_the_feed_pages_footer_matches_the_python_links(site_congelado):
    """feed.xsl carries the footer; with its variables filled as the XSLT fills them, the hrefs are
    the ones relato_links builds (an operator feed and the general feed)."""
    xsl = (site_congelado / "feed.xsl").read_text(encoding="utf-8")
    assert FEED_XSL_RELATO in xsl
    assert "Encontrou um erro?" in FEED_XSL_RELATO
    for self_url, assunto in [
        (f"{BASE_URL}/operadora/393321.xml", ASSUNTO_FEED_OPERADORA),
        (f"{BASE_URL}/geral.xml", ASSUNTO_FEED),
    ]:
        rodape = FEED_XSL_RELATO.replace("{$pagina}", troca_xsl(self_url)).replace(
            "{$assunto}", quote(assunto, safe="")
        )
        issue, mailto = relato_links(self_url, "", assunto)
        assert f'href="{q(issue)}"' in rodape
        assert f'href="{q(mailto)}"' in rodape
