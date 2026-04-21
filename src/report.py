"""Produce the three required report formats: console, CSV, JSON."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analyze import run_all
from src.config import DB_PATH, REPORTS_DIR

console = Console()


def _total_patents() -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM patents").fetchone()[0]


def _rich_table(title: str, df: pd.DataFrame, limit: int = 10) -> Table:
    t = Table(title=title, title_justify="left", header_style="bold cyan")
    for col in df.columns:
        t.add_column(str(col))
    for _, row in df.head(limit).iterrows():
        t.add_row(*[str(v) for v in row])
    return t


def console_report(results: dict[str, pd.DataFrame], total: int) -> None:
    console.print(Panel.fit("PATENT INTELLIGENCE REPORT", style="bold green"))
    console.print(f"Total patents in database: [bold yellow]{total:,}[/bold yellow]")
    console.print(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")

    titles = {
        "Q1": "Q1 | Top Inventors",
        "Q2": "Q2 | Top Companies",
        "Q3": "Q3 | Top Countries",
        "Q4": "Q4 | Patents per Year",
        "Q5": "Q5 | Patents x Inventors x Companies (sample)",
        "Q6": "Q6 | Companies Ranked by Avg Patents/Year (CTE)",
        "Q7": "Q7 | Inventor Rank Within Country (Window Fn)",
    }
    for key in ["Q1", "Q2", "Q3", "Q4", "Q6", "Q7", "Q5"]:
        if key in results:
            console.print(_rich_table(titles[key], results[key]))
            console.print()


def csv_exports(results: dict[str, pd.DataFrame]) -> list[str]:
    out = []
    mapping = {
        "Q1": "top_inventors.csv",
        "Q2": "top_companies.csv",
        "Q3": "top_countries.csv",
        "Q4": "country_trends.csv",   # required filename from brief; contains year trend
        "Q6": "companies_avg_per_year.csv",
        "Q7": "inventor_rank_by_country.csv",
    }
    for key, name in mapping.items():
        if key in results:
            path = REPORTS_DIR / name
            results[key].to_csv(path, index=False)
            out.append(str(path))
    return out


def json_report(results: dict[str, pd.DataFrame], total: int) -> str:
    top_countries_df = results.get("Q3", pd.DataFrame())
    share = {}
    if not top_countries_df.empty:
        s = top_countries_df["patent_count"].sum()
        share = {
            r["country"]: round(float(r["patent_count"]) / s, 4)
            for _, r in top_countries_df.iterrows()
        } if s else {}

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_patents": int(total),
        "top_inventors": [
            {"name": r["inventor"], "country": r.get("country", ""), "patents": int(r["patent_count"])}
            for _, r in results.get("Q1", pd.DataFrame()).iterrows()
        ],
        "top_companies": [
            {"name": r["company"], "patents": int(r["patent_count"])}
            for _, r in results.get("Q2", pd.DataFrame()).iterrows()
        ],
        "top_countries": [
            {"country": r["country"], "patents": int(r["patent_count"]), "share": share.get(r["country"], 0.0)}
            for _, r in results.get("Q3", pd.DataFrame()).iterrows()
        ],
        "patents_per_year": [
            {"year": int(r["year"]), "patents": int(r["patent_count"])}
            for _, r in results.get("Q4", pd.DataFrame()).iterrows()
        ],
    }
    path = REPORTS_DIR / "report.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def main() -> None:
    results = run_all()
    total   = _total_patents()

    console_report(results, total)
    csv_paths = csv_exports(results)
    json_path = json_report(results, total)

    console.print(Panel.fit("Artifacts written", style="bold blue"))
    for p in csv_paths:
        console.print(f"  [green]CSV [/green] {p}")
    console.print(f"  [green]JSON[/green] {json_path}")


if __name__ == "__main__":
    main()
