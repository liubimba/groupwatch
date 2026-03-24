from __future__ import annotations

import csv
from pathlib import Path

from .models import Group


def load_groups(path: Path) -> list[Group]:
    with path.open(encoding="utf-8", newline="") as f:
        return [
            Group(
                url=row["url"].strip(),
                name=(row.get("name") or "").strip(),
                members=frozenset(m.strip() for m in (row.get("accounts") or "").split(";") if m.strip()),
            )
            for row in csv.DictReader(f)
            if (row.get("url") or "").strip()
        ]
