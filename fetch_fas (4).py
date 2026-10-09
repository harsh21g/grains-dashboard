"""USDA FAS Open Data: weekly US export sales (ESR) plus a list of the PSD codes.
Needs a free API key from the FAS portal (api.data.gov), saved as FAS_API_KEY."""
import re, time, datetime
import requests
from common import DATA, save_json, need_key, num
import json

BASE = "https://apps.fas.usda.gov/OpenData"
FIRST_MY = 2011

# names to look for in the ESR commodity list (the script prints what it found)
TARGETS = {
    "ZS": ["SOYBEANS"],
    "ZM": ["SOYBEAN CAKE AND MEAL", "SOYBEAN MEAL", "SOYBEAN CAKE"],
    "ZL": ["SOYBEAN OIL"],
    "ZC": ["CORN"],
    "ZW": ["WHEAT - SRW", "WHEAT SRW", "SRW"],
    "KW": ["WHEAT - HRW", "WHEAT HRW", "HRW"],
}
SUM_FIELDS = ["weeklyexports", "accumulatedexports", "outstandingsales", "grossnewsales",
              "currentmynetsales", "currentmytotalcommitment", "nextmyoutstandingsales", "nextmynetsales"]


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
# four ways of sending the key; the first one that works is used for everything
VARIANTS = [
    ("header API_KEY", lambda k: ({"API_KEY": k}, {})),
    ("header X-Api-Key", lambda k: ({"X-Api-Key": k}, {})),
    ("query api_key", lambda k: ({}, {"api_key": k})),
    ("query API_KEY", lambda k: ({}, {"API_KEY": k})),
]
AUTH = {"build": None}


def probe(key):
    """Try each way of sending the key on one small request and print what USDA answers."""
    for name, build in VARIANTS:
        headers, params = build(key)
        headers = dict(headers, **{"Accept": "application/json", "User-Agent": UA})
        try:
            r = requests.get(BASE + "/api/esr/commodities", headers=headers, params=params, timeout=60)
        except requests.RequestException as e:
            print(f"  probe {name}: network error {str(e)[:100]}")
            continue
        info = {h: r.headers.get(h) for h in ("Server", "Via", "X-RateLimit-Remaining", "Content-Type") if r.headers.get(h)}
        print(f"  probe {name}: HTTP {r.status_code} {info} body={r.text[:70]!r}")
        if r.status_code == 200:
            AUTH["build"] = build
            return name
    return None


def api(path, key):
    build = AUTH["build"] or VARIANTS[0][1]
    headers, params = build(key)
    headers = dict(headers, **{"Accept": "application/json", "User-Agent": UA})
    last = None
    for i in range(3):
        try:
            r = requests.get(BASE + path, params=params, headers=headers, timeout=180)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code in (400, 401, 403, 404, 500):
                break
        except (requests.RequestException, ValueError) as e:
            last = str(e)
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"FAS request failed for {path}: {last}")


def nk(k):
    return re.sub(r"[^a-z]", "", str(k).lower())


def norm(row):
    return {nk(k): v for k, v in row.items()}


def find(row, *needles):
    """first field whose normalised name contains one of the needles"""
    for k, v in norm(row).items():
        if any(n in k for n in needles):
            return v
    return None


def pick_commodity(coms, words):
    rows = [(str(find(c, "commodityname", "name") or "").upper().strip(), find(c, "commoditycode", "code"), c) for c in coms]
    for w in words:                      # exact match first
        for name, code, c in rows:
            if name == w:
                return name, code
    for w in words:                      # then "contains"
        for name, code, c in rows:
            if w in name:
                return name, code
    return None, None


