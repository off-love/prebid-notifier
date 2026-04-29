"""
Nara Market Bid Notification Service - Data Models
Defines core data structures for bid notices, pre-bid notices, and alert profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class BidType(str, Enum):
        """Bid type (Business category)"""
        SERVICE = "service"       # Service
    GOODS = "goods"           # Goods
    CONSTRUCTION = "construction" # Construction
    FOREIGN = "foreign"       # Foreign

    @property
    def api_suffix(self) -> str:
                mapping = {
                                self.SERVICE: "Servic",
                                self.GOODS: "ThngPrd",
                                self.CONSTRUCTION: "Cnstwk",
                                self.FOREIGN: "Frgn",
                }
                return mapping.get(self, "Servic")

class NoticeType(str, Enum):
        """Notice type"""
        BID = "bid"
        PREBID = "prebid"

@dataclass
class AlertProfile:
        """Alert profile information"""
        id: str
        keywords: list[str]
        exclude_keywords: list[str] = field(default_factory=list)
        min_price: int = 0
        max_price: int = 0
        target_institutes: list[str] = field(default_factory=list)
        exclude_institutes: list[str] = field(default_factory=list)
        bid_types: list[BidType] = field(default_factory=list)

@dataclass
class PreBidNotice:
        """Pre-bid notice information"""
        bf_spec_rgst_no: str
        prch_ls_nm: str
        instt_nm: str
        org_nm: str
        presmpt_prce: int
        rgst_dt: str
        op_scr_dt: str
        hmpg_addr: str
        bid_type: BidType

    @property
    def unique_key(self) -> str:
                return self.bf_spec_rgst_no

    @property
    def price_display(self) -> str:
                if self.presmpt_prce <= 0:
                                return "N/A"
                            return f"{self.presmpt_prce:,} KRW"

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
