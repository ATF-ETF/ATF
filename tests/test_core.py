"""Offline contract tests; provider fixtures do not establish live connectivity."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import pandas as pd
from atf.universe import load_universe, select, Instrument
from atf.pipeline import normalize, Pipeline, align_field
from atf.demo import demo_panel
from atf.providers import clean, retry

ROOT = Path(__file__).resolve().parents[1]
KR = Instrument('KR:000660', '000660', 'SK하이닉스', 'KR', 'KRW', '^KS11')
US = Instrument('US:MU', 'MU', 'Micron', 'US', 'USD', '^GSPC')
DATES = pd.to_datetime(['2026-01-02','2026-01-05','2026-01-06'])


class Fake:
    def prices(self, *args):
        return pd.DataFrame({'close':[100,101,102],'volume':[10,0,20],
                             'price_source':'fixture'},index=DATES)
    def adjusted(self, *args):
        return pd.DataFrame({'adj_close':[100,101,102]},index=DATES)
    def fundamentals(self, *args):
        return pd.DataFrame({'market_cap':[1000,1000,1000],
                             'trading_value':[1000,0,2040]},index=DATES)
    def flows(self, *args):
        return pd.DataFrame({'institution_net_buy':[0,-10],
                             'foreign_net_buy':[0,5]},index=DATES[:2])


class CoreTests(unittest.TestCase):
    def test_mapping_deduplicated(self):
        config, instruments = load_universe(ROOT/'config/themes.json')
        selected = select(config,instruments)
        self.assertEqual(len(selected), len({x.id for x in selected}))
        self.assertEqual(len(config['themes']),5)
        self.assertEqual(instruments['KR:000660'].ticker,'000660')
        with self.assertRaises(ValueError):
            select(config,instruments,'does_not_exist')

    def test_missing_is_not_zero(self):
        raw = Fake().prices()
        raw['institution_net_buy'] = [0, np.nan, -10]
        raw['foreign_net_buy'] = [0, 10, np.nan]
        out = normalize(raw,KR,'2026-01-02','2026-01-06')
        self.assertEqual(out.net_buy_total.iloc[0],0)
        self.assertTrue(out.net_buy_total.iloc[1:].isna().all())
        self.assertTrue(out.market_cap.isna().all())
        self.assertEqual(out.flow_complete.tolist(),[True,False,False])
        self.assertEqual(out.ticker.iloc[0],'000660')

    def test_nonpositive_price_and_negative_volume(self):
        raw = pd.DataFrame({'close':[0, -1, 100],'volume':[-1,0,20]}, index=DATES)
        out = normalize(raw,KR,'2026-01-02','2026-01-06')
        self.assertTrue(out.close.iloc[:2].isna().all())
        self.assertTrue(pd.isna(out.volume.iloc[0]))
        self.assertEqual(out.volume.iloc[1],0)

    def test_duplicate_rejected(self):
        raw = pd.DataFrame({'close':[1,2]},index=[DATES[0],DATES[0]])
        with self.assertRaises(ValueError): clean(raw)

    def test_join_preserves_missing_flows(self):
        with tempfile.TemporaryDirectory() as tmp, patch('atf.pipeline.time.sleep'):
            out, status = Pipeline(tmp,krx=Fake()).collect([KR],'2026-01-02','2026-01-06')
            self.assertEqual(len(out),3)
            self.assertEqual(out.net_buy_total.iloc[1],-5)
            self.assertTrue(pd.isna(out.net_buy_total.iloc[2]))
            self.assertAlmostEqual(status.flow_coverage.iloc[0],2/3)
            self.assertEqual(out.trading_value.iloc[0],1000)
            # Incomplete flows must be retried, not cached.
            self.assertEqual(list(Path(tmp).glob('*.csv')),[])

    def test_fallback_partial_status(self):
        class Broken(Fake):
            def prices(self,*args): raise RuntimeError('price outage')
            def flows(self,*args): raise RuntimeError('flow outage')
        with tempfile.TemporaryDirectory() as tmp, patch('atf.pipeline.time.sleep'):
            out,status=Pipeline(tmp,krx=Broken(),fdr=Fake()).collect([KR],'2026-01-02','2026-01-06')
            self.assertEqual(status.status.iloc[0],'partial')
            self.assertEqual(out.flow_source.iloc[0],'unavailable')
            self.assertTrue(out.institution_net_buy.isna().all())
            self.assertTrue(out.market_cap.notna().all())

    def test_cache_and_unsupported_us_fields(self):
        with tempfile.TemporaryDirectory() as tmp, patch('atf.pipeline.time.sleep'):
            pipeline=Pipeline(tmp,yahoo=Fake())
            out,status=pipeline.collect([US],'2026-01-02','2026-01-06')
            self.assertTrue(out.institution_net_buy.isna().all())
            self.assertTrue(out.market_cap.isna().all())
            _,second=pipeline.collect([US],'2026-01-02','2026-01-06')
            self.assertTrue(second.cache_hit.iloc[0])

    def test_all_failure_no_demo_fallback(self):
        class Broken(Fake):
            def prices(self,*args): raise RuntimeError('offline')
        with tempfile.TemporaryDirectory() as tmp:
            out,status=Pipeline(tmp,yahoo=Broken()).collect([US],'2026-01-02','2026-01-06')
            self.assertTrue(out.empty)
            self.assertEqual(status.status.iloc[0],'error')

    def test_alignment_no_forward_fill(self):
        panel=pd.DataFrame({'date':[DATES[0],DATES[2],DATES[1]],'market':['KR']*3,
                           'instrument_id':['a','a','b'],'close':[100,110,200]})
        aligned=align_field(panel,'close','KR')
        self.assertTrue(pd.isna(aligned.loc[DATES[1],'a']))
        self.assertTrue(pd.isna(aligned.pct_change(fill_method=None).loc[DATES[2],'a']))

    def test_retry_empty_and_bounded(self):
        count=[]
        def call():
            count.append(1)
            return pd.DataFrame()
        with patch('atf.providers.time.sleep'):
            with self.assertRaises(ValueError): retry(call,attempts=3)
        self.assertEqual(len(count),3)

    def test_demo_explicit_and_repeatable(self):
        a=demo_panel([KR,US],'2026-01-02','2026-01-06')
        b=demo_panel([KR,US],'2026-01-02','2026-01-06')
        self.assertTrue(a.close.equals(b.close))
        self.assertTrue(a.data_mode.eq('demo').all())

class BenchmarkTests(unittest.TestCase):
    def test_unique_benchmarks_and_alignment(self):
        from atf.benchmarks import collect_benchmarks
        panel, status = collect_benchmarks([KR,KR,US],'2026-01-02','2026-01-06',provider=Fake())
        self.assertEqual(len(status),2)
        self.assertEqual(panel.instrument_id.nunique(),2)
        self.assertTrue(panel.flow_source.eq('not_applicable').all())


class AdapterTests(unittest.TestCase):
    def test_yahoo_inclusive_end_and_price_semantics(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from atf.providers import YahooProvider
        download=Mock(return_value=pd.DataFrame({'Close':[100], 'Adj Close':[99],
                                                'Volume':[10]},index=DATES[:1]))
        with patch.dict('sys.modules', {'yfinance':SimpleNamespace(download=download)}):
            result=YahooProvider().prices(US,'2026-01-02','2026-01-06')
        self.assertEqual(download.call_args.kwargs['end'],'2026-01-07')
        self.assertFalse(download.call_args.kwargs['auto_adjust'])
        self.assertEqual(result.adj_close.iloc[0],99)
        self.assertNotIn('trading_value',result)

    def test_krx_flow_columns_and_provisional_day(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from atf.providers import KRXProvider
        from datetime import datetime
        from zoneinfo import ZoneInfo
        raw=pd.DataFrame({'기관합계':[0,-10,20],'외국인합계':[0,5,30]},index=DATES)
        call=Mock(return_value=raw)
        stock=SimpleNamespace(get_market_trading_value_by_date=call)
        with patch.dict('os.environ',{'KRX_ID':'fixture','KRX_PW':'fixture'}), \
             patch.dict('sys.modules',{'pykrx':SimpleNamespace(stock=stock)}), \
             patch('atf.providers.datetime') as clock:
            clock.now.return_value=datetime(2026,1,6,10,tzinfo=ZoneInfo('Asia/Seoul'))
            result=KRXProvider().flows(KR,'2026-01-02','2026-01-06')
        self.assertEqual(result.institution_net_buy.iloc[0],0)
        self.assertEqual(result.foreign_net_buy.iloc[1],5)
        self.assertTrue(result.iloc[2].isna().all())
        self.assertEqual(call.call_args.kwargs['on'],'순매수')


if __name__=='__main__': unittest.main()
