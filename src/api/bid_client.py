"""
입찰공고정보서비스 API 클라이언트

나라장터 입찰공고 정보를 업종별로 조회합니다.
G2B_API_KEY 환경변수가 필요합니다.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from src.core.models import BidType, BidNotice
from src.utils.time_utils import get_query_range

logger = logging.getLogger(__name__)

BASE_URL = "http://apis.data.go.kr/1230000/BidPublicInfoService05"


def _get_api_key() -> str:
    """입찰공고 API 인증키"""
    key = os.environ.get("G2B_API_KEY", "")
    if not key:
        key = os.environ.get("G2B_PREBID_API_KEY", "")
    if not key:
        raise ValueError(
            "G2B_API_KEY 또는 G2B_PREBID_API_KEY 환경변수가 설정되지 않았습니다."
        )
    return key


def _build_url(bid_type: BidType) -> str:
    """입찰공고 API URL"""
    suffix = bid_type.api_suffix
    return f"{BASE_URL}/getBidPblancList{suffix}01"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_bid_notice(item: dict[str, Any], bid_type: BidType) -> BidNotice:
    """API 응답 항목을 BidNotice 객체로 변환"""
    try:
        bdgt_amt = int(item.get("bdgtAmt") or 0)
    except (ValueError, TypeError):
        bdgt_amt = 0

    try:
        presmpt_prce = int(item.get("presmptPrce") or 0)
    except (ValueError, TypeError):
        presmpt_prce = 0

    return BidNotice(
        bid_ntce_no=_safe_str(item.get("bidNtceNo", "")),
        bid_ntce_ord=_safe_str(item.get("bidNtceOrd", "")),
        bid_ntce_nm=_safe_str(item.get("bidNtceNm", "")),
        ntce_instt_nm=_safe_str(item.get("ntceInsttNm", "")),
        dmin_instt_nm=_safe_str(item.get("dminInsttNm", "")),
        bid_ntce_dt=_safe_str(item.get("bidNtceDt", "")),
        bid_clse_dt=_safe_str(item.get("bidClseDt", "")),
        bdgt_amt=bdgt_amt,
        presmpt_prce=presmpt_prce,
        dtl_url=_safe_str(item.get("bidNtceDtlUrl", "")),
        bid_type=bid_type,
        ntce_kind_nm=_safe_str(item.get("ntceKindNm", "")),
        ntce_instt_cd=_safe_str(item.get("ntceInsttCd", "")),
    )


def fetch_bid_notices(
    bid_type: BidType,
    keyword: str = "",
    buffer_hours: int = 1,
    max_results: int = 999,
) -> list[BidNotice]:
    """입찰공고 목록 조회

    Args:
        bid_type: 업종 구분
        keyword: 검색 키워드 (현재 API는 키워드 직접 검색 미지원, 클라이언트 필터링)
        buffer_hours: 조회 범위 (시간)
        max_results: 최대 결과 수
    """
    try:
        api_key = _get_api_key()
    except ValueError as e:
        logger.warning("입찰공고 API 키 없음 — 건너뜁니다: %s", e)
        return []

    bgn_dt, end_dt = get_query_range(buffer_hours)
    url = _build_url(bid_type)

    params = {
        "serviceKey": api_key,
        "numOfRows": min(max_results, 999),
        "pageNo": 1,
        "type": "json",
        "inqryBgnDt": bgn_dt,
        "inqryEndDt": end_dt,
    }

    all_notices: list[BidNotice] = []

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        items = data.get("response", {}).get("body", {}).get("items", [])
        if not items:
            logger.info("입찰공고 조회 결과 없음: %s %s", bid_type.display_name, keyword or "(전체)")
            return []

        if isinstance(items, dict):
            items = [items]

        for item in items:
            notice = _parse_bid_notice(item, bid_type)
            all_notices.append(notice)

        logger.info("입찰공고 조회 완료: %s %s → %d건", bid_type.display_name, keyword or "(전체)", len(all_notices))

    except Exception as e:
        logger.error("입찰공고 API 호출 중 오류 발생: %s", e)

    return all_notices
