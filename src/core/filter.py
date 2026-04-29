"""
Filtering Engine
"""

from __future__ import annotations
import logging
from typing import Sequence
from src.core.models import (
    AlertProfile,
    PreBidNotice,
    BidNotice,
)

logger = logging.getLogger(__name__)

def filter_notices(
        notices: Sequence[PreBidNotice | BidNotice],
        profile: AlertProfile,
) -> list[PreBidNotice | BidNotice]:
        """Apply filters to notices"""
        result = []

    for notice in notices:
                # Field mapping based on notice type
                if isinstance(notice, PreBidNotice):
                                title = notice.prcure_nm
                                agency = notice.ntce_instt_nm
                                client = notice.rgst_instt_nm
                                price = notice.presmpt_prce
else:
                title = notice.bid_ntce_nm
                agency = notice.ntce_instt_nm
                client = notice.dmin_instt_nm
                price = notice.presmpt_prce



        # 1. Exclude keywords
            if _match_exclude_keywords(title, profile.keywords.exclude):
                            continue

        # 2. Keywords matching (AND/OR)
        matched_keyword = ""
        if profile.keywords.include_and:
                        if not _match_and_keywords(title, profile.keywords.include_and):
                                            matched_keyword = _match_or_keywords(title, profile.keywords.include_or)
                                            if not matched_keyword:
                                                                    continue
                        else:
                                        matched_keyword = _match_or_keywords(title, profile.keywords.include_or)
                                        if not matched_keyword:
                                                            continue

                                    # 3. Agency name filter
                                    if not _match_demand_agency_by_name(agency, profile.demand_agencies):
                                                    if not (client and _match_demand_agency_by_name(client, profile.demand_agencies)):
                                                                        continue

        # 4. Budget range filter
        if profile.budget_range:
                        if price > 0:
                                            if not (profile.budget_range.min_amount <= price <= profile.budget_range.max_amount):
                                                                    continue

        # Attach matched keyword info
        setattr(notice, "matched_keyword", matched_keyword)
        result.append(notice)

    return result


def _match_and_keywords(name: str, and_keywords: list[str]) -> bool:
        """Check if all AND keywords are present"""
    if not and_keywords:
                return True
    name_lower = name.lower()
    return all(kw.lower() in name_lower for kw in and_keywords)

def _match_or_keywords(name: str, or_keywords: list[str]) -> str:
        """Check if any OR keyword is present and return it"""
    if not or_keywords:
                return ""
    name_lower = name.lower()
    for kw in or_keywords:
                if kw.lower() in name_lower:
                                return kw
                        return ""

def _match_exclude_keywords(name: str, exclude_keywords: list[str]) -> bool:
        """Check if any exclude keyword is present"""
    if not exclude_keywords:
                return False
    name_lower = name.lower()
    return any(kw.lower() in name_lower for kw in exclude_keywords)

def _match_demand_agency_by_name(agency_name: str, target_names: list[str]) -> bool:
        """Check if agency name matches targets"""
    if not target_names:
                return True
    agency_lower = agency_name.lower()
    return any(target.lower() in agency_lower for target in target_names)
