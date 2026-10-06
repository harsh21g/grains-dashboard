"""CFTC Commitments of Traders (Disaggregated, futures only). No API key needed."""
from common import get_json, save_json, num

URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
START = "2011-01-01T00:00:00.000"
# CFTC contract market codes
MARKETS = {
    "ZS": "005602",  # Soybeans
    "ZM": "026603",  # Soybean meal
    "ZL": "007601",  # Soybean oil
    "ZC": "002602",  # Corn
    "ZW": "001602",  # Wheat SRW (Chicago)
    "KW": "001612",  # Wheat HRW (KC)
}


def pick(row, *names):
    for n in names:
        if n in row and row[n] not in (None, ""):
            return row[n]
    return None


def run():
    out = {}
    for sym, code in MARKETS.items():
        rows, offset = [], 0
        while True:
            params = {
                "$where": f"cftc_contract_market_code='{code}' AND report_date_as_yyyy_mm_dd >= '{START}'",
                "$order": "report_date_as_yyyy_mm_dd ASC",
                "$limit": 1000,
                "$offset": offset,
            }
            chunk = get_json(URL, params)
            rows += chunk
            if len(chunk) < 1000:
                break
            offset += 1000
        if not rows:
            raise RuntimeError(f"No COT rows for {sym} (code {code}). Check the contract code.")
        series = []
        for r in rows:
            d = str(pick(r, "report_date_as_yyyy_mm_dd", "report_date") or "")[:10]
            mml = num(pick(r, "m_money_positions_long_all", "m_money_positions_long"))
            mms = num(pick(r, "m_money_positions_short_all", "m_money_positions_short"))
            pml = num(pick(r, "prod_merc_positions_long", "prod_merc_positions_long_all"))
            pms = num(pick(r, "prod_merc_positions_short", "prod_merc_positions_short_all"))
            oi = num(pick(r, "open_interest_all"))
            if not d or mml is None or mms is None:
                continue
            series.append({
                "d": d, "oi": oi,
                "mm_long": mml, "mm_short": mms, "mm_net": mml - mms,
                "pm_net": (pml - pms) if pml is not None and pms is not None else None,
            })
        name = pick(rows[0], "market_and_exchange_names", "contract_market_name")
        print(f"  {sym}: {len(series)} weeks, market = {name}")
        out[sym] = {"name": name, "rows": series}
    save_json("cot", out)
