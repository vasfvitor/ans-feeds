from pathlib import Path

import pytest

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
