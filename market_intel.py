from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import re

import pandas as pd
import yfinance as yf


def safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_low_quality_text(text: str) -> bool:
    cleaned = normalize_text(text)
    if not cleaned or len(cleaned) < 30:
        return True

    lowered = cleaned.lower()
    banned_phrases = (
        "section not found",
        "united states securities and exchange commission",
        "washington, d.c",
        "commission file number",
        "form 10-k",
        "form 10-q",
        "item 1.",
        "item 1a.",
        "item 7.",
        "member 2025",
        "cusip",
    )
    if any(phrase in lowered for phrase in banned_phrases):
        return True

    if re.search(r"\b\d{8,}\b", cleaned):
        return True
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", cleaned):
        return True
    if re.search(r"[A-Za-z]+\d{6,}", cleaned):
        return True

    digit_count = sum(char.isdigit() for char in cleaned)
    alpha_count = sum(char.isalpha() for char in cleaned)
    if digit_count > 18 or (alpha_count > 0 and digit_count / max(alpha_count, 1) > 0.25):
        return True

    return False


def is_good_sentence(text: str) -> bool:
    cleaned = normalize_text(text)
    if is_low_quality_text(cleaned):
        return False
    if len(cleaned) < 45 or len(cleaned) > 320:
        return False
    if cleaned.count(",") > 6:
        return False
    return True


def sentences(text: str) -> List[str]:
    if not text:
        return []
    cleaned = normalize_text(text)
    parts = re.split(r"(?<=[\.\?!])\s+(?=[A-Z])", cleaned)
    return [part.strip() for part in parts if is_good_sentence(part.strip())]


def unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def keyword_sentences(text: str, keywords: tuple[str, ...], limit: int = 4) -> List[str]:
    hits = [sentence for sentence in sentences(text) if any(keyword in sentence.lower() for keyword in keywords)]
    return unique_keep_order(hits)[:limit]


