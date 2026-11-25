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
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

from . import eventos as ev
from . import feed_operadora, operadoras, portabilidade, snapshots
from .atom import Entry, atom_feed, tag_uri
from .eventos import Evento
from .tabelas import tabelas

SITE_NAME = "Eventos das operadoras de planos de saúde"
REPO_URL = "https://github.com/vasfvitor/ans-feeds"
# where a reader reports a problem by e-mail; the GitHub way is an issue form in REPO_URL
RELATO_EMAIL = "ajuda@abelhaninja.de"
GERAL_LIMIT = 100  # general feed; type pages show as many, so every general entry has an anchor
TIPO_LIMIT = 50  # per-type feeds
INDEX_LIMIT = 20
# the contract version of meta.json and dados/todas.json, as in the anvisa-api manifest: a new key
# keeps it, a key removed, renamed or redefined raises it (dados_schema.md); the portal refuses one
# it does not know. operadoras.json is a bare list and carries none: meta.json speaks for the set
SCHEMA_VERSION = 1
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


def _enc(s: str) -> str:
    """As encodeURIComponent: every reserved character escaped, a space as %20."""
    return quote(s, safe="")


def relato_urls(pagina: str, item: str, titulo: str) -> tuple[str, str]:
    """The issue-form and mailto URLs that report a problem on the page at `pagina` (absolute).

    `item` names what the page is about with its identifier, empty on a page about no single item;
    `titulo` is the page title, used in the subject when there is no item. Field ids are those of
    .github/ISSUE_TEMPLATE/problema.yml."""
    return relato_links(pagina, item, f"Problema em {item or titulo}")


def relato_links(pagina: str, item: str, assunto: str) -> tuple[str, str]:
    """relato_urls with the issue title and e-mail subject given whole."""
    campos = [("template", "problema.yml"), ("title", assunto), ("pagina", pagina), ("item", item)]
    issue = f"{REPO_URL}/issues/new?" + "&".join(f"{k}={_enc(v)}" for k, v in campos)
    # lines end in CRLF, as RFC 6068 asks of a mailto body
    corpo = (
        f"Página: {pagina}\r\nItem: {item}\r\n\r\nO que está errado:\r\n\r\n"
        "O que a fonte oficial mostra (link):\r\n"
    )
    mailto = f"mailto:{RELATO_EMAIL}?subject={_enc(assunto)}&body={_enc(corpo)}"
    return issue, mailto


def relato_rodape(pagina: str, titulo: str) -> str:
    """The footer's short form of the report links, for the page at `pagina` ("" leaves the form's
    page field for the reader)."""
    issue, mailto = relato_urls(pagina, "", titulo)
    return _rodape_html(q(issue), q(mailto))


def _rodape_html(issue: str, mailto: str) -> str:
    """The footer sentence around two hrefs already escaped for HTML or XML."""
    return (
        f'<p>Encontrou um erro? <a href="{issue}">Relato no GitHub</a>'
        " (público: não inclua dados pessoais)"
        f' ou <a href="{mailto}">{q(RELATO_EMAIL)}</a>.</p>'
    )


# The report links of the feed pages, as XSLT attribute value templates. XSLT 1.0 cannot
# percent-encode, so the feed's self URL goes through the `troca` template, which escapes ":" and
# "/"; a self URL holds no other character a query must escape (build_site refuses a base_url that
# would). Operator names may carry "&", so an operator feed names the operator by its registro, the
# digits of its self URL (/operadora/<registro>.xml); other feeds leave the item empty.
_PAGINA, _ITEM, _ASSUNTO = "\x00pagina\x00", "\x00item\x00", "\x00assunto\x00"
_REGISTRO = "\x00registro\x00"
ITEM_FEED_OPERADORA = "registro ANS {registro}"
ASSUNTO_FEED_OPERADORA = f"Problema no feed da operadora de {ITEM_FEED_OPERADORA}"
ASSUNTO_FEED = "Problema num feed"
# the characters feed.xsl leaves as they are in a query; ":" and "/" it escapes itself
URL_XSL = re.compile(r"[A-Za-z0-9._~:/-]+")


def _xsl_href(url: str) -> str:
    return (
        q(url)
        .replace(_enc(_PAGINA), "{$pagina}")
        .replace(_enc(_ITEM), "{$item}")
        .replace(_enc(_ASSUNTO), "{$assunto}")
    )


