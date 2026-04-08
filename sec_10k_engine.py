from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup


ANNUAL_FORMS = {"10-K", "10-K/A"}
FLOW_MIN_DAYS = 300
FLOW_MAX_DAYS = 380


@dataclass(frozen=True)
class MetricDefinition:
    label: str
    kind: str
    concepts: Sequence[str]
    component_sets: Sequence[Sequence[str]] = ()
    absolute_value: bool = False


METRIC_DEFINITIONS: Dict[str, MetricDefinition] = {
    "Revenue": MetricDefinition(
        label="Revenue",
        kind="flow",
        concepts=(
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
            "InterestAndNoninterestRevenue",
            "InterestIncomeOperating",
            "PremiumsEarnedNet",
            "InsuranceServicesRevenue",
            "RentalRevenue",
            "LeaseRevenue",
            "Revenue",
        ),
        component_sets=(
            ("InterestIncome", "NoninterestIncome"),
            ("InterestIncomeOperating", "NoninterestIncome"),
            ("InterestAndDividendIncomeOperating", "NoninterestIncome"),
        ),
    ),
    "Expenses": MetricDefinition(
        label="Expenses",
        kind="flow",
        concepts=(
            "CostsAndExpenses",
            "OperatingExpenses",
            "NoninterestExpense",
            "BenefitsLossesAndExpenses",
            "PolicyholderBenefitsAndClaimsIncurredNet",
            "OperatingCostsAndExpenses",
        ),
    ),
    "Operating Income": MetricDefinition(
        label="Operating Income",
        kind="flow",
        concepts=(
            "OperatingIncomeLoss",
            "IncomeLossFromOperations",
            "ProfitLossFromOperatingActivities",
            "IncomeBeforeTax",
        ),
    ),
    "Net Income": MetricDefinition(
        label="Net Income",
        kind="flow",
        concepts=(
            "NetIncomeLoss",
            "ProfitLoss",
            "IncomeLossFromContinuingOperations",
        ),
    ),
    "Operating Cash Flow": MetricDefinition(
        label="Operating Cash Flow",
        kind="flow",
        concepts=(
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
            "NetCashFromUsedInOperatingActivities",
        ),
    ),
    "Diluted EPS": MetricDefinition(
        label="Diluted EPS",
        kind="flow",
        concepts=(
            "EarningsPerShareDiluted",
            "DilutedEarningsPerShare",
        ),
    ),
    "Basic EPS": MetricDefinition(
        label="Basic EPS",
        kind="flow",
        concepts=(
            "EarningsPerShareBasic",
            "BasicEarningsPerShare",
        ),
    ),
    "Capex": MetricDefinition(
        label="Capex",
        kind="flow",
        concepts=(
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "CapitalExpendituresIncurredButNotYetPaid",
            "PaymentsToAcquireProductiveAssets",
            "CapitalExpenditures",
        ),
        absolute_value=True,
    ),
    "Assets": MetricDefinition(
        label="Assets",
        kind="instant",
        concepts=(
            "Assets",
            "TotalAssets",
        ),
    ),
    "Current Assets": MetricDefinition(
        label="Current Assets",
        kind="instant",
        concepts=(
            "AssetsCurrent",
        ),
    ),
    "Liabilities": MetricDefinition(
        label="Liabilities",
        kind="instant",
        concepts=(
            "Liabilities",
            "LiabilitiesCurrentAndNoncurrent",
            "TotalLiabilities",
        ),
    ),
    "Current Liabilities": MetricDefinition(
        label="Current Liabilities",
        kind="instant",
        concepts=(
            "LiabilitiesCurrent",
        ),
    ),
    "Equity": MetricDefinition(
        label="Equity",
        kind="instant",
        concepts=(
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "StockholdersEquity",
            "CommonStockholdersEquity",
            "Equity",
        ),
    ),
    "Cash": MetricDefinition(
        label="Cash",
        kind="instant",
        concepts=(
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            "CashCashEquivalentsAndShortTermInvestments",
            "CashAndDueFromBanks",
        ),
    ),
    "Debt": MetricDefinition(
        label="Debt",
        kind="instant",
        concepts=(
            "LongTermDebtAndFinanceLeaseObligations",
            "LongTermDebtNoncurrent",
            "LongTermDebt",
            "Debt",
        ),
        component_sets=(
            ("LongTermDebtNoncurrent", "ShortTermBorrowings"),
            ("LongTermDebt", "ShortTermDebt"),
            ("LongTermDebt", "CommercialPaper"),
        ),
    ),
    "Research & Development": MetricDefinition(
        label="Research & Development",
        kind="flow",
        concepts=(
            "ResearchAndDevelopmentExpense",
            "ResearchAndDevelopmentInProcessExpense",
        ),
    ),
    "Dividends Paid": MetricDefinition(
        label="Dividends Paid",
        kind="flow",
        concepts=(
            "PaymentsOfDividends",
            "PaymentsOfDividendsCommonStock",
            "DividendsCommonStockCash",
        ),
        absolute_value=True,
    ),
    "Share Repurchases": MetricDefinition(
        label="Share Repurchases",
        kind="flow",
        concepts=(
            "PaymentsForRepurchaseOfCommonStock",
            "CommonStockRepurchasedDuringPeriodValue",
        ),
        absolute_value=True,
    ),
}


