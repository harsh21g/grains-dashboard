"""EIA weekly US ethanol production and stocks."""
from common import get_json, save_json, need_key, num

URL = "https://api.eia.gov/v2/petroleum/sum/sndw/data/"
SERIES = {
    "W_EPOOXE_YOP_NUS_MBBLD": "production_kbd",   # thousand barrels per day
    "W_EPOOXE_SAE_NUS_MBBL": "stocks_kbbl",       # thousand barrels
}


def run():
    key = need_key("EIA_API_KEY")
    rows, offset = [], 0
    while True:
        params = [
            ("api_key", key), ("frequency", "weekly"), ("data[0]", "value"),
            ("start", "2011-01-01"),
            ("sort[0][column]", "period"), ("sort[0][direction]", "asc"),
            ("offset", offset), ("length", 5000),
        ] + [("facets[series][]", s) for s in SERIES]
        j = get_json(URL, params)["response"]
        rows += j["data"]
        if len(j["data"]) < 5000:
            break
        offset += 5000
    by_date = {}
    for r in rows:
        field = SERIES.get(r.get("series"))
        v = num(r.get("value"))
        if field and v is not None:
            by_date.setdefault(r["period"], {})[field] = v
    out = [{"d": d, **vals} for d, vals in sorted(by_date.items())]
    if not out:
        raise RuntimeError("EIA returned no ethanol rows. Check EIA_API_KEY and series names.")
    print(f"  ethanol: {len(out)} weeks")
    save_json("ethanol", out)
