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


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "snapshots"
    root.mkdir()
    return root