SECTION_PATTERNS = {
    "Business": {
        "start": (
            r"item\s*1[\.\s:;-]+business",
            r"item\s*1[\.\s:;-]+overview",
        ),
        "end": (
            r"item\s*1a[\.\s:;-]+risk\s+factors",
            r"item\s*2[\.\s:;-]+properties",
        ),
    },
    "Risk Factors": {
        "start": (
            r"item\s*1a[\.\s:;-]+risk\s+factors",
        ),
        "end": (
            r"item\s*1b[\.\s:;-]+unresolved",
            r"item\s*2[\.\s:;-]+properties",
        ),
    },
    "MD&A": {
        "start": (
            r"item\s*7[\.\s:;-]+management(?:'s|s)?\s+discussion\s+and\s+analysis",
        ),
        "end": (
            r"item\s*7a[\.\s:;-]+quantitative",
            r"item\s*8[\.\s:;-]+financial\s+statements",
        ),
    },
}


PROFILE_HINTS = {
    "Bank": {
        "concepts": {
            "InterestAndNoninterestRevenue",
            "NoninterestExpense",
            "CashAndDueFromBanks",
        },
        "sic": ("bank", "banc", "financial services"),
    },
    "Insurance": {
        "concepts": {
            "PremiumsEarnedNet",
            "InsuranceServicesRevenue",
            "PolicyholderBenefitsAndClaimsIncurredNet",
        },
        "sic": ("insurance", "assurance"),
    },
    "REIT / Real Estate": {
        "concepts": {
            "RentalRevenue",
            "LeaseRevenue",
        },
        "sic": ("reit", "real estate"),
    },
}


PROFILE_METRIC_OVERRIDES: Dict[str, Dict[str, MetricDefinition]] = {
    "Bank": {
        "Expenses": MetricDefinition(
            label="Expenses",
            kind="flow",
            concepts=(
                "NoninterestExpense",
                "OperatingExpenses",
                "CostsAndExpenses",
                "OperatingCostsAndExpenses",
            ),
        ),
    },
    "Insurance": {
        "Expenses": MetricDefinition(
            label="Expenses",
            kind="flow",
            concepts=(
                "BenefitsLossesAndExpenses",
                "PolicyholderBenefitsAndClaimsIncurredNet",
                "OperatingExpenses",
                "CostsAndExpenses",
                "OperatingCostsAndExpenses",
            ),
        ),
    },
}


