"""Optional benchmark price collection, separately from investable securities."""
import pandas as pd
from .universe import Instrument
from .providers import YahooProvider
from .pipeline import normalize


def collect_benchmarks(instruments, start, end, provider=None):
    """Return local-session index prices; do not mix KR and US same-date returns."""
    provider = provider or YahooProvider()
    frames, statuses = [], []
    pairs = sorted({(item.market,item.currency,item.benchmark) for item in instruments})
    for market, currency, ticker in pairs:
        item = Instrument(f'BENCH:{market}:{ticker}',ticker,ticker,market,currency,ticker)
        try:
            frame = provider.prices(item, start, end)
            out = normalize(frame,item,start,end)
            if not out.close.notna().any():
                raise ValueError('No valid benchmark close')
            out['data_mode'] = 'live'
            out['flow_source'], out['cap_source'] = 'not_applicable','not_applicable'
            frames.append(out)
            statuses.append({'benchmark':ticker,'market':market,'status':'ok','rows':len(out)})
        except Exception as error:
            statuses.append({'benchmark':ticker,'market':market,'status':'error','rows':0,
                             'issues':f'{type(error).__name__}: {error}'})
    return (pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(),
            pd.DataFrame(statuses))
