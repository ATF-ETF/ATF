"""Comparable, market-specific theme observations on one benchmark calendar."""
import numpy as np
import pandas as pd


def compare_themes(config, master, panel, benchmark, market):
    index = benchmark.loc[benchmark.market.eq(market)] if not benchmark.empty else benchmark
    prices = index.set_index('date')['adj_close'].dropna().sort_index() if not index.empty else pd.Series(dtype=float)
    if len(prices) < 2:
        return pd.DataFrame(), None

    dates = prices.index
    market_return = prices.iloc[-1] / prices.iloc[0] - 1
    stocks = panel.loc[panel.market.eq(market)].set_index(['instrument_id', 'date'])
    rows = []
    for group in config['themes'].values():
        for theme in group['subthemes'].values():
            ids = [key for key in theme['instruments'] if master[key].market == market]
            if not ids:
                continue
            keys = pd.MultiIndex.from_product([ids, dates], names=['instrument_id', 'date'])
            aligned = stocks.reindex(keys)
            adjusted = aligned['adj_close'].unstack('instrument_id')
            valid = adjusted.notna().all()
            count = int(valid.sum())
            returns = adjusted.iloc[-1] / adjusted.iloc[0] - 1
            complete = count == len(ids)
            theme_return = returns.mean() if complete else np.nan
            caps = aligned['market_cap'].unstack('instrument_id').iloc[0]
            flows = aligned['net_buy_total'].unstack('instrument_id').iloc[1:]
            flow_valid = flows.notna().all() & caps.gt(0)
            flow_count = int(flow_valid.sum())
            flow_strength = flows.sum().sum() / caps.sum() if flow_count == len(ids) else np.nan
            rows.append({
                '대분류': group['label'], '테마': theme['label'],
                '테마 수익률 (%)': theme_return * 100,
                '시장 대비 (%p)': (theme_return - market_return) * 100,
                '상승 종목 비율 (%)': returns.gt(0).mean() * 100 if complete else np.nan,
                '순매수 강도 (%)': flow_strength * 100,
                '가격 관측': f'{count}/{len(ids)}', '수급 관측': f'{flow_count}/{len(ids)}',
                '기간 상승 1위': master[returns.idxmax()].name if complete else '—',
            })
    board = pd.DataFrame(rows).sort_values('시장 대비 (%p)', ascending=False, na_position='last')
    return board, (dates[0], dates[-1], market_return * 100)


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
