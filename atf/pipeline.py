"""Daily long-form panel, component-level provenance and cache.

Dates remain local exchange session labels, not globally simultaneous timestamps.
Missing price/flow/cap values are NEVER forward-filled or replaced with zero.
"""
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
from .providers import NUMERIC, KRXProvider, FDRProvider, YahooProvider, clean

CACHE_VERSION = "1"


def normalize(frame, instrument, start, end):
    out = clean(frame)
    out = out.loc[pd.Timestamp(start):pd.Timestamp(end)].copy()
    if out.empty:
        raise ValueError("No observations within requested interval")
    for column in NUMERIC:
        out[column] = pd.to_numeric(out.get(column, np.nan), errors="coerce")
    out[NUMERIC] = out[NUMERIC].replace([np.inf, -np.inf], np.nan)
    for column in ["open", "high", "low", "close", "adj_close", "market_cap"]:
        out.loc[out[column] <= 0, column] = np.nan
    for column in ["volume", "trading_value"]:
        out.loc[out[column] < 0, column] = np.nan
    out["trading_value_estimate"] = out["close"] * out["volume"]
    out["flow_complete"] = out[["institution_net_buy", "foreign_net_buy"]].notna().all(axis=1)
    out["net_buy_total"] = out["institution_net_buy"] + out["foreign_net_buy"]
    out["price_missing"] = out["close"].isna()
    out["cap_missing"] = out["market_cap"].isna()
    # Scope metadata makes cross-currency summation an explicit downstream choice.
    for field in ["id", "ticker", "name", "market", "currency", "benchmark"]:
        out["instrument_id" if field == "id" else field] = getattr(instrument, field)
    out["date"] = out.index
    out["fetched_at_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    return out.reset_index(drop=True)


class Pipeline:
    def __init__(self, cache_dir="data/cache", ttl_hours=6, krx=None, fdr=None, yahoo=None):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_hours * 3600
        self.krx, self.fdr, self.yahoo = krx or KRXProvider(), fdr or FDRProvider(), yahoo or YahooProvider()

    def _fetch(self, instrument, start, end):
        issues = []
        if instrument.market == "US":
            frame = self.yahoo.prices(instrument, start, end)
            frame["flow_source"] = "unavailable"
            frame["cap_source"] = "unavailable"
        else:
            try:
                frame = self.krx.prices(instrument, start, end)
            except Exception as error:
                issues.append(f"KRX prices: {type(error).__name__}: {error}")
                frame = self.fdr.prices(instrument, start, end)
            for method, columns, label in [
                (self.krx.adjusted, ["adj_close"], "adjusted"),
                (self.krx.fundamentals, ["market_cap", "trading_value"], "cap"),
                (self.krx.flows, ["institution_net_buy", "foreign_net_buy"], "flow")]:
                try:
                    extra = method(instrument, start, end)
                    # Align on observed price dates only; no manufactured business days.
                    frame = frame.drop(columns=columns, errors="ignore").join(extra, how="left")
                    if label == "adjusted":
                        frame["adjustment_basis"] = "pykrx_adjusted_price_not_total_return"
                    else:
                        frame[label + "_source"] = "pykrx"
                        if label == "cap":
                            frame["trading_value_source"] = "pykrx"
                except Exception as error:
                    issues.append(f"{label}: {type(error).__name__}: {error}")
                    if label != "adjusted":
                        frame[label + "_source"] = "unavailable"
        out = normalize(frame, instrument, start, end)
        if not out["close"].notna().any():
            raise ValueError("Provider returned no valid closing prices")
        out["issues"] = " | ".join(issues)
        out["data_mode"] = "live"
        return out

    def collect(self, instruments, start, end, refresh=False):
        start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
        if start > end:
            raise ValueError("start must be <= end")
        frames, statuses = [], []
        for instrument in instruments:
            key = hashlib.sha256(json.dumps(
                [CACHE_VERSION, instrument.__dict__, str(start.date()), str(end.date())],
                sort_keys=True).encode()).hexdigest()[:24]
            path = self.cache / f"{key}.csv"
            hit = not refresh and path.exists() and time.time() - path.stat().st_mtime < self.ttl
            try:
                if hit:
                    frame = pd.read_csv(path, dtype={"ticker": str}, parse_dates=["date"])
                    frame["issues"] = frame["issues"].fillna("")
                else:
                    frame = self._fetch(instrument, start, end)
                    # Partial data is never cached, allowing the next run to retry.
                    if (frame["issues"].eq("").all() and not frame["price_missing"].any()
                        and (instrument.market != "KR" or (frame["flow_complete"].all()
                        and frame["market_cap"].notna().all()))):
                        temp = path.with_suffix(".tmp.csv")
                        frame.to_csv(temp, index=False)
                        temp.replace(path)
                    time.sleep(0.25)  # Sequential collection limits upstream pressure.
                frames.append(frame)
                statuses.append({"instrument_id": instrument.id, "status": ("price_only" if instrument.market == "US" else
                    "partial" if (frame["issues"].ne("").any() or not frame.flow_complete.all()
                    or frame.market_cap.isna().any() or frame.close.isna().any()) else "ok"), "cache_hit": hit,
                    "rows": len(frame), "last_date": str(frame.date.max().date()),
                    "flow_coverage": float(frame.flow_complete.mean()),
                    "cap_coverage": float(frame.market_cap.notna().mean()),
                    "issues": frame["issues"].iloc[0]})
            except Exception as error:
                statuses.append({"instrument_id": instrument.id, "status": "error", "cache_hit": False,
                                 "rows": 0, "issues": f"{type(error).__name__}: {error}"})
        panel = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not panel.empty:
            panel = panel.sort_values(["date", "instrument_id"]).reset_index(drop=True)
        return panel, pd.DataFrame(statuses)


def align_field(panel, field, market):
    """Union of observed sessions in one market; gaps stay NaN, including returns."""
    part = panel.loc[panel.market.eq(market)]
    return part.pivot(index="date", columns="instrument_id", values=field).sort_index()
