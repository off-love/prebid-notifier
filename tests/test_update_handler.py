from pathlib import Path

from src import update_handler
from src.storage import admin_manager
from src.storage.profile_manager import get_profile_keywords


def _write_profiles(path: Path) -> None:
    path.write_text(
        """
profiles:
- name: 지적측량 용역
  enabled: true
  bid_types:
  - service
  keywords:
    or:
    - 지적측량
    and: []
    exclude:
    - 취소공고
  demand_agencies:
    by_code: []
    by_name: []
  regions: []
  price_range:
    min: 0
    max: 0
settings:
  check_interval_minutes: 30
  query_buffer_hours: 1
  max_results_per_page: 999
  timezone: Asia/Seoul
""".lstrip(),
        encoding="utf-8",
    )


def _capture_replies(monkeypatch) -> list[str]:
    replies: list[str] = []
    monkeypatch.setattr(
        update_handler,
        "_send_reply",
        lambda chat_id, text: replies.append(text) or True,
    )
    return replies


def test_admin_can_add_and_remove_keyword(monkeypatch, tmp_path):
    profiles_path = tmp_path / "profiles.yaml"
    _write_profiles(profiles_path)
    replies = _capture_replies(monkeypatch)

    monkeypatch.setenv("PROFILES_PATH", str(profiles_path))
    monkeypatch.setenv("SUPER_ADMIN_CHAT_ID", "100")

    update_handler._handle_command("100", "/addkeyword 드론측량")
    assert "드론측량" in get_profile_keywords("지적측량 용역")
    assert "키워드 추가 완료" in replies[-1]

    update_handler._handle_command("100", "/delkeyword 드론측량")
    assert "드론측량" not in get_profile_keywords("지적측량 용역")
    assert "키워드 삭제 완료" in replies[-1]


def test_non_admin_cannot_add_keyword(monkeypatch, tmp_path):
    profiles_path = tmp_path / "profiles.yaml"
    _write_profiles(profiles_path)
    replies = _capture_replies(monkeypatch)

    monkeypatch.setenv("PROFILES_PATH", str(profiles_path))
    monkeypatch.setenv("SUPER_ADMIN_CHAT_ID", "100")

    update_handler._handle_command("200", "/addkeyword 드론측량")

    assert "드론측량" not in get_profile_keywords("지적측량 용역")
    assert "관리자 전용" in replies[-1]


def test_super_admin_can_add_and_remove_admin(monkeypatch, tmp_path):
    replies = _capture_replies(monkeypatch)
    monkeypatch.setenv("SUPER_ADMIN_CHAT_ID", "100")
    monkeypatch.setattr(admin_manager, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(admin_manager, "_ADMIN_FILE", tmp_path / "admins.json")

    update_handler._handle_command("100", "/addadmin 200")
    assert admin_manager.is_admin("200") is True
    assert "관리자 추가 완료" in replies[-1]

    update_handler._handle_command("100", "/deladmin 200")
    assert admin_manager.is_admin("200") is False
    assert "관리자 삭제 완료" in replies[-1]


def test_admin_report_uses_existing_state(monkeypatch):
    replies = _capture_replies(monkeypatch)
    monkeypatch.setenv("SUPER_ADMIN_CHAT_ID", "100")
    monkeypatch.setattr(update_handler, "get_subscriber_count", lambda mode="prebid": 4)
    monkeypatch.setattr(update_handler, "get_profile_keywords", lambda profile_name: ["측량", "드론"])
    monkeypatch.setattr(
        update_handler,
        "load_state",
        lambda: {
            "last_check": "2026-04-30T10:00:00+09:00",
            "notified_bids": {"B1": {}},
            "notified_prebids": {"P1": {}, "P2": {}},
            "telegram_offset_prebid": 123,
        },
    )

    update_handler._handle_command("100", "/report")

    assert "운영 리포트" in replies[-1]
    assert "구독자 수: <b>4</b>" in replies[-1]
    assert "키워드 수: <b>2</b>" in replies[-1]
