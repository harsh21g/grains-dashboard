"""USDA NASS QuickStats: crop condition, crop progress, and yearly production/yield/area."""
from collections import defaultdict
from common import get_json, save_json, need_key, num
 
URL = "https://quickstats.nass.usda.gov/api/api_GET/"
FIRST_YEAR = 2011
LAST_YEAR = 2030
CROPS = ["CORN", "SOYBEANS", "WHEAT"]
 
 
def query(key, **kw):
    """Ask NASS for rows, 5 years at a time (NASS limits one answer to 50,000 rows)."""
    rows = []
    for y0 in range(FIRST_YEAR, LAST_YEAR + 1, 5):
        params = {
            "key": key, "format": "JSON",
            "source_desc": "SURVEY", "agg_level_desc": "NATIONAL",
            "year__GE": y0, "year__LE": y0 + 4,
        }
        params.update(kw)
        try:
            j = get_json(URL, params)
        except RuntimeError as e:
            # NASS answers HTTP 400 when there is no data for the filter (for example future years)
            if "HTTP 400" in str(e):
                continue
            raise
        rows += j.get("data", [])
    return rows
 
 
def group(rows, weekly):
    g = defaultdict(list)
    seen = set()
    for r in rows:
        v = num(r.get("Value"))
        if v is None:
            continue
        sd = r.get("short_desc", "")
        if any(w in sd for w in ("IRRIGATED", "ORGANIC")):
            continue
        item = {"y": int(r["year"]), "v": v}
        if weekly:
            item["d"] = r.get("week_ending")
        key = (sd, item["y"], item.get("d"))
        if key in seen:      # NASS repeats identical rows; keep one
            continue
        seen.add(key)
        g[sd].append(item)
    for sd in g:
        g[sd].sort(key=lambda x: (x.get("d") or "", x["y"]))
    return dict(g)
 
 
def run():
    key = need_key("NASS_API_KEY")
    weekly, annual = {}, {}
    for crop in CROPS:
        for cat in ("CONDITION", "PROGRESS"):
            rows = query(key, commodity_desc=crop, statisticcat_desc=cat, freq_desc="WEEKLY")
            g = group(rows, True)
            print(f"  {crop} {cat}: {len(rows)} rows, {len(g)} series")
            weekly.update(g)
        for cat in ("PRODUCTION", "YIELD", "AREA HARVESTED", "AREA PLANTED"):
            rows = query(key, commodity_desc=crop, statisticcat_desc=cat,
                         freq_desc="ANNUAL", reference_period_desc="YEAR", domain_desc="TOTAL")
            g = group(rows, False)
            print(f"  {crop} {cat}: {len(rows)} rows, {len(g)} series")
            annual.update(g)
    if not weekly:
        raise RuntimeError("NASS returned no weekly data. Check NASS_API_KEY.")
    save_json("nass_weekly", weekly)
    save_json("nass_annual", annual)
 
