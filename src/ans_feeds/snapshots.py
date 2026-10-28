"""Read the incremental snapshot tree written by scripts/snapshot.sh.

`snapshots/YYYY-MM-DD/` holds only the files that changed that day, plus `FONTES.tsv` (name, url,
Last-Modified, collection time in UTC). A file absent from a day did not change, so its current
version is the one in the latest earlier day that has it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def days(root: Path) -> list[str]:
    """Snapshot days, oldest first."""
    return sorted(p.name for p in root.iterdir() if p.is_dir() and DAY.match(p.name))


def versions(root: Path, name: str) -> list[tuple[str, Path]]:
    """Every stored version of `name`, oldest first, as (day, path)."""
    return [(d, root / d / name) for d in days(root) if (root / d / name).is_file()]


def falhas(root: Path) -> list[dict]:
    """The sources the last snapshot run could not update, from FALHAS.tsv (written by
    scripts/snapshot.sh): [{dia, fonte, motivo}], empty when none failed or the file is absent."""
    path = Path(root) / "FALHAS.tsv"
    if not path.is_file():
        return []
    out = []
    for linha in path.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            dia, fonte, motivo = (linha.split("\t") + ["", ""])[:3]
            out.append({"dia": dia, "fonte": fonte, "motivo": motivo})
    return out


def latest(root: Path, name: str) -> Path | None:
    found = versions(root, name)
    return found[-1][1] if found else None


def collected_at(root: Path, day: str, name: str) -> datetime | None:
    """Collection time of `name` in `day`, from FONTES.tsv (absent for files stored by hand)."""
    fontes = root / day / "FONTES.tsv"
    if not fontes.is_file():
        return None
    for line in fontes.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if len(cols) >= 4 and cols[0] == name:
            return datetime.strptime(cols[3], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return None


def first_seen(
    root: Path, name: str, keys: Callable[[Path], Iterable[str]]
) -> dict[str, tuple[str, datetime | None]]:
    """For each key that appeared after the first stored version of `name`: (day, collection time).

    Keys already in the first version are the baseline: when they appeared is unknown, so they are
    left out and the caller falls back to the date of the act itself.
    """
    seen: set[str] = set()
    out: dict[str, tuple[str, datetime | None]] = {}
    for i, (day, path) in enumerate(versions(root, name)):
        current = set(keys(path))
        if i:
            when = collected_at(root, day, name)
            for key in sorted(current - seen):
                out[key] = (day, when)
        seen |= current
    return out
