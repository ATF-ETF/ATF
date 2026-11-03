"""Stage 1 ingestion inspection UI. Composite scoring is intentionally pending."""
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import streamlit as st
from atf.universe import load_universe, select
from atf.pipeline import Pipeline
from atf.demo import demo_panel

st.set_page_config(page_title='ATF | ACE Theme Flow', layout='wide')
st.title('ATF · ACE Theme Flow')
st.caption('1단계: 테마 유니버스 · 데이터 수집 및 품질 점검')
root = Path(__file__).resolve().parent
config, instruments = load_universe(root/'config/themes.json')
mode = st.sidebar.radio('데이터 모드', ['데모 (합성 데이터)', '실제 데이터 수집'])
mega = st.sidebar.selectbox('Mega Trend', list(config['themes']),
    format_func=lambda x: config['themes'][x]['label'])
subs = config['themes'][mega]['subthemes']
sub = st.sidebar.selectbox('Sub-Theme', list(subs), format_func=lambda x: subs[x]['label'])
universe = select(config, instruments, mega, sub)
markets = st.sidebar.multiselect('시장', ['KR', 'US'], default=['KR', 'US'])
universe = [i for i in universe if i.market in markets]
yesterday = datetime.now(ZoneInfo('Asia/Seoul')).date() - timedelta(days=1)
start = st.sidebar.date_input('시작일', yesterday-timedelta(days=180))
end = st.sidebar.date_input('종료일 (포함)', yesterday)
refresh = st.sidebar.checkbox('캐시 무시', value=False)
st.info(config['notice'])
st.dataframe([i.__dict__ for i in universe], hide_index=True, width='stretch')
# Store results explicitly; ordinary widget reruns do not re-fetch from upstream.
selection_key = (mode, mega, sub, tuple(markets), str(start), str(end))
if st.sidebar.button('수집 / 데모 실행', type='primary'):
    if start > end or not universe:
        st.error('기간 및 선택 시장을 확인하세요.')
    else:
        with st.spinner('데이터 처리 중…'):
            if mode.startswith('데모'):
                panel = demo_panel(universe, start, end)
                status = None
            else:
                panel, status = Pipeline(root/'data/cache').collect(universe, start, end, refresh)
            st.session_state['result'] = (selection_key, panel, status)
result = st.session_state.get('result')
if result and result[0] == selection_key:
    _, panel, status = result
    if mode.startswith('데모'):
        st.warning('합성 데이터입니다. 실제 시장 흐름·순매수·순위로 해석할 수 없습니다.')
    if status is not None:
        st.subheader('수집 상태')
        st.dataframe(status, hide_index=True, width='stretch')
    if panel.empty:
        st.error('반환된 데이터가 없습니다. 실제 모드에서 데모로 자동 대체하지 않습니다.')
    else:
        a, b, c = st.columns(3)
        a.metric('수집 종목', panel.instrument_id.nunique())
        b.metric('수집 마지막 일자', str(panel.date.max().date()))
        c.metric('수급 관측 커버리지', f'{panel.flow_complete.mean():.0%}')
        st.caption('커버리지는 행 기준입니다. 해외 수급 미지원도 결측에 포함됩니다.')
        selected = st.selectbox('종목별 확인', list(panel.instrument_id.unique()))
        data = panel[panel.instrument_id.eq(selected)].set_index('date').sort_index()
        st.subheader('가격 및 기관·외국인 일간 순매수')
        st.line_chart(data[['close']])
        st.bar_chart(data[['institution_net_buy','foreign_net_buy']])
        st.caption('순매수 단위: 해당 시장 통화. 국가별 금액은 합산하지 않습니다.')
        st.dataframe(data, width='stretch')
        st.download_button('현재 패널 CSV', panel.to_csv(index=False).encode('utf-8-sig'),
            file_name='atf_demo_panel.csv' if mode.startswith('데모') else 'atf_live_panel.csv')
        st.caption('Theme Flow Score / Leader·Laggard / 베타는 2단계 산출 예정입니다.')
else:
    st.caption('좌측에서 범위를 선택한 뒤 실행하세요. 선택 변경 시 기존 결과는 숨겨집니다.')
