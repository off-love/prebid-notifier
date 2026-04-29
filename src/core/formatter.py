"""
Message Formatter
"""

from __future__ import annotations
from src.core.models import PreBidNotice, BidNotice
from src.utils.time_utils import calc_d_day, format_display_dt

def format_notice(notice: PreBidNotice, profile_name: str, matched_keyword: str = "") -> str:
        """Pre-bid notice formatting"""
        d_day = calc_d_day(notice.opnn_reg_clse_dt)
        d_day_text = f" ({d_day})" if d_day else ""

    prcure_name = _escape_html(notice.prcure_nm)
    if matched_keyword:
                prcure_name = prcure_name.replace(
                                _escape_html(matched_keyword),
                                f"<u>{_escape_html(matched_keyword)}</u>"
                )

    lines = [
                f"<b>[{_escape_html(profile_name)}] New Pre-Bid</b>",
                f"Title: <b>{prcure_name}</b>",
                f"Agency: {_escape_html(notice.ntce_instt_nm)}",
    ]

    if notice.rgst_instt_nm:
                lines.append(f"Client: {_escape_html(notice.rgst_instt_nm)}")

    lines.append(f"Budget: {notice.price_display}")
    lines.append(f"Deadline: {format_display_dt(notice.opnn_reg_clse_dt)}{d_day_text}")

    if notice.dtl_url:
                lines.append(f"Detail: {notice.dtl_url}")

    lines.append("-" * 20)
    return "\n".join(lines)


def format_bid_notice(notice: BidNotice, profile_name: str, matched_keyword: str = "") -> str:
        """Bid notice formatting"""
        lines = [
            f"<b>[{_escape_html(profile_name)}] New Bid</b>",
            f"Title: <b>{_escape_html(notice.bid_ntce_nm)}</b>"
        ]

    if matched_keyword:
                lines[1] = lines[1].replace(
                                _escape_html(matched_keyword), 
                                f"<u>{_escape_html(matched_keyword)}</u>"
                )

    lines.extend([
                f"Agency: {_escape_html(notice.ntce_instt_nm)}",
                f"Client: {_escape_html(notice.dmin_instt_nm)}",
                f"Type: {_escape_html(notice.ntce_kind_nm)}",
                f"Budget: {notice.price_display}",
                f"Deadline: {format_display_dt(notice.bid_clse_dt)}",
                f"Detail: {notice.dtl_url}",
                "-" * 20
    ])

    return "\n".join(lines)


def format_summary(
        profile_name: str, 
        prebid_count: int, 
        bid_count: int,
        check_time: str,
) -> str:
        """Execution summary"""
        lines = [
            f"<b>[{_escape_html(profile_name)}] Result</b> ({_escape_html(check_time)})",
        ]

    if prebid_count > 0 or bid_count > 0:
                if prebid_count > 0:
                                lines.append(f" - Pre-Bid: <b>{prebid_count}</b>")
                            if bid_count > 0:
                                            lines.append(f" - Bid: <b>{bid_count}</b>")
else:
        lines.append(" - No new notices")

    return "\n".join(lines)

def _escape_html(text: str) -> str:
        """Escape HTML special characters"""
    if not text:
                return ""
    return (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;")
    )
