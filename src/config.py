"""Central configuration for the patent intelligence pipeline.

Change values here to scale the pipeline up or down. Every other
module imports from this file so a single edit reconfigures the
whole project.
"""
from __future__ import annotations

from pathlib import Path

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR       = ROOT_DIR / "data"
RAW_DIR        = DATA_DIR / "raw"
PROCESSED_DIR  = DATA_DIR / "processed"
DB_DIR         = ROOT_DIR / "db"
SQL_DIR        = ROOT_DIR / "sql"
REPORTS_DIR    = ROOT_DIR / "reports"
CHARTS_DIR     = REPORTS_DIR / "charts"

DB_PATH        = DB_DIR / "patents.db"
SCHEMA_PATH    = SQL_DIR / "schema.sql"
QUERIES_PATH   = SQL_DIR / "queries.sql"

for _d in (RAW_DIR, PROCESSED_DIR, DB_DIR, REPORTS_DIR, CHARTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# Data source (PatentsView on S3 -- same files as data.uspto.gov/pvgpatdis)
# ----------------------------------------------------------------------
PATENTSVIEW_BASE = "https://s3.amazonaws.com/data.patentsview.org/download"

# ----------------------------------------------------------------------
# Feature flags -- every heavy file is OPT-IN so a fresh clone is never
# forced to download gigabytes. Set a flag to True and rerun
#   python -m src.run_all
# to pull the real file and switch the pipeline over to it.
# ----------------------------------------------------------------------
# When True, replaces the synthetic inventor universe with the real
# disambiguated 700 MB PatentsView file.
USE_REAL_INVENTORS = False
# When True, replaces synthetic companies with the real 359 MB file.
USE_REAL_COMPANIES = False
# When True, downloads g_cpc_current.tsv.zip (495 MB) and enables the
# CPC innovation-category reports and dashboard tab.
USE_CPC = True

# URLs are computed from the flags so `download.py` stays flag-driven.
def _files() -> dict[str, str]:
    out = {
        "g_patent":                 f"{PATENTSVIEW_BASE}/g_patent.tsv.zip",
        "g_location_disambiguated": f"{PATENTSVIEW_BASE}/g_location_disambiguated.tsv.zip",
    }
    if USE_REAL_INVENTORS:
        out["g_inventor_disambiguated"]     = f"{PATENTSVIEW_BASE}/g_inventor_disambiguated.tsv.zip"
        out["g_inventor_not_disambiguated"] = f"{PATENTSVIEW_BASE}/g_inventor_not_disambiguated.tsv.zip"
    if USE_REAL_COMPANIES:
        out["g_assignee_disambiguated"]     = f"{PATENTSVIEW_BASE}/g_assignee_disambiguated.tsv.zip"
        out["g_assignee_not_disambiguated"] = f"{PATENTSVIEW_BASE}/g_assignee_not_disambiguated.tsv.zip"
    if USE_CPC:
        out["g_cpc_current"]                = f"{PATENTSVIEW_BASE}/g_cpc_current.tsv.zip"
    return out


FILES: dict[str, str] = _files()

# ----------------------------------------------------------------------
# Pipeline tuning
# ----------------------------------------------------------------------
# Year range kept after filtering. 2020-2024 gives Q4 (trends over time)
# a meaningful curve.
YEAR_MIN = 2020
YEAR_MAX = 2024

# Hard cap on patents kept after filtering. Set to None for no cap.
# Sample is stratified by year.
MAX_PATENTS = 100_000

# Pandas chunk size for reading the big TSVs.
CHUNKSIZE = 100_000

# Size of the synthetic universe (only used when USE_REAL_* flags are
# False).
N_INVENTORS = 5_000
N_COMPANIES = 800

# RNG seed so synthetic data is reproducible.
RANDOM_SEED = 42

# ----------------------------------------------------------------------
# Dashboard / plots branding
# ----------------------------------------------------------------------
BRAND = {
    "title":    "Patent Intelligence",
    "tagline":  "Global innovation trends from USPTO PatentsView",
    "primary":  "#0B5FFF",      # USPTO-ish deep blue
    "accent":   "#00C2A8",      # mint green
    "dark":     "#0E1F3A",
    "muted":    "#6B7280",
}

# Discrete categorical palette used across plots AND plotly dashboard
PALETTE = [
    "#0B5FFF", "#00C2A8", "#F59E0B", "#EF4444", "#8B5CF6",
    "#10B981", "#EC4899", "#14B8A6", "#F97316", "#6366F1",
]
