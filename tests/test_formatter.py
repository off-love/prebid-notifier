from src.core.formatter import format_bid_notice, format_prebid_notice
from src.core.models import BidNotice, BidType, PreBidNotice


def test_format_bid_notice_uses_notice_type_and_keyword_heading():
    notice = BidNotice(
        bid_ntce_no="R26BK0001",
        bid_ntce_ord="000",
        bid_ntce_nm="지적측량 입찰공고",
        ntce_instt_nm="서울특별시",
        dmin_instt_nm="서울특별시",
        bid_clse_dt="2026-05-07 18:00:00",
        dtl_url="https://example.com/bid",
        bid_type=BidType.SERVICE,
    )

    message = format_bid_notice(notice, "지적측량 용역", "측량")

    assert message.splitlines()[0] == "📢 <b>[입찰공고] 측량</b>"
    assert "[지적측량 용역] 입찰공고" not in message


def test_format_prebid_notice_uses_notice_type_and_keyword_heading():
    notice = PreBidNotice(
        prcure_no="R26BD0001",
        prcure_nm="지적측량 사전규격",
        ntce_instt_nm="서울특별시",
        opnn_reg_clse_dt="2026-05-07 18:00:00",
        bid_type=BidType.SERVICE,
    )

    message = format_prebid_notice(notice, "지적측량 용역", "측량")

    assert message.splitlines()[0] == "📋 <b>[사전규격] 측량</b>"
    assert "[지적측량 용역] 사전규격" not in message


def test_format_notice_heading_falls_back_to_all_without_keyword():
    notice = BidNotice(
        bid_ntce_no="R26BK0001",
        bid_ntce_ord="000",
        bid_ntce_nm="입찰공고",
        bid_type=BidType.SERVICE,
    )

    message = format_bid_notice(notice, "지적측량 용역", "")

    assert message.splitlines()[0] == "📢 <b>[입찰공고] 전체</b>"
