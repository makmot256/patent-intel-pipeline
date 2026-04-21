"""End-to-end pipeline runner.

Running  `python -m src.run_all`  from the project root is enough to
reproduce every artifact in the repo: raw data is downloaded, cleaned,
loaded into SQLite, analysed, and reported.
"""
from __future__ import annotations

import time

from src import clean, download, load, plot, report


def _step(label: str, func):
    print(f"\n{'=' * 70}\n>>> {label}\n{'=' * 70}")
    t0 = time.time()
    func()
    print(f"<<< {label} done in {time.time() - t0:0.1f}s")


def main() -> None:
    _step("STEP 1/5  DOWNLOAD", download.main)
    _step("STEP 2/5  CLEAN",    clean.main)
    _step("STEP 3/5  LOAD",     load.main)
    _step("STEP 4/5  REPORT",   report.main)
    _step("STEP 5/5  CHARTS",   plot.main)
    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
