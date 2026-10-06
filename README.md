# Grains Dashboard: data collector

This folder downloads free public data and saves it in the `data/` folder:

| File | What | Source |
|---|---|---|
| cot.json | Fund and commercial positions, 2011 to now | CFTC |
| nass_weekly.json | Crop condition and progress | USDA NASS |
| nass_annual.json | Yearly production, yield, area | USDA NASS |
| ethanol.json | Weekly ethanol production and stocks | EIA |
| rates.json | Interest rates | FRED |
| status.json | Which download worked or failed | (this tool) |

It runs by itself every weekday evening on GitHub. You can also run it by hand:
Actions tab, then "Update data", then "Run workflow".

API keys are never stored in these files. They are kept in GitHub Secrets:
NASS_API_KEY, FRED_API_KEY, EIA_API_KEY.

Futures prices from your company API are NOT part of this folder.
They will run on your own computer so the licensed data stays private.
