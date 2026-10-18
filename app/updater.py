"""Check GitHub releases for a newer version. Never raises."""
import json
import urllib.request

from . import config


def _parse_version(tag):
    parts = []
    for p in str(tag).strip().lstrip("vV").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_for_update(timeout=10):
    """Return (newer_available: bool, latest_tag: str | None)."""
    try:
        req = urllib.request.Request(
            config.RELEASES_API_URL,
            headers={"User-Agent": config.APP_NAME,
                     "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latest = (data.get("tag_name") or "").strip()
        if not latest:
            return False, None
        newer = _parse_version(latest) > _parse_version(config.APP_VERSION)
        return newer, latest
    except Exception:
        return False, None
