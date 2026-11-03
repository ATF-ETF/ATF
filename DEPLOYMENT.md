# ATF Streamlit Cloud 배포

코드 저장소: https://github.com/ATF-ETF/ATF

## 웹에서 배포

1. https://share.streamlit.io 에 로그인합니다.
2. ATF-ETF/ATF 저장소에 접근할 수 있는 GitHub 계정을 연결합니다.
3. Create app에서 다음 항목을 지정합니다.

| 항목 | 값 |
|---|---|
| Repository | ATF-ETF/ATF |
| Branch | main |
| Main file path | app.py |
| Python version | 3.12 |

4. Advanced settings의 Secrets에서 필요한 경우 KRX_ID, KRX_PW를 설정합니다.
   `.streamlit/secrets.example.toml`은 형식 예시이며, 실제 자격증명을 커밋하지 않습니다.
   최상위 Secrets 값은 Streamlit이 환경변수로도 제공하므로 기존 수집 모듈이 사용할 수 있습니다.
5. Deploy를 누르고 초기 설치 로그를 확인합니다.

웹주소는 배포를 완료해야 발급됩니다. GitHub 연결만으로 배포가 완료되지는 않습니다.
기본 실행 모드는 합성 데이터 데모이며, 실제 데이터 수집은 화면에서 명시적으로 실행합니다.
인증을 설정하지 않아도 데모는 동작합니다. 해외 기관/외국인 수급은 이 버전에서 지원하지 않습니다.

## 저장소 자동 점검

`.github/workflows/ci.yml`은 push 또는 PR 시 오프라인 데이터 계약 테스트와 CLI 데모를 실행합니다.
시세 API에 연결하거나 KRX 자격증명을 사용하지 않습니다.
자동 데이터 수집 스케줄러는 이번 배포 연결 작업에서 추가하지 않았습니다.

## 데이터 저장의 범위

Streamlit 서버의 캐시와 CSV는 영구 데이터베이스가 아닙니다.
서버 재시작으로 사라질 수 있으므로 필요한 결과는 CSV로 다운로드하세요.
데이터를 장기 보관하거나 정기 배치 수집하려면 별도 저장소 연동이 필요합니다.

## 공식 문서

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
