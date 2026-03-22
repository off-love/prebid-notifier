"""
포맷터 유닛 테스트
"""

from src.core.formatter import format_notice, format_summary
from src.core.models import BidType, PreBidNotice


def test_prebid_format():
    """사전규격 알림 메시지 포맷 테스트"""
    notice = PreBidNotice(
        prcure_no="PS001",
        prcure_nm="지적측량 사전규격",
        ntce_instt_nm="한국국토정보공사",
        rcpt_dt="2026/03/11 00:00:00",
        opnn_reg_clse_dt="2026/03/18 00:00:00",
        asign_bdgt_amt=150_000_000,
        dtl_url="https://example.com",
        bid_type=BidType.SERVICE,
    )
    result = format_notice(notice, "지적측량 용역", matched_keyword="측량")

    assert "사전규격" in result
    assert "지적<code><b>측량</b></code> 사전규격" in result
    assert "한국국토정보공사" in result


def test_summary_format():
    """요약 메시지 포맷 테스트"""
    result = format_summary("지적측량 용역", 3, "14:30")
    assert "3건" in result
    assert "지적측량 용역" in result


def test_summary_no_results():
    """결과 없을 때 요약"""
    result = format_summary("테스트", 0, "14:30")
    assert "신규 사전규격 공고 없음" in result
    assert "테스트" in result


def test_html_escape():
    """HTML 특수문자 이스케이프"""
    notice = PreBidNotice(
        prcure_no="T001",
        prcure_nm="<script>alert('xss')</script>",
        ntce_instt_nm="기관&회사",
        rcpt_dt="",
        opnn_reg_clse_dt="",
        asign_bdgt_amt=0,
        dtl_url="",
        bid_type=BidType.SERVICE,
    )
    result = format_notice(notice, "테스트")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert "&amp;회사" in result
