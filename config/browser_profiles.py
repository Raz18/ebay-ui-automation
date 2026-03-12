"""Browser matrix definitions for cross-browser parallel execution."""

from __future__ import annotations


BROWSER_MATRIX: list[dict[str, str | bool | None]] = [
    {
        "name": "chrome",
        "browser": "chromium",
        "channel": "chrome",
        "headless": True,
    },
    {
        "name": "msedge",
        "browser": "chromium",
        "channel": "msedge",
        "headless": True,
    },
    {
        "name": "firefox",
        "browser": "firefox",
        "channel": None,
        "headless": True,
    },
]


def get_browser_profile(name: str) -> dict[str, str | bool | None]:
    """Retrieve a browser profile by name. Raises ValueError if unknown."""
    for profile in BROWSER_MATRIX:
        if profile["name"] == name:
            return profile

    available = [p["name"] for p in BROWSER_MATRIX]
    raise ValueError(
        f"Unknown browser profile '{name}'. "
        f"Available profiles: {', '.join(str(n) for n in available)}"
    )
