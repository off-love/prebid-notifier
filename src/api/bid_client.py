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

BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"


def _get_api_key() -> str:
    """입찰공고 API 인증키"""
    key = os.environ.get("G2B_API_KEY", "")
    if not key:
        key = os.environ.get("G2B_BID_API_KEY", "")
    if not key:
        key = os.environ.get("G2B_PREBID_API_KEY", "")
    if not key:
        raise ValueError(
            "G2B_API_KEY 또는 G2B_PREBID_API_KEY 환경변수가 설정되지 않았습니다."
        )
    return key


def _build_url(bid_type: BidType) -> str:
    """입찰공고 API URL"""
    return f"{BASE_URL}/getBidPblancListInfo{bid_type.api_suffix}"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(str(value).replace(",", "").strip() or "0")
    except (ValueError, TypeError):
        return 0


def _parse_bid_notice(item: dict[str, Any], bid_type: BidType) -> BidNotice:
    """API 응답 항목을 BidNotice 객체로 변환"""
    return BidNotice(
        bid_ntce_no=_safe_str(item.get("bidNtceNo", "")),
        bid_ntce_ord=_safe_str(item.get("bidNtceOrd", "")),
        bid_ntce_nm=_safe_str(item.get("bidNtceNm", "")),
        ntce_instt_nm=_safe_str(item.get("ntceInsttNm", "")),
        dmin_instt_nm=_safe_str(
            item.get("dmndInsttNm") or item.get("dminsttNm") or item.get("dminInsttNm")
        ),
        bid_ntce_dt=_safe_str(item.get("bidNtceDt", "")),
        bid_clse_dt=_safe_str(item.get("bidClseDt", "")),
        bdgt_amt=_parse_int(item.get("asignBdgtAmt") or item.get("bdgtAmt")),
        presmpt_prce=_parse_int(item.get("presmptPrce")),
        dtl_url=_safe_str(item.get("bidNtceDtlUrl", "")),
        bid_type=bid_type,
        ntce_kind_nm=_safe_str(item.get("ntceKindNm") or item.get("ntceDivNm")),
        ntce_instt_cd=_safe_str(item.get("ntceInsttCd", "")),
    )


def _extract_items(response_data: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    response = response_data.get("response", {})
    header = response.get("header", {})
    result_code = str(header.get("resultCode", ""))

    if result_code != "00":
        result_msg = header.get("resultMsg", "알 수 없는 오류")
        raise RuntimeError(f"입찰공고 API 오류 [{result_code}]: {result_msg}")

    body = response.get("body", {})
    try:
        total_count = int(body.get("totalCount", 0))
    except (ValueError, TypeError):
        total_count = 0

    items = body.get("items", [])
    if not items:
        return [], total_count

    if isinstance(items, dict):
        items = [items]

    return items, total_count


def fetch_bid_notices(
    bid_type: BidType,
    keyword: str = "",
    buffer_hours: int = 1,
    max_results: int = 999,
    inqry_bgn_dt: str | None = None,
    inqry_end_dt: str | None = None,
) -> list[BidNotice]:
    """입찰공고 목록 조회

    Args:
        bid_type: 업종 구분
        keyword: 검색 키워드 (공고명 API 필터)
        buffer_hours: 조회 범위 (시간)
        max_results: 최대 결과 수
    """
    api_key = _get_api_key()
    if inqry_bgn_dt and inqry_end_dt:
        bgn_dt, end_dt = inqry_bgn_dt, inqry_end_dt
    else:
        bgn_dt, end_dt = get_query_range(buffer_hours)

    url = _build_url(bid_type)
    all_notices: list[BidNotice] = []
    page_no = 1

    while True:
        params = {
            "ServiceKey": api_key,
            "numOfRows": str(min(max_results, 999)),
            "pageNo": str(page_no),
            "type": "json",
            "inqryDiv": "1",
            "inqryBgnDt": bgn_dt,
            "inqryEndDt": end_dt,
        }
        if keyword:
            params["bidNtceNm"] = keyword

        logger.info(
            "입찰공고 API 호출: %s (키워드=%s, 기간=%s~%s, page=%d)",
            bid_type.display_name,
            keyword or "전체",
            bgn_dt,
            end_dt,
            page_no,
        )

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        items, total_count = _extract_items(response.json())

        if not items:
            break

        for item in items:
            notice = _parse_bid_notice(item, bid_type)
            all_notices.append(notice)

        logger.info(
            "  → 입찰공고 %d건 조회 (페이지 %d, 전체 %d건)",
            len(items),
            page_no,
            total_count,
        )

        if len(all_notices) >= total_count or len(all_notices) >= max_results:
            break

        page_no += 1
        time.sleep(0.3)

    logger.info("입찰공고 조회 완료: %s %s → %d건", bid_type.display_name, keyword or "(전체)", len(all_notices))
    return all_notices