def get_market_snapshot(ticker: str) -> Dict[str, Any]:
    stock = yf.Ticker(ticker)
    try:
        info = stock.info or {}
    except Exception:
        info = {}
    analyst_targets = {}
    try:
        analyst_targets = stock.analyst_price_targets or {}
    except Exception:
        analyst_targets = {}

    try:
        revenue_estimate = stock.revenue_estimate
    except Exception:
        revenue_estimate = pd.DataFrame()

    try:
        earnings_estimate = stock.earnings_estimate
    except Exception:
        earnings_estimate = pd.DataFrame()

    try:
        recommendations = stock.recommendations_summary
    except Exception:
        recommendations = pd.DataFrame()

    return {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "long_business_summary": info.get("longBusinessSummary"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "industry_key": info.get("industryKey"),
        "sector_key": info.get("sectorKey"),
        "country": info.get("country"),
        "employees": info.get("fullTimeEmployees"),
        "market_cap": safe_float(info.get("marketCap")),
        "revenue_growth_pct": safe_float(info.get("revenueGrowth")) * 100 if safe_float(info.get("revenueGrowth")) is not None else None,
        "profit_margin_pct": safe_float(info.get("profitMargins")) * 100 if safe_float(info.get("profitMargins")) is not None else None,
        "operating_margin_pct": safe_float(info.get("operatingMargins")) * 100 if safe_float(info.get("operatingMargins")) is not None else None,
        "trailing_pe": safe_float(info.get("trailingPE")),
        "forward_pe": safe_float(info.get("forwardPE")),
        "price_to_book": safe_float(info.get("priceToBook")),
        "enterprise_to_revenue": safe_float(info.get("enterpriseToRevenue")),
        "analyst_targets": analyst_targets,
        "revenue_estimate": revenue_estimate,
        "earnings_estimate": earnings_estimate,
        "recommendations_summary": recommendations,
    }


def get_peer_table(target_ticker: str, industry_key: str | None, limit: int = 3) -> pd.DataFrame:
    if not industry_key:
        return pd.DataFrame()

    try:
        industry = yf.Industry(industry_key)
        candidates = industry.top_companies.reset_index()
    except Exception:
        return pd.DataFrame()

    if candidates.empty or "symbol" not in candidates.columns:
        return pd.DataFrame()

    peers = candidates[candidates["symbol"].str.upper() != target_ticker.upper()].head(limit)
    rows: List[Dict[str, Any]] = []

    for peer in peers.itertuples(index=False):
        snapshot = get_market_snapshot(peer.symbol)
        rows.append(
            {
                "Ticker": peer.symbol,
                "Company": snapshot["name"],
                "Rating": getattr(peer, "rating", None),
                "Market Weight": getattr(peer, "weight", None),
                "Revenue Growth %": snapshot["revenue_growth_pct"],
                "Operating Margin %": snapshot["operating_margin_pct"],
                "Profit Margin %": snapshot["profit_margin_pct"],
                "Forward P/E": snapshot["forward_pe"],
                "P/B": snapshot["price_to_book"],
                "EV / Revenue": snapshot["enterprise_to_revenue"],
                "Market Cap": snapshot["market_cap"],
            }
        )

    return pd.DataFrame(rows)


def get_consensus_summary(market_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    revenue_estimate = market_snapshot.get("revenue_estimate", pd.DataFrame())
    earnings_estimate = market_snapshot.get("earnings_estimate", pd.DataFrame())
    recommendations = market_snapshot.get("recommendations_summary", pd.DataFrame())
    targets = market_snapshot.get("analyst_targets", {})

    summary: Dict[str, Any] = {
        "revenue_growth_next_year_pct": None,
        "eps_growth_next_year_pct": None,
        "recommendation_mix": None,
        "target_upside_pct": None,
    }

    if isinstance(revenue_estimate, pd.DataFrame) and not revenue_estimate.empty and "+1y" in revenue_estimate.index:
        growth = safe_float(revenue_estimate.loc["+1y", "growth"])
        summary["revenue_growth_next_year_pct"] = growth * 100 if growth is not None else None

    if isinstance(earnings_estimate, pd.DataFrame) and not earnings_estimate.empty and "+1y" in earnings_estimate.index:
        growth = safe_float(earnings_estimate.loc["+1y", "growth"])
        summary["eps_growth_next_year_pct"] = growth * 100 if growth is not None else None

    if isinstance(recommendations, pd.DataFrame) and not recommendations.empty:
        latest = recommendations.iloc[0]
        summary["recommendation_mix"] = {
            "strong_buy": int(latest.get("strongBuy", 0)),
            "buy": int(latest.get("buy", 0)),
            "hold": int(latest.get("hold", 0)),
            "sell": int(latest.get("sell", 0)),
            "strong_sell": int(latest.get("strongSell", 0)),
        }

    current = safe_float(targets.get("current"))
    mean = safe_float(targets.get("mean"))
    if current not in (None, 0) and mean is not None:
        summary["target_upside_pct"] = ((mean - current) / current) * 100

    return summary


def is_valid_section(text: str) -> bool:
    if not text:
        return False
    cleaned = normalize_text(text)
    return bool(cleaned) and len(cleaned) > 120 and not cleaned.lower().startswith("section not found")


def summarize_business(market_snapshot: Dict[str, Any], fallback_text: str = "", max_sentences: int = 2) -> str:
    for source in [market_snapshot.get("long_business_summary"), fallback_text]:
        parsed = sentences(source or "")
        if parsed:
            return " ".join(parsed[:max_sentences])

        cleaned = normalize_text(source or "")
        if cleaned and not is_low_quality_text(cleaned):
            return cleaned[:280].rsplit(" ", 1)[0] + "..." if len(cleaned) > 280 else cleaned

    name = market_snapshot.get("name") or "The company"
    industry = market_snapshot.get("industry") or market_snapshot.get("sector") or "its industry"
    country = market_snapshot.get("country")
    if country:
        return f"{name} operates in the {industry} market and reports as a public company based in {country}."
    return f"{name} operates in the {industry} market."


def find_priority_lines(mda_text: str, limit: int = 4) -> List[str]:
    keywords = (
        "focus",
        "priorit",
        "invest",
        "strategy",
        "transform",
        "productivity",
        "efficiency",
        "digital",
        "growth",
        "customer",
        "capital allocation",
        "innovation",
        "ai",
        "margin",
    )
    return keyword_sentences(mda_text, keywords, limit=limit)


def find_future_focus_lines(text: str, limit: int = 4) -> List[str]:
    keywords = (
        "expect",
        "plan",
        "continue to",
        "will",
        "focus",
        "invest",
        "transform",
        "expand",
        "priorit",
        "growth",
        "improve",
        "productivity",
        "digital",
        "innovation",
        "capacity",
        "efficiency",
        "moderniz",
    )
    return keyword_sentences(text, keywords, limit=limit)


def find_guidance_lines(text: str, limit: int = 3) -> List[str]:
    keywords = (
        "guidance",
        "outlook",
        "expect",
        "expects",
        "forecast",
        "anticipate",
        "target",
        "plan to",
        "we believe",
    )
    return keyword_sentences(text, keywords, limit=limit)


def find_esg_lines(text: str, limit: int = 2) -> List[str]:
    keywords = (
        "sustainab",
        "climate",
        "carbon",
        "emissions",
        "renewable",
        "diversity",
        "safety",
        "net zero",
        "community",
    )
    return keyword_sentences(text, keywords, limit=limit)


def find_initiative_lines(text: str, limit: int = 5) -> List[str]:
    keywords = (
        "initiative",
        "strateg",
        "focus",
        "invest",
        "expand",
        "launch",
        "transform",
        "digital",
        "technology",
        "platform",
        "productivity",
        "efficiency",
        "moderniz",
        "automation",
        "customer",
        "ai",
        "innovation",
    )
    return keyword_sentences(text, keywords, limit=limit)


def find_operating_driver_lines(text: str, limit: int = 5) -> List[str]:
    keywords = (
        "pricing",
        "volume",
        "mix",
        "margin",
        "expense",
        "cost",
        "demand",
        "rate",
        "yield",
        "spread",
        "utilization",
        "occupancy",
        "claims",
        "premium",
        "deposit",
        "loan",
        "efficiency",
    )
    return keyword_sentences(text, keywords, limit=limit)


def find_risk_lines(text: str, limit: int = 5) -> List[str]:
    keywords = (
        "risk",
        "uncertain",
        "volatility",
        "competition",
        "regulator",
        "regulation",
        "cyber",
        "litigation",
        "inflation",
        "interest rate",
        "credit",
        "supply chain",
        "commodity",
        "foreign exchange",
        "geopolitical",
        "tariff",
    )
    return keyword_sentences(text, keywords, limit=limit)


def find_capital_allocation_lines(text: str, limit: int = 4) -> List[str]:
    keywords = (
        "capital allocation",
        "capital return",
        "dividend",
        "repurchase",
        "buyback",
        "debt",
        "liquidity",
        "cash",
        "capital expenditure",
        "capex",
        "leverage",
        "funding",
        "maturity",
        "facility",
    )
    return keyword_sentences(text, keywords, limit=limit)


def find_segment_lines(text: str, limit: int = 4) -> List[str]:
    keywords = (
        "segment",
        "geograph",
        "region",
        "market",
        "customer",
        "product",
        "service",
        "business line",
        "portfolio",
    )
    return keyword_sentences(text, keywords, limit=limit)


def find_liquidity_lines(text: str, limit: int = 4) -> List[str]:
    keywords = (
        "liquidity",
        "capital resources",
        "cash",
        "borrowings",
        "debt",
        "credit facility",
        "maturity",
        "funding",
        "capital ratios",
        "deposits",
        "cash flow",
    )
    return keyword_sentences(text, keywords, limit=limit)


def fallback_narrative_lines(text: str, limit: int = 4) -> List[str]:
    return unique_keep_order(sentences(text))[:limit]


def find_text_disclosures(filing_text: str) -> List[Dict[str, str]]:
    patterns = [
        ("Customer Concentration", r"[^\.]{0,140}(customer|tenant|client)[^\.]{0,100}\d{1,3}\%[^\.]*\."),
        ("Geography / Segment", r"[^\.]{0,140}(segment|geograph|americas|emea|asia|international|united states)[^\.]{0,160}\."),
        ("Debt Maturity", r"[^\.]{0,120}(maturit|due|repay)[^\.]{0,120}(debt|notes|borrowings)[^\.]{0,80}\."),
        ("Capital Allocation", r"[^\.]{0,120}(repurchase|buyback|dividend|capital allocation)[^\.]{0,140}\."),
        ("Expansion / Transformation", r"[^\.]{0,120}(transform|expand|expansion|moderniz|restructur|optimiz)[^\.]{0,160}\."),
    ]

    disclosures: List[Dict[str, str]] = []
    for label, pattern in patterns:
        match = re.search(pattern, filing_text, flags=re.IGNORECASE)
        if match:
            text = normalize_text(match.group(0))
            if is_low_quality_text(text):
                continue
            disclosures.append({"label": label, "detail": text})
    return disclosures


def build_dynamic_metric_cards(history: pd.DataFrame, profile: str) -> List[Dict[str, Any]]:
    if history.empty:
        return []

    latest_row = history.iloc[-1]
    revenue = safe_float(latest_row.get("Revenue"))

    candidates = [
        ("Net Margin", safe_float(latest_row.get("Net Margin %")), "%", "Profitability"),
        ("Operating Margin", safe_float(latest_row.get("Operating Margin %")), "%", "Profitability"),
        ("FCF Margin", safe_float(latest_row.get("FCF Margin %")), "%", "Cash"),
        ("Current Ratio", safe_float(latest_row.get("Current Ratio")), "x", "Liquidity"),
        ("Leverage", safe_float(latest_row.get("Leverage")), "x", "Balance Sheet"),
        ("Debt / Equity", safe_float(latest_row.get("Debt / Equity")), "x", "Balance Sheet"),
        ("Asset Turnover", safe_float(latest_row.get("Asset Turnover")), "x", "Efficiency"),
        ("Cash Conversion", safe_float(latest_row.get("Cash Conversion")), "x", "Cash"),
        ("R&D % of Revenue", safe_float(latest_row.get("R&D % of Revenue")), "%", "Investment"),
    ]

    cards: List[Dict[str, Any]] = []
    for label, value, suffix, theme in candidates:
        if value is None:
            continue
        if label == "R&D % of Revenue" and value < 1:
            continue
        if profile == "Bank" and label in {"Current Ratio", "Asset Turnover", "FCF Margin"}:
            continue
        cards.append({"label": label, "value": value, "suffix": suffix, "theme": theme})
    return cards[:6]


def build_numeric_highlights(history: pd.DataFrame) -> List[Dict[str, Any]]:
    if history.empty:
        return []

    latest_row = history.iloc[-1]
    revenue = safe_float(latest_row.get("Revenue"))
    highlights: List[Dict[str, str]] = []

    def add(label: str, value: float | None, detail: str) -> None:
        if value is None:
            return
        highlights.append({"label": label, "value": value, "detail": detail})

    rnd = safe_float(latest_row.get("Research & Development"))
    if rnd is not None and revenue not in (None, 0) and rnd / revenue >= 0.01:
        add("R&D Spend", rnd, "R&D investment disclosed in the annual filing.")

    dividends = safe_float(latest_row.get("Dividends Paid"))
    if dividends is not None and dividends > 0:
        add("Dividends", dividends, "Cash dividends paid during the annual period.")

    repurchases = safe_float(latest_row.get("Share Repurchases"))
    if repurchases is not None and repurchases > 0:
        add("Buybacks", repurchases, "Share repurchases disclosed in the filing.")

    capex = safe_float(latest_row.get("Capex"))
    if capex is not None and capex > 0:
        add("Capex", capex, "Capital expenditure run-rate based on the latest 10-K.")

    debt = safe_float(latest_row.get("Debt"))
    if debt is not None and debt > 0:
        add("Debt", debt, "Debt balance captured from annual XBRL facts.")

    cash = safe_float(latest_row.get("Cash"))
    if cash is not None and cash > 0:
        add("Cash", cash, "Cash or cash-equivalent balance from the latest annual filing.")

    eps = safe_float(latest_row.get("Diluted EPS")) or safe_float(latest_row.get("Basic EPS"))
    if eps is not None:
        highlights.append({"label": "EPS", "value": eps, "detail": "Earnings-per-share disclosure available in annual facts."})

    return highlights[:6]


def load_filing_text(local_text_path: str) -> str:
    try:
        return Path(local_text_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
