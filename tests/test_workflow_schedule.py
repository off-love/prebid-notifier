from pathlib import Path


WORKFLOW = Path(".github/workflows/check_notices.yml")


def test_workflow_avoids_bidtalk_minutes_and_peak_minutes():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "*/30" not in content
    assert "cron: '7 " not in content
    assert "cron: '37 " not in content
    assert "cron: '11 " in content
    assert "cron: '41 " in content


def test_workflow_disables_prebid_on_41_minute_runs():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert '[[ "$schedule" == 41\\ * ]]' in content
    assert "RUN_PREBID=0" in content
    assert "RUN_PREBID=1" in content
