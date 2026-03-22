"""
메시지 포맷터

텔레그램 알림 메시지를 Markdown 형식으로 구성합니다.
"""

from __future__ import annotations

from src.core.models import PreBidNotice
from src.utils.time_utils import calc_d_day, format_display_dt



def format_notice(notice: PreBidNotice, profile_name: str, matched_keyword: str = "") -> str:
    """사전규격공개 알림 메시지 포맷팅"""
    prcure_nm = _escape_html(notice.prcure_nm)
    if matched_keyword:
        prcure_nm = _highlight_keyword(prcure_nm, matched_keyword)

    d_day = calc_d_day(notice.opnn_reg_clse_dt)
    d_day_text = f" ({d_day})" if d_day else ""

    lines = [
        "📢 <b>[사전규격] 신규 공고</b>",
        "━━━━━━━━━━━━━━━━━",
        "",
        f"📋 <b>{prcure_nm}</b>",
        f"📌 유형: {notice.bid_type.display_name}",
        "",
        f"🏢 공고/수요기관: {_escape_html(notice.ntce_instt_nm)}",
        f"💰 배정예산: {notice.price_display}",
        f"📅 공개일: {format_display_dt(notice.rcpt_dt)}",
        f"📝 의견등록마감: {format_display_dt(notice.opnn_reg_clse_dt)}{d_day_text}",
        "",
        "⚠️ 사전규격 단계입니다. 추후 본 공고가 게시됩니다.",
    ]

    if notice.dtl_url:
        lines.append("")
        lines.append(f'🔗 <a href="{notice.dtl_url}">상세 URL 열기</a>')

    return "\n".join(lines)


def _highlight_keyword(text: str, keyword: str) -> str:
    """텍스트 내의 키워드에 볼드+코드 태그를 입혀 시각적 강조(음영) 효과를 줍니다."""
    if not keyword:
        return text
    
    import re
    # 대소문자 구분 없이 매칭 (HTML 이스케이프된 텍스트 기준이므로 조심)
    # 키워드 자체도 이스케이프해서 검색해야 안전함
    escaped_kw = _escape_html(keyword)
    
    # 정규표현식으로 교체 (대소문자 보존하며 태그 감싸기)
    pattern = re.compile(re.escape(escaped_kw), re.IGNORECASE)
    return pattern.sub(lambda m: f"<code><b>{m.group(0)}</b></code>", text)


def format_summary(
    profile_name: str,
    prebid_count: int,
    check_time: str,
) -> str:
    """실행 요약 메시지"""
    lines = [
        f"📊 <b>[{_escape_html(profile_name)}] 수동 조회 결과</b> ({_escape_html(check_time)})",
    ]

    if prebid_count > 0:
        lines.append(f"• 신규 사전규격: <b>{prebid_count}건</b>")

    if prebid_count == 0:
        lines.append("• 신규 사전규격 공고 없음")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
