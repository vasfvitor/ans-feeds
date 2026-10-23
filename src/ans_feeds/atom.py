"""Atom 1.0 output, in the same shape as anvisa-feeds (stylesheet PI, generator, author)."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from . import __version__

ATOM = "http://www.w3.org/2005/Atom"


def tag_uri(base_tag: str, *parts: str) -> str:
    """RFC 4151 tag URI. Every part must be non-empty: an empty segment changes the id later."""
    if not parts or not all(parts):
        raise ValueError(f"empty segment in tag URI parts {parts!r}")
    return f"tag:{base_tag}:" + "/".join(parts)


@dataclass
class Entry:
    id: str
    title: str
    updated: str
    published: str
    link: str
    content: str


def atom_feed(
    *,
    feed_id: str,
    title: str,
    subtitle: str,
    self_url: str,
    alt_url: str,
    updated: str,
    entries: list[Entry],
    xsl_href: str = "feed.xsl",
    author: str = "ans-feeds (dados: ANS)",
) -> bytes:
    feed = ET.Element("feed", xmlns=ATOM)
    ET.SubElement(feed, "id").text = feed_id
    ET.SubElement(feed, "title").text = title
    ET.SubElement(feed, "subtitle").text = subtitle
    ET.SubElement(feed, "updated").text = updated
    ET.SubElement(feed, "link", rel="self", href=self_url)
    ET.SubElement(feed, "link", rel="alternate", href=alt_url)
    ET.SubElement(feed, "generator", version=__version__).text = "ans-feeds"
    ET.SubElement(ET.SubElement(feed, "author"), "name").text = author
    for e in entries:
        entry = ET.SubElement(feed, "entry")
        ET.SubElement(entry, "id").text = e.id
        ET.SubElement(entry, "title").text = e.title
        ET.SubElement(entry, "updated").text = e.updated
        ET.SubElement(entry, "published").text = e.published
        ET.SubElement(entry, "link", rel="alternate", href=e.link)
        ET.SubElement(entry, "content", type="html").text = e.content
    # The stylesheet makes a browser show a readable page instead of raw XML; readers ignore it.
    return (
        b'<?xml version="1.0" encoding="utf-8"?>\n'
        + f'<?xml-stylesheet type="text/xsl" href="{xsl_href}"?>\n'.encode()
        + ET.tostring(feed, encoding="unicode").encode("utf-8")
    )
