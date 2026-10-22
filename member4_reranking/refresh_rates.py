"""
Monthly refresh of the rates snapshot (same method as notebook 19_n2_rates), without Colab.

    python member4_reranking/refresh_rates.py

Downloads World Bank PPP (private consumption), CPI and GNI per capita PPP for Sri Lanka, Pakistan, USA,
and today's exchange rates (open.er-api.com), then writes:
    price_data/rates_snapshot.json              (used by the API)
    price_data/rates_snapshot_<date>.json       (frozen copy, for repeatable experiments)
Schedule it monthly with Windows Task Scheduler (or cron). The API itself refreshes exchange rates daily.
If a source does not answer, the old snapshot is kept unchanged.
"""
import datetime
import json
import os
import sys
import time

import httpx

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "price_data")
COUNTRIES = {"LKA": "LKR", "PAK": "PKR", "USA": "USD"}
IND = {"ppp_private": "PA.NUS.PRVT.PP", "cpi": "FP.CPI.TOTL", "gni_pc_ppp": "NY.GNP.PCAP.PP.CD"}


def wb(indicator):
    out = {}
    for iso in COUNTRIES:
        url = (f"https://api.worldbank.org/v2/country/{iso}/indicator/{indicator}"
               f"?format=json&date=2015:2030&per_page=100&source=2")
        for attempt in range(4):
            try:
                payload = httpx.get(url, timeout=120).json(); break
            except Exception as e:
                print(f"  {indicator} {iso}: try {attempt + 1} failed ({type(e).__name__})"); time.sleep(10 * (attempt + 1))
        else:
            raise RuntimeError(f"World Bank not answering for {indicator} {iso}")
        for row in (payload[1] or []) if len(payload) > 1 else []:
            if row.get("value") is not None:
                out.setdefault(row["countryiso3code"], {})[int(row["date"])] = float(row["value"])
    return out


def main():
    try:
        data = {k: wb(v) for k, v in IND.items()}
        fx = httpx.get("https://open.er-api.com/v6/latest/USD", timeout=30).json()
        assert fx.get("result") == "success"
    except Exception as e:
        sys.exit(f"Refresh failed ({e}); the old snapshot was NOT changed.")
    ppp, cpi, gni = data["ppp_private"], data["cpi"], data["gni_pc_ppp"]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    snap = {"created_at": now, "fx_fetched_at": now, "fx_as_of": fx.get("time_last_update_utc"),
            "method": "PPP_now = PPP_base * (CPI_c(t)/CPI_c(base)) / (CPI_US(t)/CPI_US(base)), only if newer CPI exists for both",
            "sources": {k: f"https://api.worldbank.org/v2/country/LKA;PAK;USA/indicator/{v}" for k, v in IND.items()} |
                       {"fx": "https://open.er-api.com/v6/latest/USD"},
            "countries": {}}
    for iso, cur in COUNTRIES.items():
        if iso == "USA":
            continue
        base = max(ppp[iso])
        newer = [y for y in set(cpi.get(iso, {})) & set(cpi.get("USA", {})) if y > base]
        if newer and base in cpi[iso] and base in cpi["USA"]:
            t = max(newer); ic, iu, applied = cpi[iso][t] / cpi[iso][base], cpi["USA"][t] / cpi["USA"][base], True
        else:
            t, ic, iu, applied = base, 1.0, 1.0, False
        ppp_now = ppp[iso][base] * ic / iu
        gy = max(gni[iso])
        snap["countries"][iso] = {"currency": cur, "ppp_base_year": base, "ppp_base": ppp[iso][base], "cpi_year": t,
                                  "update_applied": applied, "inflation_factor_country": round(ic, 4),
                                  "inflation_factor_us": round(iu, 4), "ppp_updated": round(ppp_now, 4),
                                  "fx_per_usd_now": fx["rates"][cur], "price_level_ratio": round(ppp_now / fx["rates"][cur], 4),
                                  "gni_pc_ppp_year": gy, "gni_pc_ppp": round(gni[iso][gy], 1),
                                  "monthly_income_ppp": round(gni[iso][gy] / 12, 1)}
        print(iso, {k: snap["countries"][iso][k] for k in ("ppp_base_year", "ppp_updated", "fx_per_usd_now", "price_level_ratio")})
    os.makedirs(OUT, exist_ok=True)
    for name in ("rates_snapshot.json", f"rates_snapshot_{datetime.date.today().isoformat()}.json"):
        json.dump(snap, open(os.path.join(OUT, name), "w", encoding="utf-8"), indent=2)
    print("saved to", OUT)


if __name__ == "__main__":
    main()
