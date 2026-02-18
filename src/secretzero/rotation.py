"""Secret rotation utilities and logic."""

import re
from datetime import UTC, datetime, timedelta


def parse_rotation_period(period: str) -> timedelta | None:
    """Parse a rotation period string into a timedelta.

    Supported formats:
    - Nd (N days, e.g., "90d", "30d")
    - Nw (N weeks, e.g., "2w")
    - Nm (N months, approximated as 30 days, e.g., "3m")
    - Ny (N years, approximated as 365 days, e.g., "1y")

    Args:
        period: Rotation period string

    Returns:
        timedelta object or None if invalid format
    """
    if not period:
        return None

    # Match pattern: number followed by unit (d, w, m, y)
    match = re.match(r"^(\d+)([dwmy])$", period.lower())
    if not match:
        return None

    value, unit = match.groups()
    value = int(value)

    if unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    elif unit == "m":
        # Approximate month as 30 days
        return timedelta(days=value * 30)
    elif unit == "y":
        # Approximate year as 365 days
        return timedelta(days=value * 365)

    return None


def should_rotate_secret(
    rotation_period: str | None,
    last_rotated: str | None,
    created_at: str | None,
) -> tuple[bool, str]:
    """Check if a secret should be rotated.

    Args:
        rotation_period: Rotation period string (e.g., "90d")
        last_rotated: ISO timestamp of last rotation, None if never rotated
        created_at: ISO timestamp of secret creation

    Returns:
        Tuple of (should_rotate, reason)
    """
    # No rotation period means no rotation needed
    if not rotation_period:
        return False, "No rotation period configured"

    # Parse rotation period
    period = parse_rotation_period(rotation_period)
    if not period:
        return False, f"Invalid rotation period format: {rotation_period}"

    # Determine reference timestamp (last_rotated or created_at)
    reference_time_str = last_rotated or created_at
    if not reference_time_str:
        return True, "No rotation history found"

    try:
        reference_time = datetime.fromisoformat(reference_time_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return True, "Invalid timestamp in lockfile"

    # Calculate when rotation is due
    rotation_due = reference_time + period
    now = datetime.now(UTC)

    if now >= rotation_due:
        days_overdue = (now - rotation_due).days
        return True, f"Rotation overdue by {days_overdue} days"

    days_remaining = (rotation_due - now).days
    return False, f"Rotation due in {days_remaining} days"


def format_rotation_status(
    rotation_period: str | None,
    last_rotated: str | None,
    created_at: str | None,
) -> str:
    """Format a human-readable rotation status.

    Args:
        rotation_period: Rotation period string (e.g., "90d")
        last_rotated: ISO timestamp of last rotation
        created_at: ISO timestamp of secret creation

    Returns:
        Formatted status string
    """
    should_rotate, reason = should_rotate_secret(rotation_period, last_rotated, created_at)

    if should_rotate:
        return f"⚠️  {reason}"

    return f"✓ {reason}"
