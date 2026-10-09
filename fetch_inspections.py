"""USDA FGIS grain export inspections (weekly) from the free USDA AgTransport open data portal.
No key needed. Inspections show grain loaded for export (corn, soybeans, wheat by class)."""
import time
import requests
from common import save_json, num

BASE = "https://agtransport.usda.gov"
DATASET = "sruw-w49i"                       # "Grain Inspections"
START = "2011-01-01T00:00:00"
GRAINS = ("CORN", "SOY", "WHEAT")
PAGE = 50000


def get(url, params=None):
    last = None
    for i in range(3):
        try:
            r = requests.get(url, params=params, timeout=180,
                             headers={"User-Agent": "grains-dashboard/1.0", "Accept": "application/json"})
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (400, 401, 403, 404):
                break
        except (requests.RequestException, ValueError) as e:
            last = str(e)[:150]
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"AgTransport request failed: {last}")


def pick(cols, exact=(), contains=(), numeric=False):
    for f, n, t in cols:                      # exact name first
        if n.strip().lower() in exact and (not numeric or t == "number"):
            return f
    for f, n, t in cols:
        text = (f + " " + n).lower()
        if any(c in text for c in contains) and (not numeric or t == "number"):
            return f
    return None


def run():
    meta = get(f"{BASE}/api/views/{DATASET}.json")
    cols = [(c["fieldName"], c.get("name", ""), c.get("dataTypeName", "")) for c in meta["columns"]]
    print("  columns:", "; ".join(f"{f} ({n})" for f, n, t in cols))
    date_f = pick(cols, exact=("week ending date",), contains=("week ending", "week_ending"))
    grain_f = pick(cols, exact=("grain",), contains=("grain",))
    class_f = pick(cols, exact=("class",), contains=("class",))
    tons_f = pick(cols, contains=("metric ton", "metric_ton", "mt", "tons"), numeric=True)
    print(f"  using: date={date_f}, grain={grain_f}, class={class_f}, tons={tons_f}")
    if not (date_f and grain_f and tons_f):
        raise RuntimeError("Could not recognise the columns. Columns are: " +
                           ", ".join(f"{f} ({n})" for f, n, t in cols))
    sel = [date_f, grain_f] + ([class_f] if class_f else [])
    rows, offset = [], 0
    while True:
        part = get(f"{BASE}/resource/{DATASET}.json", {
            "$select": ",".join(sel) + f",sum({tons_f}) as mt",
            "$group": ",".join(sel),
            "$where": f"{date_f} >= '{START}'",
            "$order": date_f,
            "$limit": PAGE, "$offset": offset})
        rows += part
        if len(part) < PAGE:
            break
        offset += PAGE
    out = []
    for r in rows:
        g = str(r.get(grain_f, "")).upper()
        mt = num(r.get("mt"))
        d = str(r.get(date_f, ""))[:10]
        if not d or mt is None or not any(g.startswith(x) for x in GRAINS):
            continue
        out.append({"d": d, "g": g, "c": str(r.get(class_f, "")).upper() if class_f else "", "mt": round(mt)})
    if not out:
        raise RuntimeError("No inspection rows matched corn, soybeans or wheat.")
    combos = sorted({(x["g"], x["c"]) for x in out})
    print(f"  {len(out)} rows, {out[0]['d']} to {out[-1]['d']}; grain/class groups: {combos[:20]}")
    save_json("inspections", {"fields": {"date": date_f, "grain": grain_f, "class": class_f, "tons": tons_f},
                              "rows": out, "sample_raw": rows[:2]})
