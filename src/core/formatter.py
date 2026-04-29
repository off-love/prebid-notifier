"""
메시지 포매터

텔레그램 발송용 HTML 메시지를 생성합니다.
"""

from __future__ import annotations

from src.core.models import PreBidNotice, BidNotice
from src.utils.time_utils import calc_d_day, format_display_dt


def format_prebid_notice(notice: PreBidNotice, profile_name: str, matched_keyword: str = "") -> str:
    """사전규격 공고 텔레그램 메시지 포맷"""
    d_day = calc_d_day(notice.opnn_reg_clse_dt)
    d_day_text = f" ({d_day})" if d_day else ""

    title = _escape_html(notice.prcure_nm)
    if matched_keyword:
        title = title.replace(
            _escape_html(matched_keyword),
            f"<u>{_escape_html(matched_keyword)}</u>",
        )

    lines = [
        f"📋 <b>[{_escape_html(profile_name)}] 사전규격</b>",
        f"📌 <b>{title}</b>",
        f"🏢 {_escape_html(notice.ntce_instt_nm)}",
    ]

    if notice.rgst_instt_nm:
        lines.append(f"📍 {_escape_html(notice.rgst_instt_nm)}")

    lines.append(f"💰 {notice.price_display}")
    lines.append(f"⏰ 마감: {format_display_dt(notice.opnn_reg_clse_dt)}{d_day_text}")

    if notice.dtl_url:
        lines.append(f"🔗 <a href='{notice.dtl_url}'>상세보기</a>")

    lines.append("━" * 20)
    return "\n".join(lines)


def format_bid_notice(notice: BidNotice, profile_name: str, matched_keyword: str = "") -> str:
    """입찰공고 텔레그램 메시지 포맷"""
    title = _escape_html(notice.bid_ntce_nm)
    if matched_keyword:
        title = title.replace(
            _escape_html(matched_keyword),
            f"<u>{_escape_html(matched_keyword)}</u>",
        )

    d_day = calc_d_day(notice.bid_clse_dt)
    d_day_text = f" ({d_day})" if d_day else ""

    lines = [
        f"📢 <b>[{_escape_html(profile_name)}] 입찰공고</b>",
        f"📌 <b>{title}</b>",
        f"🏢 {_escape_html(notice.ntce_instt_nm)}",
        f"📍 {_escape_html(notice.dmin_instt_nm)}",
        f"📝 {_escape_html(notice.ntce_kind_nm)}",
        f"💰 {notice.price_display}",
        f"⏰ 마감: {format_display_dt(notice.bid_clse_dt)}{d_day_text}",
        f"🔗 <a href='{notice.dtl_url}'>상세보기</a>",
        "━" * 20,
    ]

    return "\n".join(lines)


def format_summary(
    profile_name: str,
    prebid_count: int,
    bid_count: int,
    check_time: str,
) -> str:
    """실행 결과 요약 메시지"""
    lines = [
        f"📊 <b>[{_escape_html(profile_name)}] 체크 결과</b> ({_escape_html(check_time)})",
    ]

    if prebid_count > 0 or bid_count > 0:
        if prebid_count > 0:
            lines.append(f"  • 사전규격: <b>{prebid_count}건</b> 신규")
        if bid_count > 0:
            lines.append(f"  • 입찰공고: <b>{bid_count}건</b> 신규")
    else:
        lines.append("  • 신규 공고 없음")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프"""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
