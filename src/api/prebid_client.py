"""
사전규격정보서비스 API 클라이언트

사전규격공개 정보를 업종별로 조회합니다.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from src.core.models import BidType, PreBidNotice
from src.utils.time_utils import get_query_range

logger = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService"


def _get_api_key() -> str:
    """사전규격 API 인증키 (별도 키 또는 공용 키)"""
    key = os.environ.get("G2B_PREBID_API_KEY", "")
    if not key:
        key = os.environ.get("G2B_API_KEY", "")
    if not key:
        raise ValueError(
            "G2B_PREBID_API_KEY 또는 G2B_API_KEY 환경변수가 설정되지 않았습니다."
        )
    return key


def _build_operation_name(bid_type: BidType) -> str:
    """사전규격 API 오퍼레이션 이름"""
    mapping = {
        BidType.SERVICE: "getPublicPrcureThngInfoServcPPSSrch",
        BidType.GOODS: "getPublicPrcureThngInfoThngPPSSrch",
        BidType.CONSTRUCTION: "getPublicPrcureThngInfoCnstwkPPSSrch",
        BidType.FOREIGN: "getPublicPrcureThngInfoFrgcptPPSSrch",
    }
    return mapping[bid_type]


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_prebid_notice(item: dict[str, Any], bid_type: BidType) -> PreBidNotice:
    """API 응답 항목을 PreBidNotice 객체로 변환"""
    prcure_no = _safe_str(item.get("bfSpecRgstNo") or item.get("refNo") or "")

    prcure_nm = _safe_str(
        item.get("prcureNm") or item.get("bidNtceNm") or item.get("prdctClsfcNoNm") or ""
    )

    ntce_instt_nm = _safe_str(
        item.get("orderInsttNm") or item.get("ntceInsttNm") or item.get("rlDminsttNm") or item.get("insttNm") or ""
    )

    rcpt_dt = _safe_str(item.get("rgstDt") or item.get("rcptDt") or "")

    opnn_reg_clse_dt = _safe_str(
        item.get("opninRgstClseDt") or item.get("bfSpecOpnnRcptClseDt") or ""
    )

    try:
        asign_bdgt_amt = int(item.get("asignBdgtAmt") or item.get("bdgtAmt") or 0)
    except (ValueError, TypeError):
        asign_bdgt_amt = 0

    dtl_url = ""
    if prcure_no:
        dtl_url = f"https://www.g2b.go.kr:8081/ep/preparation/prebid/preBidDetail.do?preBidRegNo={prcure_no}"

    return PreBidNotice(
        prcure_no=prcure_no,
        prcure_nm=prcure_nm,
        ntce_instt_nm=ntce_instt_nm,
        rcpt_dt=rcpt_dt,
        opnn_reg_clse_dt=opnn_reg_clse_dt,
        asign_bdgt_amt=asign_bdgt_amt,
        dtl_url=dtl_url,
        bid_type=bid_type,
    )


def _fetch_prebid_page(
    bid_type: BidType,
    page_no: int = 1,
    num_of_rows: int = 999,
    inqry_bgn_dt: str = "",
    inqry_end_dt: str = "",
    keyword: str = "",
) -> dict[str, Any]:
    """API 한 페이지 호출"""
    operation = _build_operation_name(bid_type)
    url = f"{BASE_URL}/{operation}"

    params = {
        "ServiceKey": _get_api_key(),
        "type": "json",
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "inqryDiv": "1",
        "inqryBgnDt": inqry_bgn_dt,
        "inqryEndDt": inqry_end_dt,
    }

    if keyword:
        params["prdctClsfcNoNm"] = keyword
        params["prcureNm"] = keyword
        params["bidNtceNm"] = keyword

    logger.debug(
        "사전규격 API 호출: %s (키워드=%s, 기간=%s~%s, page=%d)",
        operation, keyword or "전체", inqry_bgn_dt, inqry_end_dt, page_no,
    )

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_prebid_notices(
    bid_type: BidType,
    keyword: str = "",
    buffer_hours: int = 1,
    max_results: int = 999,
    inqry_bgn_dt: str | None = None,
    inqry_end_dt: str | None = None,
) -> list[PreBidNotice]:
    """사전규격 공개 목록 조회 (페이지네이션 지원)"""
    if inqry_bgn_dt and inqry_end_dt:
        bgn_dt, end_dt = inqry_bgn_dt, inqry_end_dt
    else:
        bgn_dt, end_dt = get_query_range(buffer_hours)

    all_notices: list[PreBidNotice] = []
    page_no = 1

    while True:
        data = _fetch_prebid_page(
            bid_type=bid_type,
            page_no=page_no,
            num_of_rows=min(max_results, 999),
            inqry_bgn_dt=bgn_dt,
            inqry_end_dt=end_dt,
            keyword=keyword,
        )

        resp = data.get("response", {})
        header = resp.get("header", {})
        result_code = str(header.get("resultCode", ""))

        if result_code == "00":
            logger.debug("사전규격 API 응답 수집 완료: %s", bid_type.display_name)
        else:
            raise RuntimeError(
                "사전규격 API 오류 "
                f"[{result_code}]: {header.get('resultMsg', '알 수 없음')}"
            )

        body = resp.get("body", {})
        try:
            total_count = int(body.get("totalCount", 0))
        except (ValueError, TypeError):
            total_count = 0

        items = body.get("items", [])
        if not items:
            break

        if isinstance(items, dict):
            items = [items]

        for item in items:
            notice = _parse_prebid_notice(item, bid_type)
            all_notices.append(notice)

        logger.info(
            "  → 사전규격 %d건 조회 (페이지 %d, 전체 %d건)",
            len(items), page_no, total_count,
        )

        if len(all_notices) >= total_count or len(all_notices) >= max_results:
            break

        page_no += 1
        time.sleep(0.3)

    logger.info("사전규격 조회 완료: %s %s → %d건", bid_type.display_name, keyword or "(전체)", len(all_notices))
    return all_notices
