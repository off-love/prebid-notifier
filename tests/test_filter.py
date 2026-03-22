"""
필터링 엔진 유닛 테스트
"""

import pytest

from src.core.filter import filter_notices
from src.core.models import (
    AlertProfile,
    BidType,
    DemandAgencyConfig,
    KeywordConfig,
    PreBidNotice,
    PriceRange,
)


def _make_prebid(
    name: str = "테스트 공고",
    price: int = 100_000_000,
    bid_type: BidType = BidType.SERVICE,
) -> PreBidNotice:
    """테스트용 PreBidNotice 생성"""
    return PreBidNotice(
        prcure_no="P-001",
        prcure_nm=name,
        ntce_instt_nm="공고기관",
        rcpt_dt="2026/03/11 14:00:00",
        opnn_reg_clse_dt="2026/03/18 10:00:00",
        asign_bdgt_amt=price,
        dtl_url="https://example.com",
        bid_type=bid_type,
    )


def _make_profile(**kwargs) -> AlertProfile:
    """테스트용 AlertProfile 생성"""
    defaults = {
        "name": "테스트 프로필",
        "bid_types": [BidType.SERVICE],
        "keywords": KeywordConfig(),
        "demand_agencies": DemandAgencyConfig(),
        "regions": [],
        "price_range": PriceRange(),
    }
    defaults.update(kwargs)
    return AlertProfile(**defaults)


class TestKeywordFilter:
    """키워드 필터링 테스트"""

    def test_no_keywords_passes_all(self):
        """키워드 미설정 시 모든 공고 통과"""
        profile = _make_profile()
        notices = [_make_prebid(name="지적측량 용역")]
        result = filter_notices(notices, profile)
        assert len(result) == 1

    def test_exclude_keyword(self):
        """제외 키워드 포함 시 제외"""
        profile = _make_profile(
            keywords=KeywordConfig(exclude=["취소공고"])
        )
        notices = [
            _make_prebid(name="지적측량 업무 위탁용역"),
            _make_prebid(name="지적측량 취소공고"),
        ]
        result = filter_notices(notices, profile)
        assert len(result) == 1
        assert result[0].prcure_nm == "지적측량 업무 위탁용역"

    def test_and_keywords(self):
        """AND 키워드: 모두 포함해야 통과"""
        profile = _make_profile(
            keywords=KeywordConfig(and_keywords=["지적", "측량"])
        )
        notices = [
            _make_prebid(name="지적측량 업무"),
            _make_prebid(name="지적 확정측량"),
            _make_prebid(name="건설공사"),
        ]
        result = filter_notices(notices, profile)
        assert len(result) == 2

    def test_exclude_case_insensitive(self):
        """대소문자 무관 제외"""
        profile = _make_profile(
            keywords=KeywordConfig(exclude=["CANCEL"])
        )
        notices = [_make_prebid(name="Test Cancel Notice")]
        result = filter_notices(notices, profile)
        assert len(result) == 0

    def test_or_keywords(self):
        """OR 키워드(하나라도 포함)"""
        profile = _make_profile(
            keywords=KeywordConfig(or_keywords=["지적측량", "확정측량"])
        )
        notices = [
            _make_prebid(name="지적측량 사전규격"),
            _make_prebid(name="건설공사 사전규격"),
        ]
        result = filter_notices(notices, profile)
        assert len(result) == 1
        assert "지적측량" in result[0].prcure_nm


class TestPriceFilter:
    """금액 범위 필터 테스트"""

    def test_no_price_range_passes_all(self):
        """금액 범위 미설정 시 전체 통과 (0원 포함)"""
        profile = _make_profile()
        notices = [_make_prebid(price=999_999_999)]
        result = filter_notices(notices, profile)
        assert len(result) == 1

    def test_min_price(self):
        """최소 금액 필터"""
        profile = _make_profile(
            price_range=PriceRange(min_price=50_000_000)
        )
        notices = [
            _make_prebid(price=100_000_000),  # 통과
            _make_prebid(price=10_000_000),   # 미달
            _make_prebid(price=0),            # 미정 → 통과
        ]
        result = filter_notices(notices, profile)
        assert len(result) == 2

    def test_max_price(self):
        """최대 금액 필터"""
        profile = _make_profile(
            price_range=PriceRange(max_price=200_000_000)
        )
        notices = [
            _make_prebid(price=100_000_000),  # 통과
            _make_prebid(price=500_000_000),  # 초과
        ]
        result = filter_notices(notices, profile)
        assert len(result) == 1

    def test_min_max_range(self):
        """최소~최대 범위"""
        profile = _make_profile(
            price_range=PriceRange(min_price=10_000_000, max_price=500_000_000)
        )
        notices = [
            _make_prebid(price=150_000_000),   # 범위 내
            _make_prebid(price=5_000_000),     # 미달
            _make_prebid(price=1_000_000_000), # 초과
        ]
        result = filter_notices(notices, profile)
        assert len(result) == 1

