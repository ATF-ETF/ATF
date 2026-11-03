"""Presentation-only transforms. No theme scores or synthetic live fallbacks."""
import numpy as np
import pandas as pd


def price_series(frame):
    """Select one price basis for the entire series; never splice adjusted/raw."""
    data = frame.sort_values('date').set_index('date')
    adjusted = data['adj_close'].where(data['adj_close'].gt(0))
    if adjusted.notna().any():
        return adjusted, '수정종가'
    return data['close'].where(data['close'].gt(0)), '종가 (수정 여부 미확인)'


def stock_summary(panel):
    rows = []
    for instrument_id, group in panel.groupby('instrument_id', sort=False):
        group = group.sort_values('date')
        last = group.iloc[-1]
        series, basis = price_series(group)
        observed = series.dropna()
        change = np.nan
        if len(observed) >= 2 and pd.notna(series.iloc[-1]):
            change = (series.iloc[-1] / observed.iloc[0] - 1) * 100
        close = last['close']
        rows.append({'instrument_id': instrument_id, '종목명': last['name'],
            '시장': '국내' if last['market'] == 'KR' else '미국',
            '종목코드': last['ticker'],
            '최근가격': ('—' if pd.isna(close) else
                f'{close:,.0f}원' if last['currency'] == 'KRW' else f'${close:,.2f}'),
            '관측기간 등락 (%)': change, '기준일': str(last['date'].date()),
            '가격기준': basis})
    return pd.DataFrame(rows)


def cumulative_flow(series):
    """Stop at first gap rather than silently compressing unknown daily flows."""
    return series.cumsum(skipna=False)
