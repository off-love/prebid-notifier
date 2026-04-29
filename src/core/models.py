"""
나라장터 입찰 알림 서비스 — 데이터 모델

핵심 데이터 구조를 정의합니다:
- BidType: 업종 구분 (용역/물품/공사/외자)
- AlertProfile: 알림 프로필 (키워드, 업종, 필터 등)
- PreBidNotice: 사전규격 공고 정보
- BidNotice: 입찰 공고 정보
- BroadcastResult: 알림 발송 결과
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BidType(str, Enum):
    """업종 구분"""
    SERVICE = "service"
    GOODS = "goods"
    CONSTRUCTION = "construction"
    FOREIGN = "foreign"

    @property
    def display_name(self) -> str:
        mapping = {
            self.SERVICE: "용역",
            self.GOODS: "물품",
            self.CONSTRUCTION: "공사",
            self.FOREIGN: "외자",
        }
        return mapping.get(self, self.value)

    @property
    def api_suffix(self) -> str:
        """입찰공고 API suffix"""
        mapping = {
            self.SERVICE: "Servc",
            self.GOODS: "Thng",
            self.CONSTRUCTION: "Cnstwk",
            self.FOREIGN: "Frgcpt",
        }
        return mapping.get(self, "Servc")


class NoticeType(str, Enum):
    """공고 유형"""
    BID = "bid"
    PREBID = "prebid"


# ── 프로필 관련 설정 객체 ────────────────────────────

@dataclass
class KeywordConfig:
    """키워드 검색 설정"""
    or_keywords: list[str] = field(default_factory=list)
    and_keywords: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    @property
    def include_or(self) -> list[str]:
        return self.or_keywords

    @property
    def include_and(self) -> list[str]:
        return self.and_keywords


@dataclass
class DemandAgencyConfig:
    """수요기관 필터 설정"""
    by_code: list[str] = field(default_factory=list)
    by_name: list[str] = field(default_factory=list)


@dataclass
class PriceRange:
    """금액 범위 필터"""
    min_price: int = 0
    max_price: int = 0

    @property
    def min_amount(self) -> int:
        return self.min_price

    @property
    def max_amount(self) -> int:
        return self.max_price


@dataclass
class GlobalSettings:
    """전역 실행 설정"""
    check_interval_minutes: int = 30
    query_buffer_hours: int = 1
    max_results_per_page: int = 999
    timezone: str = "Asia/Seoul"


@dataclass
class AlertProfile:
    """알림 프로필"""
    name: str = ""
    enabled: bool = True
    bid_types: list[BidType] = field(default_factory=list)
    keywords: KeywordConfig = field(default_factory=KeywordConfig)
    demand_agencies: DemandAgencyConfig = field(default_factory=DemandAgencyConfig)
    regions: list[str] = field(default_factory=list)
    price_range: PriceRange = field(default_factory=PriceRange)
    telegram_chat_id: str = ""

    @property
    def budget_range(self) -> PriceRange | None:
        """예산 범위가 설정되어 있으면 반환, 아니면 None"""
        if self.price_range.min_price == 0 and self.price_range.max_price == 0:
            return None
        return self.price_range


# ── 공고 데이터 ─────────────────────────────────────

@dataclass
class PreBidNotice:
    """사전규격 공고 정보"""
    prcure_no: str = ""
    prcure_nm: str = ""
    ntce_instt_nm: str = ""
    rcpt_dt: str = ""
    opnn_reg_clse_dt: str = ""
    asign_bdgt_amt: int = 0
    dtl_url: str = ""
    bid_type: BidType = BidType.SERVICE
    rgst_instt_nm: str = ""

    @property
    def unique_key(self) -> str:
        return self.prcure_no

    @property
    def price_display(self) -> str:
        if self.asign_bdgt_amt <= 0:
            return "N/A"
        return f"{self.asign_bdgt_amt:,}원"

    @property
    def presmpt_prce(self) -> int:
        """하위 호환용 — filter.py에서 가격 비교 시 사용"""
        return self.asign_bdgt_amt


@dataclass
class BidNotice:
    """입찰 공고 정보"""
    bid_ntce_no: str = ""
    bid_ntce_ord: str = ""
    bid_ntce_nm: str = ""
    ntce_instt_nm: str = ""
    dmin_instt_nm: str = ""
    bid_ntce_dt: str = ""
    bid_clse_dt: str = ""
    bdgt_amt: int = 0
    presmpt_prce: int = 0
    dtl_url: str = ""
    bid_type: BidType = BidType.SERVICE
    ntce_kind_nm: str = ""
    ntce_instt_cd: str = ""

    @property
    def unique_key(self) -> str:
        return f"{self.bid_ntce_no}-{self.bid_ntce_ord}"

    @property
    def price_display(self) -> str:
        if self.presmpt_prce <= 0:
            return "N/A"
        return f"{self.presmpt_prce:,}원"


# ── 실행 결과 ────────────────────────────────────────

@dataclass
class NotifiedRecord:
    """알림 발송 기록"""
    notified_at: str = ""
    profile: str = ""
    notice_type: str = ""


@dataclass
class BroadcastResult:
    """브로드캐스트 발송 결과"""
    total: int = 0
    success_count: int = 0
    fail_count: int = 0
    blocked_ids: list[str] = field(default_factory=list)
    error_ids: list[str] = field(default_factory=list)
    rate_limited_count: int = 0
    elapsed_seconds: float = 0.0
    profile_name: str = ""
    count: int = 0

    @property
    def invalid_ids(self) -> list[str]:
        return self.blocked_ids + self.error_ids

    def merge(self, other: BroadcastResult) -> None:
        self.success_count += other.success_count
        self.fail_count += other.fail_count
        self.blocked_ids.extend(other.blocked_ids)
        self.error_ids.extend(other.error_ids)
        self.rate_limited_count += other.rate_limited_count
        self.elapsed_seconds += other.elapsed_seconds
