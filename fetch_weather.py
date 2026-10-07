"""Weather by growing region from Open-Meteo (free, no key). Weekly rain and temperature since 2000,
plus the last days and a 16-day forecast. Open-Meteo's free service is for non-commercial use."""
import datetime, time
import requests
from common import save_json

REGIONS = {
    "Iowa (corn, soy)": (42.0, -93.5), "Illinois (corn, soy, SRW wheat)": (40.2, -89.0),
    "Nebraska (corn, soy)": (41.0, -99.0), "Minnesota (corn, soy)": (45.0, -94.5),
    "Kansas (HRW wheat)": (38.5, -98.5), "Oklahoma (HRW wheat)": (36.0, -98.0),
    "Brazil: Mato Grosso (soy, corn)": (-13.5, -56.0), "Brazil: Parana (soy, corn)": (-24.5, -51.5),
    "Brazil: Rio Grande do Sul (soy)": (-29.0, -53.0), "Argentina: Pampas (soy, corn)": (-34.0, -61.0),
}
VARS = "precipitation_sum,temperature_2m_mean"
START = "2000-01-01"


def get(url, params):
    for i in range(3):
        r = requests.get(url, params=params, timeout=120, headers={"User-Agent": "grains-dashboard/1.0"})
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            time.sleep(20 * (i + 1))
            continue
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:150]}")
    raise RuntimeError("rate limit, try again later")


def weekly(dates, precip, temp):
    wk = {}
    for d, p, t in zip(dates, precip, temp):
        day = datetime.date.fromisoformat(d)
        monday = (day - datetime.timedelta(days=day.weekday())).isoformat()
        w = wk.setdefault(monday, {"p": 0.0, "t": [], "n": 0})
        if p is not None:
            w["p"] += p
        if t is not None:
            w["t"].append(t)
        w["n"] += 1
    return [[m, round(w["p"], 1), round(sum(w["t"]) / len(w["t"]), 1) if w["t"] else None]
            for m, w in sorted(wk.items()) if w["n"] == 7]       # complete weeks only


def run():
    today = datetime.date.today()
    arch_end = (today - datetime.timedelta(days=7)).isoformat()
    out = {}
    for name, (lat, lon) in REGIONS.items():
        try:
            a = get("https://archive-api.open-meteo.com/v1/archive",
                    {"latitude": lat, "longitude": lon, "start_date": START, "end_date": arch_end,
                     "daily": VARS, "timezone": "UTC"})["daily"]
            f = get("https://api.open-meteo.com/v1/forecast",
                    {"latitude": lat, "longitude": lon, "daily": VARS, "past_days": 14,
                     "forecast_days": 16, "timezone": "UTC"})["daily"]
        except Exception as e:
            print(f"  {name}: {str(e)[:150]}")
            continue
        recent = [{"d": d, "p": p, "t": t, "fc": d > today.isoformat()}
                  for d, p, t in zip(f["time"], f["precipitation_sum"], f["temperature_2m_mean"])]
        out[name] = {"lat": lat, "lon": lon,
                     "weekly": weekly(a["time"], a["precipitation_sum"], a["temperature_2m_mean"]),
                     "recent": recent}
        print(f"  {name}: {len(out[name]['weekly'])} weeks, {len(recent)} recent/forecast days")
        time.sleep(1)
    if not out:
        raise RuntimeError("No weather data downloaded.")
    save_json("weather", out)
