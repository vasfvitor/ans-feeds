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
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from . import eventos as ev
from . import operadoras, portabilidade, snapshots
from .atom import Entry, atom_feed, tag_uri
from .eventos import Evento

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
<a class="name" href="index.html">{SITE_NAME}</a></div></header>
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


def feed_bytes(
    items: list[Evento],
    *,
    nome: str,
    titulo: str,
    subtitulo: str,
    alt: str,
    base_url: str,
    base_tag: str,
) -> bytes:
    entries = [
        Entry(
            id=tag_uri(base_tag, e.tipo, *e.chave.split("/")),
            title=f"{br_date(e.data)}: {e.titulo}",
            updated=e.updated.isoformat(),
            published=f"{e.data.isoformat()}T00:00:00-03:00",
            link=f"{base_url}/{e.tipo}.html#{anchor(e)}",
            content=f"<div>{event_html(e)}</div>",
        )
        for e in items
    ]
    updated = max((x.updated for x in entries), default="2026-10-22T00:00:00-03:00")
    return atom_feed(
        feed_id=tag_uri(base_tag, nome),
        title=titulo,
        subtitle=subtitulo,
        self_url=f"{base_url}/{nome}.xml",
        alt_url=alt,
        updated=updated,
        entries=entries,
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
                items[:TIPO_LIMIT],
                nome=tipo,
                titulo=f"ANS: {nome}",
                subtitulo=desc,
                alt=f"{base_url}/{tipo}.html",
                base_url=base_url,
                base_tag=base_tag,
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
            geral,
            nome="geral",
            titulo=f"ANS: {SITE_NAME.lower()}",
            subtitulo="Cancelamentos, novos registros, direção técnica e portabilidade especial.",
            alt=f"{base_url}/index.html",
            base_url=base_url,
            base_tag=base_tag,
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
        '<div class="box">Direção fiscal e liquidação extrajudicial não têm fonte aberta que possa'
        " ser coletada automaticamente (o Diário Oficial e o site antigo da ANS não permitem"
        " robôs)."
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
    registros = operadoras.operadoras(
        snapshots_dir, [e for items in por_tipo.values() for e in items]
    )
    write("dados/operadoras.json", compact(operadoras.indice(registros)))
    for o in registros:
        write(f"dados/operadora/{o['registro']}.json", compact(o))
    write("dados/schema.md", operadoras.SCHEMA.read_text(encoding="utf-8"))

    meta = {
        "date": stamp_day,
        "eventos": len(geral),
        "tipos": {t: len(items) for t, items in por_tipo.items()},
        "mais_recente": geral[0].data.isoformat() if geral else None,
        "portabilidade_atualizada_em": atualizado.date().isoformat() if atualizado else None,
        "operadoras": len(registros),
    }
    write("meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta
