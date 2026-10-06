"""Shared helpers for all data scripts."""
import os, json, time, pathlib, datetime
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)


def load_env():
    """Read the local .env file (only used when testing on your own computer)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need_key(name):
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(
            f"Missing {name}. Add it as a GitHub Secret (or in your local .env file)."
        )
    return v


def get_json(url, params=None, tries=4, timeout=120):
    """GET a URL and return JSON. Retries on temporary errors."""
    last = None
    for i in range(tries):
        try:
            r = requests.get(
                url, params=params, timeout=timeout,
                headers={"User-Agent": "grains-dashboard/1.0"},
            )
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code in (400, 401, 403, 404):
                break  # trying again will not help
        except (requests.RequestException, ValueError) as e:
            last = str(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"Request failed for {url}: {last}")


def save_json(name, obj):
    payload = {
        "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "data": obj,
    }
    path = DATA / f"{name}.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"  saved {path.name} ({path.stat().st_size // 1024} KB)")


def num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
