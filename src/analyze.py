"""Run each named query from sql/queries.sql and return a dict of DataFrames."""
from __future__ import annotations

import re
import sqlite3
from typing import Dict

import pandas as pd

from src.config import DB_PATH, QUERIES_PATH


# queries.sql is split on `-- Qn |` title markers. Within each block
# we strip leading comment / separator lines so only real SQL is fed
# to pandas. The body extends until the next `-- Qn |` marker.
_HEADER_RE = re.compile(r"^--\s*(Q\d+)\s*\|[^\n]*\n", re.MULTILINE)


def load_queries() -> Dict[str, str]:
    text = QUERIES_PATH.read_text(encoding="utf-8")
    matches = list(_HEADER_RE.finditer(text))
    out: Dict[str, str] = {}
    for idx, m in enumerate(matches):
        key = m.group(1)
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end]
        # Drop leading comment-only / separator lines until first SQL line.
        lines = body.splitlines()
        cleaned: list[str] = []
        started = False
        for line in lines:
            stripped = line.strip()
            if not started and (stripped.startswith("--") or stripped == ""):
                continue
            started = True
            cleaned.append(line)
        out[key] = "\n".join(cleaned).strip().rstrip(";").strip()
    return out


def run_all() -> Dict[str, pd.DataFrame]:
    queries = load_queries()
    if not queries:
        raise RuntimeError("No Qn queries parsed from queries.sql")
    results: Dict[str, pd.DataFrame] = {}
    with sqlite3.connect(DB_PATH) as conn:
        for key, sql in queries.items():
            results[key] = pd.read_sql(sql, conn)
    return results


if __name__ == "__main__":
    res = run_all()
    for k, df in res.items():
        print(f"\n===== {k} ({len(df)} rows) =====")
        print(df.head(10).to_string(index=False))
