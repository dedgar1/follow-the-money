"""
Industry taxonomy — canonical list used for classifying donors and tagging bills.

No string literals for industries anywhere else in the codebase — always use
this enum.
"""

from __future__ import annotations

from enum import Enum


class Industry(str, Enum):
    FINANCE_INSURANCE_REAL_ESTATE = "finance_insurance_real_estate"
    ENERGY_NATURAL_RESOURCES      = "energy_natural_resources"
    HEALTH                        = "health"
    LAWYERS_LOBBYISTS             = "lawyers_lobbyists"
    COMMUNICATIONS_ELECTRONICS    = "communications_electronics"
    DEFENSE                       = "defense"
    AGRICULTURE                   = "agriculture"
    TRANSPORTATION                = "transportation"
    LABOR                         = "labor"
    IDEOLOGICAL_SINGLE_ISSUE      = "ideological_single_issue"
    OTHER                         = "other"
    UNKNOWN                       = "unknown"


INDUSTRY_DISPLAY_NAMES: dict[Industry, str] = {
    Industry.FINANCE_INSURANCE_REAL_ESTATE: "Finance, Insurance & Real Estate",
    Industry.ENERGY_NATURAL_RESOURCES:      "Energy & Natural Resources",
    Industry.HEALTH:                        "Health",
    Industry.LAWYERS_LOBBYISTS:             "Lawyers & Lobbyists",
    Industry.COMMUNICATIONS_ELECTRONICS:    "Communications & Electronics",
    Industry.DEFENSE:                       "Defense",
    Industry.AGRICULTURE:                   "Agriculture",
    Industry.TRANSPORTATION:                "Transportation",
    Industry.LABOR:                         "Labor",
    Industry.IDEOLOGICAL_SINGLE_ISSUE:      "Ideological/Single Issue",
    Industry.OTHER:                         "Other",
    Industry.UNKNOWN:                       "Unknown",
}