class Sec10KAnalyzer:
    def __init__(self, user_agent: str, cache_dir: str | Path = "sec-edgar-filings") -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError("Provide a valid SEC user-agent string that includes an email address.")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )
        self.cache_dir = Path(cache_dir)
        self._company_lookup: Optional[pd.DataFrame] = None

    def analyze(self, query: str, years: int = 5) -> Dict[str, Any]:
        company = self.resolve_company(query)
        submissions = self.get_submissions(company["cik"])
        filing = self.get_latest_annual_filing(submissions)
        filing_content = self.download_filing(company, filing)
        companyfacts = self.get_companyfacts(company["cik"])

        facts = companyfacts.get("facts", {})
        profile = self.infer_profile(facts, submissions.get("sicDescription", ""))
        metric_results = self.build_metric_results(facts, profile=profile)
        history = self.build_history(metric_results, years=years)
        sections = self.extract_sections(filing_content["text"])
        insights = self.build_insights(history, profile, sections)
        source_table = self.build_source_table(metric_results, history, profile)

        return {
            "company": {
                "name": submissions.get("name", company["title"]),
                "ticker": company["ticker"],
                "cik": company["cik"],
                "sic": submissions.get("sic", ""),
                "sic_description": submissions.get("sicDescription", ""),
                "state_of_incorporation": submissions.get("stateOfIncorporation", ""),
                "fiscal_year_end": submissions.get("fiscalYearEnd", ""),
                "profile": profile,
            },
            "filing": {
                **filing,
                "filing_url": filing_content["filing_url"],
                "local_html_path": filing_content["local_html_path"],
                "local_text_path": filing_content["local_text_path"],
            },
            "history": history,
            "insights": insights,
            "sections": sections,
            "metric_sources": source_table,
        }

    def resolve_company(self, query: str) -> Dict[str, str]:
        if not query or not query.strip():
            raise ValueError("Enter a ticker, company name, or CIK.")

        needle = query.strip()
        needle_upper = needle.upper()
        needle_lower = needle.lower()
        needle_compact = self._compact_lookup_text(needle)
        lookup = self.company_lookup()

        if needle.isdigit():
            match = lookup[lookup["cik"] == needle.zfill(10)]
            if not match.empty:
                row = match.iloc[0]
                return row.to_dict()

        ticker_match = lookup[lookup["ticker"] == needle_upper]
        if not ticker_match.empty:
            row = ticker_match.iloc[0]
            return row.to_dict()

        exact_name = lookup[lookup["title_lower"] == needle_lower]
        if not exact_name.empty:
            row = exact_name.iloc[0]
            return row.to_dict()

        compact_match = lookup[lookup["title_compact"] == needle_compact]
        if not compact_match.empty:
            row = compact_match.sort_values(["title_length", "title"]).iloc[0]
            return row.to_dict()

        starts_with = lookup[lookup["title_lower"].str.startswith(needle_lower, na=False)]
        if not starts_with.empty:
            row = starts_with.sort_values("title").iloc[0]
            return row.to_dict()

        compact_starts_with = lookup[lookup["title_compact"].str.startswith(needle_compact, na=False)]
        if not compact_starts_with.empty:
            row = compact_starts_with.sort_values(["title_length", "title"]).iloc[0]
            return row.to_dict()

        contains = lookup[lookup["title_lower"].str.contains(re.escape(needle_lower), na=False)]
        if not contains.empty:
            row = contains.sort_values(["title_length", "title"]).iloc[0]
            return row.to_dict()

        compact_contains = lookup[lookup["title_compact"].str.contains(re.escape(needle_compact), na=False)]
        if not compact_contains.empty:
            row = compact_contains.sort_values(["title_length", "title"]).iloc[0]
            return row.to_dict()

        raise ValueError(f"No SEC filer matched '{query}'.")

    def search_companies(self, query: str, limit: int = 8) -> pd.DataFrame:
        if not query or not query.strip():
            return pd.DataFrame(columns=["ticker", "title", "cik", "display"])

        needle = query.strip()
        needle_upper = needle.upper()
        needle_lower = needle.lower()
        needle_compact = self._compact_lookup_text(needle)
        needle_digits = re.sub(r"\D", "", needle)
        padded_cik = needle_digits.zfill(10) if needle_digits else ""
        lookup = self.company_lookup().copy()

        tokens = [token for token in re.split(r"[^a-z0-9]+", needle_lower) if token]

        def score_row(row: pd.Series) -> int:
            score = 0
            if padded_cik and row["cik"] == padded_cik:
                score += 220
            if needle_digits and row["cik"].endswith(needle_digits):
                score += 100
            if row["ticker"] == needle_upper:
                score += 200
            if row["title_lower"] == needle_lower:
                score += 180
            if row["title_compact"] == needle_compact:
                score += 175
            if row["ticker"].startswith(needle_upper):
                score += 120
            if row["title_lower"].startswith(needle_lower):
                score += 110
            if row["title_compact"].startswith(needle_compact):
                score += 105
            if needle_lower in row["title_lower"]:
                score += 80
            if needle_compact and needle_compact in row["title_compact"]:
                score += 75
            if needle_upper in row["ticker"]:
                score += 60
            if tokens and all(token in row["title_lower"] for token in tokens):
                score += 70
            score -= int(row["title_length"] / 100)
            return score

        lookup["score"] = lookup.apply(score_row, axis=1)
        matches = lookup[lookup["score"] > 0].sort_values(["score", "title_length", "title"], ascending=[False, True, True]).head(limit).copy()
        if matches.empty:
            return pd.DataFrame(columns=["ticker", "title", "cik", "display"])

        matches["display"] = matches.apply(lambda row: f"{row['ticker']} | {row['title']} | CIK {row['cik']}", axis=1)
        return matches[["ticker", "title", "cik", "display"]].reset_index(drop=True)

    def company_lookup(self) -> pd.DataFrame:
        if self._company_lookup is None:
            data = self._get_json("https://www.sec.gov/files/company_tickers.json")
            rows: List[Dict[str, Any]] = []
            for item in data.values():
                title = item["title"].strip()
                rows.append(
                    {
                        "ticker": item["ticker"].upper(),
                        "title": title,
                        "title_lower": title.lower(),
                        "title_compact": self._compact_lookup_text(title),
                        "title_length": len(title),
                        "cik": str(item["cik_str"]).zfill(10),
                    }
                )
            self._company_lookup = pd.DataFrame(rows)
        return self._company_lookup.copy()

    @staticmethod
    def _compact_lookup_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (text or "").lower())

    def get_submissions(self, cik: str) -> Dict[str, Any]:
        return self._get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")

    def get_companyfacts(self, cik: str) -> Dict[str, Any]:
        return self._get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")

    def get_latest_annual_filing(self, submissions: Dict[str, Any]) -> Dict[str, str]:
        recent = pd.DataFrame(submissions.get("filings", {}).get("recent", {}))
        if recent.empty:
            raise ValueError("No recent SEC filings were returned.")

        annual = recent[recent["form"].isin(ANNUAL_FORMS)].copy()
        if annual.empty:
            raise ValueError("No 10-K or 10-K/A filing was found in the recent SEC feed.")

        annual["filingDate"] = pd.to_datetime(annual["filingDate"], errors="coerce")
        annual = annual.sort_values("filingDate", ascending=False)
        row = annual.iloc[0]
        accession = row["accessionNumber"]
        accession_clean = accession.replace("-", "")

        return {
            "form": row["form"],
            "filing_date": str(row["filingDate"].date()),
            "accession_number": accession,
            "accession_number_clean": accession_clean,
            "primary_document": row["primaryDocument"],
            "primary_doc_description": row.get("primaryDocDescription", ""),
        }

    def download_filing(self, company: Dict[str, str], filing: Dict[str, str]) -> Dict[str, str]:
        base_dir = (
            self.cache_dir
            / company["ticker"]
            / "10-K"
            / filing["accession_number_clean"]
        )
        base_dir.mkdir(parents=True, exist_ok=True)

        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(company['cik'])}/{filing['accession_number_clean']}/{filing['primary_document']}"
        )
        html_path = base_dir / filing["primary_document"]
        text_path = base_dir / "filing-text.txt"

        if not html_path.exists():
            response = self.session.get(filing_url, timeout=30)
            response.raise_for_status()
            html_path.write_text(response.text, encoding="utf-8")

        if not text_path.exists():
            text = self.html_to_text(html_path.read_text(encoding="utf-8", errors="ignore"))
            text_path.write_text(text, encoding="utf-8")

        return {
            "filing_url": filing_url,
            "local_html_path": str(html_path.resolve()),
            "local_text_path": str(text_path.resolve()),
            "text": text_path.read_text(encoding="utf-8", errors="ignore"),
        }

    def build_metric_results(
        self,
        facts: Dict[str, Any],
        profile: str = "Corporate / Industrial",
    ) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        for metric, base_definition in METRIC_DEFINITIONS.items():
            definition = self._definition_for_profile(metric, profile, base_definition)
            direct = self._pick_best_direct_series(facts, definition)
            if direct is not None:
                results[metric] = direct
                continue

            component = self._pick_component_series(facts, definition)
            if component is not None:
                results[metric] = component
                continue

            results[metric] = {
                "series": pd.DataFrame(columns=["Year", "Value"]),
                "source": "Not found",
                "taxonomy": "",
            }
        return results

    def build_history(
        self,
        metric_results: Dict[str, Dict[str, Any]],
        years: int = 5,
    ) -> pd.DataFrame:
        history: Optional[pd.DataFrame] = None

        for metric, payload in metric_results.items():
            series = payload["series"]
            if series.empty:
                continue

            frame = series[["Year", "Value"]].rename(columns={"Value": metric})
            history = frame if history is None else history.merge(frame, on="Year", how="outer")

        if history is None or history.empty:
            return pd.DataFrame(columns=["Year"])

        history = history.sort_values("Year").tail(max(1, years)).reset_index(drop=True)
        history = self._add_derived_metrics(history)
        return history

    def build_source_table(
        self,
        metric_results: Dict[str, Dict[str, Any]],
        history: pd.DataFrame,
        profile: str,
    ) -> pd.DataFrame:
        rows = []
        for metric, payload in metric_results.items():
            series = payload["series"]
            preferred_label = metric
            validation_status = "ok"
            validation_note = "Series selected from the best matching annual SEC fact pattern."

            if metric == "Expenses" and profile == "Bank":
                preferred_label = "Operating Expense"
                validation_note = "For banks, this metric reflects annual operating or noninterest expense from SEC companyfacts when available."

            if not series.empty:
                ordered = series.sort_values("Year").reset_index(drop=True)
                gaps = ordered["Year"].diff().dropna()
                if not gaps.empty and gaps.max() > 1:
                    validation_status = "review"
                    validation_note = "Year gaps were detected in the selected SEC fact series. Review the source concept against the filing."

                yoy = ordered["Value"].pct_change().abs().dropna()
                if not yoy.empty and yoy.max() > 0.60:
                    validation_status = "review"
                    validation_note = "A large year-over-year move was detected in the selected SEC fact series. Review the source concept and filing footnotes."

                if " + " in payload["source"] and validation_status == "ok":
                    validation_note = "Metric is derived from multiple SEC concepts combined into one annual series."
            else:
                validation_status = "missing"
                validation_note = "No annual SEC fact series was captured for this metric."

            rows.append(
                {
                    "Metric": metric,
                    "Preferred Label": preferred_label,
                    "Source Concept": payload["source"],
                    "Taxonomy": payload["taxonomy"],
                    "Years Captured": int(series["Year"].nunique()) if not series.empty else 0,
                    "Validation Status": validation_status,
                    "Validation Note": validation_note,
                }
            )
        return pd.DataFrame(rows)

    def extract_sections(self, text: str) -> Dict[str, str]:
        clean = re.sub(r"\s+", " ", text).strip()
        sections: Dict[str, str] = {}

        for label, patterns in SECTION_PATTERNS.items():
            excerpt = self._extract_section(clean, patterns["start"], patterns["end"])
            sections[label] = excerpt

        return sections

    def infer_profile(self, facts: Dict[str, Any], sic_description: str) -> str:
        available = set()
        for taxonomy in facts.values():
            available.update(taxonomy.keys())

        sic_lower = (sic_description or "").lower()
        for profile, hints in PROFILE_HINTS.items():
            if hints["concepts"] & available:
                return profile
            if any(token in sic_lower for token in hints["sic"]):
                return profile

        return "Corporate / Industrial"

    def build_insights(
        self,
        history: pd.DataFrame,
        profile: str,
        sections: Dict[str, str],
    ) -> List[str]:
        if history.empty:
            return ["The filing was downloaded, but the normalized metric set could not be built from companyfacts."]

        latest = history.iloc[-1]
        previous = history.iloc[-2] if len(history) > 1 else None
        insights: List[str] = [f"Detected reporting profile: {profile}."]

        if "Revenue" in history.columns and pd.notna(latest.get("Revenue")):
            revenue_text = f"Latest annual revenue is {self.format_currency(latest['Revenue'])}."
            if previous is not None and pd.notna(previous.get("Revenue")) and previous["Revenue"] != 0:
                change = ((latest["Revenue"] - previous["Revenue"]) / abs(previous["Revenue"])) * 100
                revenue_text = (
                    f"Latest annual revenue is {self.format_currency(latest['Revenue'])}, "
                    f"up {change:.1f}% versus the prior 10-K."
                )
            insights.append(revenue_text)

        if "Net Margin %" in history.columns and pd.notna(latest.get("Net Margin %")):
            insights.append(f"Net margin is {latest['Net Margin %']:.1f}% on the latest annual filing.")

        if "Operating Cash Flow" in history.columns and pd.notna(latest.get("Operating Cash Flow")):
            cash_text = f"Operating cash flow is {self.format_currency(latest['Operating Cash Flow'])}."
            if "Free Cash Flow" in history.columns and pd.notna(latest.get("Free Cash Flow")):
                cash_text += f" Free cash flow is {self.format_currency(latest['Free Cash Flow'])}."
            insights.append(cash_text)

        if {"Liabilities", "Assets"}.issubset(history.columns):
            assets = latest.get("Assets")
            liabilities = latest.get("Liabilities")
            if pd.notna(assets) and pd.notna(liabilities) and assets:
                insights.append(f"Liabilities-to-assets ratio is {(liabilities / assets):.2f}x.")

        business_excerpt = sections.get("Business", "")
        if business_excerpt and not business_excerpt.startswith("Section not found"):
            insights.append("Business overview extracted successfully from Item 1.")

        mda_excerpt = sections.get("MD&A", "")
        if mda_excerpt and not mda_excerpt.startswith("Section not found"):
            insights.append("MD&A text is available for qualitative review and management commentary.")

        return insights

    @staticmethod
    def format_currency(value: float) -> str:
        absolute = abs(value)
        if absolute >= 1_000_000_000:
            return f"${value / 1_000_000_000:,.2f}B"
        if absolute >= 1_000_000:
            return f"${value / 1_000_000:,.2f}M"
        return f"${value:,.0f}"

    def _pick_best_direct_series(
        self,
        facts: Dict[str, Any],
        definition: MetricDefinition,
    ) -> Optional[Dict[str, Any]]:
        best_choice: Optional[Dict[str, Any]] = None
        best_score: tuple[int, int, int, int] = (-1, -1, -10_000, -1)

        for priority, concept in enumerate(definition.concepts):
            for taxonomy in ("us-gaap", "ifrs-full", "dei"):
                concept_data = facts.get(taxonomy, {}).get(concept)
                if not concept_data:
                    continue

                series = self._normalize_series(concept_data, definition.kind, definition.absolute_value)
                if series.empty:
                    continue

                continuity = 0
                if len(series) > 1:
                    continuity = -int(series["Year"].sort_values().diff().fillna(1).sub(1).abs().sum())
                score = (
                    int(series["Year"].max()),
                    int(series["Year"].nunique()),
                    continuity,
                    -priority,
                )
                if score > best_score:
                    best_score = score
                    best_choice = {
                        "series": series,
                        "source": concept,
                        "taxonomy": taxonomy,
                    }

        return best_choice

    @staticmethod
    def _definition_for_profile(
        metric: str,
        profile: str,
        default_definition: MetricDefinition,
    ) -> MetricDefinition:
        return PROFILE_METRIC_OVERRIDES.get(profile, {}).get(metric, default_definition)

    def _pick_component_series(
        self,
        facts: Dict[str, Any],
        definition: MetricDefinition,
    ) -> Optional[Dict[str, Any]]:
        best_choice: Optional[Dict[str, Any]] = None
        best_score: tuple[int, int, int, int] = (-1, -1, -10_000, -1)

        for priority, component_set in enumerate(definition.component_sets):
            parts: List[pd.DataFrame] = []
            sources: List[str] = []
            taxonomies: List[str] = []

            for concept in component_set:
                metric = MetricDefinition(label=concept, kind=definition.kind, concepts=(concept,), absolute_value=definition.absolute_value)
                component = self._pick_best_direct_series(facts, metric)
                if component is None or component["series"].empty:
                    parts = []
                    break

                frame = component["series"][["Year", "Value"]].rename(columns={"Value": concept})
                parts.append(frame)
                sources.append(component["source"])
                taxonomies.append(component["taxonomy"])

            if not parts:
                continue

            merged = parts[0]
            for frame in parts[1:]:
                merged = merged.merge(frame, on="Year", how="inner")

            if merged.empty:
                continue

            value_columns = [col for col in merged.columns if col != "Year"]
            merged["Value"] = merged[value_columns].sum(axis=1)
            series = merged[["Year", "Value"]].sort_values("Year").reset_index(drop=True)
            continuity = 0
            if len(series) > 1:
                continuity = -int(series["Year"].sort_values().diff().fillna(1).sub(1).abs().sum())
            score = (
                int(series["Year"].max()),
                int(series["Year"].nunique()),
                continuity,
                -priority,
            )
            if score > best_score:
                best_score = score
                best_choice = {
                    "series": series,
                    "source": " + ".join(sources),
                    "taxonomy": " + ".join(sorted(set(taxonomies))),
                }

        return best_choice

    def _normalize_series(
        self,
        concept_data: Dict[str, Any],
        metric_kind: str,
        absolute_value: bool,
    ) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []

        for unit_name, entries in concept_data.get("units", {}).items():
            if not self._valid_unit(unit_name):
                continue
            for entry in entries:
                rows.append(
                    {
                        "start": entry.get("start"),
                        "end": entry.get("end"),
                        "fy": entry.get("fy"),
                        "fp": entry.get("fp"),
                        "filed": entry.get("filed"),
                        "form": entry.get("form"),
                        "frame": entry.get("frame"),
                        "value": entry.get("val"),
                    }
                )

        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=["Year", "Value"])

        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["start"] = pd.to_datetime(df["start"], errors="coerce")
        df["end"] = pd.to_datetime(df["end"], errors="coerce")
        df["filed"] = pd.to_datetime(df["filed"], errors="coerce")
        df = df[df["form"].isin(ANNUAL_FORMS) & df["value"].notna() & df["end"].notna()].copy()
        if df.empty:
            return pd.DataFrame(columns=["Year", "Value"])

        if metric_kind == "flow":
            duration = (df["end"] - df["start"]).dt.days
            annual_mask = duration.between(FLOW_MIN_DAYS, FLOW_MAX_DAYS) | (df["fp"] == "FY") | df["frame"].fillna("").str.contains(r"CY\d{4}", regex=True)
            df = df[annual_mask].copy()
        else:
            df = df[df["fp"].isin(["FY", "Q4", None]) | df["fp"].isna()].copy()

        if df.empty:
            return pd.DataFrame(columns=["Year", "Value"])

        df["Year"] = pd.to_numeric(df["fy"], errors="coerce").fillna(df["end"].dt.year)
        df = df[df["Year"].notna()].copy()
        if df.empty:
            return pd.DataFrame(columns=["Year", "Value"])

        df["Year"] = df["Year"].astype(int)
        df = df.sort_values(["Year", "filed", "end", "value"]).drop_duplicates(["Year"], keep="last")
        if absolute_value:
            df["value"] = df["value"].abs()

        return df[["Year", "value"]].rename(columns={"value": "Value"}).sort_values("Year").reset_index(drop=True)

    @staticmethod
    def _valid_unit(unit_name: str) -> bool:
        lowered = unit_name.lower()
        return lowered.startswith("usd")

    @staticmethod
    def _add_derived_metrics(history: pd.DataFrame) -> pd.DataFrame:
        enriched = history.copy()

        if {"Revenue", "Net Income"}.issubset(enriched.columns):
            enriched["Net Margin %"] = (enriched["Net Income"] / enriched["Revenue"]) * 100

        if {"Revenue", "Operating Income"}.issubset(enriched.columns):
            enriched["Operating Margin %"] = (enriched["Operating Income"] / enriched["Revenue"]) * 100

        if {"Revenue", "Expenses"}.issubset(enriched.columns):
            enriched["Expense Ratio %"] = (enriched["Expenses"] / enriched["Revenue"]) * 100

        if {"Operating Cash Flow", "Capex"}.issubset(enriched.columns):
            enriched["Free Cash Flow"] = enriched["Operating Cash Flow"] - enriched["Capex"]

        if {"Revenue", "Free Cash Flow"}.issubset(enriched.columns):
            enriched["FCF Margin %"] = (enriched["Free Cash Flow"] / enriched["Revenue"]) * 100

        if {"Net Income", "Assets"}.issubset(enriched.columns):
            enriched["ROA %"] = (enriched["Net Income"] / enriched["Assets"]) * 100

        if {"Revenue", "Assets"}.issubset(enriched.columns):
            enriched["Asset Turnover"] = enriched["Revenue"] / enriched["Assets"]

        if {"Liabilities", "Assets"}.issubset(enriched.columns):
            enriched["Leverage"] = enriched["Liabilities"] / enriched["Assets"]

        if {"Debt", "Equity"}.issubset(enriched.columns):
            enriched["Debt / Equity"] = enriched["Debt"] / enriched["Equity"]

        if {"Current Assets", "Current Liabilities"}.issubset(enriched.columns):
            enriched["Current Ratio"] = enriched["Current Assets"] / enriched["Current Liabilities"]

        if {"Operating Cash Flow", "Net Income"}.issubset(enriched.columns):
            enriched["Cash Conversion"] = enriched["Operating Cash Flow"] / enriched["Net Income"]

        if {"Research & Development", "Revenue"}.issubset(enriched.columns):
            enriched["R&D % of Revenue"] = (enriched["Research & Development"] / enriched["Revenue"]) * 100

        return enriched

    @staticmethod
    def html_to_text(raw_html: str) -> str:
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _extract_section(text: str, start_patterns: Sequence[str], end_patterns: Sequence[str]) -> str:
        candidates: List[tuple[int, int]] = []

        for start_pattern in start_patterns:
            for match in re.finditer(start_pattern, text, flags=re.IGNORECASE):
                start = match.start()
                end = Sec10KAnalyzer._find_nearest_end(text, start, end_patterns)
                if end and end - start > 800:
                    candidates.append((start, end))

        if not candidates:
            return "Section not found."

        start, end = max(candidates, key=lambda item: item[1] - item[0])
        return text[start:end].strip()

    @staticmethod
    def _find_nearest_end(text: str, start: int, end_patterns: Sequence[str]) -> Optional[int]:
        nearest: Optional[int] = None
        for end_pattern in end_patterns:
            match = re.search(end_pattern, text[start + 200 :], flags=re.IGNORECASE)
            if not match:
                continue
            position = start + 200 + match.start()
            if nearest is None or position < nearest:
                nearest = position
        return nearest

    def _get_json(self, url: str) -> Dict[str, Any]:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
