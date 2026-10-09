"""Run every data download. One failure does not stop the others."""
import sys, json, datetime, traceback
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import load_env, save_json
import fetch_cftc, fetch_nass, fetch_eia, fetch_fred, fetch_fas, fetch_psd, fetch_drought, fetch_weather

JOBS = [("cftc", fetch_cftc), ("nass", fetch_nass), ("eia", fetch_eia), ("fred", fetch_fred),
        ("psd", fetch_psd), ("drought", fetch_drought), ("weather", fetch_weather), ("fas", fetch_fas)]
# New sources: if one fails, the run stays green and the problem is written to status.json
OPTIONAL = {"psd", "drought", "weather", "fas"}


def main():
    load_env()
    status, failed = {}, 0
    for name, mod in JOBS:
        print(f"== {name}")
        try:
            mod.run()
            status[name] = {"ok": True}
        except Exception as e:  # keep going with the other sources
            if name not in OPTIONAL:
                failed += 1
            status[name] = {"ok": False, "error": str(e)[:300]}
            print(f"  FAILED: {e}")
            traceback.print_exc()
    save_json("status", status)
    print(f"Done. {sum(1 for v in status.values() if v['ok'])} of {len(JOBS)} sources worked.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
