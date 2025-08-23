import requests

REPO = "Azrea-Shade/Azreas-Daily-Companion-Tracker"

def check_latest_release(timeout=6):
    """
    Returns dict like {"tag": "...", "name": "...", "published_at": "..."} or None.
    Network errors are swallowed by callers.
    """
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/releases/latest", timeout=timeout)
        if r.status_code == 200:
            j = r.json()
            return {
                "tag": j.get("tag_name"),
                "name": j.get("name"),
                "published_at": j.get("published_at"),
            }
    except Exception:
        pass
    return None
