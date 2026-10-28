"""Build the static site: one Atom feed per event type, a general feed, an HTML page per type and an
index, all rebuilt from the snapshots on every run.

Nothing depends on the build time: entry dates come from the acts and the collections, the site date
from the latest snapshot day, so two builds of the same snapshots are byte for byte equal.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from . import eventos as ev
from . import feed_operadora, operadoras, portabilidade, snapshots
from .atom import Entry, atom_feed, tag_uri
from .eventos import Evento
from .tabelas import tabelas

SITE_NAME = "Eventos das operadoras de planos de saúde"
REPO_URL = "https://github.com/vasfvitor/ans-feeds"
GERAL_LIMIT = 100  # general feed; type pages show as many, so every general entry has an anchor
TIPO_LIMIT = 50  # per-type feeds
INDEX_LIMIT = 20
STALE_DAYS = 90  # portability page older than this gets a warning

TIPOS = {
    "cancelamento": (
        "Cancelamentos",
        "Operadoras com registro cancelado na ANS, com o motivo do cancelamento.",
    ),
    "registro": ("Novos registros", "Operadoras que receberam registro na ANS."),
    "direcao-tecnica": (
        "Direção técnica",
        "Resoluções Operacionais que instauram regime de direção técnica numa operadora.",
    ),
    "portabilidade": (
        "Portabilidade especial",
        "Operadoras cujos beneficiários podem trocar de plano sem carência (portabilidade especial"
        " ou extraordinária).",
    ),
}

CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--muted:#6b7280;--line:#e5e7eb;--soft:#f6f7f9;--accent:#1d4ed8;
--down:#b91c1c;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#111214;--fg:#e7e7ea;--muted:#9ca3af;
--line:#2a2c31;--soft:#1a1c20;--accent:#7aa2ff;--down:#f87171}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,
"Segoe UI",Roboto,sans-serif;font-variant-numeric:tabular-nums}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:64rem;margin:0 auto;padding:0 1rem}
.site{border-bottom:1px solid var(--line)}.site .wrap{display:flex;flex-wrap:wrap;gap:.5rem 1.5rem;
align-items:baseline;padding:.75rem 1rem}.site .name{font-weight:600;color:var(--fg)}
.site nav{margin-left:auto;display:flex;flex-wrap:wrap;gap:.25rem 1rem;font-size:.9em}
main{padding:1.25rem 0 2rem}
h1{font-size:1.5rem;line-height:1.25;margin:.25rem 0 .5rem;font-weight:650}
h2{font-size:1.05rem;margin:2rem 0 .5rem;padding-bottom:.25rem;border-bottom:1px solid var(--line)}
p{margin:.5rem 0}code{font:.92em var(--mono)}
.meta{color:var(--muted);font-size:.9em}
.box{background:var(--soft);border-left:3px solid var(--accent);padding:.75rem 1rem;margin:1rem 0}
.box.warn{border-left-color:var(--down);font-weight:600}
ul.events{list-style:none;padding:0;margin:0}
ul.events li{padding:.6rem 0;border-bottom:1px solid var(--line)}
ul.events li.destaque{border-left:3px solid var(--down);padding-left:.6rem}
.when{color:var(--muted);font-size:.9em;margin-right:.5rem}
.det{color:var(--muted);font-size:.9em;margin:.15rem 0 0}
ul.feeds{padding-left:1.1rem}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.85em;padding:1rem 0 2rem}
""".strip()


def q(s: str) -> str:
    return html.escape(s, quote=True)


def anchor(e: Evento) -> str:
    return re.sub(r"[^a-z0-9]+", "-", e.id.lower()).strip("-")


def br_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def page(
    title: str,
    body: str,
    *,
    url: str,
    description: str,
    feed_url: str | None = None,
    notice: str | None = None,
    stamp: str,
) -> str:
    head = [
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta name="color-scheme" content="light dark">',
        f"<title>{q(title)}</title>",
        f'<meta name="description" content="{q(description)}">',
        f'<link rel="canonical" href="{q(url)}">',
    ]
    if feed_url:
        head.append(
            f'<link rel="alternate" type="application/atom+xml" title="{q(title)}" '
            f'href="{q(feed_url)}">'
        )
    head += [
        '<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{q(title)}">',
        f'<meta property="og:description" content="{q(description)}">',
        f'<meta property="og:url" content="{q(url)}">',
        '<meta property="og:locale" content="pt_BR">',
        f"<style>{CSS}</style></head><body>",
    ]
    nav = "".join(f'<a href="{t}.html">{q(n)}</a>' for t, (n, _) in TIPOS.items())
    aviso = f'<div class="box warn">{q(notice)}</div>' if notice else ""
    return "".join(
        head
        + [
            f'<header class="site"><div class="wrap"><a class="name" href="index.html">'
            f"{q(SITE_NAME)}</a><nav>{nav}</nav></div></header>",
            f'<main class="wrap">{aviso}{body}</main>',
            '<footer><div class="wrap">Dados abertos da ANS (dadosabertos.ans.gov.br e gov.br/ans),'
            f" coletados até {q(stamp)}. Código e histórico das coletas em "
            f'<a href="{REPO_URL}">{REPO_URL.removeprefix("https://")}</a>.</div></footer>',
            "</body></html>\n",
        ]
    )


