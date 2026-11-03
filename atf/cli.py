"""Run from repository root: python -m atf.cli --demo ..."""
import argparse
import json
from pathlib import Path
import pandas as pd
from .universe import load_universe, select
from .pipeline import Pipeline
from .demo import demo_panel
from .benchmarks import collect_benchmarks


def main():
    parser = argparse.ArgumentParser(description="ATF daily ingestion")
    parser.add_argument('--config', default='config/themes.json')
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--mega')
    parser.add_argument('--subtheme')
    parser.add_argument('--benchmarks', action='store_true', help='Also collect KOSPI / S&P 500 prices (live only)')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--output', default='data/output')
    args = parser.parse_args()
    if pd.Timestamp(args.start) > pd.Timestamp(args.end):
        parser.error('start must be <= end')
    config, instruments = load_universe(args.config)
    universe = select(config, instruments, args.mega, args.subtheme)
    if args.demo:
        panel = demo_panel(universe, args.start, args.end)
        status = pd.DataFrame([{'status': 'demo', 'rows': len(panel)}])
    else:
        panel, status = Pipeline().collect(universe, args.start, args.end, args.refresh)
    folder = Path(args.output) / ('demo' if args.demo else 'live')
    folder.mkdir(parents=True, exist_ok=True)
    panel.to_csv(folder/'panel.csv', index=False, encoding='utf-8-sig')
    status.to_csv(folder/'status.csv', index=False, encoding='utf-8-sig')
    (folder/'run.json').write_text(json.dumps({
        'mode': 'demo' if args.demo else 'live', 'start': args.start, 'end': args.end,
        'universe_version': config['universe_version'], 'requested_ids': [i.id for i in universe],
        'run_utc': pd.Timestamp.now(tz='UTC').isoformat()}, indent=2), encoding='utf-8')
    benchmark_failed = False
    if args.benchmarks and not args.demo:
        bench, bench_status = collect_benchmarks(universe, args.start, args.end)
        bench.to_csv(folder/'benchmarks.csv', index=False, encoding='utf-8-sig')
        bench_status.to_csv(folder/'benchmark_status.csv', index=False, encoding='utf-8-sig')
        benchmark_failed = bench_status.status.eq('error').any()
    print(status.to_string(index=False))
    print(f'Output: {folder.resolve()}')
    return 2 if benchmark_failed or panel.empty or (not args.demo and status.status.eq('error').any()) else 0


if __name__ == '__main__':
    raise SystemExit(main())
