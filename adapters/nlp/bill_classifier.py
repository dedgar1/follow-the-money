"""
Industry tagger for congressional bills — Sprint 7.

Uses a keyword taxonomy to assign Industry categories to bill titles + subjects.
No spaCy model is required; the classifier operates on normalised plain text and
applies the longest-matching keyword first (more specific beats generic).
"""

from __future__ import annotations

import re

from domain.shared.industry import Industry

# ── Keyword taxonomy ──────────────────────────────────────────────────────────
# Longer/more-specific phrases appear before single words within each list.
# During matching, ALL phrases are sorted globally by length descending so the
# most-specific match always wins.

_INDUSTRY_KEYWORDS: dict[Industry, list[str]] = {
    Industry.ENERGY_NATURAL_RESOURCES: [
        "oil and gas", "natural gas", "fossil fuel", "offshore drilling",
        "clean energy", "renewable energy", "solar energy", "wind energy",
        "nuclear energy", "carbon emissions", "greenhouse gas", "climate change",
        "energy efficiency", "energy policy", "carbon tax", "cap and trade",
        "liquefied natural gas", "petroleum", "pipeline",
        "energy", "oil", "coal", "drilling", "emissions", "climate",
        "refinery", "fracking", "lng",
    ],
    Industry.HEALTH: [
        "affordable care act", "mental health parity", "public health",
        "drug pricing", "prescription drug", "health insurance",
        "health care", "medicare advantage", "medicare",
        "medicaid", "opioid epidemic", "telehealth", "pharmaceutical",
        "patient rights", "nursing home", "cancer research",
        "health", "medical", "hospital", "patient", "drug", "pharma",
        "vaccine", "disease", "nursing", "addiction",
    ],
    Industry.FINANCE_INSURANCE_REAL_ESTATE: [
        "wall street reform", "consumer financial protection",
        "dodd-frank", "securities and exchange", "bank regulation",
        "private equity", "hedge fund", "credit union",
        "financial regulation", "mortgage backed",
        "real estate investment", "housing finance",
        "banking", "bank", "financial", "finance", "credit",
        "mortgage", "insurance", "investment", "housing", "real estate",
        "securities", "derivatives",
    ],
    Industry.DEFENSE: [
        "national defense authorization", "department of defense",
        "national security", "armed forces", "military spending",
        "weapons system", "nuclear weapon", "missile defense",
        "defense", "military", "army", "navy", "air force",
        "veteran", "war", "pentagon", "munition", "missile",
        "combat", "troop",
    ],
    Industry.AGRICULTURE: [
        "farm bill", "food safety modernization", "rural development",
        "crop insurance", "commodity program", "food stamp",
        "agricultural subsidy", "animal welfare",
        "agriculture", "farming", "farm", "livestock", "crop",
        "usda", "pesticide", "fertilizer", "rural", "commodity",
    ],
    Industry.COMMUNICATIONS_ELECTRONICS: [
        "net neutrality", "data privacy", "broadband access",
        "artificial intelligence", "cybersecurity act",
        "spectrum allocation", "social media regulation",
        "internet access", "online privacy",
        "communications", "broadband", "internet", "telecom",
        "cyber", "technology", "tech", "data", "digital",
        "online", "satellite", "wireless", "5g",
    ],
    Industry.TRANSPORTATION: [
        "infrastructure investment", "highway funding",
        "public transit", "federal aviation administration",
        "railroad safety", "electric vehicle", "high speed rail",
        "transportation", "highway", "road", "bridge",
        "aviation", "airline", "port", "shipping", "rail",
        "vehicle", "amtrak", "transit",
    ],
    Industry.LABOR: [
        "minimum wage", "worker protection", "employee rights",
        "occupational safety", "workforce development",
        "collective bargaining", "union organizing",
        "labor", "worker", "wage", "union", "employment",
        "osha", "workplace", "job training", "workforce",
    ],
    Industry.LAWYERS_LOBBYISTS: [
        "civil rights act", "criminal justice reform",
        "sentencing reform", "lobbying disclosure",
        "campaign finance reform", "judicial appointment",
        "due process", "class action",
        "justice", "court", "judiciary", "legal", "criminal",
        "civil rights", "constitution", "amendment", "lawsuit",
    ],
    Industry.IDEOLOGICAL_SINGLE_ISSUE: [
        "second amendment", "gun control", "assault weapons",
        "abortion rights", "right to life",
        "immigration reform", "border security",
        "voting rights act", "religious freedom",
        "gun", "abortion", "immigration", "border",
        "voting rights", "election", "religion", "lgbtq",
    ],
}

# Pre-sort all (keyword, industry) pairs: longest phrase first
_SORTED_RULES: list[tuple[str, Industry]] = sorted(
    ((kw, ind) for ind, kws in _INDUSTRY_KEYWORDS.items() for kw in kws),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text.lower().strip())


class BillClassifier:
    """
    Classify congressional bill titles (and optional subject strings) into
    Industry categories using a deterministic keyword taxonomy.

    Longer/more-specific phrases score higher than single keywords, so
    ``classify("National Defense Authorization Act")`` → DEFENSE with high
    confidence rather than being swamped by short-word matches.
    """

    def classify(
        self,
        title: str,
        subjects: list[str] | None = None,
    ) -> tuple[Industry, float]:
        """
        Return ``(Industry, confidence)`` for a bill.

        Confidence is in ``[0.0, 1.0]`` where:
          * 0.0 = no keywords matched → UNKNOWN
          * 1.0 = all matched weight belongs to a single industry

        Parameters
        ----------
        title:    Bill title or short description.
        subjects: Optional list of Congress.gov subject-tag strings.
        """
        combined = _normalize(title + " " + " ".join(subjects or []))
        scores: dict[Industry, float] = {}

        for keyword, industry in _SORTED_RULES:
            if keyword in combined:
                weight = float(len(keyword.split()))  # longer phrase → higher weight
                scores[industry] = scores.get(industry, 0.0) + weight

        if not scores:
            return Industry.UNKNOWN, 0.0

        best = max(scores, key=scores.__getitem__)
        total = sum(scores.values())
        confidence = round(scores[best] / total, 3) if total else 0.0
        return best, confidence

    def classify_many(
        self,
        bills: list[tuple[str, list[str] | None]],
    ) -> list[tuple[Industry, float]]:
        """Classify a batch of ``(title, subjects)`` pairs."""
        return [self.classify(title, subjects) for title, subjects in bills]
