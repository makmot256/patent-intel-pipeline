"""Load the cleaned CSVs into a SQLite database following schema.sql."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.config import DB_PATH, PROCESSED_DIR, SCHEMA_PATH


# (table, csv filename, required?)
TABLE_FILES = [
    ("patents",         "clean_patents.csv",          True),
    ("inventors",       "clean_inventors.csv",        True),
    ("companies",       "clean_companies.csv",        True),
    ("patent_inventor", "clean_patent_inventor.csv",  True),
    ("patent_company",  "clean_patent_company.csv",   True),
    ("patent_cpc",      "clean_patent_cpc.csv",       False),  # optional bonus
]


def _apply_schema(conn: sqlite3.Connection) -> None:
    print(f"[load] applying schema from {SCHEMA_PATH}")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())


def _insert_csv(conn: sqlite3.Connection, table: str, path: Path) -> int:
    df = pd.read_csv(path)
    df.to_sql(table, conn, if_exists="append", index=False, chunksize=10_000)
    return len(df)


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    print(f"[load] creating {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        _apply_schema(conn)

        for table, fname, required in TABLE_FILES:
            path = PROCESSED_DIR / fname
            if not path.exists():
                msg = "WARNING" if required else "info"
                print(f"[load] {msg}: {path.name} missing, skipping {table}")
                continue
            n = _insert_csv(conn, table, path)
            print(f"[load] inserted {n:,} rows into {table}")

        conn.commit()
        counts = {}
        for t, *_ in TABLE_FILES:
            try:
                counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.OperationalError:
                counts[t] = 0
        print("[load] final table sizes:", counts)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