def _xsl_operadora(var: str, modelo: str, outro: str) -> str:
    """An XSLT variable holding `modelo` percent-encoded, with the feed's registro in it, on an
    operator feed, and `outro` on any other."""
    sim = _enc(modelo.format(registro=_REGISTRO)).replace(
        _enc(_REGISTRO), '<xsl:value-of select="$registro"/>'
    )
    return (
        f'<xsl:variable name="{var}"><xsl:choose><xsl:when test="$operadora">{sim}</xsl:when>'
        f"<xsl:otherwise>{_enc(outro)}</xsl:otherwise></xsl:choose></xsl:variable>"
    )


def _xsl_troca(var: str, origem: str, de: str, para: str) -> str:
    return (
        f'<xsl:variable name="{var}"><xsl:call-template name="troca">'
        f'<xsl:with-param name="s" select="{origem}"/>'
        f'<xsl:with-param name="de" select="\'{de}\'"/>'
        f'<xsl:with-param name="para" select="\'{para}\'"/>'
        "</xsl:call-template></xsl:variable>"
    )


FEED_XSL_RELATO = (
    '<xsl:variable name="self" select="atom:feed/atom:link[@rel=\'self\']/@href"/>'
    + _xsl_troca("sem_dois_pontos", "$self", ":", _enc(":"))
    + _xsl_troca("pagina", "$sem_dois_pontos", "/", _enc("/"))
    + '<xsl:variable name="registro"'
    " select=\"substring-before(substring-after($self, '/operadora/'), '.xml')\"/>"
    '<xsl:variable name="operadora"'
    " select=\"$registro != '' and translate($registro, '0123456789', '') = ''\"/>"
    + _xsl_operadora("item", ITEM_FEED_OPERADORA, "")
    + _xsl_operadora("assunto", ASSUNTO_FEED_OPERADORA, ASSUNTO_FEED)
    + '<footer><div class="wrap">'
    + _rodape_html(*map(_xsl_href, relato_links(_PAGINA, _ITEM, _ASSUNTO)))
    + "</div></footer>"
)


