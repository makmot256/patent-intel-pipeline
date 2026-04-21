# Global Patent Intelligence Pipeline

An end-to-end data-engineering project that turns raw USPTO
PatentsView bulk data into a clean SQLite warehouse, publication-
quality charts, three flavours of reports, and an interactive Plotly
dashboard.

```
PatentsView bulk files → Python → pandas → SQLite → SQL → Reports / Charts / Dashboard
```

**What you get out of the box**

- SQLite warehouse with seven fully-indexed tables
- 9 analytical SQL queries (7 required + 2 bonus CPC queries)
- Console report with pretty `rich` tables
- 6 CSV exports + one JSON summary in `reports/`
- 4 publication-quality PNG charts in `reports/charts/`
- A branded, interactive **Plotly dashboard** with KPI cards, filters,
  a world map, tabs and a live SQL browser
- One-command reproducibility: `python -m src.run_all`

---

## Quick start (local)

```powershell
git clone <your-repo-url>
cd patent-intel-pipeline

python -m venv .venv
.\.venv\Scripts\Activate.ps1            # Windows
# source .venv/bin/activate             # macOS / Linux

pip install -r requirements.txt
python -m src.run_all                   # download → clean → load → report → charts

# launch the dashboard
streamlit run src/dashboard.py
```

The dashboard opens at <http://localhost:8501>.

---

## What gets downloaded (default, lightweight)

Default mode downloads only two PatentsView files (~233 MB total):

| File | Size | Used for |
|------|------|----------|
| `g_patent.tsv.zip`                 | 230 MB | Patents (title, grant date, year) |
| `g_location_disambiguated.tsv.zip` |   3 MB | Real country distribution |

Inventors and companies are generated as a realistic synthetic universe
(5 000 inventors / 800 companies, Zipfian-weighted, country-sampled
from real locations, reproducible seed). This keeps a fresh clone
laptop-friendly while still exercising every piece of the pipeline.

### Opting in to the real (heavy) data

Flip the flags in `src/config.py` and rerun `python -m src.run_all`:

| Flag | Extra download | What it enables |
|------|-----|-----|
| `USE_REAL_INVENTORS = True` | +1.7 GB  | Real disambiguated inventor names + country from PatentsView |
| `USE_REAL_COMPANIES = True` | +850 MB  | Real disambiguated assignee names |
| `USE_CPC = True`            | +495 MB  | CPC classification (innovation categories) – adds Q8/Q9 and a whole dashboard tab |

Everything downstream (schema, queries, reports, dashboard) just works;
the synthetic path is only active while the corresponding flag is off.

---

## Project layout

```
patent-intel-pipeline/
├── data/
│   ├── raw/                   # downloaded zips (gitignored)
│   └── processed/             # clean_*.csv (committed - tiny)
├── db/patents.db              # SQLite (gitignored, self-heals)
├── reports/
│   ├── top_inventors.csv, top_companies.csv, ...
│   ├── report.json
│   └── charts/
│       ├── trend.png
│       ├── top_countries.png
│       ├── top_companies.png
│       ├── top_inventors.png
│       └── cpc_sections.png   # only when USE_CPC = True
├── sql/
│   ├── schema.sql             # tables + indexes + CPC section seed
│   └── queries.sql            # Q1..Q9
├── src/
│   ├── config.py              # flags, paths, branding, tuning knobs
│   ├── download.py            # streaming downloader w/ progress bar
│   ├── clean.py               # pandas cleaning + synthetic + CPC
│   ├── load.py                # builds SQLite from clean CSVs
│   ├── analyze.py             # parses queries.sql and runs each Qn
│   ├── report.py              # console + CSV + JSON outputs
│   ├── plot.py                # matplotlib PNG charts
│   ├── dashboard.py           # Streamlit + Plotly interactive dashboard
│   └── run_all.py             # one-command orchestrator
├── .streamlit/config.toml     # branded dashboard theme
├── requirements.txt
└── README.md
```

---

## Database schema

```sql
patents         (patent_id PK, title, abstract, filing_date, year)
inventors       (inventor_id PK, name, country)
companies       (company_id PK, name)
patent_inventor (patent_id, inventor_id)          -- M:N
patent_company  (patent_id, company_id)           -- M:N
cpc_sections    (section_code PK, description)    -- seeded A..H, Y
patent_cpc      (patent_id, section_code, subclass)
```

The brief showed a single "relationships" table; patents have
**independent** many-to-many relationships to inventors and companies,
so splitting them avoids a Cartesian cross-product.

See [`sql/schema.sql`](sql/schema.sql) for the DDL, including the
indexes that make every query run in under a second.

---

## The queries

All in [`sql/queries.sql`](sql/queries.sql), parsed at runtime by
`src/analyze.py` so `dashboard.py` and `report.py` share one source of
truth.

