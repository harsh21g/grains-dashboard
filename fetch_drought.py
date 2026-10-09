"""U.S. Drought Monitor: percent of area in drought, by state. Free, no key needed."""
import datetime, requests
import xml.etree.ElementTree as ET
from common import save_json, num

BASE = "https://usdmdataservices.unl.edu/api"
STATES = ["IA", "IL", "IN", "OH", "MN", "NE", "SD", "ND", "MO", "KS", "OK", "TX", "CO"]
START = "1/1/2011"
FIPS = {"IA": "19", "IL": "17", "IN": "18", "OH": "39", "MN": "27", "NE": "31", "SD": "46",
        "ND": "38", "MO": "29", "KS": "20", "OK": "40", "TX": "48", "CO": "08"}


def get(url, params):
    r = requests.get(url, params=params, timeout=120,
                     headers={"Accept": "application/json", "User-Agent": "grains-dashboard/1.0"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} for {url}: {r.text[:150]}")
    try:
        return r.json()
    except ValueError:
        root = ET.fromstring(r.text)          # some answers come back as XML
        out = []
        for el in root.iter():
            kids = list(el)
            if kids and all(len(list(k)) == 0 for k in kids):
                out.append({k.tag.split("}")[-1]: k.text for k in kids})
        return out


def clean(rows):
    out = []
    for r in rows:
        n = {str(k).lower(): v for k, v in r.items()}
        d = str(n.get("mapdate") or n.get("validstart") or "")
        d = d[:10] if "-" in d[:10] else (f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else "")
        vals = [num(n.get(k)) for k in ("none", "d0", "d1", "d2", "d3", "d4")]
        if not d or any(v is None for v in vals):
            continue
        none, d0, d1, d2, d3, d4 = vals
        if abs(sum(vals) - 100) < 1.5:            # separate bands: make them cumulative (D1 or worse)
            d3c, d2c = d3 + d4, d2 + d3 + d4
            d1c, d0c = d1 + d2c, d0 + d1 + d2c
            d0, d1, d2, d3 = d0c, d1c, d2c, d3c
        out.append({"d": d, "d0": round(d0, 1), "d1": round(d1, 1), "d2": round(d2, 1),
                    "d3": round(d3, 1), "d4": round(d4, 1)})
    out.sort(key=lambda x: x["d"])
    return out


def run():
    end = datetime.date.today()
    end_s = f"{end.month}/{end.day}/{end.year}"
    out = {}
    # national (lower 48): try the names the service may use
    for aoi in ("conus", "us", "total"):
        try:
            rows = clean(get(f"{BASE}/USStatistics/GetDroughtSeverityStatisticsByAreaPercent",
                             {"aoi": aoi, "startdate": START, "enddate": end_s, "statisticsType": 1}))
            if rows:
                out["US"] = rows
                print(f"  US (aoi={aoi}): {len(rows)} weeks")
                break
        except Exception as e:
            print(f"  US aoi={aoi}: {str(e)[:150]}")
    errors = {}
    for st in STATES:
        rows, why = [], ""
        for aoi in (st, FIPS[st]):               # state letters first, then the 2-digit FIPS code
            try:
                for y0 in range(2011, end.year + 1, 4):   # ask in 4-year pieces
                    a = f"1/1/{y0}"
                    b = f"12/31/{min(y0 + 3, end.year)}" if y0 + 3 < end.year else end_s
                    rows += clean(get(f"{BASE}/StateStatistics/GetDroughtSeverityStatisticsByAreaPercent",
                                      {"aoi": aoi, "startdate": a, "enddate": b, "statisticsType": 1}))
                if rows:
                    break
                why = f"aoi={aoi}: answer had no usable rows"
            except Exception as e:
                rows, why = [], f"aoi={aoi}: {str(e)[:160]}"
        if rows:
            seen, uniq = set(), []
            for r in sorted(rows, key=lambda x: x["d"]):
                if r["d"] not in seen:
                    seen.add(r["d"]); uniq.append(r)
            out[st] = uniq
            print(f"  {st}: {len(uniq)} weeks, latest {uniq[-1]['d']}")
        else:
            errors[st] = why
            print(f"  {st}: {why}")
    if errors:
        out["_errors"] = errors
    if not out:
        raise RuntimeError("No drought data downloaded.")
    save_json("drought", out)
