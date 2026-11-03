"""Independent adapters; all monetary amounts are native currency units.

KRX data endpoints are unofficial wrappers. Errors/empty results must remain
visible, never be translated into zero flows. No live fallback to demo data.
"""
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd


NUMERIC = ["open", "high", "low", "close", "adj_close", "volume",
           "trading_value", "market_cap", "institution_net_buy", "foreign_net_buy"]


def clean(frame):
    frame = frame.copy()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index)).tz_localize(None).normalize()
    if frame.index.has_duplicates:
        raise ValueError("Duplicate daily timestamps returned by provider")
    return frame.sort_index()


def nonempty(frame):
    if frame is None or frame.empty:
        raise ValueError("Provider returned no observations")
    return frame


def retry(call, attempts=3, pause=0.4):
    for attempt in range(attempts):
        try:
            return nonempty(call())
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(pause * (2 ** attempt))


class YahooProvider:
    def prices(self, instrument, start, end):
        import yfinance as yf
        # Public API end date is exclusive; ATF date interval is inclusive.
        raw = retry(lambda: yf.download(
            instrument.ticker, start=start,
            end=(pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=False, multi_level_index=False, progress=False,
            threads=False, timeout=20))
        out = clean(raw.rename(columns={"Open": "open", "High": "high", "Low": "low",
                  "Close": "close", "Adj Close": "adj_close", "Volume": "volume"}))
        out = out[[c for c in NUMERIC if c in out]]
        out["price_source"] = "yfinance"
        # close*volume is only an approximation, never actual traded value.
        out["trading_value_source"] = "unavailable"
        out["adjustment_basis"] = "yahoo_adj_close" if "adj_close" in out else "unavailable"
        return out


class FDRProvider:
    def prices(self, instrument, start, end):
        import FinanceDataReader as fdr
        raw = retry(lambda: fdr.DataReader(instrument.ticker, start, end))
        out = clean(raw.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                        "Close": "close", "Volume": "volume"}))
        out = out[[c for c in NUMERIC if c in out and c != "adj_close"]]
        # FDR adjustment semantics vary by upstream; don't assert adjusted returns.
        out["price_source"] = "FinanceDataReader"
        out["adjustment_basis"] = "unverified"
        out["trading_value_source"] = "unavailable"
        return out


class KRXProvider:
    @staticmethod
    def require_auth():
        if not os.getenv("KRX_ID") or not os.getenv("KRX_PW"):
            raise RuntimeError("KRX_ID / KRX_PW required for authenticated KRX endpoints")

    def prices(self, instrument, start, end):
        self.require_auth()
        from pykrx import stock
        s, e = pd.Timestamp(start).strftime("%Y%m%d"), pd.Timestamp(end).strftime("%Y%m%d")
        raw = retry(lambda: stock.get_market_ohlcv_by_date(s, e, instrument.ticker, adjusted=False))
        out = clean(raw.rename(columns={"시가": "open", "고가": "high", "저가": "low",
                        "종가": "close", "거래량": "volume", "거래대금": "trading_value"}))
        out = out[[c for c in NUMERIC if c in out]]
        out["price_source"] = "pykrx"
        out["trading_value_source"] = "pykrx" if "trading_value" in out else "unavailable"
        out["adjustment_basis"] = "unavailable"
        return out

    def adjusted(self, instrument, start, end):
        from pykrx import stock
        raw = retry(lambda: stock.get_market_ohlcv_by_date(
            pd.Timestamp(start).strftime("%Y%m%d"), pd.Timestamp(end).strftime("%Y%m%d"),
            instrument.ticker, adjusted=True))
        return clean(raw[["종가"]].rename(columns={"종가": "adj_close"}))

    def fundamentals(self, instrument, start, end):
        self.require_auth()
        from pykrx import stock
        raw = retry(lambda: stock.get_market_cap_by_date(
            pd.Timestamp(start).strftime("%Y%m%d"), pd.Timestamp(end).strftime("%Y%m%d"),
            instrument.ticker))
        return clean(raw[["시가총액", "거래대금"]].rename(columns={"시가총액": "market_cap", "거래대금": "trading_value"}))

    def flows(self, instrument, start, end):
        self.require_auth()
        from pykrx import stock
        raw = retry(lambda: stock.get_market_trading_value_by_date(
            pd.Timestamp(start).strftime("%Y%m%d"), pd.Timestamp(end).strftime("%Y%m%d"),
            instrument.ticker, on="순매수"))
        out = clean(raw[["기관합계", "외국인합계"]].rename(
            columns={"기관합계": "institution_net_buy", "외국인합계": "foreign_net_buy"}))
        # Guard provisional current-day data. Historical revisions remain possible.
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        if now.hour < 19:
            out.loc[out.index >= pd.Timestamp(now.date()), :] = float("nan")
        return out
