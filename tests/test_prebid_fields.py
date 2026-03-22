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

# 로깅 설정
logging.basicConfig(level=logging.INFO)

def inspect_api_response():
    api_key = _get_api_key()
    operation = _build_operation_name(BidType.SERVICE)
    url = f"{BASE_URL}/{operation}"
    bgn_dt, end_dt = get_query_range(72)

    params = {
        "ServiceKey": api_key,
        "type": "json",
        "pageNo": "1",
        "numOfRows": "5",
        "inqryDiv": "1",
        "inqryBgnDt": bgn_dt,
        "inqryEndDt": end_dt,
    }

    print(f"URL: {url}")
    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    
    items = data.get("response", {}).get("body", {}).get("items", [])
    if not items:
        print("데이터가 없습니다.")
        return

    if isinstance(items, dict):
        items = [items]

    print(f"\n--- 데이터 필드 분석 (첫 번째 항목) ---")
    item = items[0]
    for k, v in item.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    inspect_api_response()
