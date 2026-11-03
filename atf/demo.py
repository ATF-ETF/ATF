"""Deterministic synthetic fixtures. Never used as a live-data fallback."""
import hashlib
import numpy as np
import pandas as pd
from .pipeline import normalize


def demo_panel(instruments, start, end):
    frames = []
    dates = pd.bdate_range(start, end)  # Synthetic weekdays, NOT exchange calendar.
    if dates.empty:
        return pd.DataFrame()
    for item in instruments:
        seed = int(hashlib.sha256(item.id.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        close = (50000 if item.market == "KR" else 150) * np.exp(np.cumsum(rng.normal(0, .02, len(dates))))
        volume = rng.integers(100000, 1000000, len(dates))
        cap = close * 100000000
        frame = pd.DataFrame({"open": close, "high": close*1.01, "low": close*.99,
            "close": close, "adj_close": close, "volume": volume,
            "trading_value": close*volume, "market_cap": cap,
            "institution_net_buy": cap*rng.normal(0, .0001, len(dates)),
            "foreign_net_buy": cap*rng.normal(0, .0001, len(dates))}, index=dates)
        for col in ["price_source", "flow_source", "cap_source", "trading_value_source", "adjustment_basis"]:
            frame[col] = "synthetic"
        out = normalize(frame, item, start, end)
        out["data_mode"], out["issues"] = "demo", "SYNTHETIC: 실제 시세·수급 아님"
        frames.append(out)
    return pd.concat(frames, ignore_index=True)