def aggregate(rows, total_codes):
    """one row per week: use the 'total' row if the API has one, otherwise add up all countries"""
    weeks = {}
    for r in rows:
        n = norm(r)
        d = str(n.get("weekendingdate", ""))[:10]
        if not d:
            continue
        weeks.setdefault(d, []).append(n)
    out = []
    for d, rs in sorted(weeks.items()):
        use = [x for x in rs if str(x.get("countrycode")) in total_codes] or rs
        rec = {"d": d, "my": use[0].get("marketyear")}
        for f in SUM_FIELDS:
            vals = [num(x.get(f)) for x in use if num(x.get(f)) is not None]
            if vals:
                rec[f] = sum(vals)
        rec["n"] = len(use)
        out.append(rec)
    return out


def run():
    key = need_key("FAS_API_KEY")
    key = "".join(key.split())          # remove any spaces or line breaks from pasting
    print(f"  FAS key length: {len(key)} characters (the key itself is never printed)")
    meta, sample = {}, None
    how = probe(key)
    print(f"  working way to send the key: {how}")
    for name, path in [("esr_commodities", "/api/esr/commodities"), ("esr_countries", "/api/esr/countries"),
                       ("esr_units", "/api/esr/unitsOfMeasure"),
                       ("psd_commodities", "/api/psd/commodities"), ("psd_countries", "/api/psd/countries"),
                       ("psd_attributes", "/api/psd/commodityAttributes"), ("psd_units", "/api/psd/unitsOfMeasure")]:
        try:
            meta[name] = api(path, key)
            print(f"  {name}: {len(meta[name])} items")
        except Exception as e:           # PSD lists are only for the next step, so do not stop here
            meta[name] = f"error: {e}"
            print(f"  {name}: {e}")
    if not isinstance(meta["esr_commodities"], list):
        raise RuntimeError("Could not read the ESR commodity list. The FAS API answers HTTP 500 when the key "
                           "is wrong or not active. Check FAS_API_KEY.")
    (DATA / "fas_meta.json").write_text(json.dumps(meta, separators=(",", ":")))

    total_codes = set()
    if isinstance(meta["esr_countries"], list):
        for c in meta["esr_countries"]:
            nm = str(find(c, "countryname", "name") or "").upper()
            if nm in ("TOTAL", "WORLD", "ALL COUNTRIES", "GRAND TOTAL"):
                total_codes.add(str(find(c, "countrycode", "code")))

    path = DATA / "export_sales.json"
    old = {}
    if path.exists():
        try:
            old = json.loads(path.read_text())["data"]
        except Exception:
            old = {}

    out, today = {}, datetime.date.today()
    for sym, words in TARGETS.items():
        cname, code = pick_commodity(meta["esr_commodities"], words)
        if code is None:
            print(f"  {sym}: no ESR commodity found for {words}")
            continue
        print(f"  {sym}: using ESR commodity '{cname}' (code {code})")
        have = {}                         # keep old years, refresh the last two
        for r in (old.get(sym, {}).get("rows") or []):
            have.setdefault(str(r.get("my")), []).append(r)
        first = FIRST_MY if not have else today.year - 1
        years = range(first, today.year + 2)
        rows_by_my = dict(have)
        for my in years:
            try:
                raw = api(f"/api/esr/exports/commodityCode/{code}/allCountries/marketYear/{my}", key)
            except Exception as e:
                print(f"    {my}: {str(e)[:120]}")
                continue
            if not raw:
                continue
            if sample is None:
                sample = raw[0]
            agg = aggregate(raw, total_codes)
            if agg:
                rows_by_my[str(my)] = agg
            time.sleep(0.3)
        rows = [r for my in sorted(rows_by_my) for r in rows_by_my[my]]
        rows.sort(key=lambda r: r["d"])
        print(f"    {len(rows)} weekly rows, {rows[0]['d'] if rows else '-'} to {rows[-1]['d'] if rows else '-'}")
        out[sym] = {"commodity": cname, "code": code, "rows": rows}
    if not any(v["rows"] for v in out.values()):
        raise RuntimeError("No export sales rows were downloaded.")
    out["_sample_row"] = sample
    save_json("export_sales", out)
