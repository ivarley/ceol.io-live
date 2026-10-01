"""The public thesession.org dump: one row per setting, ABC included.

`services/tune_merge_scan_service.py` already downloads this file weekly for
merge detection and deliberately never reads the ABC column. The lab reads
nothing else. Columns are looked up by header name, since the dump's column
order is the site owner's to change.
"""

import csv
import os
import sys
from dataclasses import dataclass
from typing import Iterator, Optional

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


@dataclass(frozen=True)
class Setting:
    tune_id: int
    setting_id: int
    name: str
    tune_type: str
    meter: str
    mode: str
    abc: str


def iter_settings(path: str, tune_ids: Optional[set] = None) -> Iterator[Setting]:
    """Stream the dump. `tune_ids` restricts to a candidate set."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return
        col = {name.strip().lower(): i for i, name in enumerate(header)}
        need = ("tune_id", "setting_id", "name", "type", "meter", "mode", "abc")
        missing = [c for c in need if c not in col]
        if missing:
            raise ValueError(f"tunes.csv is missing columns {missing}; header was {header}")
        for row in reader:
            if len(row) <= col["abc"]:
                continue
            try:
                tune_id = int(row[col["tune_id"]])
                setting_id = int(row[col["setting_id"]])
            except ValueError:
                continue
            if tune_ids is not None and tune_id not in tune_ids:
                continue
            yield Setting(
                tune_id=tune_id,
                setting_id=setting_id,
                name=row[col["name"]],
                tune_type=row[col["type"]],
                meter=row[col["meter"]],
                mode=row[col["mode"]],
                abc=row[col["abc"]],
            )


def dump_age_days(path: str) -> Optional[float]:
    if not os.path.exists(path):
        return None
    import time

    return (time.time() - os.path.getmtime(path)) / 86400.0
