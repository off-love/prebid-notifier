"""
나라장터 입찰 알림 서비스 — 메인 실행 스크립트

GitHub Actions에서 주기적으로 실행되어:
1. 프로필 설정을 로드
2. 프로필별 사전규격/입찰공고를 API에서 조회
3. 키워드/조건 필터링
4. 중복 확인 (state.json)
5. 신규 공고를 텔레그램으로 발송
6. 상태 저장
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import sys

from src.api.prebid_client import fetch_prebid_notices
from src.api.bid_client import fetch_bid_notices
from src.core.filter import filter_notices
from src.core.formatter import format_prebid_notice, format_bid_notice, format_summary
from src.core.models import PreBidNotice, BidNotice
from src.storage.profile_manager import load_profiles
from src.storage.state_manager import (
    load_state,
    save_state,
    is_notified,
    mark_notified,
    update_last_check,
    cleanup_old_records,
)
from src.storage.subscriber_manager import load_subscribers
from src.telegram_bot import send_message, broadcast_message
from src.utils.time_utils import get_incremental_query_range, now_kst

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

QUERY_OVERLAP_MINUTES = 15


@dataclass
class ProfileProcessResult:
    """프로필 처리 결과"""

    prebid_count: int = 0
    bid_count: int = 0
    had_failures: bool = False


def _dedupe_notices(notices):
    """unique_key 기준으로 조회 결과 중복을 제거합니다."""
    seen = set()
    unique = []
    for notice in notices:
        if notice.unique_key in seen:
            continue
        seen.add(notice.unique_key)
        unique.append(notice)
    return unique


def _collect_subscribers() -> set[str]:
    """기존 prebid 구독자 파일을 통합 알림 수신자 목록으로 사용합니다."""
    subscribers = load_subscribers(mode="prebid")
    default_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if default_chat_id:
        subscribers.add(default_chat_id)
    return subscribers


def _send_to_subscribers(message: str, subscribers: set[str]) -> tuple[bool, bool]:
    """알림을 전송하고 (성공 여부, 일부 실패 여부)를 반환합니다."""
    if len(subscribers) == 1:
        success = send_message(message, chat_id=next(iter(subscribers)), mode="prebid")
        return success, not success

    result = broadcast_message(message, subscribers, mode="prebid")
    return result.success_count > 0, result.fail_count > 0


def process_profile(profile, settings, state, query_begin: str, query_end: str) -> ProfileProcessResult:
    """단일 프로필에 대해 사전규격 + 입찰공고를 조회하고 알림을 발송합니다."""
    result = ProfileProcessResult()

    logger.info("=" * 50)
    logger.info("프로필 처리: %s (업종: %s)",
                profile.name,
                ", ".join(bt.display_name for bt in profile.bid_types))
    logger.info("=" * 50)

    all_prebid_notices = []
    all_bid_notices = []
    or_keywords = profile.keywords.include_or

    # 키워드가 없으면 전체 조회
    keywords_to_search = or_keywords if or_keywords else [""]

    for bid_type in profile.bid_types:
        for keyword in keywords_to_search:
            # ── 사전규격 조회 ──
            try:
                prebid_notices = fetch_prebid_notices(
                    bid_type=bid_type,
                    keyword=keyword,
                    buffer_hours=settings.query_buffer_hours,
                    max_results=settings.max_results_per_page,
                    inqry_bgn_dt=query_begin,
                    inqry_end_dt=query_end,
                )
                all_prebid_notices.extend(prebid_notices)
            except Exception as e:
                logger.error("사전규격 조회 실패 (%s/%s): %s", bid_type.display_name, keyword, e)
                result.had_failures = True

            # ── 입찰공고 조회 ──
            try:
                bid_notices = fetch_bid_notices(
                    bid_type=bid_type,
                    keyword=keyword,
                    buffer_hours=settings.query_buffer_hours,
                    max_results=settings.max_results_per_page,
                    inqry_bgn_dt=query_begin,
                    inqry_end_dt=query_end,
                )
                all_bid_notices.extend(bid_notices)
            except Exception as e:
                logger.error("입찰공고 조회 실패 (%s/%s): %s", bid_type.display_name, keyword, e)
                result.had_failures = True

    # 중복 제거 (같은 공고번호가 여러 키워드에 의해 조회될 수 있음)
    unique_prebid = _dedupe_notices(all_prebid_notices)
    unique_bid = _dedupe_notices(all_bid_notices)

    logger.info("조회 결과: 사전규격 %d건, 입찰공고 %d건 (중복 제거 후)",
                len(unique_prebid), len(unique_bid))

    # ── 프로필 조건 필터링 ──
    filtered_prebid = filter_notices(unique_prebid, profile)
    filtered_bid = filter_notices(unique_bid, profile)

    logger.info("필터링 결과: 사전규격 %d건, 입찰공고 %d건",
                len(filtered_prebid), len(filtered_bid))

    # ── 중복 확인 (이미 알림 보낸 공고 제외) ──
    new_prebid = []
    for notice in filtered_prebid:
        if not is_notified(state, notice.unique_key, "prebid"):
            new_prebid.append(notice)

    new_bid = []
    for notice in filtered_bid:
        if not is_notified(state, notice.unique_key, "bid"):
            new_bid.append(notice)

    logger.info("신규 공고: 사전규격 %d건, 입찰공고 %d건", len(new_prebid), len(new_bid))

    subscribers = _collect_subscribers()

    if not subscribers:
        logger.warning("구독자가 없습니다. 알림을 건너뜁니다.")
        return result

    # 사전규격 알림 발송
    for notice in new_prebid:
        matched_kw = getattr(notice, "matched_keyword", "")
        msg = format_prebid_notice(notice, profile.name, matched_kw)
        success, partial_failure = _send_to_subscribers(msg, subscribers)

        if success:
            mark_notified(state, notice.unique_key, profile.name, "prebid")
            result.prebid_count += 1
        if partial_failure:
            result.had_failures = True

    # 입찰공고 알림 발송
    for notice in new_bid:
        matched_kw = getattr(notice, "matched_keyword", "")
        msg = format_bid_notice(notice, profile.name, matched_kw)
        success, partial_failure = _send_to_subscribers(msg, subscribers)

        if success:
            mark_notified(state, notice.unique_key, profile.name, "bid")
            result.bid_count += 1
        if partial_failure:
            result.had_failures = True

    # ── 결과 요약 발송 ──
    check_time = now_kst().strftime("%m/%d %H:%M")
    summary = format_summary(profile.name, result.prebid_count, result.bid_count, check_time)
    summary_ok, summary_failure = _send_to_subscribers(summary, subscribers)
    if not summary_ok or summary_failure:
        result.had_failures = True

    return result


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("나라장터 입찰 알림 서비스 시작")
    logger.info("=" * 60)

    # 필수 환경변수 확인
    required_vars = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        logger.error("필수 환경변수 누락: %s", ", ".join(missing))
        sys.exit(1)

    # API 키 확인
    has_prebid_key = bool(os.environ.get("G2B_PREBID_API_KEY") or os.environ.get("G2B_API_KEY"))
    has_bid_key = bool(os.environ.get("G2B_API_KEY") or os.environ.get("G2B_BID_API_KEY"))

    if not has_prebid_key and not has_bid_key:
        logger.error("G2B_PREBID_API_KEY, G2B_API_KEY 또는 G2B_BID_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    logger.info("API 키 상태: 사전규격=%s, 입찰공고=%s",
                "✅" if has_prebid_key else "❌",
                "✅" if has_bid_key else "❌")

    # 프로필 로드
    try:
        profiles, settings = load_profiles()
    except Exception as e:
        logger.error("프로필 로드 실패: %s", e)
        sys.exit(1)

    if not profiles:
        logger.warning("활성 프로필이 없습니다.")
        return

    logger.info("활성 프로필 %d개 로드", len(profiles))

    # 상태 로드
    state = load_state()

    # 오래된 기록 정리
    cleanup_old_records(state)

    query_begin, query_end = get_incremental_query_range(
        state.get("last_check", ""),
        buffer_hours=settings.query_buffer_hours,
        overlap_minutes=QUERY_OVERLAP_MINUTES,
    )
    logger.info("조회 범위: %s ~ %s", query_begin, query_end)

    # 프로필별 처리
    total_prebid = 0
    total_bid = 0
    had_failures = False

    for profile in profiles:
        try:
            profile_result = process_profile(profile, settings, state, query_begin, query_end)
            total_prebid += profile_result.prebid_count
            total_bid += profile_result.bid_count
            had_failures = had_failures or profile_result.had_failures
        except Exception as e:
            logger.error("프로필 '%s' 처리 중 오류: %s", profile.name, e, exc_info=True)
            had_failures = True

    if not had_failures:
        update_last_check(state)
    else:
        logger.warning("실패가 있어 last_check를 갱신하지 않습니다. 다음 실행에서 재시도합니다.")
    save_state(state)

    logger.info("=" * 60)
    logger.info("실행 완료: 사전규격 %d건, 입찰공고 %d건 알림 발송", total_prebid, total_bid)
    logger.info("=" * 60)

    if had_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
