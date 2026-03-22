import logging
import os
import sys
from datetime import datetime

# 프로젝트 루트를 path에 추가 (src 접근을 위해)
sys.path.append(os.getcwd())

from src.api.prebid_client import fetch_prebid_notices
from src.core.models import BidType

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("test_prebid_api")

def test_api():
    print("\n" + "="*50)
    print("사전규격공고 API 테스트 시작")
    print("="*50)

    # 1. 환경 변수 확인
    api_key = os.environ.get("G2B_API_KEY") or os.environ.get("G2B_PREBID_API_KEY")
    if not api_key:
        print("❌ 오류: G2B_API_KEY 또는 G2B_PREBID_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("참고: '.env' 파일을 소싱하거나(source .env), 환경 변수를 직접 설정해 주세요.")
        return

    print(f"✅ API 키 확인됨: {api_key[:10]}...")

    # 2. 테스트 호출 (용역, 최근 72시간)
    try:
        print("\n[테스트 1: 용역(SERVICE) - 전체 조회]")
        notices = fetch_prebid_notices(BidType.SERVICE, buffer_hours=72, max_results=5000)
        print(f"결과: {len(notices)}건 조회됨")
        
        if notices:
            print(f"\n최근 1건 상세 정보:")
            n = notices[0]
            print(f"- 등록번호: {n.prcure_no}")
            print(f"- 공고명: {n.prcure_nm}")
            print(f"- 수요기관: {n.ntce_instt_nm}")
            print(f"- 등록일시: {n.rcpt_dt}")
            print(f"- 상세 URL: {n.dtl_url}")
        else:
            print("데이터가 없습니다. (기간 내 공고 없음)")

        # 3. 키워드 검색 테스트
        print("\n[테스트 2: 용역(SERVICE) - '용역' 키워드 조회]")
        keyword_notices = fetch_prebid_notices(BidType.SERVICE, keyword="용역", buffer_hours=72)
        print(f"결과: {len(keyword_notices)}건 조회됨")

    except Exception as e:
        print(f"❌ API 호출 중 예외 발생: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*50)
    print("테스트 종료")
    print("="*50)

if __name__ == "__main__":
    test_api()
