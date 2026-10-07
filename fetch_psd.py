"""USDA PSD (world supply and demand, the data behind WASDE) from the free bulk CSV files.
No key needed. The files are updated every month with the WASDE report."""
import io, csv, re, zipfile, datetime, json
import requests
from common import DATA, save_json, num

BASE = "https://apps.fas.usda.gov/psdonline/downloads/"
FILES = ["psd_grains_pulses_csv.zip", "psd_oilseeds_csv.zip"]
ALL_FILE = "psd_alldata_csv.zip"          # backup (bigger)
FIRST_MY = 2010
COMMODITIES = {"Corn": "corn", "Wheat": "wheat", "Oilseed, Soybean": "soybeans",
               "Meal, Soybean": "meal", "Oil, Soybean": "oil"}
COUNTRIES = ["United States", "Brazil", "Argentina", "China", "European Union", "Russia", "Ukraine",
             "Canada", "Australia", "India", "Paraguay", "Mexico", "Indonesia", "Egypt", "Kazakhstan"]


def nk(s):
    return re.sub(r"[^a-z]", "", str(s).lower())


def download(name):
    r = requests.get(BASE + name, timeout=300, headers={"User-Agent": "grains-dashboard/1.0"})
    if r.status_code != 200:
        raise RuntimeError(f"{name}: HTTP {r.status_code}")
    return r.content


def rows_from_zip(blob):
    z = zipfile.ZipFile(io.BytesIO(blob))
    for member in z.namelist():
        if member.lower().endswith(".csv"):
            with z.open(member) as f:
                text = io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")
                for row in csv.DictReader(text):
                    yield {nk(k): v for k, v in row.items()}


def run():
    blobs = []
    for name in FILES:
        try:
            blobs.append(download(name))
            print(f"  downloaded {name} ({len(blobs[-1]) // 1024} KB)")
        except Exception as e:
            print(f"  {e}")
    if len(blobs) < len(FILES):
        print(f"  trying the backup file {ALL_FILE}")
        blobs = [download(ALL_FILE)]
    data, units, seen_c, seen_k = {}, {}, set(), set()
    for blob in blobs:
        for r in rows_from_zip(blob):
            com = (r.get("commoditydescription") or "").strip()
            cty = (r.get("countryname") or "").strip()
            seen_c.add(com); seen_k.add(cty)
            ck = COMMODITIES.get(com)
            if not ck or cty not in COUNTRIES:
                continue
            my = r.get("marketyear")
            v = num(r.get("value"))
            if not my or v is None or int(my) < FIRST_MY:
                continue
            attr = (r.get("attributedescription") or "").strip()
            data.setdefault(ck, {}).setdefault(cty, {}).setdefault(my, {})[attr] = v
            units.setdefault(ck, {})[attr] = (r.get("unitdescription") or "").strip()
    if not data:
        raise RuntimeError("No PSD rows matched. Commodities seen: " + ", ".join(sorted(seen_c))[:300])
    for ck, cs in data.items():
        print(f"  {ck}: {len(cs)} countries, e.g. {sorted(cs)[:4]}")
    missing = [c for c in COUNTRIES if c not in seen_k]
    if missing:
        print("  countries not found by name:", missing)

    # remember the US ending stocks each time they change (to show "change vs last month")
    snap_now = {}
    for ck, cs in data.items():
        us = cs.get("United States", {})
        snap_now[ck] = {my: a.get("Ending Stocks") for my, a in us.items() if a.get("Ending Stocks") is not None}
    old = []
    p = DATA / "psd.json"
    if p.exists():
        try:
            old = json.loads(p.read_text())["data"].get("snapshots", [])
        except Exception:
            old = []
    if not old or old[-1].get("us_ending_stocks") != snap_now:
        old.append({"date": datetime.date.today().isoformat(), "us_ending_stocks": snap_now})
    save_json("psd", {"data": data, "units": units, "snapshots": old[-36:],
                      "all_countries": sorted(seen_k)[:400]})