def event_html(e: Evento) -> str:
    det = [f"{q(k)}: {q(v)}" for k, v in e.detalhes.items() if v]
    if e.registro:
        det.insert(0, f"Registro ANS {q(e.registro)}")
    if e.visto_em:
        det.append(f"publicado pela ANS até {q(e.visto_em.strftime('%d/%m/%Y'))}")
    links = []
    if e.link:
        links.append(f'<a href="{q(e.link)}">Resolução Operacional</a>')
    if e.fonte:
        links.append(f'<a href="{q(e.fonte)}">fonte</a>')
    return (
        f'<span class="when">{br_date(e.data)}</span>{q(e.titulo)}'
        f'<p class="det">{" · ".join(det)}{" · " if links else ""}{" · ".join(links)}</p>'
    )


def events_list(items: list[Evento]) -> str:
    destaque = ' class="destaque"'
    lis = "".join(
        f'<li id="{anchor(e)}"{destaque if e.destaque else ""}>{event_html(e)}</li>' for e in items
    )
    return f'<ul class="events">{lis}</ul>'


def ordered(items: list[Evento]) -> list[Evento]:
    return sorted(items, key=lambda e: (e.data, e.id), reverse=True)


FEED_XSL = f"""<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom" exclude-result-prefixes="atom">
<xsl:output method="html" encoding="utf-8" indent="yes"/>
<xsl:template match="/">
<html lang="pt-BR"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title><xsl:value-of select="atom:feed/atom:title"/></title>
<style>{CSS}</style></head>
<body>
<header class="site"><div class="wrap">
<a class="name" href="/">{SITE_NAME}</a></div></header>
<main class="wrap">
<h1><xsl:value-of select="atom:feed/atom:title"/></h1>
<div class="box"><strong>Isto é um feed Atom.</strong> Para receber os novos eventos, copie o
endereço desta página e cole no seu leitor de feeds (Feedly, Inoreader, NetNewsWire, Thunderbird…).
A versão para ler no navegador está na
<a><xsl:attribute name="href">
<xsl:value-of select="atom:feed/atom:link[@rel='alternate']/@href"/>
</xsl:attribute>página do feed</a>.</div>
<ul class="events">
<xsl:for-each select="atom:feed/atom:entry">
<li><a><xsl:attribute name="href">
<xsl:value-of select="atom:link[@rel='alternate']/@href"/></xsl:attribute>
<xsl:value-of select="atom:title"/></a></li>
</xsl:for-each>
</ul>
</main>
</body></html>
</xsl:template>
</xsl:stylesheet>
"""


def event_entry(e: Evento, *, base_tag: str, link: str) -> Entry:
    return Entry(
        id=tag_uri(base_tag, e.tipo, *e.chave.split("/")),
        title=f"{br_date(e.data)}: {e.titulo}",
        updated=e.updated.isoformat(),
        published=f"{e.data.isoformat()}T00:00:00-03:00",
        link=link,
        content=f"<div>{event_html(e)}</div>",
    )


def feed_bytes(
    entries: list[Entry],
    *,
    feed_id: str,
    titulo: str,
    subtitulo: str,
    self_url: str,
    alt: str,
    xsl_href: str = "feed.xsl",
) -> bytes:
    # compared as instants: collection times are in UTC, act dates in Brasília time
    latest = max(entries, key=lambda x: datetime.fromisoformat(x.updated), default=None)
    return atom_feed(
        feed_id=feed_id,
        title=titulo,
        subtitle=subtitulo,
        self_url=self_url,
        alt_url=alt,
        updated=latest.updated if latest else "2026-10-22T00:00:00-03:00",
        entries=entries,
        xsl_href=xsl_href,
    )


def compact(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def xml_bytes(root: ET.Element) -> bytes:
    return b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="utf-8")


