"""Tests for secret rotation functionality."""

import pytest
from datetime import UTC, datetime, timedelta

from secretzero.rotation import (
    parse_rotation_period,
    should_rotate_secret,
    format_rotation_status,
)


class TestParseRotationPeriod:
    """Tests for parse_rotation_period function."""

    def test_parse_days(self):
        """Test parsing days format."""
        assert parse_rotation_period("30d") == timedelta(days=30)
        assert parse_rotation_period("90d") == timedelta(days=90)
        assert parse_rotation_period("1d") == timedelta(days=1)

    def test_parse_weeks(self):
        """Test parsing weeks format."""
        assert parse_rotation_period("2w") == timedelta(weeks=2)
        assert parse_rotation_period("1w") == timedelta(weeks=1)
        assert parse_rotation_period("4w") == timedelta(weeks=4)

    def test_parse_months(self):
        """Test parsing months format (approximated as 30 days)."""
        assert parse_rotation_period("3m") == timedelta(days=90)
        assert parse_rotation_period("1m") == timedelta(days=30)
        assert parse_rotation_period("6m") == timedelta(days=180)

    def test_parse_years(self):
        """Test parsing years format (approximated as 365 days)."""
        assert parse_rotation_period("1y") == timedelta(days=365)
        assert parse_rotation_period("2y") == timedelta(days=730)

    def test_case_insensitive(self):
        """Test that parsing is case insensitive."""
        assert parse_rotation_period("30D") == timedelta(days=30)
        assert parse_rotation_period("2W") == timedelta(weeks=2)
        assert parse_rotation_period("3M") == timedelta(days=90)
        assert parse_rotation_period("1Y") == timedelta(days=365)

    def test_invalid_format(self):
        """Test invalid formats return None."""
        assert parse_rotation_period("") is None
        assert parse_rotation_period("invalid") is None
        assert parse_rotation_period("30") is None
        assert parse_rotation_period("d30") is None
        assert parse_rotation_period("30x") is None
        assert parse_rotation_period(None) is None


class TestShouldRotateSecret:
    """Tests for should_rotate_secret function."""

    def test_no_rotation_period(self):
        """Test that no rotation period means no rotation."""
        should_rotate, reason = should_rotate_secret(None, None, None)
        assert should_rotate is False
        assert "No rotation period" in reason

    def test_invalid_rotation_period(self):
        """Test invalid rotation period format."""
        should_rotate, reason = should_rotate_secret("invalid", None, None)
        assert should_rotate is False
        assert "Invalid rotation period" in reason

    def test_no_rotation_history(self):
        """Test secret with no history should rotate."""
        should_rotate, reason = should_rotate_secret("90d", None, None)
        assert should_rotate is True
        assert "No rotation history" in reason

    def test_rotation_due_overdue(self):
        """Test secret that is overdue for rotation."""
        # Secret created 100 days ago, rotation period 90 days
        created_at = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        should_rotate, reason = should_rotate_secret("90d", None, created_at)
        assert should_rotate is True
        assert "overdue" in reason.lower()
        assert "10 days" in reason

    def test_rotation_due_just_overdue(self):
        """Test secret that just became overdue."""
        # Secret created exactly 91 days ago, rotation period 90 days
        created_at = (datetime.now(UTC) - timedelta(days=91)).isoformat()
        should_rotate, reason = should_rotate_secret("90d", None, created_at)
        assert should_rotate is True
        assert "overdue" in reason.lower()

    def test_rotation_not_due(self):
        """Test secret that is not due for rotation."""
        # Secret created 30 days ago, rotation period 90 days
        created_at = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        should_rotate, reason = should_rotate_secret("90d", None, created_at)
        assert should_rotate is False
        assert "due in" in reason.lower()
        # Allow for timing differences in test execution
        assert any(f"{d} days" in reason for d in range(59, 61))

    def test_rotation_uses_last_rotated(self):
        """Test that last_rotated is used over created_at when available."""
        # Created 100 days ago, but rotated 20 days ago
        created_at = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        last_rotated = (datetime.now(UTC) - timedelta(days=20)).isoformat()
        should_rotate, reason = should_rotate_secret("90d", last_rotated, created_at)
        assert should_rotate is False
        assert "due in" in reason.lower()
        # Allow for timing differences in test execution
        assert any(f"{d} days" in reason for d in range(69, 71))

    def test_rotation_just_created(self):
        """Test secret that was just created."""
        created_at = datetime.now(UTC).isoformat()
        should_rotate, reason = should_rotate_secret("90d", None, created_at)
        assert should_rotate is False
        assert "due in" in reason.lower()

    def test_rotation_invalid_timestamp(self):
        """Test handling of invalid timestamps."""
        should_rotate, reason = should_rotate_secret("90d", None, "invalid")
        assert should_rotate is True
        assert "Invalid timestamp" in reason


class TestFormatRotationStatus:
    """Tests for format_rotation_status function."""

    def test_format_overdue(self):
        """Test formatting of overdue status."""
        created_at = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        status = format_rotation_status("90d", None, created_at)
        assert "⚠️" in status
        assert "overdue" in status.lower()

    def test_format_not_due(self):
        """Test formatting of not due status."""
        created_at = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        status = format_rotation_status("90d", None, created_at)
        assert "✓" in status
        assert "due in" in status.lower()

    def test_format_no_period(self):
        """Test formatting when no rotation period."""
        status = format_rotation_status(None, None, None)
        assert "✓" in status
        assert "No rotation period" in status