def page(
    title: str,
    body: str,
    *,
    url: str,
    description: str,
    feed_url: str | None = None,
    notice: str | None = None,
    falhas: str = "",
    stamp: str,
    pagina_relato: str | None = None,
    raiz: str = "",
) -> str:
    """`pagina_relato`: the page the report links name, when not `url` ("" for none). `raiz`
    prefixes the site's own links: the site's address on a page served at other paths (404)."""
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
    nav = "".join(f'<a href="{q(raiz)}{t}.html">{q(n)}</a>' for t, (n, _) in TIPOS.items())
    aviso = f'<div class="box warn">{q(notice)}</div>' if notice else ""
    if falhas:  # already HTML (falha_html)
        aviso += f'<div class="box warn">{falhas}</div>'
    return "".join(
        head
        + [
            f'<header class="site"><div class="wrap"><a class="name" href="{q(raiz)}index.html">'
            f"{q(SITE_NAME)}</a><nav>{nav}</nav></div></header>",
            f'<main class="wrap">{aviso}{body}</main>',
            '<footer><div class="wrap">Dados abertos da ANS (dadosabertos.ans.gov.br e gov.br/ans),'
            f" coletados até {q(stamp)}. Código e histórico das coletas em "
            f'<a href="{REPO_URL}">{REPO_URL.removeprefix("https://")}</a>.'
            f"{relato_rodape(url if pagina_relato is None else pagina_relato, title)}"
            "</div></footer>",
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
    if e.fonte:  # named, never just "fonte"
        links.append(f'<a href="{q(e.fonte)}">{q(NOMES.get(e.arquivo, "Arquivo da ANS"))}</a>')
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
{FEED_XSL_RELATO}
</body></html>
</xsl:template>
<xsl:template name="troca">
<xsl:param name="s"/><xsl:param name="de"/><xsl:param name="para"/>
<xsl:choose>
<xsl:when test="contains($s, $de)">
<xsl:value-of select="substring-before($s, $de)"/><xsl:value-of select="$para"/>
<xsl:call-template name="troca">
<xsl:with-param name="s" select="substring-after($s, $de)"/>
<xsl:with-param name="de" select="$de"/><xsl:with-param name="para" select="$para"/>
</xsl:call-template>
</xsl:when>
<xsl:otherwise><xsl:value-of select="$s"/></xsl:otherwise>
</xsl:choose>
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
    vazio: str,
    xsl_href: str = "feed.xsl",
) -> bytes:
    """`vazio`: the feed's updated time when it has no entry (the data's day)."""
    # compared as instants: collection times are in UTC, act dates in Brasília time
    latest = max(entries, key=lambda x: datetime.fromisoformat(x.updated), default=None)
    return atom_feed(
        feed_id=feed_id,
        title=titulo,
        subtitle=subtitulo,
        self_url=self_url,
        alt_url=alt,
        updated=latest.updated if latest else vazio,
        entries=entries,
        xsl_href=xsl_href,
    )


# a failed source's subject, as the `fontes` keys of dados/operadora/*.json (the portal's labels);
# the names are this package's own constants, or the page names scripts/snapshot.sh gives
ASSUNTOS = {
    ev.ATIVAS: "cadastro",
    ev.CANCELADAS: "cancelamentos",
    operadoras.IGR: "reclamacoes",
    ev.DIRECAO_TECNICA: "direcao_tecnica",
    portabilidade.PAGINA: "portabilidade",
    "índice de ressarcimento": "ressarcimento",
    "HC do ressarcimento": "ressarcimento",
    "histórico do IDSS": "idss",
    "listas RN 623": "rn623",
}


def assunto_da_fonte(fonte: str) -> str | None:
    if operadoras.RESSARCIMENTO.match(fonte) or fonte.startswith("HC_"):
        return "ressarcimento"
    if operadoras.IDSS.match(fonte):
        return "idss"
    if fonte.endswith(".pdf"):  # the RN 623 lists
        return "rn623"
    return ASSUNTOS.get(fonte)


# the failed source as the notice names it; by file or page name, then by subject
NOMES = {
    ev.ATIVAS: "Cadastro de operadoras ativas da ANS (CADOP)",
    ev.CANCELADAS: "Cadastro de operadoras canceladas da ANS",
    operadoras.IGR: "Índice Geral de Reclamações (IGR) da ANS",
    ev.DIRECAO_TECNICA: "Arquivo da ANS de regimes especiais de direção técnica",
    portabilidade.PAGINA: "Página da ANS de operadoras em portabilidade especial",
    "listas RN 623": "Página da ANS com as listas da Resolução Normativa (RN) 623",
}
NOMES_ASSUNTO = {
    "ressarcimento": "Arquivo da ANS de ressarcimento ao SUS",
    "idss": "Histórico do Índice de Desempenho da Saúde Suplementar (IDSS) da ANS",
    "rn623": "Listas da Resolução Normativa (RN) 623 da ANS",
}
# the subjects each event page is built from (eventos.py, portabilidade.py)
ASSUNTOS_DO_TIPO = {
    "cancelamento": {"cancelamentos"},
    "registro": {"cadastro", "cancelamentos"},
    "direcao-tecnica": {"direcao_tecnica"},
    # the CADOP files match each operator on the page to its registration (indice_cadop)
    "portabilidade": {"portabilidade", "cadastro", "cancelamentos"},
}
# the row feeds.yml writes when snapshot.sh stops halfway: any source may be stale, so every page
PAROU = "algumas fontes (a coleta parou no meio)"


def br_iso(dia: str) -> str:
    return br_date(date.fromisoformat(dia))


# curl's exit codes that say what happened to the connection (snapshot.sh: "erro N do curl")
ERROS_CURL = {
    6: "o endereço do site da ANS não foi encontrado",
    7: "a coleta não conseguiu se conectar ao site da ANS",
    28: "o site da ANS não respondeu dentro do tempo limite da coleta",
    35: "a conexão segura com o site da ANS foi interrompida",
    52: "o site da ANS fechou a conexão sem responder",
    56: "a conexão com o site da ANS caiu durante o download",
}
# a cause snapshot.sh did not record: older rows ("HTTP 000", "página fora do ar"), other curl codes
SEM_CAUSA = "a coleta não conseguiu abrir a página da ANS"


def motivo_legivel(motivo: str) -> str:
    """snapshot.sh's reason in plain words; an unknown one as it is."""
    if motivo == "HTTP 000" or motivo.endswith("fora do ar"):
        return SEM_CAUSA
    if m := re.fullmatch(r"erro (\d+) do curl", motivo):
        return f"{ERROS_CURL.get(int(m.group(1)), SEM_CAUSA)} (erro {m.group(1)} do curl)"
    if m := re.fullmatch(r"HTTP (\d{3})", motivo):
        if int(m.group(1)) >= 400:
            return f"o site da ANS respondeu com o erro HTTP {m.group(1)}"
        return f"o site da ANS respondeu com o código HTTP {m.group(1)}, sem o arquivo"
    if motivo == "nenhum PDF na página":
        return "a página da ANS veio sem nenhum PDF"
    if motivo == "nenhum arquivo no diretório":
        return "a pasta da ANS veio sem o arquivo"
    if re.fullmatch(r"\d+ bytes contra \d+ na versão anterior", motivo):
        return "o arquivo novo veio com menos da metade do tamanho do anterior, e foi descartado"
    return motivo


def falha_quando(f: dict) -> str:
    """'desde 21/11/2026 (em 24/11/2026, …)', or 'em 24/11/2026 (…)' on its first day."""
    motivo = motivo_legivel(f["motivo"])
    if f["desde"] == f["dia"]:
        return f"em {br_iso(f['dia'])} ({motivo})"
    return f"desde {br_iso(f['desde'])} (em {br_iso(f['dia'])}, {motivo})"


# the stored files behind a source snapshot.sh names by a label, not by a file name
ARQUIVOS_DO_ROTULO: dict[str, snapshots.Nome] = {
    "listas RN 623": re.compile(r"^.*\.pdf$"),
    "índice de ressarcimento": operadoras.RESSARCIMENTO,
    "HC do ressarcimento": re.compile(r"^HC_\d{4}\.csv$"),
    "histórico do IDSS": operadoras.IDSS,
}


def dia_da_copia(root: Path, fonte: str) -> str | None:
    """The collection day of the newest stored copy of a source; None when none is kept."""
    found = snapshots.versions(root, ARQUIVOS_DO_ROTULO.get(fonte, fonte))
    return found[-1][0] if found else None


def falha_html(f: dict, root: Path) -> str:
    """One failed source: its name, linked to its ANS address when known, the reason, since when
    and the day of the copy shown (`ultima_copia`)."""
    if f["fonte"] == PAROU:
        return (
            f"<p>A coleta de {br_iso(f['dia'])} parou no meio: algumas fontes podem estar com a"
            " versão da coleta anterior.</p>"
        )
    nome = (
        NOMES.get(f["fonte"]) or NOMES_ASSUNTO.get(f["assunto"]) or f"Arquivo {f['fonte']} da ANS"
    )
    url = ev.source_url(root, f["fonte"])
    nome = f'<a href="{q(url)}">{q(nome)}</a>' if url else q(nome)
    copia = f.get("ultima_copia")
    shown = (
        f"é a cópia da coleta de {br_iso(copia)}, a última versão baixada"
        if copia
        else f"é da última coleta que deu certo, antes de {br_iso(f['desde'])}"
    )
    return (
        f"<p>{nome}: a coleta deste site {'falhou' if f['desde'] == f['dia'] else 'falha'}"
        f" {q(falha_quando(f))}. O que vem dessa fonte {shown}.</p>"
    )


def _iso(cols: list[str] | None) -> str | None:
    """An ESTADO.tsv row's Last-Modified as ISO 8601 UTC, or None when there is none."""
    if not cols or len(cols) < 3 or cols[2] in ("", "-"):
        return None
    return parsedate_to_datetime(cols[2]).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    if not URL_XSL.fullmatch(base_url):
        raise ValueError(
            f"base_url {base_url!r} may hold only A-Z, a-z, 0-9 and ._~:/-"
            " (feed.xsl escapes only ':' and '/' in the report links)"
        )
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
    vazio = f"{stamp_day}T00:00:00-03:00"

    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)

    def write(name: str, data: str | bytes) -> None:
        (site / name).parent.mkdir(parents=True, exist_ok=True)
        (site / name).write_bytes(data.encode("utf-8") if isinstance(data, str) else data)

    def type_entry(e: Evento) -> Entry:
        return event_entry(e, base_tag=base_tag, link=f"{base_url}/{e.tipo}.html#{anchor(e)}")

    # the sources the last run could not update, with the subject the portal labels them by and
    # the day of the copy still shown (absent when no copy is kept)
    falhas = []
    for f in snapshots.falhas(snapshots_dir):
        f = {**f, "assunto": assunto_da_fonte(f["fonte"])}
        if f["fonte"] != PAROU and (copia := dia_da_copia(snapshots_dir, f["fonte"])):
            f["ultima_copia"] = copia
        falhas.append(f)
    falha_port = next((f for f in falhas if f["assunto"] == "portabilidade"), None)

    def avisos(assuntos: set[str] | None) -> str:
        """The failures shown on a page built from `assuntos` (None: every one, for the index)."""
        return "".join(
            falha_html(f, snapshots_dir)
            for f in falhas
            if assuntos is None or f["fonte"] == PAROU or f["assunto"] in assuntos
        )

    stale = ""
    if atualizado:
        idade = (date.fromisoformat(stamp_day) - atualizado.date()).days
        em = atualizado.strftime("%d/%m/%Y")
        copia = br_iso(dia_da_copia(snapshots_dir, portabilidade.PAGINA))
        url = ev.source_url(snapshots_dir, portabilidade.PAGINA)
        pagina = "página de portabilidade da ANS"
        pagina = f'<a href="{q(url)}">{pagina}</a>' if url else pagina
        if falha_port:
            # our download fails: the ANS may well have updated the page since
            primeiro_dia = falha_port["desde"] == falha_port["dia"]
            stale = (
                '<div class="box warn">A coleta deste site'
                f" {'não conseguiu' if primeiro_dia else 'não consegue'} baixar a {pagina}"
                f" {q(falha_quando(falha_port))}."
                f" A versão usada aqui é a cópia da coleta de {copia}; nela, a ANS diz ter"
                f" atualizado a página em {em}."
                " Portabilidades decretadas depois podem já estar na página da ANS sem aparecer"
                " aqui.</div>"
            )
        else:
            stale = (
                f'<div class="box{" warn" if idade > STALE_DAYS else ""}">A versão da {pagina}'
                f" usada aqui é a cópia da coleta de {copia}; nela, a ANS diz ter atualizado a"
                f" página em {em}"
                f"{f' ({idade} dias antes de {stamp})' if idade > STALE_DAYS else ''}.</div>"
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
                vazio=vazio,
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
                # on the portability page the box above the list says it, with the page's date
                falhas=avisos(
                    ASSUNTOS_DO_TIPO[tipo] - ({"portabilidade"} if stale and falha_port else set())
                ),
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
            vazio=vazio,
        ),
    )
    feeds = "".join(
        f'<li><a href="{t}.html">{q(n)}</a>: {q(d)} Feed: <a href="{t}.xml">{t}.xml</a></li>'
        for t, (n, d) in TIPOS.items()
    )
    index_body = (
        f"<h1>{q(SITE_NAME)}</h1>"
        "<p>Feeds Atom com o que acontece com as operadoras de planos de saúde registradas na ANS,"
        " montados a partir dos dados abertos e das páginas da agência, coletados por este site."
        " Assine num leitor de feeds para receber cada novo evento.</p>"
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
            falhas=avisos(None),
            stamp=stamp,
        ),
    )
    write(
        "404.html",
        page(
            f"Página não encontrada · {SITE_NAME}",
            f'<h1>Página não encontrada</h1><p><a href="{q(base_url)}/">Voltar ao início</a></p>',
            url=f"{base_url}/404.html",
            description="Página não encontrada.",
            stamp=stamp,
            # served for any missing path (/operadora/999999.html too): the reader names the page
            # in the form, and the links are absolute, since a relative one would follow that path
            pagina_relato="",
            raiz=f"{base_url}/",
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
                vazio=vazio,
                xsl_href="../feed.xsl",
            ),
        )
    write("dados/operadoras.json", compact(operadoras.indice(registros)))
    for o in registros:
        write(f"dados/operadora/{o['registro']}.json", compact(o))
    # every operator in one file: the portal build reads this instead of ~1,340 requests
    todas = {"schema_version": SCHEMA_VERSION, "date": stamp_day, "operadoras": registros}
    write("dados/todas.json", compact(todas))
    write("dados/schema.md", operadoras.SCHEMA.read_text(encoding="utf-8"))
    # the same records as tables for people who redistribute (Procon, press): no ranking
    for nome, texto in tabelas(registros, date.fromisoformat(stamp_day)).items():
        write(f"dados/tabelas/{nome}", texto)

    meta = {
        "schema_version": SCHEMA_VERSION,
        "date": stamp_day,
        "eventos": len(geral),
        "tipos": {t: len(items) for t, items in por_tipo.items()},
        "mais_recente": geral[0].data.isoformat() if geral else None,
        "portabilidade_atualizada_em": atualizado.date().isoformat() if atualizado else None,
        "operadoras": len(registros),
        "falhas": falhas,
        # the CADOP changes every weekday at the ANS: its age says whether the source has stopped
        "cadop_last_modified": _iso(snapshots.estado(snapshots_dir, ev.ATIVAS)),
    }
    write("meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta
