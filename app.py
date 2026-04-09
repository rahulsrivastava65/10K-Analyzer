from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import market_intel as mi
from exports import (
    build_excel_export,
    build_kpi_rows,
    build_pdf_export,
    build_ppt_export,
)
from sec_10k_engine import Sec10KAnalyzer


build_dynamic_metric_cards = mi.build_dynamic_metric_cards
build_numeric_highlights = mi.build_numeric_highlights
fallback_narrative_lines = mi.fallback_narrative_lines
find_future_focus_lines = mi.find_future_focus_lines
find_priority_lines = mi.find_priority_lines
find_text_disclosures = mi.find_text_disclosures
get_market_snapshot = mi.get_market_snapshot
get_peer_table = mi.get_peer_table
is_valid_section = mi.is_valid_section
load_filing_text = mi.load_filing_text
summarize_business = mi.summarize_business
find_capital_allocation_lines = getattr(mi, "find_capital_allocation_lines", lambda text, limit=4: [])
find_esg_lines = getattr(mi, "find_esg_lines", lambda text, limit=2: [])
find_guidance_lines = getattr(mi, "find_guidance_lines", lambda text, limit=3: [])
find_initiative_lines = getattr(mi, "find_initiative_lines", lambda text, limit=5: [])
find_liquidity_lines = getattr(mi, "find_liquidity_lines", lambda text, limit=4: [])
find_operating_driver_lines = getattr(mi, "find_operating_driver_lines", lambda text, limit=5: [])
find_risk_lines = getattr(mi, "find_risk_lines", lambda text, limit=5: [])
find_segment_lines = getattr(mi, "find_segment_lines", lambda text, limit=4: [])
get_consensus_summary = getattr(
    mi,
    "get_consensus_summary",
    lambda market_snapshot: {
        "revenue_growth_next_year_pct": None,
        "eps_growth_next_year_pct": None,
        "recommendation_mix": None,
        "target_upside_pct": None,
    },
)


st.set_page_config(page_title="10K Summary", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --ink: #11243f;
        --muted: #5e6c80;
        --line: #d9e3ef;
        --panel: rgba(255, 255, 255, 0.94);
        --panel-soft: rgba(246, 248, 251, 0.96);
        --navy: #17365d;
        --teal: #0f766e;
        --gold: #9a6700;
        --crimson: #b42318;
        --sky: #1d4ed8;
    }
    html, body, [class*="css"] { font-family: "Aptos", "Segoe UI", sans-serif; }
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(23, 54, 93, 0.10), transparent 28%),
            radial-gradient(circle at top right, rgba(15, 118, 110, 0.08), transparent 22%),
            linear-gradient(180deg, #f8fafc 0%, #eef3f8 100%);
        color: var(--ink);
    }
    h1, h2, h3 { color: var(--ink); letter-spacing: -0.02em; }
    .hero, .panel, .kpi, .chip, .disclaimer {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        box-shadow: 0 14px 30px rgba(17, 36, 63, 0.06);
    }
    .hero, .panel, .disclaimer { padding: 1rem 1.1rem; }
    .hero { margin-top: 0.7rem; margin-bottom: 0.9rem; }
    .eyebrow {
        color: var(--teal);
        text-transform: uppercase;
        letter-spacing: 0.14em;
        font-size: 0.76rem;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }
    .hero-title { font-size: 2.05rem; font-weight: 700; margin: 0.2rem 0 0.3rem 0; }
    .hero-copy, .copy {
        color: var(--muted);
        line-height: 1.56;
        margin: 0;
    }
    .section-title {
        font-size: 1.08rem;
        font-weight: 700;
        color: var(--ink);
        margin-bottom: 0.18rem;
    }
    .section-caption {
        color: var(--muted);
        font-size: 0.88rem;
        margin-bottom: 0.75rem;
    }
    .kpi {
        background: var(--panel-soft);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 0.85rem 0.95rem;
        min-height: 132px;
    }
    .kpi-label {
        color: var(--muted);
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .kpi-value {
        color: var(--ink);
        font-size: 1.52rem;
        font-weight: 700;
        margin-top: 0.28rem;
    }
    .kpi-delta {
        font-size: 0.92rem;
        font-weight: 700;
        margin-top: 0.18rem;
    }
    .tone-green { color: var(--teal); }
    .tone-amber { color: var(--gold); }
    .tone-red { color: var(--crimson); }
    .tone-blue { color: var(--sky); }
    .panel { height: 100%; }
    .chip {
        background: var(--panel-soft);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 0.72rem 0.82rem;
        min-height: 110px;
    }
    .chip-theme {
        color: var(--sky);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .chip-label {
        color: var(--ink);
        font-size: 0.93rem;
        font-weight: 700;
        margin-top: 0.18rem;
    }
    .chip-value {
        color: var(--ink);
        font-size: 1.16rem;
        font-weight: 700;
        margin-top: 0.16rem;
    }
    .chip-note {
        color: var(--muted);
        font-size: 0.84rem;
        line-height: 1.45;
        margin-top: 0.16rem;
    }
    .timeline-pill {
        display: inline-block;
        margin-right: 0.4rem;
        margin-top: 0.3rem;
        padding: 0.28rem 0.6rem;
        border-radius: 999px;
        background: rgba(23, 54, 93, 0.07);
        color: var(--navy);
        font-size: 0.8rem;
        font-weight: 600;
    }
    .bullet-list {
        color: var(--muted);
        font-size: 0.92rem;
        line-height: 1.55;
        margin: 0;
        padding-left: 1rem;
    }
    .divider { margin: 0.95rem 0 0.85rem 0; border-top: 1px solid var(--line); }
    .disclaimer { margin-top: 1rem; }
    .disclaimer-title {
        color: var(--crimson);
        font-size: 0.9rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.4rem;
    }
    .search-helper {
        color: var(--muted);
        font-size: 0.92rem;
        margin-bottom: 0.55rem;
    }
    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: 0;
    }
    div[data-testid="stPlotlyChart"] {
        width: 100%;
    }
    div[data-testid="stForm"] {
        background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(246,248,251,0.92));
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 1rem 1.05rem 0.55rem 1.05rem;
        box-shadow: 0 14px 30px rgba(17, 36, 63, 0.06);
        margin-top: 0.35rem;
        margin-bottom: 0.9rem;
    }
    div[data-testid="stForm"] label {
        color: var(--ink);
        font-weight: 700;
    }
    div.stButton > button, button[kind="primary"] {
        border-radius: 12px;
        border: 1px solid rgba(23, 54, 93, 0.12);
        box-shadow: 0 10px 18px rgba(23, 54, 93, 0.08);
        font-weight: 700;
    }
    button[kind="primary"] {
        background: linear-gradient(135deg, #17365d, #0f766e);
        color: white;
    }
    div[data-testid="stTextInput"] input, div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        border-radius: 12px;
    }
    @media (max-width: 1024px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.8rem;
            flex-wrap: wrap;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            flex: 1 1 calc(50% - 0.45rem) !important;
            width: calc(50% - 0.45rem) !important;
            min-width: calc(50% - 0.45rem) !important;
        }
        .hero-title {
            font-size: 1.8rem;
        }
        .kpi-value {
            font-size: 1.34rem;
        }
        .panel, .hero, .disclaimer {
            padding: 0.9rem 0.95rem;
        }
    }
    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
            padding-top: 0.75rem;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.65rem;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 100% !important;
        }
        .hero-title {
            font-size: 1.52rem;
            line-height: 1.2;
        }
        .hero-copy, .copy, .bullet-list {
            font-size: 0.89rem;
        }
        .section-title {
            font-size: 1rem;
        }
        .section-caption {
            font-size: 0.84rem;
        }
        .kpi, .chip {
            min-height: 0;
            padding: 0.78rem 0.82rem;
        }
        .kpi-value {
            font-size: 1.22rem;
        }
        .timeline-pill {
            font-size: 0.74rem;
            margin-right: 0.3rem;
        }
        div.stButton > button, button[kind="primary"] {
            min-height: 2.75rem;
        }
    }
    @media (max-width: 768px) {
        div[data-testid="stPlotlyChart"] .modebar {
            display: none !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


DISCLAIMER_LINES = [
    "This 10K Summary is generated from public filings and external market data for informational purposes only and is not investment, legal, accounting, tax, or other professional advice.",
    "No representation or warranty, express or implied, is made regarding the completeness, accuracy, timeliness, or fitness of any figures, narrative extraction, peer mapping, or outlook content.",
    "Outputs should be independently verified against the original Form 10-K, earnings materials, and other primary sources before being used for reporting, valuation, forecasting, or decision-making.",
    "Forward-looking statements, consensus estimates, and peer comparisons are inherently uncertain, and any production or external use should be reviewed by your finance, controls, compliance, and legal teams.",
]


CHART_BLUE_DARK = "#17365d"
CHART_BLUE_MID = "#4f6fae"
CHART_BLUE_LIGHT = "#8fb3e8"
CHART_BLUE_SOFT = "#bfd3f2"


PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "displayModeBar": False,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
        "toggleSpikelines",
    ],
}


def clean(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def latest(history: pd.DataFrame, metric: str) -> float | None:
    if history.empty or metric not in history.columns:
        return None
    return clean(history.iloc[-1][metric])


def prior(history: pd.DataFrame, metric: str) -> float | None:
    if len(history) < 2 or metric not in history.columns:
        return None
    return clean(history.iloc[-2][metric])


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / abs(previous)) * 100


def format_currency(value: float | None) -> str:
    if value is None:
        return "-"
    negative = value < 0
    amount = abs(value)
    if amount >= 1_000_000_000:
        text = f"${amount / 1_000_000_000:,.2f}B"
    elif amount >= 1_000_000:
        text = f"${amount / 1_000_000:,.2f}M"
    else:
        text = f"${amount:,.0f}"
    return f"({text})" if negative else text


def format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}%"


def format_ratio(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}x"


def format_delta(value: float | None, prior_year_label: str, suffix: str = "%") -> str:
    if value is None:
        return f"No {prior_year_label} comparison"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}{suffix} vs {prior_year_label}"


def tone_for_change(value: float | None, positive_good: bool = True) -> str:
    if value is None:
        return "tone-blue"
    adjusted = value if positive_good else -value
    if adjusted > 0:
        return "tone-green"
    if adjusted == 0:
        return "tone-blue"
    return "tone-red"


def render_kpi(title: str, value: str, delta: str, note: str, tone: str) -> None:
    st.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-label">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-delta {tone}">{delta}</div>
            <div class="copy">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chip(theme: str, label: str, value: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="chip">
            <div class="chip-theme">{theme}</div>
            <div class="chip-label">{label}</div>
            <div class="chip-value">{value}</div>
            <div class="chip-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_panel(title: str, body_html: str) -> None:
    st.markdown(
        f"""
        <div class="panel">
            <div class="section-title">{title}</div>
            <div class="copy">{body_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def list_to_html(items: List[str]) -> str:
    if not items:
        return "<ul class='bullet-list'><li>Not available.</li></ul>"
    return "<ul class='bullet-list'>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def combine_unique_lines(*groups: List[str], limit: int = 6) -> List[str]:
    combined: List[str] = []
    seen = set()
    for group in groups:
        for item in group:
            key = (item or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            combined.append(item)
            if len(combined) >= limit:
                return combined
    return combined


def label_billions(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value / 1_000_000_000:.1f}"


def label_billions_with_symbol(value: float | None) -> str:
    if value is None:
        return ""
    return f"${value / 1_000_000_000:.1f}B"


def period_labels(history: pd.DataFrame) -> List[str]:
    if history.empty or "Year" not in history.columns:
        return []
    return [f"FY{int(year)}" for year in history["Year"].tolist()]


def year_context(history: pd.DataFrame, filing_date: str) -> Dict[str, str]:
    if history.empty or "Year" not in history.columns or history["Year"].dropna().empty:
        return {
            "latest_year": "Latest FY",
            "prior_year": "Prior FY",
            "range_label": "Historical period unavailable",
            "latest_period_note": f"Latest filing date {filing_date}",
        }
    years = [int(year) for year in history["Year"].dropna().tolist()]
    latest_year = max(years)
    prior_year = sorted(years)[-2] if len(years) >= 2 else latest_year - 1
    return {
        "latest_year": f"FY{latest_year}",
        "prior_year": f"FY{prior_year}",
        "range_label": f"Annual periods shown: FY{min(years)} to FY{max(years)}",
        "latest_period_note": f"Latest Form 10-K filed on {filing_date} covering FY{latest_year}",
    }


def build_financial_story_lines(history: pd.DataFrame, context: Dict[str, str], profile: str) -> List[str]:
    lines: List[str] = []
    revenue_now = latest(history, "Revenue")
    revenue_prev = prior(history, "Revenue")
    expense_now = latest(history, "Expenses")
    expense_prev = prior(history, "Expenses")
    net_income_now = latest(history, "Net Income")
    net_income_prev = prior(history, "Net Income")
    ocf_now = latest(history, "Operating Cash Flow")
    fcf_now = latest(history, "Free Cash Flow")
    assets_now = latest(history, "Assets")
    liabilities_now = latest(history, "Liabilities")

    if revenue_now is not None:
        revenue_line = f"{context['latest_year']} revenue was {format_currency(revenue_now)}"
        revenue_change = pct_change(revenue_now, revenue_prev)
        if revenue_change is not None:
            revenue_line += f", {revenue_change:+.1f}% versus {context['prior_year']}."
        else:
            revenue_line += "."
        lines.append(revenue_line)

    if expense_now is not None:
        expense_label = "Operating expense" if profile == "Bank" else "Expenses"
        expense_line = f"{expense_label} were {format_currency(expense_now)}"
        expense_change = pct_change(expense_now, expense_prev)
        expense_ratio = latest(history, "Expense Ratio %")
        details = []
        if expense_change is not None:
            details.append(f"{expense_change:+.1f}% versus {context['prior_year']}")
        if expense_ratio is not None:
            details.append(f"{expense_ratio:.1f}% of revenue")
        if details:
            expense_line += " (" + "; ".join(details) + ")."
        else:
            expense_line += "."
        lines.append(expense_line)

    if net_income_now is not None:
        net_line = f"Net income was {format_currency(net_income_now)}"
        net_change = pct_change(net_income_now, net_income_prev)
        net_margin = latest(history, "Net Margin %")
        details = []
        if net_change is not None:
            details.append(f"{net_change:+.1f}% versus {context['prior_year']}")
        if net_margin is not None:
            details.append(f"net margin {net_margin:.1f}%")
        if details:
            net_line += " (" + "; ".join(details) + ")."
        else:
            net_line += "."
        lines.append(net_line)

    if ocf_now is not None:
        cash_line = f"Operating cash flow was {format_currency(ocf_now)}"
        if fcf_now is not None:
            cash_line += f"; free cash flow was {format_currency(fcf_now)}."
        else:
            cash_line += "."
        lines.append(cash_line)

    if assets_now is not None and liabilities_now is not None and assets_now != 0:
        leverage = liabilities_now / assets_now
        lines.append(
            f"Balance sheet scale remains significant with assets of {format_currency(assets_now)} and liabilities of {format_currency(liabilities_now)} ({leverage:.2f}x liabilities-to-assets)."
        )

    return lines[:5]


def build_capital_story_lines(history: pd.DataFrame, context: Dict[str, str]) -> List[str]:
    lines: List[str] = []
    cash_now = latest(history, "Cash")
    debt_now = latest(history, "Debt")
    capex_now = latest(history, "Capex")
    dividends_now = latest(history, "Dividends Paid")
    buybacks_now = latest(history, "Share Repurchases")

    if cash_now is not None or debt_now is not None:
        parts = []
        if cash_now is not None:
            parts.append(f"cash at {format_currency(cash_now)}")
        if debt_now is not None:
            parts.append(f"debt at {format_currency(debt_now)}")
        if parts:
            lines.append(f"{context['latest_year']} capital structure ended with " + " and ".join(parts) + ".")

    if capex_now is not None:
        lines.append(f"Capital expenditure was {format_currency(capex_now)} in {context['latest_year']}.")
    if dividends_now is not None:
        lines.append(f"Cash dividends paid were {format_currency(dividends_now)} in {context['latest_year']}.")
    if buybacks_now is not None:
        lines.append(f"Share repurchases were {format_currency(buybacks_now)} in {context['latest_year']}.")

    return lines[:4]


def build_market_context_lines(
    market: Dict[str, Any],
    peers: pd.DataFrame,
    consensus: Dict[str, Any],
    market_snapshot_date: str,
) -> List[str]:
    lines: List[str] = []
    industry = market.get("industry") or market.get("sector")
    country = market.get("country")
    employees = market.get("employees")
    if industry:
        base = f"The company is mapped to the {industry} industry"
        if country:
            base += f" and reports operations in {country}"
        base += "."
        lines.append(base)
    if employees:
        lines.append(f"External company profile indicates approximately {int(employees):,} employees as of the latest market profile refresh.")
    if consensus.get("revenue_growth_next_year_pct") is not None:
        lines.append(
            f"External consensus implies next-year revenue growth of about {consensus['revenue_growth_next_year_pct']:.1f}% as of {market_snapshot_date}."
        )
    if consensus.get("eps_growth_next_year_pct") is not None:
        lines.append(
            f"External consensus implies next-year EPS growth of about {consensus['eps_growth_next_year_pct']:.1f}% as of {market_snapshot_date}."
        )
    if not peers.empty and market.get("forward_pe") is not None and not pd.isna(peers["Forward P/E"].mean()):
        lines.append(
            f"Forward P/E is {market['forward_pe'] - peers['Forward P/E'].mean():+.1f} turns versus the peer average."
        )
    return lines[:4]


def build_narrative_fact_lines(
    text_disclosures: List[Dict[str, str]],
    numeric_highlights: List[Dict[str, Any]],
    limit: int = 5,
) -> List[str]:
    lines: List[str] = []
    for item in numeric_highlights[:3]:
        value = f"{item['value']:.2f}" if item["label"] == "EPS" else format_currency(item["value"])
        lines.append(f"{item['label']}: {value}. {item['detail']}")
    for item in text_disclosures[: max(0, limit - len(lines))]:
        lines.append(f"{item['label']}: {item['detail']}")
    return lines[:limit]


def make_revenue_net_income_fig(history_plot: pd.DataFrame, history: pd.DataFrame, period_order: List[str]) -> go.Figure:
    fig = go.Figure()
    if "Revenue" in history.columns:
        fig.add_trace(
            go.Scatter(
                x=history_plot["Period"],
                y=history["Revenue"] / 1_000_000_000,
                mode="lines+markers+text",
                name="Revenue",
                text=[label_billions_with_symbol(value) for value in history["Revenue"]],
                textposition="top center",
                textfont=dict(size=10, color=CHART_BLUE_DARK),
                cliponaxis=False,
                line=dict(color=CHART_BLUE_DARK, width=3),
            )
        )
    if "Net Income" in history.columns:
        fig.add_trace(
            go.Scatter(
                x=history_plot["Period"],
                y=history["Net Income"] / 1_000_000_000,
                mode="lines+markers+text",
                name="Net Income",
                text=[label_billions_with_symbol(value) for value in history["Net Income"]],
                textposition="bottom center",
                textfont=dict(size=10, color=CHART_BLUE_MID),
                cliponaxis=False,
                line=dict(color=CHART_BLUE_MID, width=3),
            )
        )
    fig.update_layout(
        title=dict(text="Revenue & Net Income ($B)", x=0.02, xanchor="left", font=dict(size=16)),
        height=330,
        legend_title_text="",
        margin=dict(l=10, r=10, t=55, b=25),
        yaxis_title="$B",
        xaxis=dict(type="category", categoryorder="array", categoryarray=period_order),
    )
    return fig


def make_balance_fig(history_plot: pd.DataFrame, history: pd.DataFrame, period_order: List[str]) -> go.Figure | None:
    balance = history_plot[["Period"]].copy()
    if "Assets" in history.columns:
        balance["Assets"] = history["Assets"] / 1_000_000_000
    if "Liabilities" in history.columns:
        balance["Liabilities"] = history["Liabilities"] / 1_000_000_000
    balance_melt = balance.melt(id_vars="Period", var_name="Metric", value_name="Value").dropna(subset=["Value"])
    if balance_melt.empty:
        return None

    fig = px.bar(
        balance_melt,
        x="Period",
        y="Value",
        color="Metric",
        barmode="group",
        text="Value",
        color_discrete_map={"Assets": CHART_BLUE_DARK, "Liabilities": CHART_BLUE_LIGHT},
    )
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        texttemplate="$%{y:.1f}B",
        textfont=dict(size=10, color=CHART_BLUE_DARK),
        constraintext="none",
    )
    balance_max = balance_melt["Value"].max()
    fig.update_layout(
        title=dict(text="Assets vs Liabilities ($B)", x=0.02, xanchor="left", font=dict(size=16)),
        height=330,
        legend_title_text="",
        margin=dict(l=10, r=10, t=65, b=25),
        yaxis=dict(title="$B", range=[0, balance_max * 1.18 if balance_max else 1]),
        xaxis=dict(type="category", categoryorder="array", categoryarray=period_order),
    )
    return fig


def render_comprehensive_brief(
    company: Dict[str, Any],
    filing: Dict[str, Any],
    history: pd.DataFrame,
    context: Dict[str, str],
    market_snapshot_date: str,
    business_summary: str,
    scale_line: str,
    dynamic_metrics: List[Dict[str, Any]],
    numeric_highlights: List[Dict[str, Any]],
    text_disclosures: List[Dict[str, str]],
    focus_lines: List[str],
    reporting_lines: List[str],
    section_coverage_lines: List[str],
    peer_lines: List[str],
    peers: pd.DataFrame,
    metric_sources: pd.DataFrame,
    available_sections: Dict[str, str],
    market_context_lines: List[str],
    initiative_lines: List[str],
    operating_driver_lines: List[str],
    segment_lines: List[str],
    capital_lines: List[str],
    liquidity_lines: List[str],
    risk_lines: List[str],
    outlook_lines: List[str],
    esg_lines: List[str],
    financial_story_lines: List[str],
    capital_story_lines: List[str],
) -> None:
    hero_cols = st.columns([1.9, 1.1], vertical_alignment="top")
    with hero_cols[0]:
        st.markdown(
            f"""
            <div class="hero">
                <div class="eyebrow">Comprehensive Brief</div>
                <div class="hero-title">{company['name']} ({company['ticker']})</div>
                <p class="hero-copy">{business_summary}</p>
                <p class="copy" style="margin-top:0.45rem;">{scale_line}</p>
                <div>
                    <span class="timeline-pill">{context['range_label']}</span>
                    <span class="timeline-pill">Filed: {filing['filing_date']}</span>
                    <span class="timeline-pill">Profile: {company['profile']}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hero_cols[1]:
        render_panel(
            "How To Read This",
            list_to_html(
                [
                    "This version is designed as a short-form filing brief, organized like a 3-4 page management memo.",
                    "It emphasizes business context, management priorities, operating drivers, risks, capital allocation, and outlook.",
                    "The current download exports still reflect the executive snapshot format.",
                ]
            ),
        )

    metric_cols = st.columns(4)
    eps_metric = "Diluted EPS" if "Diluted EPS" in history.columns else "Basic EPS"
    brief_specs = [
        ("Revenue", format_currency(latest(history, "Revenue")), format_delta(pct_change(latest(history, "Revenue"), prior(history, "Revenue")), context["prior_year"]), f"{context['latest_year']} annual revenue.", tone_for_change(pct_change(latest(history, "Revenue"), prior(history, "Revenue")))),
        ("Expenses", format_currency(latest(history, "Expenses")), format_delta(pct_change(latest(history, "Expenses"), prior(history, "Expenses")), context["prior_year"]), f"{context['latest_year']} annual expenses.", tone_for_change(pct_change(latest(history, "Expenses"), prior(history, "Expenses")), positive_good=False)),
        ("Net Income", format_currency(latest(history, "Net Income")), format_delta(pct_change(latest(history, "Net Income"), prior(history, "Net Income")), context["prior_year"]), f"{context['latest_year']} annual net income.", tone_for_change(pct_change(latest(history, "Net Income"), prior(history, "Net Income")))),
        ("EPS", "-" if latest(history, eps_metric) is None else f"{latest(history, eps_metric):.2f}", format_delta(pct_change(latest(history, eps_metric), prior(history, eps_metric)), context["prior_year"]), f"{eps_metric} for {context['latest_year']}.", tone_for_change(pct_change(latest(history, eps_metric), prior(history, eps_metric)))),
    ]
    for idx, spec in enumerate(brief_specs):
        with metric_cols[idx]:
            render_kpi(*spec)

    tabs = st.tabs(["Overview", "Initiatives", "Financials", "Risks & Outlook"])

    with tabs[0]:
        left, right = st.columns([1.1, 1.0])
        with left:
            render_panel("Company Overview", list_to_html(combine_unique_lines(financial_story_lines[:2], market_context_lines[:2], limit=4)))
            render_panel("Business Footprint", list_to_html(combine_unique_lines(segment_lines, market_context_lines, limit=4)))
        with right:
            render_panel("What Changed This Year", list_to_html(financial_story_lines))
            render_panel("Reported Facts Worth Knowing", list_to_html(build_narrative_fact_lines(text_disclosures, numeric_highlights, limit=5)))

    with tabs[1]:
        left, right = st.columns(2)
        with left:
            render_panel("Management Priorities", list_to_html(combine_unique_lines(initiative_lines, focus_lines, limit=6)))
            render_panel("Operating Drivers", list_to_html(operating_driver_lines))
        with right:
            render_panel("Capital Allocation & Investment", list_to_html(combine_unique_lines(capital_lines, capital_story_lines, limit=6)))
            render_panel("ESG / People / Other Themes", list_to_html(esg_lines if esg_lines else ["Material ESG or people themes were not clearly captured in the extracted filing text."]))

    with tabs[2]:
        chart_left, chart_right = st.columns(2)
        history_plot = history.copy()
        history_plot["Period"] = period_labels(history_plot) if not history_plot.empty and "Year" in history_plot.columns else pd.Series(dtype=str)
        period_order = history_plot["Period"].tolist() if "Period" in history_plot.columns else []
        with chart_left:
            if not history.empty:
                st.plotly_chart(make_revenue_net_income_fig(history_plot, history, period_order), width="stretch", config=PLOTLY_CONFIG)
        with chart_right:
            balance_fig = make_balance_fig(history_plot, history, period_order)
            if balance_fig is not None:
                st.plotly_chart(balance_fig, width="stretch", config=PLOTLY_CONFIG)
            else:
                render_panel("Assets vs Liabilities", "Balance sheet history was not available for the periods shown.")

        bottom_left, bottom_right = st.columns([1.1, 1.0])
        with bottom_left:
            render_panel("Financial Performance Readout", list_to_html(financial_story_lines))
        with bottom_right:
            render_panel("Liquidity & Capital Position", list_to_html(combine_unique_lines(capital_story_lines, liquidity_lines, limit=6)))

        if dynamic_metrics:
            st.markdown('<div class="section-title" style="margin-top:0.8rem;">Key Ratios</div>', unsafe_allow_html=True)
            ratio_cols = st.columns(min(4, len(dynamic_metrics[:4])) or 1)
            for idx, item in enumerate(dynamic_metrics[:4]):
                value = format_percent(item["value"]) if item["suffix"] == "%" else format_ratio(item["value"])
                with ratio_cols[idx]:
                    render_chip(item["theme"], item["label"], value, f"{context['latest_year']} disclosed value.")

    with tabs[3]:
        left, right = st.columns([1.05, 1.0])
        with left:
            render_panel("Key Risks & Watch Items", list_to_html(risk_lines))
            render_panel("Management Outlook", list_to_html(outlook_lines))
        with right:
            render_panel("Peer / Market Context", list_to_html(combine_unique_lines(peer_lines, market_context_lines, limit=5)))
            render_panel("Source Basis", list_to_html(reporting_lines[:4] + section_coverage_lines[:2]))
            if not metric_sources.empty:
                preferred_cols = [column for column in ["Metric", "Source Concept", "Validation Status"] if column in metric_sources.columns]
                if preferred_cols:
                    st.dataframe(metric_sources[preferred_cols], width="stretch", hide_index=True)


@st.cache_data(show_spinner=False, ttl=3600)
def run_sec_analysis(query: str, user_agent: str, years: int) -> dict:
    analyzer = Sec10KAnalyzer(user_agent=user_agent, cache_dir="sec-edgar-filings")
    return analyzer.analyze(query=query, years=years)


@st.cache_data(show_spinner=False, ttl=3600)
def run_company_matches(query: str, user_agent: str) -> pd.DataFrame:
    if not query or not query.strip():
        return pd.DataFrame(columns=["ticker", "title", "cik", "display"])
    try:
        analyzer = Sec10KAnalyzer(user_agent=user_agent, cache_dir="sec-edgar-filings")
        return analyzer.search_companies(query=query, limit=8)
    except Exception:
        return pd.DataFrame(columns=["ticker", "title", "cik", "display"])


@st.cache_data(show_spinner=False, ttl=3600)
def run_market_snapshot(ticker: str) -> Dict[str, Any]:
    return get_market_snapshot(ticker)


@st.cache_data(show_spinner=False, ttl=3600)
def run_peer_table(ticker: str, industry_key: str | None) -> pd.DataFrame:
    return get_peer_table(ticker, industry_key, limit=3)


st.title("10K Summary")
st.caption("A concise one-page annual filing summary built for executive review.")
st.markdown("<div class='search-helper'>Search by company name, ticker, or CIK. Start with the company name if you are unsure of the ticker.</div>", unsafe_allow_html=True)

default_user_agent = st.session_state.get("summary_user_agent", "10K Summary analyst@example.com")
default_years = st.session_state.get("summary_years", 5)
if "company_search_input" not in st.session_state:
    st.session_state["company_search_input"] = st.session_state.get("summary_query", "AAPL")
if "company_match_display" not in st.session_state:
    st.session_state["company_match_display"] = ""
default_summary_style = st.session_state.get("summary_style", "Executive Snapshot")

c1, c2, c3, c4 = st.columns([2.2, 0.8, 0.75, 1.0], vertical_alignment="bottom")
query = c1.text_input(
    "Company Name or Ticker",
    key="company_search_input",
    placeholder="Try Apple, Citi, JPM, or a CIK",
)
years = c2.selectbox(
    "Years",
    options=[3, 4, 5],
    index=[3, 4, 5].index(default_years) if default_years in [3, 4, 5] else 2,
)
advanced = c3.toggle("Advanced", value=False)
user_agent = default_user_agent
if advanced:
    user_agent = c3.text_input(
        "SEC User-Agent",
        value=default_user_agent,
        help="SEC requires a descriptive identity string that includes an email address.",
    )
build_clicked = c4.button("Generate Summary", type="primary", use_container_width=True)
summary_style = st.radio(
    "Summary Style",
    ["Executive Snapshot", "Comprehensive Brief"],
    index=["Executive Snapshot", "Comprehensive Brief"].index(default_summary_style) if default_summary_style in ["Executive Snapshot", "Comprehensive Brief"] else 0,
    horizontal=True,
)
st.session_state["summary_style"] = summary_style

matches = run_company_matches(query, user_agent)
selected_query = query.strip()

if query.strip() and not matches.empty:
    match_options = matches["display"].tolist()
    default_display = st.session_state.get("company_match_display")
    if default_display not in match_options:
        default_display = match_options[0]
        st.session_state["company_match_display"] = default_display
    selected_display = st.selectbox(
        "SEC Filer Match",
        match_options,
        index=match_options.index(default_display),
        key="company_match_display",
        help="Choose the exact SEC filer if several similar company names appear.",
    )
    selected_row = matches.loc[matches["display"] == selected_display].iloc[0]
    selected_query = str(selected_row["ticker"]).strip()
    if len(matches) == 1:
        st.caption(f"Using SEC filer match `{selected_row['ticker']}` for {selected_row['title']}.")
    else:
        st.caption(f"{len(matches)} similar SEC filers found. Select the correct company before generating the summary.")
elif query.strip():
    st.caption("No suggested SEC filer matches are shown yet. You can still submit an exact ticker or CIK.")

if build_clicked:
    st.session_state["summary_query"] = query
    st.session_state["summary_user_agent"] = user_agent
    st.session_state["summary_years"] = years
    st.session_state["summary_request"] = {"query": selected_query or query, "user_agent": user_agent, "years": years}

request = st.session_state.get("summary_request")
analysis = {
    "history": pd.DataFrame(columns=["Year"]),
    "company": {"name": "Select a Company", "ticker": "-", "profile": "-", "cik": "-", "sic_description": ""},
    "filing": {"filing_date": "-", "form": "-", "filing_url": "", "local_text_path": ""},
    "sections": {"Business": "", "Risk Factors": "", "MD&A": ""},
    "metric_sources": pd.DataFrame(),
}
market: Dict[str, Any] = {}
peers = pd.DataFrame()

if not request:
    st.info("Choose a company above and generate the summary.")
    st.stop()

try:
    with st.spinner("Pulling the latest Form 10-K, selecting available metrics, and assembling the summary..."):
        analysis = run_sec_analysis(request["query"], request["user_agent"], request["years"])
        market = run_market_snapshot(analysis["company"]["ticker"])
        peers = run_peer_table(analysis["company"]["ticker"], market.get("industry_key"))
except Exception as exc:
    st.error(str(exc))
    st.stop()

history = analysis["history"]
company = analysis["company"]
filing = analysis["filing"]
sections = analysis["sections"]
metric_sources = analysis["metric_sources"]
filing_text = load_filing_text(filing["local_text_path"])
available_sections = {name: text for name, text in sections.items() if is_valid_section(text)}
context = year_context(history, filing["filing_date"])
market_snapshot_date = date.today().strftime("%B %d, %Y")
consensus = get_consensus_summary(market)
business_summary = summarize_business(market, available_sections.get("Business", ""))
narrative_source = " ".join(
    [
        available_sections.get("MD&A", ""),
        available_sections.get("Business", ""),
        available_sections.get("Risk Factors", ""),
    ]
)
industry_label = market.get("industry") or company.get("sic_description") or company.get("profile")
industry_label = industry_label or "Not clearly disclosed"
revenue_value = latest(history, "Revenue")
market_cap_value = market.get("market_cap")
scale_line = f"Industry: {industry_label}."
if revenue_value is not None:
    scale_line += f" Scale reference: {context['latest_year']} revenue {format_currency(revenue_value)}."
elif market_cap_value is not None:
    scale_line += f" Scale reference: market capitalization about {format_currency(market_cap_value)} as of {market_snapshot_date}."

future_focus_lines = find_future_focus_lines(" ".join([available_sections.get("MD&A", ""), available_sections.get("Business", "")]), limit=4)
priority_lines = find_priority_lines(available_sections.get("MD&A", ""), limit=4)
focus_lines = future_focus_lines or priority_lines or fallback_narrative_lines(narrative_source, limit=4)
dynamic_metrics = build_dynamic_metric_cards(history, company["profile"])
numeric_highlights = build_numeric_highlights(history)
text_disclosures = find_text_disclosures(narrative_source)
initiative_lines = find_initiative_lines(" ".join([available_sections.get("MD&A", ""), available_sections.get("Business", "")]), limit=6)
operating_driver_lines = find_operating_driver_lines(available_sections.get("MD&A", ""), limit=5)
segment_lines = find_segment_lines(" ".join([available_sections.get("Business", ""), available_sections.get("MD&A", "")]), limit=4)
capital_lines = find_capital_allocation_lines(" ".join([available_sections.get("MD&A", ""), filing_text]), limit=5)
liquidity_lines = find_liquidity_lines(" ".join([available_sections.get("MD&A", ""), filing_text]), limit=4)
risk_watch_lines = find_risk_lines(" ".join([available_sections.get("Risk Factors", ""), available_sections.get("MD&A", "")]), limit=5)
guidance_lines = find_guidance_lines(" ".join([available_sections.get("MD&A", ""), available_sections.get("Business", "")]), limit=4)
esg_lines = find_esg_lines(narrative_source, limit=3)
financial_story_lines = build_financial_story_lines(history, context, company["profile"])
capital_story_lines = build_capital_story_lines(history, context)
market_context_lines = build_market_context_lines(market, peers, consensus, market_snapshot_date)

peer_lines: List[str] = []
if not peers.empty:
    if market.get("revenue_growth_pct") is not None and not pd.isna(peers["Revenue Growth %"].mean()):
        peer_lines.append(f"Revenue growth is {market['revenue_growth_pct'] - peers['Revenue Growth %'].mean():+.1f} pts versus the peer average.")
    if market.get("operating_margin_pct") is not None and not pd.isna(peers["Operating Margin %"].mean()):
        peer_lines.append(f"Operating margin is {market['operating_margin_pct'] - peers['Operating Margin %'].mean():+.1f} pts versus the peer average.")
    if market.get("forward_pe") is not None and not pd.isna(peers["Forward P/E"].mean()):
        peer_lines.append(f"Forward P/E is {market['forward_pe'] - peers['Forward P/E'].mean():+.1f} turns versus the peer average.")
if not peer_lines:
    peer_lines = ["Peer comparison is limited by external industry coverage or missing valuation fields."]

reporting_lines: List[str] = [
    f"Financial snapshot and charts reflect annual Form 10-K history from {context['range_label'].replace('Annual periods shown: ', '')}.",
    f"YoY comparisons on this page use {context['latest_year']} versus {context['prior_year']}.",
    f"Latest filing used: {filing['form']} filed on {filing['filing_date']}.",
]
if not peers.empty:
    reporting_lines.append(f"Peer matching uses external market fields pulled on {market_snapshot_date}.")
section_coverage_lines = [f"{name}: included in the narrative summary." for name in available_sections.keys()]
if not section_coverage_lines:
    section_coverage_lines = ["Narrative sections were limited, so the summary relies primarily on structured financial data."]

period_summary = f"{context['range_label']}. {context['latest_period_note']}. Market data snapshot: {market_snapshot_date}."
outlook_lines = combine_unique_lines(guidance_lines, future_focus_lines, market_context_lines, limit=5)
if not risk_watch_lines:
    risk_watch_lines = ["Specific risk statements were not cleanly extracted from the available filing text, so the original Risk Factors section should still be reviewed."]
if not outlook_lines:
    outlook_lines = ["Forward-looking commentary was limited in the extracted text, so expectations should be checked directly in MD&A and earnings materials."]

excel_bytes = build_excel_export(
    company,
    filing,
    history,
    peers,
    metric_sources,
    available_sections,
    period_summary,
    DISCLAIMER_LINES,
)
pdf_bytes = build_pdf_export(
    company,
    filing,
    business_summary,
    period_summary,
    history,
    build_kpi_rows(history),
    focus_lines,
    peer_lines,
    reporting_lines,
    DISCLAIMER_LINES,
)
ppt_bytes = build_ppt_export(
    company,
    business_summary,
    f"{context['range_label']} | {context['latest_period_note']} | Market data snapshot {market_snapshot_date}",
    history,
    peers,
    focus_lines,
    reporting_lines,
    DISCLAIMER_LINES,
)

if summary_style == "Comprehensive Brief":
    render_comprehensive_brief(
        company=company,
        filing=filing,
        history=history,
        context=context,
        market_snapshot_date=market_snapshot_date,
        business_summary=business_summary,
        scale_line=scale_line,
        dynamic_metrics=dynamic_metrics,
        numeric_highlights=numeric_highlights,
        text_disclosures=text_disclosures,
        focus_lines=focus_lines,
        reporting_lines=reporting_lines,
        section_coverage_lines=section_coverage_lines,
        peer_lines=peer_lines,
        peers=peers,
        metric_sources=metric_sources,
        available_sections=available_sections,
        market_context_lines=market_context_lines,
        initiative_lines=initiative_lines,
        operating_driver_lines=operating_driver_lines,
        segment_lines=segment_lines,
        capital_lines=capital_lines,
        liquidity_lines=liquidity_lines,
        risk_lines=risk_watch_lines,
        outlook_lines=outlook_lines,
        esg_lines=esg_lines,
        financial_story_lines=financial_story_lines,
        capital_story_lines=capital_story_lines,
    )
    st.markdown(
        f"""
        <div class="disclaimer">
            <div class="disclaimer-title">Important Disclaimer</div>
            <ul class="bullet-list">
                {''.join(f'<li>{line}</li>' for line in DISCLAIMER_LINES)}
            </ul>
            <div class="copy" style="margin-top:0.5rem;">Comprehensive brief reflects annual Form 10-K periods through {context['latest_year']} and external market data pulled on {market_snapshot_date}.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

top_row = st.columns([2.5, 0.55, 0.55, 0.55])
with top_row[0]:
    st.markdown(
        f"""
        <div class="hero">
            <div class="eyebrow">10K Summary</div>
            <div class="hero-title">{company['name']} ({company['ticker']})</div>
            <p class="hero-copy">{business_summary}</p>
            <p class="copy" style="margin-top:0.45rem;">{scale_line}</p>
            <div>
                <span class="timeline-pill">{context['range_label']}</span>
                <span class="timeline-pill">YoY basis: {context['latest_year']} vs {context['prior_year']}</span>
                <span class="timeline-pill">Filed: {filing['filing_date']}</span>
                <span class="timeline-pill">Market snapshot: {market_snapshot_date}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with top_row[1]:
    st.download_button("Excel", data=excel_bytes, file_name=f"{company['ticker']}_10k_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
with top_row[2]:
    st.download_button("PDF", data=pdf_bytes, file_name=f"{company['ticker']}_10k_summary.pdf", mime="application/pdf", use_container_width=True)
with top_row[3]:
    st.download_button("PPT", data=ppt_bytes, file_name=f"{company['ticker']}_10k_summary.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", use_container_width=True)

st.markdown('<div class="section-title">Financial Snapshot</div>', unsafe_allow_html=True)
st.markdown(
    f"<div class='section-caption'>Latest values from {context['latest_year']} with change versus {context['prior_year']}. All history shown below is based on annual 10-K periods only.</div>",
    unsafe_allow_html=True,
)

kpi_cols = st.columns(6)
eps_metric = "Diluted EPS" if "Diluted EPS" in history.columns else "Basic EPS"
snapshot_specs = [
    ("Revenue", format_currency(latest(history, "Revenue")), format_delta(pct_change(latest(history, "Revenue"), prior(history, "Revenue")), context["prior_year"]), f"{context['latest_year']} annual revenue.", tone_for_change(pct_change(latest(history, "Revenue"), prior(history, "Revenue")))),
    ("Expenses", format_currency(latest(history, "Expenses")), format_delta(pct_change(latest(history, "Expenses"), prior(history, "Expenses")), context["prior_year"]), f"{context['latest_year']} annual expenses.", tone_for_change(pct_change(latest(history, "Expenses"), prior(history, "Expenses")), positive_good=False)),
    ("Net Income", format_currency(latest(history, "Net Income")), format_delta(pct_change(latest(history, "Net Income"), prior(history, "Net Income")), context["prior_year"]), f"{context['latest_year']} annual net income.", tone_for_change(pct_change(latest(history, "Net Income"), prior(history, "Net Income")))),
    ("Operating CF", format_currency(latest(history, "Operating Cash Flow")), format_delta(pct_change(latest(history, "Operating Cash Flow"), prior(history, "Operating Cash Flow")), context["prior_year"]), f"{context['latest_year']} operating cash flow.", tone_for_change(pct_change(latest(history, "Operating Cash Flow"), prior(history, "Operating Cash Flow")))),
    ("Free Cash Flow", format_currency(latest(history, "Free Cash Flow")), format_delta(pct_change(latest(history, "Free Cash Flow"), prior(history, "Free Cash Flow")), context["prior_year"]), f"{context['latest_year']} free cash flow.", tone_for_change(pct_change(latest(history, "Free Cash Flow"), prior(history, "Free Cash Flow")))),
    ("EPS", "-" if latest(history, eps_metric) is None else f"{latest(history, eps_metric):.2f}", format_delta(pct_change(latest(history, eps_metric), prior(history, eps_metric)), context["prior_year"]), f"{eps_metric} for {context['latest_year']}.", tone_for_change(pct_change(latest(history, eps_metric), prior(history, eps_metric)))),
]
for idx, spec in enumerate(snapshot_specs):
    with kpi_cols[idx]:
        render_kpi(*spec)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Key Metrics</div>', unsafe_allow_html=True)
st.markdown(
    f"<div class='section-caption'>Dynamic metrics selected only when clearly available and material in the filing. Displayed values reflect {context['latest_year']}.</div>",
    unsafe_allow_html=True,
)
metric_cols = st.columns(6)
for idx, item in enumerate(dynamic_metrics[:6]):
    value = format_percent(item["value"]) if item["suffix"] == "%" else format_ratio(item["value"])
    with metric_cols[idx]:
        render_chip(item["theme"], item["label"], value, f"{context['latest_year']} disclosed value.")

history_plot = history.copy()
if not history_plot.empty and "Year" in history_plot.columns:
    history_plot["Period"] = period_labels(history_plot)
else:
    history_plot["Period"] = pd.Series(dtype=str)
period_order = history_plot["Period"].tolist() if "Period" in history_plot.columns else []

left_col, right_col = st.columns([1.6, 1.05])

with left_col:
    st.markdown('<div class="section-title">Trends & Visuals</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='section-caption'>All charts below use annual periods from {context['range_label'].replace('Annual periods shown: ', '')}. Labels are shown directly on the visuals for quicker reading.</div>",
        unsafe_allow_html=True,
    )

    row1 = st.columns(2)

    # ── TOP LEFT: Revenue & Net Income only ──────────────────────────────────
    with row1[0]:
        fig = go.Figure()
        if "Revenue" in history.columns:
            fig.add_trace(
                go.Scatter(
                    x=history_plot["Period"],
                    y=history["Revenue"] / 1_000_000_000,
                    mode="lines+markers+text",
                    name="Revenue",
                    text=[label_billions_with_symbol(value) for value in history["Revenue"]],
                    textposition="top center",
                    textfont=dict(size=11, color=CHART_BLUE_DARK),
                    cliponaxis=False,
                    line=dict(color=CHART_BLUE_DARK, width=3),
                )
            )
        if "Net Income" in history.columns:
            fig.add_trace(
                go.Scatter(
                    x=history_plot["Period"],
                    y=history["Net Income"] / 1_000_000_000,
                    mode="lines+markers+text",
                    name="Net Income",
                    text=[label_billions_with_symbol(value) for value in history["Net Income"]],
                    textposition="bottom center",
                    textfont=dict(size=11, color=CHART_BLUE_MID),
                    cliponaxis=False,
                    line=dict(color=CHART_BLUE_MID, width=3),
                )
            )
        fig.update_layout(
            title=dict(text="Revenue & Net Income ($B)", x=0.02, xanchor="left", font=dict(size=16)),
            height=340,
            legend_title_text="",
            margin=dict(l=10, r=10, t=55, b=25),
            yaxis_title="$B",
            xaxis=dict(type="category", categoryorder="array", categoryarray=period_order),
        )
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

    # ── TOP RIGHT: Expenses only ──────────────────────────────────────────────
    with row1[1]:
        if "Expenses" not in history.columns or history["Expenses"].dropna().empty:
            render_panel(
                "Expenses Trend",
                f"Expense history was not available across {context['range_label'].replace('Annual periods shown: ', '')}.",
            )
        else:
            exp_plot = history_plot[["Period"]].copy()
            exp_plot["ExpenseValue"] = history["Expenses"]
            exp_plot = exp_plot.dropna(subset=["ExpenseValue"])

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=exp_plot["Period"],
                    y=exp_plot["ExpenseValue"] / 1_000_000_000,
                    mode="lines+markers+text",
                    text=[label_billions_with_symbol(value) for value in exp_plot["ExpenseValue"]],
                    textposition="top center",
                    textfont=dict(size=11, color=CHART_BLUE_MID),
                    cliponaxis=False,
                    line=dict(color=CHART_BLUE_MID, width=3),
                    name="Expenses",
                )
            )
            fig.update_layout(
                title=dict(text="Expenses ($B)", x=0.02, xanchor="left", font=dict(size=16)),
                height=340,
                showlegend=True,
                legend_title_text="",
                margin=dict(l=10, r=10, t=55, b=25),
                yaxis_title="$B",
                xaxis=dict(type="category", categoryorder="array", categoryarray=period_order),
            )
            st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

    row2 = st.columns(2)
    with row2[0]:
        balance = history_plot[["Period"]].copy()
        if "Assets" in history.columns:
            balance["Assets"] = history["Assets"] / 1_000_000_000
        if "Liabilities" in history.columns:
            balance["Liabilities"] = history["Liabilities"] / 1_000_000_000
        balance_melt = balance.melt(id_vars="Period", var_name="Metric", value_name="Value").dropna(subset=["Value"])
        balance_melt["Text"] = balance_melt["Value"].map(lambda v: f"{v:.1f}")
        if balance_melt.empty:
            render_panel("Assets vs Liabilities", f"Balance sheet history was not available across {context['range_label'].replace('Annual periods shown: ', '')}.")
        else:
            fig = px.bar(
                balance_melt,
                x="Period",
                y="Value",
                color="Metric",
                barmode="group",
                text="Text",
                title=f"Assets vs Liabilities ({context['range_label'].replace('Annual periods shown: ', '')}, $B)",
                color_discrete_map={"Assets": CHART_BLUE_DARK, "Liabilities": CHART_BLUE_LIGHT},
            )
            fig.update_traces(
                textposition="outside",
                cliponaxis=False,
                texttemplate="$%{y:.1f}B",
                textfont=dict(size=11, color=CHART_BLUE_DARK),
                constraintext="none",
            )
            balance_max = balance_melt["Value"].max() if not balance_melt.empty else 0
            fig.update_layout(
                height=340,
                title=dict(text="Assets vs Liabilities ($B)", x=0.02, xanchor="left", font=dict(size=16)),
                legend_title_text="",
                margin=dict(l=10, r=10, t=70, b=25),
                yaxis=dict(title="$B", range=[0, balance_max * 1.18 if balance_max else 1]),
                xaxis=dict(type="category", categoryorder="array", categoryarray=period_order),
            )
            st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

    with row2[1]:
        if all(metric in history.columns for metric in ["Revenue", "Expenses", "Net Income"]):
            waterfall = pd.DataFrame(
                {
                    "Stage": ["Revenue", "Expenses", "Net Income"],
                    "Amount": [latest(history, "Revenue"), -abs(latest(history, "Expenses")), latest(history, "Net Income")],
                    "Measure": ["relative", "relative", "total"],
                }
            )
            fig = go.Figure(
                go.Waterfall(
                    orientation="v",
                    measure=waterfall["Measure"],
                    x=waterfall["Stage"],
                    y=waterfall["Amount"] / 1_000_000_000,
                    text=[format_currency(value) for value in waterfall["Amount"]],
                    textposition="outside",
                    connector={"line": {"color": "#94a3b8"}},
                    increasing={"marker": {"color": CHART_BLUE_DARK}},
                    decreasing={"marker": {"color": CHART_BLUE_LIGHT}},
                    totals={"marker": {"color": CHART_BLUE_MID}},
                )
            )
            fig.update_layout(
                title=dict(text=f"Net Income Bridge ({context['latest_year']}, $B)", x=0.02, xanchor="left", font=dict(size=16)),
                height=340,
                margin=dict(l=10, r=10, t=55, b=25),
                yaxis_title="$B",
            )
            st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
        else:
            render_panel("Net Income Bridge", f"Bridge view was skipped because one of Revenue, Expenses, or Net Income was not available for {context['latest_year']}.")

with right_col:
    st.markdown('<div class="section-title">Business Focus & Insights</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='section-caption'>Narrative insights are taken from the latest filed Form 10-K dated {filing['filing_date']}. Forward-looking themes are shown only when the filing language is clear enough to use.</div>",
        unsafe_allow_html=True,
    )
    render_panel("Management Focus", list_to_html(focus_lines[:4] if focus_lines else [business_summary]))

    highlights = numeric_highlights[:4] + text_disclosures[:2]
    if highlights:
        st.markdown("<div style='height:0.7rem'></div>", unsafe_allow_html=True)
        grid = st.columns(2)
        for idx, item in enumerate(highlights[:6]):
            with grid[idx % 2]:
                if "value" in item:
                    value = f"{item['value']:.2f}" if item["label"] == "EPS" else format_currency(item["value"])
                    render_chip("Reported", item["label"], value, item["detail"])
                else:
                    render_chip("Narrative", item["label"], "Mentioned", item["detail"])

lower_left, lower_right = st.columns([1.25, 1.35])

with lower_left:
    st.markdown('<div class="section-title">Peer Matching</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='section-caption'>External peer and market fields are shown as of {market_snapshot_date}. Industry averages are calculated from the peer set returned for this company.</div>",
        unsafe_allow_html=True,
    )
    if peers.empty:
        render_panel("Peer Snapshot", "Peer lookup was not available for this company's industry key.")
    else:
        positioning = pd.DataFrame(
            [
                {"Metric": "Revenue Growth %", "Target": market.get("revenue_growth_pct"), "Peer Avg": peers["Revenue Growth %"].mean()},
                {"Metric": "Operating Margin %", "Target": market.get("operating_margin_pct"), "Peer Avg": peers["Operating Margin %"].mean()},
                {"Metric": "Forward P/E", "Target": market.get("forward_pe"), "Peer Avg": peers["Forward P/E"].mean()},
            ]
        )
        melted = positioning.melt(id_vars="Metric", var_name="View", value_name="Value")
        melted["Text"] = melted["Value"].map(lambda v: "" if pd.isna(v) else f"{v:.1f}")
        fig = px.bar(
            melted,
            x="Metric",
            y="Value",
            color="View",
            barmode="group",
            text="Text",
            color_discrete_map={"Target": CHART_BLUE_DARK, "Peer Avg": CHART_BLUE_LIGHT},
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(height=320, legend_title_text="", margin=dict(l=10, r=10, t=55, b=10))
        fig.update_layout(title=dict(text="Relative Position vs Peer Average", x=0.02, xanchor="left", font=dict(size=15)))
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

        peer_display = peers.copy()
        for column in ["Revenue Growth %", "Operating Margin %", "Profit Margin %"]:
            if column in peer_display.columns:
                peer_display[column] = peer_display[column].map(format_percent)
        for column in ["Forward P/E", "P/B", "EV / Revenue"]:
            if column in peer_display.columns:
                peer_display[column] = peer_display[column].map(format_ratio)
        if "Market Cap" in peer_display.columns:
            peer_display["Market Cap"] = peer_display["Market Cap"].map(format_currency)
        st.dataframe(peer_display[["Ticker", "Company", "Revenue Growth %", "Operating Margin %", "Forward P/E", "P/B"]], width="stretch", hide_index=True)

with lower_right:
    st.markdown('<div class="section-title">Reporting Basis</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div class='section-caption'>This section clarifies the timeline and source basis for the figures shown on this page.</div>",
        unsafe_allow_html=True,
    )
    render_panel("Timeframe & Sources", list_to_html(reporting_lines[:4]))
    render_panel("Section Coverage", list_to_html(section_coverage_lines[:4]))

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
with st.expander("Reference", expanded=False):
    st.markdown(
        "<div class='section-caption'>Reference details below show where the numbers and narrative on this page were taken from.</div>",
        unsafe_allow_html=True,
    )

    ref_left, ref_right = st.columns([0.95, 1.45])

    with ref_left:
        filing_reference_lines = [
            f"SEC filing used: {filing['form']} filed on {filing['filing_date']}.",
            f"Financial periods shown: {context['range_label'].replace('Annual periods shown: ', '')}.",
            f"Market data snapshot date: {market_snapshot_date}.",
        ]
        if filing.get("filing_url"):
            filing_reference_lines.append(f"Primary filing link: <a href='{filing['filing_url']}' target='_blank'>Open SEC filing</a>.")
        render_panel("Filing Reference", list_to_html(filing_reference_lines))

        narrative_reference_lines = []
        if "Business" in available_sections:
            narrative_reference_lines.append("Company description and business summary draw from the Business section of the filed Form 10-K.")
        if "MD&A" in available_sections:
            narrative_reference_lines.append("Management focus and future-oriented commentary draw primarily from MD&A.")
        if "Risk Factors" in available_sections:
            narrative_reference_lines.append("Risk and contextual commentary reference the Risk Factors section when relevant.")
        if not narrative_reference_lines:
            narrative_reference_lines.append("Narrative references were limited, so the page relies more heavily on structured SEC companyfacts data.")
        render_panel("Narrative Reference", list_to_html(narrative_reference_lines))

    with ref_right:
        metric_reference = metric_sources.copy()
        if not metric_reference.empty:
            preferred_cols = [
                column
                for column in [
                    "Metric",
                    "Preferred Label",
                    "Source Concept",
                    "Taxonomy",
                    "Years Captured",
                    "Validation Status",
                    "Validation Note",
                ]
                if column in metric_reference.columns
            ]
            st.markdown("<div class='panel'>", unsafe_allow_html=True)
            st.markdown("<div class='section-title'>Metric Reference</div>", unsafe_allow_html=True)
            st.markdown("<div class='copy' style='margin-bottom:0.6rem;'>Each financial metric is mapped to the SEC XBRL concept used to build the annual series.</div>", unsafe_allow_html=True)
            st.dataframe(metric_reference[preferred_cols], width="stretch", hide_index=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            render_panel("Metric Reference", "Metric mapping was not available for this run.")

    if available_sections:
        st.markdown("<div class='section-title' style='margin-top:0.5rem;'>Reference Excerpts</div>", unsafe_allow_html=True)
        st.markdown("<div class='copy' style='margin-bottom:0.55rem;'>Short previews from the filing text used for the business and management narrative.</div>", unsafe_allow_html=True)
        for section_name, section_text in available_sections.items():
            st.markdown(f"**{section_name}**")
            preview = section_text if len(section_text) <= 4000 else section_text[:4000] + "..."
            st.write(preview)

st.markdown(
    f"""
    <div class="disclaimer">
        <div class="disclaimer-title">Important Disclaimer</div>
        <ul class="bullet-list">
            {''.join(f'<li>{line}</li>' for line in DISCLAIMER_LINES)}
        </ul>
        <div class="copy" style="margin-top:0.5rem;">Current screen reflects annual Form 10-K periods through {context['latest_year']} and external market data pulled on {market_snapshot_date}.</div>
    </div>
    """,
    unsafe_allow_html=True,
)
