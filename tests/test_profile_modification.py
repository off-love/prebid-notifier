"""
프로필 수정 기능 테스트
"""

import os
from pathlib import Path
import yaml
import pytest
from src.storage.profile_manager import (
    get_profile_keywords,
    add_profile_keyword,
    remove_profile_keyword
)

@pytest.fixture
def temp_profile_file(tmp_path):
    """테스트용 임시 profiles.yaml 생성"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "profiles.yaml"
    
    data = {
        "profiles": [
            {
                "name": "테스트 프로필",
                "enabled": True,
                "keywords": {
                    "or": ["키워드1", "키워드2"],
                    "and": [],
                    "exclude": []
                }
            }
        ],
        "settings": {
            "timezone": "Asia/Seoul"
        }
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
        
    # 환경변수 설정하여 profile_manager가 이 파일을 보게 함
    os.environ["PROFILES_PATH"] = str(config_path)
    yield config_path
    if "PROFILES_PATH" in os.environ:
        del os.environ["PROFILES_PATH"]

def test_get_profile_keywords(temp_profile_file):
    keywords = get_profile_keywords("테스트 프로필")
    assert keywords == ["키워드1", "키워드2"]
    
    # 존재하지 않는 프로필
    assert get_profile_keywords("없는 프로필") == []

def test_add_profile_keyword(temp_profile_file):
    # 신규 추가
    assert add_profile_keyword("테스트 프로필", "키워드3") is True
    assert "키워드3" in get_profile_keywords("테스트 프로필")
    
    # 중복 추가
    assert add_profile_keyword("테스트 프로필", "키워드1") is False
    assert get_profile_keywords("테스트 프로필").count("키워드1") == 1

def test_remove_profile_keyword(temp_profile_file):
    # 삭제
    assert remove_profile_keyword("테스트 프로필", "키워드1") is True
    assert "키워드1" not in get_profile_keywords("테스트 프로필")
    
    # 없는 키워드 삭제
    assert remove_profile_keyword("테스트 프로필", "없는키워드") is False