| # | Question | Technique |
|---|----------|-----------|
| Q1 | Who has the most patents? | `GROUP BY` + `COUNT` + `LIMIT` |
| Q2 | Which companies own the most patents? | Same pattern via `patent_company` |
| Q3 | Which countries produce the most patents? | `JOIN` inventors + `GROUP BY country` |
| Q4 | Patents granted per year? | `GROUP BY year` |
| Q5 | Combined patents × inventors × companies | Four-way `LEFT JOIN` |
| Q6 | Companies ranked by avg patents/year | Two chained CTEs (`WITH`) |
| Q7 | Inventor rank inside each country | `RANK()`, `DENSE_RANK()`, `ROW_NUMBER()` |
| **Q8** (bonus) | CPC section share | `GROUP BY` on CPC + lookup |
| **Q9** (bonus) | CPC volume per section per year | Two-key `GROUP BY` |

---

## Reports produced

### A. Console (via `rich`)
Runs during `python -m src.report` — prints a banner, a KPI line, and
one pretty table per query.

### B. CSV (six files)
`top_inventors.csv`, `top_companies.csv`, `top_countries.csv`,
`country_trends.csv`, `companies_avg_per_year.csv`,
`inventor_rank_by_country.csv` — all in `reports/`.

### C. JSON (`reports/report.json`)
```json
{
  "generated_at": "2026-04-21T10:09:33+00:00",
  "total_patents": 100000,
  "top_inventors":  [{"name": "...", "country": "US", "patents": 8352}, ...],
  "top_companies":  [{"name": "Sony Group", "patents": 5672}, ...],
  "top_countries":  [{"country": "US", "patents": 51940, "share": 0.42}, ...],
  "patents_per_year":[{"year": 2020, "patents": 20000}, ...]
}
```

### D. Charts (`reports/charts/*.png`)
Produced by `python -m src.plot` — matplotlib, 150 DPI, branded,
publication-quality. Trend line, top countries / companies / inventors
and (when `USE_CPC=True`) a donut of CPC section share.

---

## The Streamlit dashboard

`streamlit run src/dashboard.py` opens a single-page dashboard with:

- **Hero banner** + **five KPI cards** (patents, inventors, companies,
  relationship counts, CPC classifications)
- **Sidebar controls**: year range slider, Top-N selector
- **Tabs**:
  - **Overview** – trend area chart + top companies + recent patents sample
  - **Inventors** – leaderboard + full Q7 table with country filter
  - **Companies** – top-N bars + Q6 CTE ranking
  - **Countries** – interactive **world map** (Plotly choropleth) + top-N bars
  - **CPC Categories** – donut + time-series (unlocked when `USE_CPC=True`)
  - **SQL Queries** – every Qn with its raw SQL and live result table
- **Self-healing database**: if `db/patents.db` is missing (e.g. fresh
  deployment) the dashboard rebuilds it from the committed
  `data/processed/*.csv` on first load.

Branding / theming live in `.streamlit/config.toml` and `src/config.py::BRAND`.

---

## Deploy to Streamlit Community Cloud (free, one click)

1. Push this repo to GitHub. **Commit `data/processed/*.csv`** (they're
   ~15 MB total) so the dashboard can rebuild the database on deploy.
   `db/patents.db` stays gitignored.
2. Go to <https://streamlit.io/cloud> → **New app** → pick this repo.
3. Set **Main file path** to `src/dashboard.py`.
4. Click Deploy. First load takes ~30 s while the DB is rebuilt.

No secrets or env vars needed.

---

## Tuning knobs (`src/config.py`)

| Variable | Default | What it does |
|----------|---------|--------------|
| `YEAR_MIN` / `YEAR_MAX`          | `2020` / `2024` | Year window kept after filtering |
| `MAX_PATENTS`                    | `100_000`       | Stratified sample cap (set `None` for the full ~1.8 M) |
| `N_INVENTORS` / `N_COMPANIES`    | `5_000` / `800` | Synthetic universe size |
| `CHUNKSIZE`                      | `100_000`       | Pandas chunk size for big TSVs |
| `USE_REAL_INVENTORS`             | `False`         | Pull 1.7 GB of real inventor files |
| `USE_REAL_COMPANIES`             | `False`         | Pull ~850 MB of real assignee files |
| `USE_CPC`                        | `False`         | Pull 495 MB, enable Q8/Q9 and CPC tab |
| `BRAND` / `PALETTE`              | USPTO blues     | Dashboard + chart colours |

---

## Reproducibility

Same input → same output, every time:

- All random draws are seeded (`RANDOM_SEED = 42`)
- The year filter is deterministic
- SQLite is rebuilt from scratch on every load
- Synthetic names are pulled from a fixed alphabet

Anyone who clones the repo and runs `python -m src.run_all` gets
byte-identical `data/processed/*.csv` and identical query results.

---

## Data attribution

- USPTO Open Data Portal – PatentsView Granted Patent Disambiguated Data:
  <https://data.uspto.gov/bulkdata/datasets/pvgpatdis>
- S3 mirror (direct downloads):
  `https://s3.amazonaws.com/data.patentsview.org/download/`
- Data dictionary: `PV_grant_data_dictionary.pdf` on the dataset page.
