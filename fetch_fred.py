"""FRED interest rates (for cost of carry)."""
from common import get_json, save_json, need_key, num

URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES = {
    "DGS3MO": "Treasury 3-month yield (%)",
    "DFF": "Effective federal funds rate (%)",
}


def run():
    key = need_key("FRED_API_KEY")
    out = {}
    for sid, label in SERIES.items():
        j = get_json(URL, {"series_id": sid, "api_key": key, "file_type": "json",
                           "observation_start": "2011-01-01"})
        rows = [{"d": o["date"], "v": num(o["value"])} for o in j.get("observations", [])
                if num(o["value"]) is not None]
        print(f"  {sid}: {len(rows)} days")
        out[sid] = {"label": label, "rows": rows}
    save_json("rates", out)
