"""
관리자 권한 관리자 유닛 테스트
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# admins.json 경로를 임시 파일로 교체하기 위한 픽스처
@pytest.fixture(autouse=True)
def temp_admins_file(tmp_path, monkeypatch):
    """admins.json 경로를 임시 디렉터리로 변경합니다."""
    import src.storage.admin_manager as am
    fake_path = tmp_path / "config" / "admins.json"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(am, "_ADMINS_PATH", fake_path)
    return fake_path


@pytest.fixture
def super_admin_env(monkeypatch):
    """SUPER_ADMIN_CHAT_ID 환경변수를 설정합니다."""
    monkeypatch.setenv("SUPER_ADMIN_CHAT_ID", "99999")
    return "99999"


class TestIsAdminAndSuperAdmin:
    """is_admin / is_super_admin 테스트"""

    def test_super_admin_is_recognized(self, super_admin_env):
        from src.storage.admin_manager import is_super_admin
        assert is_super_admin("99999") is True

    def test_non_super_admin_is_rejected(self, super_admin_env):
        from src.storage.admin_manager import is_super_admin
        assert is_super_admin("11111") is False

    def test_super_admin_env_not_set(self, monkeypatch):
        from src.storage.admin_manager import is_super_admin
        monkeypatch.delenv("SUPER_ADMIN_CHAT_ID", raising=False)
        assert is_super_admin("99999") is False

    def test_super_admin_is_also_admin(self, super_admin_env):
        from src.storage.admin_manager import is_admin
        assert is_admin("99999") is True

    def test_regular_admin_is_recognized_after_add(self, super_admin_env):
        from src.storage.admin_manager import add_admin, is_admin
        add_admin("11111")
        assert is_admin("11111") is True

    def test_unknown_user_is_not_admin(self, super_admin_env):
        from src.storage.admin_manager import is_admin
        assert is_admin("00000") is False


class TestAddAdmin:
    """add_admin 테스트"""

    def test_add_new_admin(self):
        from src.storage.admin_manager import add_admin, load_admins
        result = add_admin("12345")
        assert result is True
        assert "12345" in load_admins()

    def test_add_duplicate_admin(self):
        from src.storage.admin_manager import add_admin
        add_admin("12345")
        result = add_admin("12345")  # 중복 추가
        assert result is False

    def test_add_multiple_admins(self):
        from src.storage.admin_manager import add_admin, load_admins
        add_admin("11111")
        add_admin("22222")
        add_admin("33333")
        admins = load_admins()
        assert admins == {"11111", "22222", "33333"}


class TestRemoveAdmin:
    """remove_admin 테스트"""

    def test_remove_existing_admin(self):
        from src.storage.admin_manager import add_admin, load_admins, remove_admin
        add_admin("12345")
        result = remove_admin("12345")
        assert result is True
        assert "12345" not in load_admins()

    def test_remove_nonexistent_admin(self):
        from src.storage.admin_manager import remove_admin
        result = remove_admin("99998")
        assert result is False

    def test_super_admin_cannot_be_removed(self, super_admin_env):
        from src.storage.admin_manager import remove_admin
        result = remove_admin("99999")  # 슈퍼 관리자
        assert result is False


class TestLoadSaveAdmins:
    """admins.json 저장/로드 일관성 테스트"""

    def test_load_from_empty_file_returns_empty_set(self):
        from src.storage.admin_manager import load_admins
        admins = load_admins()
        assert isinstance(admins, set)
        assert len(admins) == 0

    def test_load_nonexistent_file_returns_empty_set(self, tmp_path, monkeypatch):
        import src.storage.admin_manager as am
        monkeypatch.setattr(am, "_ADMINS_PATH", tmp_path / "no_such.json")
        from src.storage.admin_manager import load_admins
        assert load_admins() == set()

    def test_save_and_load_roundtrip(self):
        from src.storage.admin_manager import load_admins, save_admins
        original = {"111", "222", "333"}
        save_admins(original)
        loaded = load_admins()
        assert loaded == original


class TestGetAllAdmins:
    """get_all_admins 테스트"""

    def test_super_admin_first(self, super_admin_env):
        from src.storage.admin_manager import add_admin, get_all_admins
        add_admin("11111")
        all_admins = get_all_admins()
        assert all_admins[0] == "99999"  # 슈퍼 관리자가 맨 앞
        assert "11111" in all_admins

    def test_no_super_admin_env(self, monkeypatch):
        from src.storage.admin_manager import add_admin, get_all_admins
        monkeypatch.delenv("SUPER_ADMIN_CHAT_ID", raising=False)
        add_admin("11111")
        all_admins = get_all_admins()
        assert all_admins == ["11111"]
