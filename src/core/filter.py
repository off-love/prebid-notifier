"""
필터링 엔진

AlertProfile의 키워드, 수요기관, 예산 범위 조건에 따라
공고 목록을 필터링합니다.
"""

from __future__ import annotations

import logging
from typing import Sequence

from src.core.models import AlertProfile, PreBidNotice, BidNotice

logger = logging.getLogger(__name__)


def filter_notices(
    notices: Sequence[PreBidNotice | BidNotice],
    profile: AlertProfile,
) -> list[PreBidNotice | BidNotice]:
    """프로필 조건에 따라 공고 목록을 필터링합니다."""
    result = []

    for notice in notices:
        # 공고 유형에 따른 필드 매핑
        if isinstance(notice, PreBidNotice):
            title = notice.prcure_nm
            agency = notice.ntce_instt_nm
            client = notice.rgst_instt_nm
            price = notice.asign_bdgt_amt
        else:
            title = notice.bid_ntce_nm
            agency = notice.ntce_instt_nm
            client = notice.dmin_instt_nm
            price = notice.presmpt_prce

        # 1. 제외 키워드 체크
        if _match_exclude_keywords(title, profile.keywords.exclude):
            continue

        # 2. OR/AND 키워드 매칭
        matched_keyword = ""
        or_kws = profile.keywords.include_or
        and_kws = profile.keywords.include_and

        if and_kws:
            if not _match_and_keywords(title, and_kws):
                continue

        if or_kws:
            matched_keyword = _match_or_keywords(title, or_kws)
            if not matched_keyword:
                continue

        # 3. 수요기관 필터
        agency_names = profile.demand_agencies.by_name
        if agency_names:
            if not _match_demand_agency_by_name(agency, agency_names):
                if not (client and _match_demand_agency_by_name(client, agency_names)):
                    continue

        # 4. 예산 범위 필터
        budget = profile.budget_range
        if budget and price > 0:
            if not (budget.min_amount <= price <= budget.max_amount):
                continue

        # 매칭된 키워드 정보 첨부
        setattr(notice, "matched_keyword", matched_keyword)
        result.append(notice)

    return result


def _match_and_keywords(name: str, and_keywords: list[str]) -> bool:
    """모든 AND 키워드가 포함되어 있는지 확인"""
    if not and_keywords:
        return True
    name_lower = name.lower()
    return all(kw.lower() in name_lower for kw in and_keywords)


def _match_or_keywords(name: str, or_keywords: list[str]) -> str:
    """OR 키워드 중 하나라도 매칭되면 해당 키워드 반환"""
    if not or_keywords:
        return ""
    name_lower = name.lower()
    for kw in or_keywords:
        if kw.lower() in name_lower:
            return kw
    return ""


def _match_exclude_keywords(name: str, exclude_keywords: list[str]) -> bool:
    """제외 키워드가 포함되어 있는지 확인"""
    if not exclude_keywords:
        return False
    name_lower = name.lower()
    return any(kw.lower() in name_lower for kw in exclude_keywords)


def _match_demand_agency_by_name(agency_name: str, target_names: list[str]) -> bool:
    """수요기관명이 타겟 목록에 포함되는지 확인"""
    if not target_names:
        return True
    agency_lower = agency_name.lower()
    return any(target.lower() in agency_lower for target in target_names)
