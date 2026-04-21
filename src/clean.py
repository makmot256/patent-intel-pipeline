"""Clean PatentsView data and assemble every table needed by the DB.

Behaviour is controlled by flags in src/config.py:

  USE_REAL_INVENTORS / USE_REAL_COMPANIES
      When False (default) inventors / companies are generated as a
      realistic synthetic universe linked to the real patent IDs.
      When True, the real PatentsView files are read in chunks and
      filtered to patents we kept.

  USE_CPC
      When True, g_cpc_current.tsv.zip is read, CPC sections are
      extracted and written to data/processed/clean_patent_cpc.csv.
"""
from __future__ import annotations

import random
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    CHUNKSIZE,
    MAX_PATENTS,
    N_COMPANIES,
    N_INVENTORS,
    PROCESSED_DIR,
    RANDOM_SEED,
    RAW_DIR,
    USE_CPC,
    USE_REAL_COMPANIES,
    USE_REAL_INVENTORS,
    YEAR_MAX,
    YEAR_MIN,
)


# ----------------------------------------------------------------------
# Zip helpers
# ----------------------------------------------------------------------
def _inner_tsv(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        for n in zf.namelist():
            if n.lower().endswith(".tsv"):
                return n
    raise RuntimeError(f"No .tsv inside {zip_path}")


def _iter_tsv(zip_path: Path, **read_csv_kw) -> pd.io.parsers.TextFileReader:
    """Open a chunked TSV reader over the single .tsv inside a zip."""
    zf = zipfile.ZipFile(zip_path)
    inner = _inner_tsv(zip_path)
    fh = zf.open(inner)
    defaults = dict(sep="\t", dtype=str, on_bad_lines="skip",
                    encoding="utf-8", low_memory=False, chunksize=CHUNKSIZE)
    defaults.update(read_csv_kw)
    reader = pd.read_csv(fh, **defaults)
    reader._zf_handle = zf  # keep zip alive for the duration of the reader
    return reader


# ----------------------------------------------------------------------
# Real: patents
# ----------------------------------------------------------------------
def clean_patents() -> pd.DataFrame:
    src = RAW_DIR / "g_patent.tsv.zip"
    print(f"[patents] reading {src.name} in chunks of {CHUNKSIZE:,}...")

    wanted_cols = {"patent_id", "patent_title", "patent_abstract", "patent_date"}
    kept: list[pd.DataFrame] = []
    total_rows = 0
    reader = _iter_tsv(src, usecols=lambda c: c in wanted_cols)
    for chunk in reader:
        total_rows += len(chunk)
        chunk["patent_date"] = pd.to_datetime(chunk["patent_date"], errors="coerce")
        chunk["year"] = chunk["patent_date"].dt.year
        mask = chunk["year"].between(YEAR_MIN, YEAR_MAX)
        kept.append(chunk.loc[mask].copy())

    df = pd.concat(kept, ignore_index=True) if kept else pd.DataFrame()
    print(f"[patents] scanned {total_rows:,} rows, kept {len(df):,} for {YEAR_MIN}-{YEAR_MAX}")

    df = df.rename(columns={
        "patent_title":    "title",
        "patent_abstract": "abstract",
        "patent_date":     "filing_date",
    })
    if "abstract" not in df.columns:
        df["abstract"] = ""  # g_patent.tsv does not ship abstracts

    df["patent_id"] = df["patent_id"].astype(str).str.strip()
    df["title"]    = df["title"].fillna("").str.strip()
    df["abstract"] = df["abstract"].fillna("").str.strip()
    df["year"]     = df["year"].astype("Int64")

    df = df.dropna(subset=["patent_id"])
    df = df[df["patent_id"] != ""]
    df = df.drop_duplicates(subset=["patent_id"])

    if MAX_PATENTS is not None and len(df) > MAX_PATENTS:
        years = df["year"].dropna().unique()
        per_year = max(1, MAX_PATENTS // max(1, len(years)))
        df = (
            df.groupby("year", group_keys=False)[df.columns.tolist()]
              .apply(lambda g: g.sample(n=min(per_year, len(g)), random_state=RANDOM_SEED))
              .reset_index(drop=True)
        )
        print(f"[patents] stratified-sampled down to {len(df):,} rows (~{per_year:,}/year)")

    out = PROCESSED_DIR / "clean_patents.csv"
    df.to_csv(out, index=False)
    print(f"[patents] wrote {len(df):,} rows -> {out}")
    return df


# ----------------------------------------------------------------------
# Real: locations (for country distribution)
# ----------------------------------------------------------------------
def load_location_countries() -> pd.DataFrame:
    """Return DataFrame with columns: location_id, country (upper-case 2-letter)."""
    src = RAW_DIR / "g_location_disambiguated.tsv.zip"
    print(f"[location] reading {src.name}...")
    zf = zipfile.ZipFile(src)
    inner = _inner_tsv(src)
    with zf.open(inner) as fh:
        df = pd.read_csv(fh, sep="\t", dtype=str, on_bad_lines="skip",
                         encoding="utf-8", low_memory=False)
    cols = {c.lower(): c for c in df.columns}
    country_col = cols.get("disambig_country") or cols.get("country")
    id_col      = cols.get("location_id")
    out = pd.DataFrame({
        "location_id": df[id_col] if id_col else pd.Series(range(len(df))).astype(str),
        "country":     df[country_col].astype(str).str.strip().str.upper(),
    }).dropna()
    out = out[out["country"] != ""]
    print(f"[location] collected {len(out):,} rows")
    return out


# ----------------------------------------------------------------------
# Real: inventors (only if USE_REAL_INVENTORS = True)
# ----------------------------------------------------------------------
def clean_real_inventors(
    patents: pd.DataFrame, locations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    patent_ids = set(patents["patent_id"].astype(str))

    # 1) mapping patent_id -> inventor_id (+ location) from the huge file
    map_src = RAW_DIR / "g_inventor_not_disambiguated.tsv.zip"
    print(f"[inventors] scanning {map_src.name} for matching patents...")
    map_rows: list[pd.DataFrame] = []
    reader = _iter_tsv(map_src)
    for chunk in reader:
        # Columns: patent_id, inventor_id, location_id, ...
        keep_cols = [c for c in ("patent_id", "inventor_id", "location_id") if c in chunk.columns]
        if not {"patent_id", "inventor_id"}.issubset(keep_cols):
            continue
        sub = chunk[keep_cols]
        sub = sub[sub["patent_id"].isin(patent_ids)]
        if len(sub):
            map_rows.append(sub)

    pi = pd.concat(map_rows, ignore_index=True) if map_rows else pd.DataFrame(
        columns=["patent_id", "inventor_id", "location_id"])
    pi = pi.dropna(subset=["patent_id", "inventor_id"]).drop_duplicates(
        subset=["patent_id", "inventor_id"])
    inventor_ids = set(pi["inventor_id"])

    # 2) inventor names
    inv_src = RAW_DIR / "g_inventor_disambiguated.tsv.zip"
    print(f"[inventors] scanning {inv_src.name} for {len(inventor_ids):,} ids...")
    inv_rows: list[pd.DataFrame] = []
    reader = _iter_tsv(inv_src)
    for chunk in reader:
        sub = chunk[chunk["inventor_id"].isin(inventor_ids)]
        if len(sub):
            keep = {"inventor_id", "disambig_inventor_name_first",
                    "disambig_inventor_name_last"} & set(sub.columns)
            sub = sub[list(keep)]
            inv_rows.append(sub)
    inventors_raw = pd.concat(inv_rows, ignore_index=True) if inv_rows else pd.DataFrame()

    if inventors_raw.empty:
        raise RuntimeError("No inventor rows matched -- did the real files download?")

    first = "disambig_inventor_name_first"
    last  = "disambig_inventor_name_last"
    inventors_raw["name"] = (
        inventors_raw.get(first, "").fillna("") + " "
        + inventors_raw.get(last, "").fillna("")
    ).str.strip().str.title()

    # 3) join to country via location mapping
    country_by_loc = locations.set_index("location_id")["country"].to_dict()
    pi["country"] = pi["location_id"].map(country_by_loc)
    # Inventor's country = most common country observed in their patents
    inventor_country = (
        pi.dropna(subset=["country"])
          .groupby("inventor_id")["country"]
          .agg(lambda s: s.value_counts().idxmax())
    )
    inventors = inventors_raw[["inventor_id", "name"]].drop_duplicates("inventor_id")
    inventors["country"] = inventors["inventor_id"].map(inventor_country).fillna("")

    pi = pi[["patent_id", "inventor_id"]]
    print(f"[inventors] real inventors: {len(inventors):,}, links: {len(pi):,}")
    return inventors, pi


# ----------------------------------------------------------------------
# Real: companies (only if USE_REAL_COMPANIES = True)
# ----------------------------------------------------------------------
def clean_real_companies(patents: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    patent_ids = set(patents["patent_id"].astype(str))

    map_src = RAW_DIR / "g_assignee_not_disambiguated.tsv.zip"
    print(f"[companies] scanning {map_src.name}...")
    map_rows: list[pd.DataFrame] = []
    reader = _iter_tsv(map_src)
    for chunk in reader:
        if not {"patent_id", "assignee_id"}.issubset(chunk.columns):
            continue
        sub = chunk[["patent_id", "assignee_id"]]
        sub = sub[sub["patent_id"].isin(patent_ids)]
        if len(sub):
            map_rows.append(sub)
    pc = pd.concat(map_rows, ignore_index=True) if map_rows else pd.DataFrame(
        columns=["patent_id", "assignee_id"])
    pc = pc.dropna().drop_duplicates()
    pc = pc.rename(columns={"assignee_id": "company_id"})
    company_ids = set(pc["company_id"])

    asn_src = RAW_DIR / "g_assignee_disambiguated.tsv.zip"
    print(f"[companies] scanning {asn_src.name} for {len(company_ids):,} ids...")
    asn_rows: list[pd.DataFrame] = []
    reader = _iter_tsv(asn_src)
    for chunk in reader:
        if "assignee_id" not in chunk.columns:
            continue
        sub = chunk[chunk["assignee_id"].isin(company_ids)]
        if len(sub):
            name_col = next((c for c in sub.columns if "organization" in c.lower()), None)
            if not name_col:
                continue
            asn_rows.append(sub[["assignee_id", name_col]].rename(
                columns={"assignee_id": "company_id", name_col: "name"}))
    companies = pd.concat(asn_rows, ignore_index=True) if asn_rows else pd.DataFrame()
    if companies.empty:
        raise RuntimeError("No company rows matched -- did the real files download?")
    companies = companies.dropna(subset=["name"]).drop_duplicates("company_id")
    companies["name"] = companies["name"].astype(str).str.strip()
    companies = companies[companies["name"] != ""]
    print(f"[companies] real companies: {len(companies):,}, links: {len(pc):,}")
    return companies, pc


# ----------------------------------------------------------------------
# Synthetic: inventors + companies + links
# ----------------------------------------------------------------------
_FIRST_NAMES = [
    "John", "Mary", "David", "Sarah", "Michael", "Emma", "James", "Olivia",
    "Robert", "Sophia", "William", "Isabella", "Daniel", "Mia", "Thomas",
    "Charlotte", "Hiroshi", "Yuki", "Wei", "Li", "Ming", "Jing", "Raj",
    "Priya", "Ahmed", "Fatima", "Hans", "Greta", "Pierre", "Chloe",
    "Carlos", "Lucia", "Ivan", "Anastasia", "Kenji", "Akira", "Sanjay",
    "Anita", "Marco", "Elena", "Andre", "Beatriz", "Mehmet", "Zeynep",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Martin",
    "Lee", "Chen", "Wang", "Zhang", "Liu", "Singh", "Patel", "Kumar",
    "Yamamoto", "Tanaka", "Suzuki", "Nakamura", "Schmidt", "Mueller",
    "Schneider", "Dubois", "Martinez", "Rossi", "Ferrari", "Kowalski",
    "Novak", "Ivanov", "Petrov", "Ozturk", "Demir", "Kim", "Park",
]
_COMPANY_PREFIXES = [
    "International Business Machines", "Samsung Electronics", "Intel",
    "Microsoft", "Apple", "Google", "Qualcomm", "Huawei Technologies",
    "Canon", "Sony Group", "Toyota Motor", "LG Electronics", "Panasonic",
    "Robert Bosch", "Siemens", "General Electric", "Honeywell", "3M",
    "Ford Motor", "Boeing", "Raytheon", "Lockheed Martin", "Tesla",
    "Amazon Technologies", "Meta Platforms", "Oracle", "Cisco Systems",
    "Nvidia", "AMD", "TSMC", "Broadcom", "Texas Instruments",
    "Johnson & Johnson", "Pfizer", "Merck", "Roche", "Novartis",
]
_COMPANY_SUFFIXES = [
    "Corporation", "Corp", "Inc", "LLC", "Ltd", "Co", "GmbH", "SA", "AG",
    "Holdings", "Group", "Industries", "Technologies", "Systems",
    "Laboratories", "Research", "Innovations",
]


def _make_synth_inventors(countries_pool: list[str]) -> pd.DataFrame:
    rng = random.Random(RANDOM_SEED)
    rows = []
    for i in range(N_INVENTORS):
        rows.append({
            "inventor_id": f"INV{i:07d}",
            "name":        f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
            "country":     rng.choice(countries_pool) if countries_pool else "US",
        })
    return pd.DataFrame(rows)


def _make_synth_companies() -> pd.DataFrame:
    rng = random.Random(RANDOM_SEED + 1)
    rows = []
    seen: set[str] = set()
    i = 0
    while len(rows) < N_COMPANIES:
        if rng.random() < 0.35 and _COMPANY_PREFIXES:
            name = rng.choice(_COMPANY_PREFIXES)
        else:
            name = f"{rng.choice(_COMPANY_PREFIXES).split()[0]} {rng.choice(_COMPANY_SUFFIXES)}"
            if rng.random() < 0.3:
                name = f"{rng.choice(['Nano','Quantum','Bio','Cyber','Aero','Neuro','Solar','Hydro'])}{name}"
        if name in seen:
            continue
        seen.add(name)
        rows.append({"company_id": f"CMP{i:06d}", "name": name})
        i += 1
    return pd.DataFrame(rows)


def _synth_link_tables(
    patents: pd.DataFrame, inventors: pd.DataFrame, companies: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RANDOM_SEED + 2)
    inv_ids = inventors["inventor_id"].to_numpy()
    cmp_ids = companies["company_id"].to_numpy()
    p_ids   = patents["patent_id"].to_numpy()
    n       = len(p_ids)

    inv_weights = 1.0 / (np.arange(1, len(inv_ids) + 1) ** 0.8)
    inv_weights /= inv_weights.sum()
    cmp_weights = 1.0 / (np.arange(1, len(cmp_ids) + 1) ** 0.7)
    cmp_weights /= cmp_weights.sum()

    inv_per = rng.integers(1, 4, size=n)
    pi_patents = np.repeat(p_ids, inv_per)
    pi_invs    = rng.choice(inv_ids, size=len(pi_patents), p=inv_weights)
    pi = pd.DataFrame({"patent_id": pi_patents, "inventor_id": pi_invs}).drop_duplicates()

    cmp_per = rng.integers(0, 3, size=n)
    force_mask = rng.random(n) < 0.8
    cmp_per[force_mask] = np.maximum(cmp_per[force_mask], 1)
    pc_patents = np.repeat(p_ids, cmp_per)
    if len(pc_patents):
        pc_cmps = rng.choice(cmp_ids, size=len(pc_patents), p=cmp_weights)
        pc = pd.DataFrame({"patent_id": pc_patents, "company_id": pc_cmps}).drop_duplicates()
    else:
        pc = pd.DataFrame(columns=["patent_id", "company_id"])
    return pi, pc


# ----------------------------------------------------------------------
# CPC (optional, only when USE_CPC = True)
# ----------------------------------------------------------------------
def clean_cpc(patents: pd.DataFrame) -> pd.DataFrame:
    """Extract CPC classifications for kept patents."""
    src = RAW_DIR / "g_cpc_current.tsv.zip"
    if not src.exists():
        print(f"[cpc] {src.name} not found, skipping")
        return pd.DataFrame(columns=["patent_id", "section_code", "subclass"])

    print(f"[cpc] reading {src.name}...")
    patent_ids = set(patents["patent_id"].astype(str))
    rows: list[pd.DataFrame] = []
    reader = _iter_tsv(src)
    for chunk in reader:
        # Columns typically include: patent_id, cpc_section, cpc_class, cpc_subclass
        if "patent_id" not in chunk.columns:
            continue
        sub = chunk[chunk["patent_id"].isin(patent_ids)]
        if not len(sub):
            continue
        # Be tolerant to column name variations
        section = next((c for c in sub.columns if c.lower().endswith("section")), None)
        subcls  = next((c for c in sub.columns if c.lower().endswith("subclass")), None)
        if not section or not subcls:
            continue
        rows.append(sub[["patent_id", section, subcls]].rename(
            columns={section: "section_code", subcls: "subclass"}))

    df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if df.empty:
        return df
    df = df.dropna(subset=["patent_id", "section_code"]).drop_duplicates(
        subset=["patent_id", "subclass"])
    df["section_code"] = df["section_code"].str.upper().str.strip()
    df = df[df["section_code"].isin(list("ABCDEFGHY"))]
    print(f"[cpc] extracted {len(df):,} patent<->cpc rows")
    return df


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------
def main() -> None:
    patents   = clean_patents()
    locations = load_location_countries()

    if USE_REAL_INVENTORS:
        inventors, pi = clean_real_inventors(patents, locations)
    else:
        countries = locations["country"].tolist()
        inventors = _make_synth_inventors(countries)
        pi = None  # computed below once companies exist

    if USE_REAL_COMPANIES:
        companies, pc = clean_real_companies(patents)
    else:
        companies = _make_synth_companies()
        pc = None

    if pi is None or pc is None:
        pi2, pc2 = _synth_link_tables(patents, inventors, companies)
        pi = pi if pi is not None else pi2
        pc = pc if pc is not None else pc2

    inventors.to_csv(PROCESSED_DIR / "clean_inventors.csv",       index=False)
    companies.to_csv(PROCESSED_DIR / "clean_companies.csv",       index=False)
    pi.to_csv       (PROCESSED_DIR / "clean_patent_inventor.csv", index=False)
    pc.to_csv       (PROCESSED_DIR / "clean_patent_company.csv",  index=False)

    print(f"[inventors] wrote {len(inventors):,} rows")
    print(f"[companies] wrote {len(companies):,} rows")
    print(f"[links] patent_inventor: {len(pi):,} rows, patent_company: {len(pc):,} rows")

    if USE_CPC:
        cpc = clean_cpc(patents)
        cpc.to_csv(PROCESSED_DIR / "clean_patent_cpc.csv", index=False)
        print(f"[cpc] wrote {len(cpc):,} rows")


if __name__ == "__main__":
    main()
