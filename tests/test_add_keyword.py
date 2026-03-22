import os
import sys
import yaml
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.append(os.getcwd())

from src.storage.profile_manager import add_profile_keyword, load_profiles

def test_add_keyword():
    print("--- 키워드 추가 테스트 ---")
    
    # 1. 초기 상태 확인
    profiles, _ = load_profiles()
    if not profiles:
        print("프로필이 없습니다.")
        return
    
    profile_name = profiles[0].name
    print(f"대상 프로필: {profile_name}")
    print(f"현재 키워드(OR): {profiles[0].keywords.or_keywords}")

    # 2. 키워드 추가
    test_keyword = "테스트용역"
    print(f"\n키워드 추가 시도: {test_keyword}")
    success = add_profile_keyword(profile_name, test_keyword)
    print(f"추가 결과: {success}")

    # 3. 파일 내용 직접 확인
    config_path = Path("config/profiles.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f)
    
    updated_or = content["profiles"][0]["keywords"]["or"]
    print(f"파일 내 업데이트된 키워드(OR): {updated_or}")

    if test_keyword in updated_or:
        print("✅ 성공: 파일에 정상적으로 기록되었습니다.")
    else:
        print("❌ 실패: 파일에 기록되지 않았습니다.")

    # 4. 복구 (삭제)
    from src.storage.profile_manager import remove_profile_keyword
    remove_profile_keyword(profile_name, test_keyword)
    print("\n테스트 키워드 삭제 완료.")

if __name__ == "__main__":
    test_add_keyword()
