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
