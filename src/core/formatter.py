"""
메시지 포맷터

텔레그램 알림 메시지를 HTML 형식으로 구성합니다.
"""

from __future__ import annotations

from src.core.models import PreBidNotice
from src.utils.time_utils import calc_d_day, format_display_dt


def format_notice(notice: PreBidNotice, profile_name: str, matched_keyword: str = "") -> str:
    """사전규격 알림 메시지 포맷팅"""
    d_day = calc_d_day(notice.opnn_reg_clse_dt)
    d_day_text = f" ({d_day})" if d_day else ""

    prcure_name = _escape_html(notice.prcure_nm)
    if matched_keyword:
        prcure_name = _highlight_keyword(prcure_name, matched_keyword)

    lines = [
        "🔔 <b>나라장터 신규 사전규격</b>",
        "━━━━━━━━━━━━━━━━━",
        "",
        f"📋 <b>{prcure_name}</b>",
        f"📌 유형: {notice.bid_type.display_name}",
    ]

    if notice.prcure_div:
        lines[-1] += f" | 조달구분: {_escape_html(notice.prcure_div)}"

    lines.append("")
    lines.append(f"🏢 공고기관: {_escape_html(notice.ntce_instt_nm)}")

    if notice.rgst_instt_nm:
        lines.append(f"🏗️ 등록기관: {_escape_html(notice.rgst_instt_nm)}")

    lines.append(f"💰 배정예산: {notice.price_display}")

    if notice.prcure_way:
        lines.append(f"💼 조달방식: {_escape_html(notice.prcure_way)}")

    lines.append("")
    lines.append(f"📅 접수일: {format_display_dt(notice.rcpt_dt)}")
    lines.append(f"⏰ 의견등록마감: {format_display_dt(notice.opnn_reg_clse_dt)}{d_day_text}")

    if notice.dtl_url:
        lines.append("")
        lines.append(f'🔗 <a href="{notice.dtl_url}">상세보기</a>')

    return "\n".join(lines)


def _highlight_keyword(text: str, keyword: str) -> str:
    """텍스트 내의 키워드에 볼드+코드 태그를 입혀 시각적 강조(음영) 효과를 줍니다."""
    if not keyword:
        return text

    import re
    escaped_kw = _escape_html(keyword)
    pattern = re.compile(re.escape(escaped_kw), re.IGNORECASE)
    return pattern.sub(lambda m: f"<code><b>{m.group(0)}</b></code>", text)


def format_share_message(notice: PreBidNotice) -> str:
    """공유용 텍스트 포맷 (강조 없이 깔끔하게)"""
    d_day = calc_d_day(notice.opnn_reg_clse_dt)
    d_day_text = f" ({d_day})" if d_day else ""

    lines = [
        "━━━━━━━━━━━━━━━━━",
        "📋 나라장터 사전규격 공유",
        "",
        f"공고명: {notice.prcure_nm}",
        f"공고기관: {notice.ntce_instt_nm}",
    ]

    if notice.rgst_instt_nm:
        lines.append(f"등록기관: {notice.rgst_instt_nm}")

    lines.append(f"배정예산: {notice.price_display}")
    lines.append(f"마감일: {format_display_dt(notice.opnn_reg_clse_dt)}{d_day_text}")

    if notice.dtl_url:
        lines.append(f"상세: {notice.dtl_url}")

    lines.append("━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_summary(
    profile_name: str,
    prebid_count: int,
    check_time: str,
) -> str:
    """실행 요약 메시지"""
    lines = [
        f"📊 <b>[{_escape_html(profile_name)}] 조회 결과</b> ({_escape_html(check_time)})",
    ]

    if prebid_count > 0:
        lines.append(f"• 신규 사전규격: <b>{prebid_count}건</b>")
    else:
        lines.append("• 신규 공고 없음")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
