"""
2단계 필터링 엔진

1단계 (API 레벨): prcureNm → prebid_client.py에서 처리
2단계 (코드 레벨): AND/제외 키워드, 기관명, 금액 → 이 모듈에서 처리
"""

from __future__ import annotations

import logging
from typing import Sequence

from src.core.models import (
    AlertProfile,
    PreBidNotice,
)

logger = logging.getLogger(__name__)


def _match_and_keywords(name: str, and_keywords: list[str]) -> bool:
    """AND 키워드: 모든 키워드가 공고명에 포함되어야 True"""
    if not and_keywords:
        return True
    name_lower = name.lower()
    return all(kw.lower() in name_lower for kw in and_keywords)


def _match_exclude_keywords(name: str, exclude_keywords: list[str]) -> bool:
    """제외 키워드: 하나라도 포함되면 True (= 제외 대상)"""
    if not exclude_keywords:
        return False
    name_lower = name.lower()
    return any(kw.lower() in name_lower for kw in exclude_keywords)


def _match_demand_agency_by_name(
    agency_name: str, target_names: list[str]
) -> bool:
    """기관명 부분 일치 검사"""
    if not target_names:
        return True  # 필터 미설정 시 전체 통과
    return any(target.lower() in agency_name.lower() for target in target_names)


def filter_notices(
    notices: Sequence[PreBidNotice],
    profile: AlertProfile,
) -> list[PreBidNotice]:
    """사전규격 목록에 코드 레벨 필터링을 적용합니다.

    필터 순서:
    1. 제외 키워드 → 제거
    2. OR 키워드 → API 누락 대비 방어 로직
    3. AND 키워드 → 모두 포함 확인
    4. 기관명 → 부분 일치
    5. 금액 범위 → 범위 내 확인

    Args:
        notices: API에서 조회한 공고 목록
        profile: 알림 프로필

    Returns:
        필터 통과한 PreBidNotice 리스트
    """
    result: list[PreBidNotice] = []

    for notice in notices:
        prcure_name = notice.prcure_nm

        # 1. 제외 키워드 체크
        if _match_exclude_keywords(prcure_name, profile.keywords.exclude):
            logger.debug("제외됨 (키워드): %s", prcure_name)
            continue

        # 1.5 OR 키워드 체크 (API 필터 누락 대비 방어 로직)
        or_keywords = profile.keywords.or_keywords
        if or_keywords:
            prcure_name_lower = prcure_name.lower()
            if not any(kw.lower() in prcure_name_lower for kw in or_keywords):
                logger.debug("제외됨 (OR): %s", prcure_name)
                continue

        # 2. AND 키워드 체크
        if not _match_and_keywords(prcure_name, profile.keywords.and_keywords):
            logger.debug("제외됨 (AND): %s", prcure_name)
            continue

        # 3. 기관명 체크 (by_name)
        if not _match_demand_agency_by_name(
            notice.ntce_instt_nm, profile.demand_agencies.by_name
        ):
            logger.debug("제외됨 (기관): %s → %s", prcure_name, notice.ntce_instt_nm)
            continue

        # 4. 금액 범위 체크
        if not profile.price_range.contains(notice.asign_bdgt_amt):
            logger.debug(
                "제외됨 (금액): %s → %s",
                prcure_name, notice.price_display,
            )
            continue

        result.append(notice)

    logger.info(
        "필터링 결과: %d건 → %d건 (프로필: %s)",
        len(notices), len(result), profile.name,
    )
    return result