def build_site(
    snapshots_dir: Path,
    site: Path,
    *,
    base_url: str,
    base_tag: str,
    portal_url: str,
    notice: str | None = None,
) -> dict:
    por_tipo: dict[str, list[Evento]] = {
        "cancelamento": ordered(ev.cancelamentos(snapshots_dir)),
        "registro": ordered(ev.registros(snapshots_dir)),
        "direcao-tecnica": ordered(ev.direcao_tecnica(snapshots_dir)),
    }
    port, atualizado = portabilidade.portabilidades(snapshots_dir)
    por_tipo["portabilidade"] = ordered(port)
    geral = ordered([e for items in por_tipo.values() for e in items])[:GERAL_LIMIT]
    stamp_day = snapshots.days(snapshots_dir)[-1]
    stamp = datetime.strptime(stamp_day, "%Y-%m-%d").strftime("%d/%m/%Y")

    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)

    def write(name: str, data: str | bytes) -> None:
        (site / name).parent.mkdir(parents=True, exist_ok=True)
        (site / name).write_bytes(data.encode("utf-8") if isinstance(data, str) else data)

    def type_entry(e: Evento) -> Entry:
        return event_entry(e, base_tag=base_tag, link=f"{base_url}/{e.tipo}.html#{anchor(e)}")

    stale = ""
    if atualizado:
        idade = (date.fromisoformat(stamp_day) - atualizado.date()).days
        stale = (
            f'<div class="box{" warn" if idade > STALE_DAYS else ""}">A página de portabilidade da'
            f" ANS foi atualizada pela última vez em {atualizado.strftime('%d/%m/%Y')}"
            f"{f' ({idade} dias antes desta coleta)' if idade > STALE_DAYS else ''}; portabilidades"
            " decretadas depois disso só aparecem aqui quando a ANS atualizar a página.</div>"
        )

    for tipo, (nome, desc) in TIPOS.items():
        items = por_tipo[tipo]
        write(
            f"{tipo}.xml",
            feed_bytes(
                [type_entry(e) for e in items[:TIPO_LIMIT]],
                feed_id=tag_uri(base_tag, tipo),
                titulo=f"ANS: {nome}",
                subtitulo=desc,
                self_url=f"{base_url}/{tipo}.xml",
                alt=f"{base_url}/{tipo}.html",
            ),
        )
        body = (
            f"<h1>{q(nome)}</h1><p>{q(desc)}</p>"
            f'<p class="meta">{len(items)} eventos no total; os {min(len(items), GERAL_LIMIT)}'
            f' mais recentes abaixo. Feed: <a href="{tipo}.xml">{tipo}.xml</a></p>'
            + (stale if tipo == "portabilidade" else "")
            + events_list(items[:GERAL_LIMIT])
        )
        write(
            f"{tipo}.html",
            page(
                f"{nome} · {SITE_NAME}",
                body,
                url=f"{base_url}/{tipo}.html",
                description=desc,
                feed_url=f"{base_url}/{tipo}.xml",
                notice=notice,
                stamp=stamp,
            ),
        )

    write(
        "geral.xml",
        feed_bytes(
            [type_entry(e) for e in geral],
            feed_id=tag_uri(base_tag, "geral"),
            titulo=f"ANS: {SITE_NAME.lower()}",
            subtitulo="Cancelamentos, novos registros, direção técnica e portabilidade especial.",
            self_url=f"{base_url}/geral.xml",
            alt=f"{base_url}/index.html",
        ),
    )
    feeds = "".join(
        f'<li><a href="{t}.html">{q(n)}</a>: {q(d)} Feed: <a href="{t}.xml">{t}.xml</a></li>'
        for t, (n, d) in TIPOS.items()
    )
    index_body = (
        f"<h1>{q(SITE_NAME)}</h1>"
        "<p>Feeds Atom com o que acontece com as operadoras de planos de saúde registradas na ANS,"
        " montados a partir dos dados abertos da agência e de coletas diárias. Assine num leitor de"
        " feeds para receber cada novo evento.</p>"
        '<ul class="feeds"><li><a href="geral.xml">geral.xml</a>: todos os eventos</li>'
        f"{feeds}</ul>"
        '<div class="box">Direção fiscal e liquidação extrajudicial ainda não estão aqui: saem em'
        " Resoluções Operacionais no Diário Oficial, que tem coleta aberta pelo INLABS da Imprensa"
        " Nacional, com cadastro, ainda não usada por este site."
        " O cancelamento por liquidação extrajudicial aparece em destaque.</div>"
        f"<h2>Eventos mais recentes</h2>{events_list(geral[:INDEX_LIMIT])}"
    )
    write(
        "index.html",
        page(
            SITE_NAME,
            index_body,
            url=f"{base_url}/",
            description="Cancelamentos, novos registros, direção técnica e portabilidade especial"
            " das operadoras de planos de saúde, como feeds Atom.",
            feed_url=f"{base_url}/geral.xml",
            notice=notice,
            stamp=stamp,
        ),
    )
    write(
        "404.html",
        page(
            f"Página não encontrada · {SITE_NAME}",
            '<h1>Página não encontrada</h1><p><a href="index.html">Voltar ao início</a></p>',
            url=f"{base_url}/404.html",
            description="Página não encontrada.",
            stamp=stamp,
        ),
    )
    write("feed.xsl", FEED_XSL)

    opml = ET.Element("opml", version="2.0")
    ET.SubElement(ET.SubElement(opml, "head"), "title").text = SITE_NAME
    body_el = ET.SubElement(opml, "body")
    for nome, titulo in [("geral", "Todos os eventos")] + [(t, n) for t, (n, _) in TIPOS.items()]:
        ET.SubElement(
            body_el,
            "outline",
            type="rss",
            text=titulo,
            title=titulo,
            xmlUrl=f"{base_url}/{nome}.xml",
            htmlUrl=f"{base_url}/{'index' if nome == 'geral' else nome}.html",
        )
    write("feeds.opml", xml_bytes(opml))

    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for nome in ["", *(f"{t}.html" for t in TIPOS)]:
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = f"{base_url}/{nome}"
        ET.SubElement(url, "lastmod").text = stamp_day
    write("sitemap.xml", xml_bytes(urlset))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n")

    # Data for the public portal: a search index and one record per operator (contract in
    # dados/schema.md).
    todos = [e for items in por_tipo.values() for e in items]
    registros = operadoras.operadoras(snapshots_dir, todos)

    # One feed per operator, linked from its portal page; left out of the OPML and the sitemap
    # (about 1,340 of them). Entries link to the portal's short /plano/<registro>/ address, which
    # redirects to the full page, so this build does not need the portal's slugs.
    por_reg: dict[str, list[Evento]] = defaultdict(list)
    for e in todos:
        if e.registro:
            por_reg[e.registro].append(e)
    trimestres, anos = feed_operadora.vistos(snapshots_dir)
    for o in registros:
        reg = o["registro"]
        o["feed"] = f"{base_url}/operadora/{reg}.xml"
        link = f"{portal_url}/plano/{reg}/"
        entries = feed_operadora.entradas(
            o,
            [(e.data, event_entry(e, base_tag=base_tag, link=link)) for e in por_reg[reg]],
            trimestres=trimestres,
            anos=anos,
            base_tag=base_tag,
            link=link,
        )
        write(
            f"operadora/{reg}.xml",
            feed_bytes(
                entries,
                feed_id=tag_uri(base_tag, "operadora", reg),
                titulo=f"{o['nome']}: avisos da ANS",
                subtitulo=f"Operadora de registro {reg} na ANS: cancelamento, direção técnica,"
                " portabilidade especial, reclamações de cada trimestre e nota anual da ANS.",
                self_url=o["feed"],
                alt=link,
                xsl_href="../feed.xsl",
            ),
        )
    write("dados/operadoras.json", compact(operadoras.indice(registros)))
    for o in registros:
        write(f"dados/operadora/{o['registro']}.json", compact(o))
    # every operator in one file: the portal build reads this instead of ~1,340 requests
    # the sources the last run could not update: the portal says which numbers are older
    falhas = snapshots.falhas(snapshots_dir)
    write(
        "dados/todas.json",
        compact({"date": stamp_day, "falhas": falhas, "operadoras": registros}),
    )
    write("dados/schema.md", operadoras.SCHEMA.read_text(encoding="utf-8"))
    # the same records as tables for people who redistribute (Procon, press): no ranking
    for nome, texto in tabelas(registros, date.fromisoformat(stamp_day)).items():
        write(f"dados/tabelas/{nome}", texto)

    meta = {
        "date": stamp_day,
        "eventos": len(geral),
        "tipos": {t: len(items) for t, items in por_tipo.items()},
        "mais_recente": geral[0].data.isoformat() if geral else None,
        "portabilidade_atualizada_em": atualizado.date().isoformat() if atualizado else None,
        "operadoras": len(registros),
        "falhas": falhas,
    }
    write("meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta
