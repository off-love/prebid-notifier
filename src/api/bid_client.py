"""
Nara Market API Client for Bid Notices.
Provides functionality to fetch bid notices from the Nara Market Open API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from src.core.models import BidNotice, BidType

logger = logging.getLogger(__name__)

class BidClient:
      """Client for Nara Market Bid Notice API"""

    BASE_URL = "http://apis.data.go.kr/1230000/BidPublicInfoService05"

    def __init__(self, api_key: str):
              self.api_key = api_key

    def fetch_notices(
              self, 
              bid_type: BidType,
              start_dt: Optional[datetime] = None,
              end_dt: Optional[datetime] = None
    ) -> list[BidNotice]:
              """Fetch bid notices for a specific bid type and date range"""

        if not start_dt:
                      start_dt = datetime.now() - timedelta(hours=1)
                  if not end_dt:
                                end_dt = datetime.now()

        suffix = bid_type.api_suffix
        url = f"{self.BASE_URL}/getBidPblancList{suffix}01"

        params = {
                      "serviceKey": self.api_key,
                      "numOfRows": 100,
                      "pageNo": 1,
                      "type": "json",
                      "inqryBgnDt": start_dt.strftime("%Y%m%d%H%M"),
                      "inqryEndDt": end_dt.strftime("%Y%m%d%H%M"),
        }

        try:
                      response = requests.get(url, params=params, timeout=15)
                      response.raise_for_status()
                      data = response.json()

            items = data.get("response", {}).get("body", {}).get("items", [])
            if not items:
                              return []

            return [self._parse_item(item, bid_type) for item in items]

except Exception as e:
            logger.error(f"Error fetching {bid_type.value} bid notices: {e}")
            return []

    def _parse_item(self, item: dict[str, Any], bid_type: BidType) -> BidNotice:
              """Parse raw API item into BidNotice model"""
              return BidNotice(
                  bid_ntce_no=item.get("bidNtceNo", ""),
                  bid_ntce_ord=item.get("bidNtceOrd", ""),
                  bid_ntce_nm=item.get("bidNtceNm", ""),
                  ntce_instt_nm=item.get("ntceInsttNm", ""),
                  dmin_instt_nm=item.get("dminInsttNm", ""),
                  bid_ntce_dt=item.get("bidNtceDt", ""),
                  bid_clse_dt=item.get("bidClseDt", ""),
                  bdgt_amt=int(item.get("bdgtAmt") or 0),
                  presmpt_prce=int(item.get("presmptPrce") or 0),
                  dtl_url=item.get("bidNtceDtlUrl", ""),
                  bid_type=bid_type,
                  ntce_kind_nm=item.get("ntceKindNm", ""),
                  ntce_instt_cd=item.get("ntceInsttCd", ""),
              )
      
