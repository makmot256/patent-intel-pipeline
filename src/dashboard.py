"""Interactive Patent Intelligence dashboard.

Run locally:
    streamlit run src/dashboard.py

Deploy on Streamlit Community Cloud:
    1. Push this repo to GitHub (keep data/processed/*.csv committed).
    2. streamlit.io/cloud  ->  New app  ->  pick repo, set main file to
       src/dashboard.py. Done.

The dashboard is self-healing: if the SQLite database is missing (e.g.
on a fresh Cloud deployment) it rebuilds it from the committed CSVs.
"""
from __future__ import annotations

# ----------------------------------------------------------------------
# Streamlit runs this file directly, which puts only src/ on sys.path.
# Prepend the project root so `from src.*` imports resolve.
# ----------------------------------------------------------------------
import sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pycountry
import streamlit as st

from src.analyze import run_all
from src.config import BRAND, DB_PATH, PALETTE, PROCESSED_DIR


# ----------------------------------------------------------------------
# Page config + custom CSS
# ----------------------------------------------------------------------
st.set_page_config(
    page_title=f"{BRAND['title']}",
    page_icon="[PI]",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = f"""
<style>
    /* Remove the default hamburger + footer for a cleaner look */
    #MainMenu, footer {{visibility: hidden;}}

    .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}

    /* Headline */
    .pi-hero {{
        background: linear-gradient(135deg, {BRAND['primary']} 0%, {BRAND['dark']} 100%);
        color: white;
        padding: 1.8rem 2rem;
        border-radius: 18px;
        margin-bottom: 1.4rem;
        box-shadow: 0 10px 30px rgba(11,95,255,0.18);
    }}
    .pi-hero h1 {{ margin: 0; font-size: 2.0rem; letter-spacing: -0.5px; }}
    .pi-hero p  {{ margin: 0.3rem 0 0 0; opacity: 0.85; font-size: 1.02rem; }}

    /* Metric cards */
    .pi-metric {{
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 14px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    .pi-metric .label {{ color:{BRAND['muted']}; font-size: 0.85rem; text-transform: uppercase; letter-spacing: .08em; }}
    .pi-metric .value {{ color:{BRAND['dark']}; font-size: 1.9rem; font-weight: 700; margin-top: .2rem; }}
    .pi-metric .delta {{ color:{BRAND['accent']}; font-size: 0.85rem; margin-top: .2rem; }}

    /* ----- Tabs: pill navigation ----- */
    .stTabs {{ margin-top: .25rem; }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 6px;
        background: #F3F5FA;
        padding: 6px;
        border-radius: 14px;
        border: 1px solid #E5E7EB;
        box-shadow: inset 0 1px 2px rgba(15,23,42,0.04);
        overflow-x: auto;
        scrollbar-width: thin;
    }}
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {{ height: 6px; }}
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb {{
        background: #CBD5E1; border-radius: 3px;
    }}
    .stTabs [data-baseweb="tab"] {{
        height: 42px !important;
        padding: 0 18px !important;
        border-radius: 10px !important;
        background: white !important;
        color: {BRAND['muted']} !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        border: 1px solid #E5E7EB !important;
        white-space: nowrap;
        transition: all 160ms ease;
        cursor: pointer;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        background: #EAF0FF !important;
        color: {BRAND['primary']} !important;
        border-color: #C7D7FF !important;
        transform: translateY(-1px);
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background: linear-gradient(135deg, {BRAND['primary']} 0%, {BRAND['dark']} 100%) !important;
        color: white !important;
        border-color: transparent !important;
        box-shadow: 0 6px 16px rgba(11,95,255,0.28);
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"]:hover {{
        transform: translateY(-1px);
    }}
    /* Hide the default active-tab underline (we use a filled pill instead) */
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {{
        display: none !important;
    }}

    /* Nav hint caption */
    .pi-navhint {{
        display: flex; align-items: center; gap: .5rem;
        color: {BRAND['muted']}; font-size: .85rem;
        margin: .25rem 0 .35rem 2px; letter-spacing: .02em;
    }}
    .pi-navhint .dot {{
        width: 6px; height: 6px; border-radius: 50%;
        background: {BRAND['primary']}; box-shadow: 0 0 0 4px rgba(11,95,255,0.12);
    }}

    /* Dataframe tweak */
    .stDataFrame {{ border-radius: 12px; overflow: hidden; border: 1px solid #E5E7EB; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Self-healing DB: if the .db file is missing (e.g. fresh Cloud
# deployment), rebuild it from the committed clean_*.csv files.
# ----------------------------------------------------------------------
def _ensure_db() -> None:
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        return
    with st.spinner("First-run setup: building local database from processed CSVs..."):
        from src import load
        # Make sure all required CSVs exist before calling load
        required = ["clean_patents.csv", "clean_inventors.csv", "clean_companies.csv",
                    "clean_patent_inventor.csv", "clean_patent_company.csv"]
        for r in required:
            if not (PROCESSED_DIR / r).exists():
                st.error(
                    f"Missing `data/processed/{r}`. "
                    "Run `python -m src.run_all` locally once to generate it, "
                    "then commit data/processed/ to the repo."
                )
                st.stop()
        load.main()


_ensure_db()


# ----------------------------------------------------------------------
# Data loading (cached)
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_results():
    results = run_all()
    with sqlite3.connect(DB_PATH) as conn:
        totals = {
            "patents":        conn.execute("SELECT COUNT(*) FROM patents").fetchone()[0],
            "inventors":      conn.execute("SELECT COUNT(*) FROM inventors").fetchone()[0],
            "companies":      conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
            "links_pi":       conn.execute("SELECT COUNT(*) FROM patent_inventor").fetchone()[0],
            "links_pc":       conn.execute("SELECT COUNT(*) FROM patent_company").fetchone()[0],
            "cpc_links":      conn.execute("SELECT COUNT(*) FROM patent_cpc").fetchone()[0],
            "min_year":       conn.execute("SELECT MIN(year) FROM patents").fetchone()[0],
            "max_year":       conn.execute("SELECT MAX(year) FROM patents").fetchone()[0],
        }
    return results, totals


@st.cache_data(show_spinner=False)
def load_patents_sample(limit: int = 500) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(
            "SELECT patent_id, title, year, filing_date FROM patents "
            "ORDER BY year DESC, patent_id LIMIT ?",
            conn, params=(limit,),
        )


results, totals = load_results()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def metric_card(col, label: str, value, delta: str | None = None) -> None:
    html = f"""
      <div class="pi-metric">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {f'<div class="delta">{delta}</div>' if delta else ''}
      </div>
    """
    col.markdown(html, unsafe_allow_html=True)


def _iso2_to_iso3(code: str) -> str | None:
    try:
        c = pycountry.countries.get(alpha_2=str(code).upper())
        return c.alpha_3 if c else None
    except Exception:
        return None


def _style_fig(fig: go.Figure, *, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=60, b=30),
        font=dict(family="Inter, -apple-system, Segoe UI, sans-serif",
                  color=BRAND["dark"], size=12),
        title_font_size=16,
        title_font_color=BRAND["dark"],
        plot_bgcolor="white",
        paper_bgcolor="white",
        hoverlabel=dict(bgcolor="white", bordercolor="#E5E7EB",
                        font_size=12, font_color=BRAND["dark"]),
        colorway=PALETTE,
    )
    fig.update_xaxes(showgrid=False, linecolor="#E5E7EB")
    fig.update_yaxes(gridcolor="#F3F4F6", linecolor="#E5E7EB")
    return fig


# ======================================================================
# HERO
# ======================================================================
st.markdown(
    f"""
    <div class="pi-hero">
      <h1>{BRAND['title']}</h1>
      <p>{BRAND['tagline']} &nbsp;-&nbsp; {totals['min_year']}-{totals['max_year']} window</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# KPI row
c1, c2, c3, c4, c5 = st.columns(5)
metric_card(c1, "Patents",          f"{totals['patents']:,}")
metric_card(c2, "Inventors",        f"{totals['inventors']:,}")
metric_card(c3, "Companies",        f"{totals['companies']:,}")
metric_card(c4, "Inventor links",   f"{totals['links_pi']:,}")
metric_card(c5, "CPC classifications", f"{totals['cpc_links']:,}" if totals['cpc_links'] else "-")

st.markdown("")

# ======================================================================
# SIDEBAR FILTERS
# ======================================================================
st.sidebar.markdown(f"### {BRAND['title']}")
st.sidebar.caption("Controls + navigation")

all_years = sorted(results["Q4"]["year"].unique().tolist()) if "Q4" in results else []
if all_years:
    year_range = st.sidebar.slider(
        "Year range", min_value=int(min(all_years)),
        max_value=int(max(all_years)),
        value=(int(min(all_years)), int(max(all_years))),
    )
else:
    year_range = (0, 0)

top_n = st.sidebar.selectbox("Show top N", [5, 10, 15, 20], index=1)
st.sidebar.divider()
st.sidebar.caption("Data source: USPTO PatentsView")
st.sidebar.caption(f"DB: `{Path(DB_PATH).name}`")


def _filter_year_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    return df[(df["year"] >= year_range[0]) & (df["year"] <= year_range[1])]


# ======================================================================
# TABS
# ======================================================================
st.markdown(
    """
    <div class="pi-navhint">
      <span class="dot"></span>
      <span>Explore the dataset &mdash; click any tab below to switch views</span>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_overview, tab_inventors, tab_companies, tab_countries, tab_cpc, tab_queries = st.tabs(
    [
        "01 - Overview",
        "02 - Inventors",
        "03 - Companies",
        "04 - Countries",
        "05 - CPC Categories",
        "06 - SQL Queries",
    ]
)

# ---------- OVERVIEW ----------
with tab_overview:
    left, right = st.columns([3, 2])

    with left:
        q4 = _filter_year_trend(results.get("Q4", pd.DataFrame()))
        if not q4.empty:
            fig = px.area(
                q4, x="year", y="patent_count",
                title="Patents granted per year (Q4)",
                labels={"year": "Year", "patent_count": "Patents"},
                color_discrete_sequence=[BRAND["primary"]],
            )
            fig.update_traces(line=dict(width=3.5), fillcolor="rgba(11,95,255,0.15)")
            fig.update_traces(mode="lines+markers", marker=dict(size=10, line=dict(width=2, color="white")))
            st.plotly_chart(_style_fig(fig), use_container_width=True)

    with right:
        q2 = results.get("Q2", pd.DataFrame()).head(top_n)
        if not q2.empty:
            fig = px.bar(
                q2.sort_values("patent_count"),
                x="patent_count", y="company", orientation="h",
                title=f"Top {top_n} companies (Q2)",
                labels={"patent_count": "Patents", "company": ""},
                color_discrete_sequence=[BRAND["accent"]],
            )
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(_style_fig(fig, height=420), use_container_width=True)

    # Recent patents sample
    st.markdown("##### Recent patents (sample)")
    recent = load_patents_sample(500)
    st.dataframe(recent, use_container_width=True, height=280, hide_index=True)

# ---------- INVENTORS ----------
with tab_inventors:
    q1 = results.get("Q1", pd.DataFrame()).head(top_n)
    if not q1.empty:
        c1, c2 = st.columns([3, 2])
        with c1:
            fig = px.bar(
                q1.sort_values("patent_count"),
                x="patent_count", y="inventor", orientation="h",
                color="country", title=f"Top {top_n} inventors (Q1)",
                labels={"patent_count": "Patents", "inventor": ""},
                color_discrete_sequence=PALETTE,
            )
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(_style_fig(fig, height=520), use_container_width=True)
        with c2:
            st.markdown("##### Full leaderboard")
            st.dataframe(q1, use_container_width=True, hide_index=True, height=520)

    st.markdown("---")
    st.markdown("##### Q7 | Inventor rank within country (window fn)")
    q7 = results.get("Q7", pd.DataFrame())
    if not q7.empty:
        countries = ["(all)"] + sorted(q7["country"].unique().tolist())
        picked = st.selectbox("Filter country", countries, index=0)
        view = q7 if picked == "(all)" else q7[q7["country"] == picked]
        st.dataframe(view, use_container_width=True, hide_index=True, height=360)

# ---------- COMPANIES ----------
with tab_companies:
    q2 = results.get("Q2", pd.DataFrame()).head(top_n)
    q6 = results.get("Q6", pd.DataFrame())

    if not q2.empty:
        fig = px.bar(
            q2.sort_values("patent_count"),
            x="patent_count", y="company", orientation="h",
            title=f"Top {top_n} companies (Q2)",
            labels={"patent_count": "Patents", "company": ""},
            color_discrete_sequence=[BRAND["primary"]],
        )
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(_style_fig(fig, height=520), use_container_width=True)

    if not q6.empty:
        st.markdown("##### Q6 | Companies ranked by avg patents / year (CTE)")
        st.dataframe(q6, use_container_width=True, hide_index=True, height=380)

# ---------- COUNTRIES ----------
with tab_countries:
    q3 = results.get("Q3", pd.DataFrame())
    if not q3.empty:
        q3 = q3.copy()
        q3["iso3"]  = q3["country"].map(_iso2_to_iso3)
        fig = px.choropleth(
            q3, locations="iso3", color="patent_count",
            hover_name="country", hover_data={"iso3": False, "patent_count": ":,"},
            color_continuous_scale="Blues",
            title="Patent volume by country (Q3)",
        )
        fig.update_geos(showframe=False, showcoastlines=True,
                        coastlinecolor="#E5E7EB", projection_type="natural earth",
                        bgcolor="white")
        st.plotly_chart(_style_fig(fig, height=520), use_container_width=True)

        c1, c2 = st.columns([3, 2])
        with c1:
            fig = px.bar(
                q3.head(top_n).sort_values("patent_count"),
                x="patent_count", y="country", orientation="h",
                title=f"Top {top_n} countries",
                color_discrete_sequence=[BRAND["accent"]],
                labels={"patent_count": "Patents", "country": ""},
            )
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(_style_fig(fig, height=420), use_container_width=True)
        with c2:
            st.markdown("##### Country leaderboard")
            st.dataframe(q3.drop(columns=["iso3"], errors="ignore"),
                         use_container_width=True, hide_index=True, height=420)

# ---------- CPC CATEGORIES ----------
with tab_cpc:
    q8 = results.get("Q8", pd.DataFrame())
    q9 = results.get("Q9", pd.DataFrame())
    if q8.empty:
        st.info(
            "CPC classification data is not loaded. "
            "Set `USE_CPC = True` in `src/config.py` and rerun "
            "`python -m src.run_all` to enable this tab "
            "(adds a ~495 MB download)."
        )
    else:
        c1, c2 = st.columns(2)
        with c1:
            fig = px.pie(
                q8, names="description", values="patent_count", hole=0.55,
                title="Q8 | Share of patents by CPC section",
                color_discrete_sequence=PALETTE,
            )
            fig.update_traces(textinfo="percent+label")
            st.plotly_chart(_style_fig(fig, height=480), use_container_width=True)
        with c2:
            st.markdown("##### Section leaderboard")
            st.dataframe(q8, use_container_width=True, hide_index=True, height=480)

        if not q9.empty:
            fig = px.line(
                q9, x="year", y="patent_count", color="section_code",
                title="Q9 | CPC volume over time",
                color_discrete_sequence=PALETTE,
            )
            fig.update_traces(mode="lines+markers")
            st.plotly_chart(_style_fig(fig, height=440), use_container_width=True)

# ---------- SQL QUERIES ----------
with tab_queries:
    from src.analyze import load_queries
    queries = load_queries()
    for qname, sql in queries.items():
        with st.expander(f"{qname} -- source SQL"):
            st.code(sql, language="sql")
            if qname in results:
                st.dataframe(results[qname], use_container_width=True, hide_index=True, height=260)
