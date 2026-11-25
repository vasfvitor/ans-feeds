from pathlib import Path

import pytest

from ans_feeds.cli import BASE_TAG, BASE_URL, PORTAL_URL
from ans_feeds.site import build_site

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "pesquisa" / "fixtures"
SNAPSHOTS = REPO / "snapshots"


def write_day(root: Path, day: str, files: dict[str, bytes | str], at: str | None = None) -> Path:
    """Write a synthetic snapshot day the way scripts/snapshot.sh does (files + FONTES.tsv)."""
    folder = root / day
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, body in files.items():
        data = body.encode("utf-8") if isinstance(body, str) else body
        (folder / name).write_bytes(data)
        if at:
            rows.append(f"{name}\thttps://example.invalid/{name}\t-\t{at}\n")
    if rows:
        (folder / "FONTES.tsv").write_text("".join(rows), encoding="utf-8")
    return folder


CONGELADO = "2026-11-05"


@pytest.fixture(scope="session")
def congelados(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The real snapshots as of CONGELADO: later days left out, so hand-checked values stay put.

    The code takes "today" from the last snapshot day, so this tree reads the same on any date. Only
    ESTADO.tsv is today's (source links and the RN 623 lists); no hand-checked value comes from it.
    """
    root = tmp_path_factory.mktemp("congelado") / "snapshots"
    root.mkdir()
    for path in SNAPSHOTS.iterdir():
        if path.is_dir() and path.name <= CONGELADO:
            (root / path.name).symlink_to(path)
    (root / "ESTADO.tsv").symlink_to(SNAPSHOTS / "ESTADO.tsv")
    return root


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "snapshots"
    root.mkdir()
    return root


OPTS = {"portal_url": PORTAL_URL, "notice": "Coleta falhou."}


@pytest.fixture(scope="session")
def site_congelado(tmp_path_factory: pytest.TempPathFactory, congelados: Path) -> Path:
    """The site built from the snapshots as of CONGELADO, for events and values checked by hand."""
    out = tmp_path_factory.mktemp("site_congelado")
    build_site(congelados, out, base_url=BASE_URL, base_tag=BASE_TAG, **OPTS)
    return out


@pytest.fixture(scope="session")
def site_falhas(tmp_path_factory: pytest.TempPathFactory, congelados: Path) -> Path:
    """CONGELADO's snapshots with failed sources, as FALHAS.tsv would have them on 2026-11-07, a run
    that stored nothing new: the RN 623 lists and the portability page failing since 2026-11-05
    (the page was last stored on 2026-11-04), the active CADOP failing on its first day, and the
    penalties file, of which no copy is kept."""
    root = tmp_path_factory.mktemp("falhas") / "snapshots"
    root.mkdir()
    for path in congelados.iterdir():
        (root / path.name).symlink_to(path.resolve())
    (root / "FALHAS.tsv").write_text(
        "2026-11-07\tlistas RN 623\tpágina fora do ar\t2026-11-05\n"  # a reason with no cause
        "2026-11-07\tportabilidade-especial.html\terro 35 do curl\t2026-11-05\n"
        "2026-11-07\tRelatorio_cadop.csv\tHTTP 503\n"  # a row from before `desde`
        "2026-11-07\tpenalidades_aplicadas_a_operadoras.csv\terro 28 do curl\t2026-11-06\n",
        encoding="utf-8",
    )
    out = tmp_path_factory.mktemp("site_falhas")
    build_site(root, out, base_url=BASE_URL, base_tag=BASE_TAG, portal_url=PORTAL_URL)
    return out
