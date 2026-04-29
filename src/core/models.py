"""
나라장터 입찰공고 알림 서비스 - 데이터 모델

입찰공고, 사전규격, 알림 프로필 등 핵심 데이터 구조를 정의합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class BidType(str, Enum):
    """입찰 유형 (업종)"""
    SERVICE = "service"           # 용역
    GOODS = "goods"               # 물품
    CONSTRUCTION = "construction" # 공사
    FOREIGN = "foreign"           # 외자

    @property
    def api_suffix(self) -> str:
        """입찰공고정보서비스 API 오퍼레이션 접미사"""
        mapping = {
            BidType.SERVICE: "Servc",
            BidType.GOODS: "Thng",
            BidType.CONSTRUCTION: "Cnstwk",
            BidType.FOREIGN: "Frgcpt",
        }
        return mapping[self]

    @property
    def display_name(self) -> str:
        """한글 표시명"""
        mapping = {
            BidType.SERVICE: "용역",
            BidType.GOODS: "물품",
            BidType.CONSTRUCTION: "공사",
            BidType.FOREIGN: "외자",
        }
        return mapping[self]


class NoticeType(str, Enum):
    """공고 종류"""
    BID = "bid"          # 입찰공고
    PREBID = "prebid"    # 사전규격공개


@dataclass
class PreBidNotice:
    """사전규격공개 정보"""
    prcure_no: str                # 사전규격등록번호
    prcure_nm: str                # 사전규격명
    ntce_instt_nm: str            # 공고기관명 (수요기관)
    rcpt_dt: str                  # 공개일(등록일시)
    opnn_reg_clse_dt: str         # 의견등록마감일
    asign_bdgt_amt: int           # 배정예산액
    dtl_url: str                  # 상세 URL
    bid_type: BidType             # 입찰 유형
    prcure_div: str = ""          # 조달구분
    rgst_instt_nm: str = ""       # 등록기관명
    prcure_way: str = ""          # 조달방식

    @property
    def unique_key(self) -> str:
        """중복 판별용 고유 키"""
        return f"{self.prcure_no}"

    @property
    def price_display(self) -> str:
        """가격 표시 포맷 (예: 150,000,000원)"""
        if self.asign_bdgt_amt <= 0:
            return "미정"
        return f"{self.asign_bdgt_amt:,}원"





@dataclass
class KeywordConfig:
    """키워드 검색 설정"""
    or_keywords: list[str] = field(default_factory=list)   # OR 조건
    and_keywords: list[str] = field(default_factory=list)   # AND 조건
    exclude: list[str] = field(default_factory=list)        # 제외 키워드


@dataclass
class DemandAgencyConfig:
    """수요기관 필터 설정"""
    by_code: list[str] = field(default_factory=list)  # 기관코드 (API 레벨)
    by_name: list[str] = field(default_factory=list)  # 기관명 (코드 레벨)


@dataclass
class PriceRange:
    """금액 범위"""
    min_price: int = 0  # 0이면 하한 없음
    max_price: int = 0  # 0이면 상한 없음

    def contains(self, price: int) -> bool:
        """가격이 범위 내에 있는지 판별"""
        if price <= 0:
            # 추정가격이 없는 경우 필터 통과
            return True
        if self.min_price > 0 and price < self.min_price:
            return False
        if self.max_price > 0 and price > self.max_price:
            return False
        return True


@dataclass
class AlertProfile:
    """알림 프로필"""
    name: str                                          # 프로필 이름
    enabled: bool = True                               # 활성 여부
    bid_types: list[BidType] = field(default_factory=list)
    keywords: KeywordConfig = field(default_factory=KeywordConfig)
    demand_agencies: DemandAgencyConfig = field(default_factory=DemandAgencyConfig)
    regions: list[str] = field(default_factory=list)
    price_range: PriceRange = field(default_factory=PriceRange)


@dataclass
class GlobalSettings:
    """전역 설정"""
    check_interval_minutes: int = 30
    query_buffer_hours: int = 1
    max_results_per_page: int = 999
    timezone: str = "Asia/Seoul"


@dataclass
class BookmarkItem:
    """북마크 항목"""
    bid_no: str                   # 사전규격번호
    name: str                     # 사전규격명
    org: str                      # 공고(수요)기관명
    close_date: str               # 마감일시
    url: str                      # 상세 URL
    saved_at: str                 # 저장 시각
    profile: str                  # 매칭된 프로필명
    demand_org: str = ""          # 수요기관명
    price: int = 0                # 배정예산액
    notice_type: str = "prebid"   # prebid
    notes: str = ""               # 사용자 메모


@dataclass
class BroadcastResult:
    """브로드캐스트 발송 결과 리포트"""
    total: int = 0                                          # 전체 대상 수
    success_count: int = 0                                  # 발송 성공 수
    fail_count: int = 0                                     # 발송 실패 수
    blocked_ids: list[str] = field(default_factory=list)     # 차단/탈퇴 사용자
    error_ids: list[str] = field(default_factory=list)       # 기타 오류 사용자
    rate_limited_count: int = 0                             # Rate Limit 재시도 횟수
    elapsed_seconds: float = 0.0                            # 발송 소요 시간(초)

    @property
    def blocked_count(self) -> int:
        return len(self.blocked_ids)

    @property
    def error_count(self) -> int:
        return len(self.error_ids)

    @property
    def invalid_ids(self) -> list[str]:
        """차단 + 오류를 합친 전체 유효하지 않은 ID 목록"""
        return self.blocked_ids + self.error_ids

    def merge(self, other: "BroadcastResult") -> None:
        """다른 BroadcastResult를 현재 결과에 병합"""
        self.success_count += other.success_count
        self.fail_count += other.fail_count
        self.blocked_ids.extend(other.blocked_ids)
        self.error_ids.extend(other.error_ids)
        self.rate_limited_count += other.rate_limited_count
        self.elapsed_seconds += other.elapsed_seconds


@dataclass
class NotifiedRecord:
    """알림 이력 기록"""
    notified_at: str              # 알림 발송 시각
    profile: str                  # 프로필명
    notice_type: str = "prebid"   # prebid


@dataclass
class BidNotice:
        """Bid notice information"""
        bid_ntce_no: str
        bid_ntce_ord: str
        bid_ntce_nm: str
        ntce_instt_nm: str
        dmin_instt_nm: str
        bid_ntce_dt: str
        bid_clse_dt: str
        bdgt_amt: int
        presmpt_prce: int
        dtl_url: str
        bid_type: BidType
        ntce_kind_nm: str = ""
        ntce_instt_cd: str = ""

    @property
    def unique_key(self) -> str:
                return f"{self.bid_ntce_no}-{self.bid_ntce_ord}"

    @property
    def price_display(self) -> str:
                if self.presmpt_prce <= 0:
                                return "N/A"
                            return f"{self.presmpt_prce:,} KRW"

            return "N/A"
        return f"{self.presmpt_prce:,} KRW"
