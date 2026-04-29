"""
Main Execution Script
"""

from __future__ import annotations
import logging
import os
import sys
from typing import Any

from src.api.prebid_client import fetch_prebid_notices
from src.api.bid_client import fetch_bid_notices
from src.core.filter import filter_notices
from src.core.formatter import (
    format_notice,
    format_bid_notice,
    format_summary,
)
from src.core.models import AlertProfile, BroadcastResult
from src.storage.profile_manager import load_profiles
from src.storage.state_manager import (
    load_state,
    save_state,
    is_already_sent,
    mark_as_sent,
)
from src.utils.bot import send_message

logger = logging.getLogger(__name__)


async def process_profile(profile: AlertProfile) -> BroadcastResult:
        """Process a single profile: fetch, filter, and send notifications"""
        logger.info(f"Processing profile: {profile.name}")

    # 1. Fetch notices (Pre-bid & Bid)
        prebid_notices = await fetch_prebid_notices(profile)
        bid_notices = await fetch_bid_notices(profile)

    all_notices = prebid_notices + bid_notices
    logger.info(f"Fetched {len(prebid_notices)} pre-bid and {len(bid_notices)} bid notices")



    # 2. Filter notices
    filtered_notices = filter_notices(all_notices, profile)
    logger.info(f"Filtered to {len(filtered_notices)} relevant notices")

    # 3. Load state to avoid duplicates
    state = load_state(profile.name)

    new_notices = []
    for notice in filtered_notices:
                if not is_already_sent(state, notice.unique_key):
                                new_notices.append(notice)

    if not new_notices:
                logger.info("No new notices to send")
                return BroadcastResult(profile_name=profile.name, count=0)

    # 4. Send notifications
    sent_count = 0
    from src.core.models import PreBidNotice, BidNotice
    for notice in new_notices:
                # Determine formatting based on notice type
                if isinstance(notice, PreBidNotice):
                                content = format_notice(notice)
else:
                content = format_bid_notice(notice)

        success = await send_message(profile.telegram_chat_id, content)
        if success:
                        mark_as_sent(state, notice.unique_key)
                        sent_count += 1



    # 5. Save state
    save_state(profile.name, state)

    # 6. Send summary if needed
    if sent_count > 0:
                summary = format_summary(sent_count, profile.name)
                await send_message(profile.telegram_chat_id, summary)

    return BroadcastResult(profile_name=profile.name, count=sent_count)


async def run():
        """Main entry point"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    profiles = load_profiles()
    if not profiles:
                logger.error("No profiles found")
                return

    results = []
    for profile in profiles:
                try:
                                result = await process_profile(profile)
                                results.append(result)
except Exception as e:
            logger.error(f"Error processing profile {profile.name}: {e}", exc_info=True)

    logger.info(f"Completed processing {len(profiles)} profiles")
    for r in results:
                logger.info(f"Profile {r.profile_name}: {r.count} messages sent")


if __name__ == "__main__":
        import asyncio
        asyncio.run(run())
    
