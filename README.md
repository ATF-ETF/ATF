# ATF · ACE Theme Flow

GitHub: [ATF-ETF/ATF](https://github.com/ATF-ETF/ATF) · [웹 배포 안내](DEPLOYMENT.md)

테마별 자금 흐름과 주도 종목을 분석하기 위한 Python MVP의 **1단계 구현**입니다.
이번 버전은 테마 정의, 일별 데이터 수집·정규화, 데이터 품질 점검 화면에 집중합니다.
Theme Flow Score, 베타, Leader/Laggard, ETF 상품 바스켓 최적화는 아직 구현하지 않았습니다.

## 1. 프로젝트 구조와 데이터 흐름

| 경로 | 역할 |
|---|---|
| `config/themes.json` | Mega Trend → Sub-Theme → Instrument ID, 종목 마스터 |
| `atf/universe.py` | 설정 검증, 테마 선택, 중복 종목 제거 |
| `atf/providers.py` | pykrx / FinanceDataReader / yfinance 어댑터 |
| `atf/pipeline.py` | 수집, 결측·단위 정규화, 6시간 캐시, 품질 상태 |
| `atf/benchmarks.py` | KOSPI / S&P 500 가격 별도 수집 |
| `atf/demo.py` | 합성 패널 생성. 실제 데이터 실패 시 자동 실행되지 않음 |
| `atf/cli.py` | 수동·배치 실행 및 CSV 저장 |
| `app.py` | Streamlit 수집 점검 화면 |
| `tests/test_core.py` | 외부 통신 없는 데이터 계약 테스트 |
| `data/output/demo/` | CLI 실행 시 생성되는 합성 패널 및 실행 정보 |
| `data/cache/` | 실행 시 생성되는 종목·조회기간별 캐시 |

테마 설정을 읽고 종목 ID를 중복 제거한 뒤 공급자에서 수집합니다.
수집 결과는 `date × instrument_id` long-form 패널로 정규화합니다.
점수 엔진과 향후 대시보드는 이 패널을 입력으로 사용하면 됩니다.
점수 엔진은 후속 단계에서 추가할 예정입니다.

화면은 가격·수급 / 종목 현황 / 데이터 점검 탭으로 구성합니다.
데모는 테마 선택 즉시 표시하고, 실제 데이터는 수집 버튼을 눌렀을 때만 조회합니다.
원본 패널·수집 출처·오류 정보는 데이터 점검 탭에서 확인할 수 있습니다.

## 2. 초기 유니버스

| Mega Trend | Sub-Theme | 예시 종목 |
|---|---|---|
| AI 인프라 | HBM / 패키징 | SK하이닉스, 한미반도체, Micron |
| AI 인프라 | 전력 / 전력망 | HD현대일렉트릭, LS ELECTRIC, Eaton |
| 방산 / 우주 | 방산 | 한화에어로스페이스, LIG넥스원, Lockheed Martin |
| 방산 / 우주 | 우주 | 한국항공우주, Rocket Lab |
| 헬스케어 | 바이오 / 바이오의약품 | 삼성바이오로직스, 셀트리온, Amgen |
| 전동화 | 이차전지 / 소재 | LG에너지솔루션, 삼성SDI, Albemarle |
| 보안 | 사이버보안 | Palo Alto Networks, Fortinet, CrowdStrike |

5개 메가 트렌드, 7개 하위 테마, 20개 종목으로 구성된 **수동 예시 후보군**입니다.
현금흐름·이익·밸류에이션 필터를 통과한 투자 유니버스가 아니며, 물리보안은 추가하지 않았습니다.
테마별 매출 노출도와 ETF 편입 적합성은 검증하지 않았습니다.
각 종목의 `benchmark`는 변경 가능합니다. 국내 기본은 KOSPI이며 KOSDAQ/업종 벤치마크와 비교할 때 변경해야 합니다.

설정 예시:

```json
{
  "instruments": {
    "KR:000660": {
      "ticker": "000660", "name": "SK하이닉스", "market": "KR",
      "currency": "KRW", "benchmark": "^KS11"
    }
  },
  "themes": {
    "ai_infrastructure": {
      "label": "AI 인프라",
      "subthemes": {
        "hbm": {"label": "HBM / 패키징", "instruments": ["KR:000660"]}
      }
    }
  }
}
```

전체 파일에는 `schema_version`, `universe_version`, `notice`도 있습니다.
종목이 여러 테마에 걸쳐 있어도 데이터는 한 번만 수집합니다.
테마끼리 금액을 합산할 때의 중복 노출 조정은 향후 집계 엔진에서 처리해야 합니다.

## 3. 수집 소스와 지원 범위

| 데이터 | 국내 | 미국 |
|---|---|---|
| OHLCV | pykrx 우선, 오류 시 FDR 보완 | yfinance |
| 수정종가 | pykrx 별도 조회 | yfinance Adj Close |
| 실제 거래대금 | pykrx 시가총액 데이터의 거래대금 열 | 미지원 |
| 일별 과거 시가총액 | pykrx | 미지원 |
| 기관 / 외국인 순매수 금액 | pykrx | 미지원 |
| 기준지수 가격 | yfinance `^KS11` | yfinance `^GSPC` |

미국 순매수·과거 시가총액을 현재 시가총액으로 소급하거나 거래량으로 대체하지 않습니다.
미국에서 비교 가능한 수급 지표가 필요하면 별도 계약 데이터나 ETF 설정·환매 데이터의
독립 모듈이 필요합니다. ETF 순유입과 구성 종목 기관·외국인 순매수는 다른 지표입니다.

KRX 로그인이 필요한 엔드포인트를 위해 프로세스 시작 전 `KRX_ID`, `KRX_PW`를 설정하세요.
코드나 설정 JSON에 계정 정보를 넣지 마세요. 환경변수 설정은 사용자의 로컬 환경에서 진행합니다.
pykrx 1.2.8 이상을 요구하며 공급자 정책 변경에 따라 수정이 필요할 수 있습니다.
권장 Python은 3.11 또는 3.12입니다. 라이브러리 버전은 범위 제약이며 완전한 lockfile은 아닙니다.

## 4. 로컬 실행

압축파일은 해제 후 `atf` 폴더에서, GitHub 저장소는 clone한 저장소 루트에서 실행합니다.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

macOS / Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

브라우저에서 터미널에 표시되는 로컬 주소(기본 `http://localhost:8501`)를 엽니다.
기본 모드는 데모입니다. 실제 데이터를 보려면 사이드바에서 실제 데이터 수집을 선택하고 실행합니다.
KRX 인증이 없으면 보완 가격 수집은 시도하지만 수급과 시가총액 확보는 보장할 수 없습니다.

외부 접속 없는 CLI 데모:

```bash
python -m atf.cli --demo --start 2026-08-03 --end 2026-10-30
```

특정 테마의 실제 수집 및 벤치마크 수집:

```bash
python -m atf.cli --mega ai_infrastructure --subtheme hbm --start 2026-08-03 --end 2026-10-30 --benchmarks
```

재시도하려면 `--refresh`를 추가합니다. 데모·실제 데이터는 별도 폴더에 저장합니다.
`--benchmarks`는 실제 모드에서만 동작하며 데모에서는 기준지수를 만들지 않습니다.
`panel.csv`, `status.csv`, `run.json`을 저장하고, 기준지수 옵션은
`benchmarks.csv`, `benchmark_status.csv`도 저장합니다.
같은 출력 폴더를 재사용하면 해당 파일은 덮어씁니다. 이력 보관은 `--output data/runs/2026-11-02`처럼 경로를 지정하세요.

함수로 사용:

```python
from atf.universe import load_universe, select
from atf.pipeline import Pipeline, align_field
from atf.benchmarks import collect_benchmarks

config, master = load_universe("config/themes.json")
universe = select(config, master, "ai_infrastructure", "hbm")
panel, status = Pipeline().collect(universe, "2026-08-03", "2026-10-30")
benchmarks, benchmark_status = collect_benchmarks(universe, "2026-08-03", "2026-10-30")
if not panel.empty:
    kr_prices = align_field(panel, "adj_close", "KR")
    returns = kr_prices.pct_change(fill_method=None)
```

자동 실행은 CLI를 로컬 작업 스케줄러 또는 cron에 등록하는 방식입니다.
이 패키지 자체가 상시 실행되거나 스케줄러를 설치하지는 않습니다.
한국 시각 19:30 이후 배치 수집을 권장하며, 휴장일은 반환된 관측일만 저장합니다.
단일 프로세스·순차 실행을 전제로 합니다. 여러 배치를 동시에 실행하지 마세요.

## 5. 데이터 계약 및 품질 원칙

| 열 | 의미 / 단위 |
|---|---|
| `date` | 해당 거래소의 현지 거래일, 종료일 포함 |
| `instrument_id`, `ticker` | 시장 포함 고유 ID, 원문 문자열 종목코드 |
| `market`, `currency`, `benchmark` | 시장, 원화/달러, 비교 기준 |
| `open/high/low/close` | 공급자 가격. FDR 보완 가격의 수정 여부는 미검증 |
| `adj_close`, `adjustment_basis` | 별도 수정가격과 수정 방식 표기 |
| `volume` | 주식 수 |
| `trading_value` | 실제 거래대금, KRW 또는 USD |
| `trading_value_estimate` | close × volume 추정값. 실제 거래대금과 분리 |
| `market_cap` | 당시 일별 시가총액, 시장 통화 |
| `institution_net_buy`, `foreign_net_buy` | 기관합계 / 외국인합계 순매수 금액 |
| `net_buy_total` | 두 순매수 금액의 합. 어느 한쪽 결측 시 결측 |
| `flow_complete`, `price_missing`, `cap_missing` | 관측 유무 플래그 |
| `price_source`, `flow_source`, `cap_source`, `trading_value_source` | 항목별 수집 출처 |
| `fetched_at_utc`, `data_mode`, `issues` | 수집 시각, live/demo, 오류 및 보완 경로 |

- 결측은 NaN으로 유지합니다. 실제 0은 0으로 보존합니다.
- 일별 가격이 반환된 날짜를 기준으로 수급·시가총액을 left join합니다.
  수급만 있고 가격이 전혀 없는 날짜는 패널에 포함하지 않습니다.
- 같은 시장 내 관측일 합집합으로 정렬하고 가격·수급·시총 모두 전일 값으로 채우지 않습니다.
  거래소 캘린더 기반의 전체 누락일 탐지는 아직 없습니다.
- KR·US는 동일 날짜여도 정보 시점이 다릅니다. 양국 당일 수익률을 동시에 알고 있었다고 가정하면 안 됩니다.
- 원화와 달러는 그대로 합산하지 않습니다. 원화 통합이 필요하면 별도 시점별 환율 모듈이 필요합니다.
- 국내 당일 수급은 한국 시각 19시 전이면 결측 처리합니다. 확정 상태 API를 확인한 것은 아니므로 이후 정정은 가능합니다.
- 수정가격은 공급자마다 정의가 다릅니다. 국내 수정가격을 배당재투자 총수익으로 간주하지 않습니다.
  국가 간 비교 전 수익률 기준을 통일해야 합니다.
- 빈 응답·예외는 최대 3회 재시도합니다. pykrx/FDR의 내부 HTTP 타임아웃은 외부 라이브러리 구현에 따릅니다.
- 캐시는 6시간 TTL입니다. 국내 수급/시총 결측, 가격 결측 또는 컴포넌트 오류가 있으면 캐시하지 않습니다.
- `status=ok`는 수집 경로와 핵심 관측을 확인했다는 뜻이며 시장 전체 완전성·최신성을 보증하지 않습니다.
  국내 일부 누락/보완은 `partial`, 해외 가격 수집은 `price_only`, 실패는 `error`입니다.
- CLI는 전부 빈 패널, 종목 수집 오류 또는 벤치마크 오류에 exit code 2를 반환합니다.
  `partial`은 CSV 저장 후 exit code 0이므로 배치 운영 시 status.csv도 점검해야 합니다.
- 현재 유니버스를 과거에 고정 적용하면 생존편향이 생깁니다. 시점별 편입/편출 이력은 미구현입니다.
- 기본 UI는 수집을 클릭할 때만 호출하며 위젯 변경만으로 외부 수집하지 않습니다.

## 6. 다음 모듈의 산출 규격 (설계안, 미구현)

수급 점수와 ETF 상품화를 분리합니다. 수급이 강하다는 사실이 ETF 편입 적격성을 뜻하지는 않습니다.

| 지표 | 정의안 | 필수 데이터 / 유의점 |
|---|---|---|
| 거래대금 회전율 | 일별 실제 거래대금 / 전일 시가총액 | 유통시총 회전율과 구분 |
| 회전율 급증 | 당일 회전율 / 직전 20거래일 평균 회전율 | 평균에서 당일 제외, 20일 warm-up |
| 5일 순매수 강도 | 5일 기관·외인 합산 순매수 / 5일 구간 직전 시총 | 5일 중 결측 발생 시 미산출 |
| 상대강도 | 20일 종목 수익률 − 동일시장 벤치마크 수익률 | 공통 관측일·동일 수익률 기준 |
| 베타 | 60일 Cov(종목, 지수) / Var(지수) | 최소 관측수, 0분산 시 미산출 |
| Leader / Laggard | 테마 내 상대강도·회전율·거래대금 점유율 비교 | 비교가능 시장 안에서 산출 |
| Theme Flow Score | 수급 40% + 회전율 30% + 상대강도 30% 백분위 | 임시 가중치; 검증 후 확정 |

지표별 관측 가능성과 편입 커버리지를 함께 표시해야 합니다.
수급 미지원 해외 시장을 국내 수급 점수와 같은 이름으로 순위 매기지 않습니다.
초기 해외는 별도 Momentum Score로 표시하고, 공통 수급 데이터 확보 후 통합을 검토합니다.
테마 종목 수가 2~3개인 초기 후보군은 순위 안정성이 낮으므로 유니버스 확장이 필요합니다.
최종 가중치는 walk-forward 검증, 거래비용 및 리밸런싱 시차를 반영해 결정합니다.

## 7. 검증 및 실행 한계

```bash
python -m unittest discover -s tests -v
```

14개 오프라인 테스트: 매핑 검증, 결측/0 구분, 음수 거래량, 중복일자,
수급 정렬, 부분 실패, 캐시, 전체 실패, 무보간 수익률, 재시도, 합성 데이터 재현성, 기준지수 중복 제거, 공급자 열 매핑·종료일 포함·당일 수급 보호.
테스트는 실제 공급자 통신 성공을 증명하지 않습니다.
이 패키지 작성 환경에서는 공급자 라이브러리 설치 및 실데이터 연결 검증 여부를
`VALIDATION.md`에 별도 기록합니다.

## 8. 공식 참고 자료

- pykrx API 및 KRX 환경변수: https://github.com/sharebook-kr/pykrx
- pykrx 1.2.8 로그인 정책 대응: https://github.com/sharebook-kr/pykrx/releases
- FinanceDataReader: https://github.com/FinanceData/FinanceDataReader
- yfinance download (종료일 exclusive): https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html

공개 라이브러리의 이용 조건 및 원천 데이터 재배포 조건은 실서비스 전 확인해야 합니다.
