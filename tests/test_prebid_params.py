import logging
import os
import sys
import requests
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.append(os.getcwd())

from src.api.prebid_client import _get_api_key, _build_operation_name, BASE_URL
from src.core.models import BidType
from src.utils.time_utils import get_query_range

import pytest

# 로깅 설정
logging.basicConfig(level=logging.INFO)

@pytest.mark.skip(reason="실제 API 호출이 필요한 수동 테스트입니다.")
def test_api_params():
    api_key = _get_api_key()
    operation = _build_operation_name(BidType.SERVICE)
    url = f"{BASE_URL}/{operation}"
    bgn_dt, end_dt = get_query_range(72)

    def call_api(param_name, keyword):
        params = {
            "ServiceKey": api_key,
            "type": "json",
            "pageNo": "1",
            "numOfRows": "10",
            "inqryDiv": "1",
            "inqryBgnDt": bgn_dt,
            "inqryEndDt": end_dt,
            param_name: keyword
        }
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        total_count = data.get("response", {}).get("body", {}).get("totalCount", 0)
        return total_count

    print(f"\n[테스트: {operation}]")
    print(f"기간: {bgn_dt} ~ {end_dt}")
    
    # 1. prctClsfcNoNm (현재 코드 사용 중)
    count1 = call_api("prctClsfcNoNm", "용역")
    print(f"1. prctClsfcNoNm=용역 -> totalCount: {count1}")

    # 2. bidNtceNm (일반적인 제목 파라미터)
    count2 = call_api("bidNtceNm", "용역")
    print(f"2. bidNtceNm=용역 -> totalCount: {count2}")

    # 3. prcureNm (사전규격명 파라미터)
    count3 = call_api("prcureNm", "용역")
    print(f"3. prcureNm=용역 -> totalCount: {count3}")

    # 4. bfSpecNm (사전규격명 - 표준)
    count4 = call_api("bfSpecNm", "용역")
    print(f"4. bfSpecNm=용역 -> totalCount: {count4}")

    # 5. 전체 조회 (파라미터 없음)
    count5 = call_api("dummy", "용역")
    print(f"5. 파라미터 없음 -> totalCount: {count5}")

if __name__ == "__main__":
    test_api_params()
