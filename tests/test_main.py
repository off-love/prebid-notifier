import pytest

from src import main as main_module
from src.core.models import (
    AlertProfile,
    BidNotice,
    BidType,
    GlobalSettings,
    KeywordConfig,
    PreBidNotice,
)
from src.storage.state_manager import is_notified


def _profile() -> AlertProfile:
    return AlertProfile(
        name="지적측량 용역",
        bid_types=[BidType.SERVICE],
        keywords=KeywordConfig(or_keywords=["측량"], exclude=["취소공고"]),
    )


def _settings() -> GlobalSettings:
    return GlobalSettings(query_buffer_hours=1, max_results_per_page=999)


def _prebid_notice() -> PreBidNotice:
    return PreBidNotice(
        prcure_no="R26BD0001",
        prcure_nm="지적측량 사전규격",
        ntce_instt_nm="서울특별시",
        rcpt_dt="2026-04-30 10:00:00",
        opnn_reg_clse_dt="2026-05-07 18:00:00",
        asign_bdgt_amt=100_000_000,
        dtl_url="https://example.com/prebid",
        bid_type=BidType.SERVICE,
    )


def _bid_notice() -> BidNotice:
    return BidNotice(
        bid_ntce_no="R26BK0001",
        bid_ntce_ord="000",
        bid_ntce_nm="지적측량 입찰공고",
        ntce_instt_nm="서울특별시",
        dmin_instt_nm="서울특별시",
        bid_ntce_dt="2026-04-30 10:00:00",
        bid_clse_dt="2026-05-07 18:00:00",
        presmpt_prce=100_000_000,
        dtl_url="https://example.com/bid",
        bid_type=BidType.SERVICE,
    )


def test_process_profile_sends_prebid_and_bid(monkeypatch):
    state = {"notified_bids": {}, "notified_prebids": {}}
    captured = {"prebid": [], "bid": [], "messages": []}

    def fake_fetch_prebid(**kwargs):
        captured["prebid"].append(kwargs)
        return [_prebid_notice()]

    def fake_fetch_bid(**kwargs):
        captured["bid"].append(kwargs)
        return [_bid_notice()]

    def fake_send(message, **kwargs):
        captured["messages"].append(message)
        return True

    monkeypatch.setattr(main_module, "fetch_prebid_notices", fake_fetch_prebid)
    monkeypatch.setattr(main_module, "fetch_bid_notices", fake_fetch_bid)
    monkeypatch.setattr(main_module, "load_subscribers", lambda mode="prebid": {"1001"})
    monkeypatch.setattr(main_module, "send_message", fake_send)

    result = main_module.process_profile(
        _profile(),
        _settings(),
        state,
        "202604301000",
        "202604301100",
    )

    assert result.prebid_count == 1
    assert result.bid_count == 1
    assert result.had_failures is False
    assert captured["prebid"][0]["inqry_bgn_dt"] == "202604301000"
    assert captured["bid"][0]["inqry_end_dt"] == "202604301100"
    assert any("사전규격" in msg for msg in captured["messages"])
    assert any("입찰공고" in msg for msg in captured["messages"])
    assert is_notified(state, "R26BD0001", "prebid") is True
    assert is_notified(state, "R26BK0001-000", "bid") is True


def test_process_profile_does_not_mark_failed_delivery(monkeypatch):
    state = {"notified_bids": {}, "notified_prebids": {}}

    monkeypatch.setattr(main_module, "fetch_prebid_notices", lambda **kwargs: [])
    monkeypatch.setattr(main_module, "fetch_bid_notices", lambda **kwargs: [_bid_notice()])
    monkeypatch.setattr(main_module, "load_subscribers", lambda mode="prebid": {"1001"})
    monkeypatch.setattr(main_module, "send_message", lambda *args, **kwargs: False)

    result = main_module.process_profile(
        _profile(),
        _settings(),
        state,
        "202604301000",
        "202604301100",
    )

    assert result.bid_count == 0
    assert result.had_failures is True
    assert is_notified(state, "R26BK0001-000", "bid") is False


def test_main_keeps_last_check_when_profile_failed(monkeypatch):
    profile = _profile()
    settings = _settings()
    state = {
        "last_check": "2026-04-30T10:00:00+09:00",
        "notified_bids": {},
        "notified_prebids": {},
    }
    update_called = False
    save_called = False

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1001")
    monkeypatch.setenv("G2B_API_KEY", "api-key")
    monkeypatch.setattr(main_module, "load_profiles", lambda: ([profile], settings))
    monkeypatch.setattr(main_module, "load_state", lambda: state)
    monkeypatch.setattr(main_module, "cleanup_old_records", lambda current_state: 0)
    monkeypatch.setattr(
        main_module,
        "process_profile",
        lambda *args, **kwargs: main_module.ProfileProcessResult(had_failures=True),
    )

    def fake_update_last_check(current_state):
        nonlocal update_called
        update_called = True
        current_state["last_check"] = "SHOULD_NOT_CHANGE"

    def fake_save_state(current_state):
        nonlocal save_called
        save_called = True

    monkeypatch.setattr(main_module, "update_last_check", fake_update_last_check)
    monkeypatch.setattr(main_module, "save_state", fake_save_state)

    with pytest.raises(SystemExit):
        main_module.main()

    assert update_called is False
    assert save_called is True
    assert state["last_check"] == "2026-04-30T10:00:00+09:00"
