"""Multi-window theme trend and recent change calculations."""
import numpy as np
import pandas as pd

from .comparison import compare_themes


def monitor_themes(config, master, panel, benchmark, market):
    """Compare completed, non-overlapping windows on the market's calendar."""
    board, period = compare_themes(config, master, panel, benchmark, market)
    if period is None:
        return board, period

    index = benchmark.loc[benchmark.market.eq(market)].sort_values('date')
    dates = index.loc[index.adj_close.notna(), 'date']
    labels = ['대분류', '테마']
    result = board.set_index(labels)[['가격 관측']].rename(columns={'가격 관측': '전체 기간 가격 관측'})

    def window(days, offset=0):
        stop = len(dates) - offset
        if stop < days + 1:
            return pd.DataFrame(index=result.index)
        common = dates.iloc[stop - days - 1:stop]
        sample = index.loc[index.date.isin(common)]
        values, _ = compare_themes(config, master, panel, sample, market)
        return values.set_index(labels)

    relative = '시장 대비 (%p)'
    breadth = '상승 종목 비율 (%)'
    flow = '순매수 강도 (%)'
    recent = window(20)
    previous = window(20, offset=20)
    recent_flow = window(5)
    previous_flow = window(5, offset=5)
    missing = pd.Series(np.nan, index=result.index)
    result['120일 초과성과 (%p)'] = window(120).get(relative, missing)
    result['60일 초과성과 (%p)'] = window(60).get(relative, missing)
    result['20일 초과성과 (%p)'] = recent.get(relative, missing)
    result['초과성과 변화 (%p)'] = recent.get(relative, missing) - previous.get(relative, missing)
    result['상승 종목 비율 변화 (%p)'] = recent.get(breadth, missing) - previous.get(breadth, missing)
    result['5일 순매수 강도 (%)'] = recent_flow.get(flow, missing)
    result['순매수 강도 변화 (%p)'] = recent_flow.get(flow, missing) - previous_flow.get(flow, missing)
    result['20일 가격 관측'] = recent.get('가격 관측', '—')
    result['5일 수급 관측'] = recent_flow.get('수급 관측', '—')

    long = result['120일 초과성과 (%p)']
    short = result['20일 초과성과 (%p)']
    change = result['초과성과 변화 (%p)']
    broader = result['상승 종목 비율 변화 (%p)'].gt(0)
    buying = result['5일 순매수 강도 (%)'].gt(0) & result['순매수 강도 변화 (%p)'].gt(0)
    result['관찰 상태'] = np.select(
        [long.isna() | short.isna() | change.isna(),
         long.le(0) & short.gt(0) & change.gt(0) & (broader | buying),
         long.gt(0) & short.lt(0) & change.lt(0)],
        ['기간·관측 부족', '반전 관찰', '둔화 관찰'],
        default='추세 확인',
    )
    return result.reset_index(), period
