"""ATF dashboard: readable overview first, collection diagnostics on demand."""
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from atf.demo import demo_panel
from atf.pipeline import Pipeline
from atf.presentation import cumulative_flow, price_series, stock_summary
from atf.universe import load_universe, select

ROOT = Path(__file__).resolve().parent
COLORS = ['#1264C4', '#17A398', '#D48A17', '#7D62BC', '#D55D73']
st.set_page_config(page_title='ATF | 테마 흐름', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.stApp { background: #F5F7FB; }
[data-testid="stMainBlockContainer"] { max-width: 1440px; padding: 2rem 2.5rem 3rem; }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E1E7F0; }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1.7rem; }
html, body, [class*="st-"] { font-family: -apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif; }
[data-testid="stMetric"] { background: white; border: 1px solid #E0E7F0; border-radius: 12px; padding: 18px 20px; }
[data-testid="stMetricLabel"] p { color: #52657B; font-size: 15px; }
[data-testid="stMetricValue"] { color: #162D48; font-size: 30px; font-weight: 700; }
[data-testid="stVerticalBlockBorderWrapper"] > div { border-color: #E0E7F0; border-radius: 12px; }
.st-key-price_card, .st-key-flow_card { background: #FFFFFF; border-radius: 12px; }
h1, h2, h3 { color: #162D48; letter-spacing: -.035em; }
h3 { font-size: 20px !important; }
[data-testid="stCaptionContainer"] { color: #52657B; }
[data-testid="stTabs"] button p { font-size: 16px; font-weight: 600; }
.atf-brand { font-size: 25px; font-weight: 800; color: #1264C4; margin-bottom: 4px; }
.atf-subtitle { font-size: 14px; color: #64758A; margin-bottom: 24px; }
.atf-eyebrow { font-size: 12px; font-weight: 700; color: #1264C4; letter-spacing: .12em; margin-bottom: 7px; }
.atf-title { font-size: 31px; font-weight: 750; color: #162D48; line-height: 1.3; margin: 0 0 9px; }
.atf-description { font-size: 15px; color: #52657B; line-height: 1.6; margin-bottom: 18px; }
.atf-badge { display: inline-block; font-size: 13px; font-weight: 650; color: #8B580B;
background: #FFF2D5; border: 1px solid #F1D99D; padding: 7px 12px; border-radius: 7px; }
.atf-badge-live { color: #14664E; background: #E6F5ED; border-color: #BEE1CE; }
@media (max-width: 768px) {
 [data-testid="stMainBlockContainer"] { padding: 1.3rem 1rem; }
 .atf-title { font-size: 25px; }
 [data-testid="stMetric"] { padding: 13px 15px; }
}
</style>''', unsafe_allow_html=True)

config, master = load_universe(ROOT / 'config/themes.json')
yesterday = datetime.now(ZoneInfo('Asia/Seoul')).date() - timedelta(days=1)

with st.sidebar:
    st.markdown('<div class="atf-brand">ATF</div><div class="atf-subtitle">테마 자금 흐름 모니터</div>', unsafe_allow_html=True)
    st.caption('분석할 테마')
    mega = st.selectbox('대분류', list(config['themes']),
        format_func=lambda key: config['themes'][key]['label'])
    subs = config['themes'][mega]['subthemes']
    sub = st.selectbox('세부 테마', list(subs), format_func=lambda key: subs[key]['label'])
    market = st.radio('시장 범위', ['전체', '국내', '미국'], horizontal=True)
    st.divider()
    mode = st.radio('데이터 모드', ['데모', '실제 데이터'], horizontal=True,
        help='데모는 합성 데이터이며 외부 데이터를 수집하지 않습니다.')
    with st.expander('조회 기간 · 수집 옵션', expanded=False):
        start = st.date_input('시작일', yesterday - timedelta(days=90))
        end = st.date_input('종료일', yesterday)
        refresh = st.checkbox('저장된 캐시 무시', value=False)
    run = st.button('실제 데이터 수집' if mode == '실제 데이터' else '데모 다시 보기',
                    type='primary', width='stretch')
    st.caption('데모는 테마 선택 시 바로 표시됩니다. 실제 데이터는 버튼을 눌러 수집합니다.')

universe = select(config, master, mega, sub)
if market != '전체':
    market_code = 'KR' if market == '국내' else 'US'
    universe = [item for item in universe if item.market == market_code]
key = (mode, mega, sub, market, str(start), str(end))

left, right = st.columns([4, 1])
with left:
    st.markdown(f'<div class="atf-eyebrow">ATF / THEME MONITOR</div>'
        f'<div class="atf-title">{escape(subs[sub]["label"])}</div>'
        f'<div class="atf-description">{escape(config["themes"][mega]["label"])} · '
        '종목별 가격과 기관·외국인 수급을 한 화면에서 확인합니다.</div>', unsafe_allow_html=True)
with right:
    badge = 'DEMO · 합성 데이터' if mode == '데모' else 'LIVE · 실제 수집 모드'
    extra = '' if mode == '데모' else ' atf-badge-live'
    st.markdown(f'<div class="atf-badge{extra}">{badge}</div>', unsafe_allow_html=True)

if mode == '데모':
    st.warning('예시 화면입니다. 아래 가격·수급·등락률은 합성 데이터이며 실제 시장 상황을 나타내지 않습니다.', icon='⚠️')
else:
    st.caption('무료 수집 경로를 사용합니다. 해외 기관·외국인 수급은 지원하지 않으며, 국내 수급에는 KRX 인증이 필요합니다.')

if start > end:
    st.error('종료일이 시작일보다 빠릅니다. 조회 기간을 확인하세요.')
    st.stop()
if not universe:
    st.info('선택한 시장에 포함된 종목이 없습니다. 시장 범위를 변경하세요.')
    st.stop()

if mode == '데모':
    panel = demo_panel(universe, start, end)
    status = None
else:
    if run:
        with st.spinner('선택한 종목의 데이터를 수집하고 있습니다…'):
            panel, status = Pipeline(ROOT / 'data/cache').collect(universe, start, end, refresh)
            st.session_state['live_result'] = (key, panel, status)
    stored = st.session_state.get('live_result')
    if not stored or stored[0] != key:
        st.info('왼쪽에서 테마와 기간을 선택한 뒤 「실제 데이터 수집」을 누르세요.')
        with st.expander('선택한 테마의 구성 종목'):
            st.dataframe([{'종목명': item.name, '종목코드': item.ticker,
                '시장': '국내' if item.market == 'KR' else '미국'} for item in universe],
                hide_index=True, width='stretch')
        st.stop()
    _, panel, status = stored

if panel.empty:
    st.error('조회된 데이터가 없습니다. 기간 또는 수집 상태를 확인하세요.')
    if status is not None:
        st.dataframe(status, hide_index=True, width='stretch')
    st.stop()

panel = panel.sort_values(['date', 'instrument_id'])
last_date = panel.date.max()
kr_rows = panel[panel.market.eq('KR')]
coverage = f'{kr_rows.flow_complete.mean():.0%}' if not kr_rows.empty else '해당 없음'
k1, k2, k3 = st.columns(3)
k1.metric('조회 종목', f'{panel.instrument_id.nunique()}개')
k2.metric('최근 관측일', last_date.strftime('%Y.%m.%d'))
k3.metric('국내 수급 관측률', coverage)
st.caption(f'조회 기간 {start:%Y.%m.%d} — {end:%Y.%m.%d} · '
    f'선택 {len(universe)}개 중 수집 {panel.instrument_id.nunique()}개 · 수급 관측률은 국내 종목의 일별 행 기준')


def chart_layout(fig, y_title, height=340):
    fig.update_layout(height=height, margin=dict(l=12, r=15, t=12, b=12),
        paper_bgcolor='white', plot_bgcolor='white',
        font=dict(family='Arial, Malgun Gothic, sans-serif', size=14, color='#3D5067'),
        legend=dict(orientation='h', y=1.14, x=0, font=dict(size=14)),
        hovermode='x unified', yaxis_title=y_title,
        xaxis=dict(showgrid=False, tickformat='%m/%d'),
        yaxis=dict(gridcolor='#EDF1F6', zerolinecolor='#C7D2E1'))
    return fig


overview, stocks, details = st.tabs(['가격 · 수급', '종목 현황', '데이터 점검'])
with overview:
    with st.container(border=True, key='price_card'):
        st.subheader('종목별 가격 흐름')
        st.caption('종목별 첫 유효 가격 = 100 · 수정종가 우선 · 통화별 가격 기준, 환율 미반영')
        fig = go.Figure()
        for position, (_, group) in enumerate(panel.groupby('instrument_id', sort=False)):
            series, basis = price_series(group)
            observed = series.dropna()
            if observed.empty:
                continue
            fig.add_trace(go.Scatter(x=series.index, y=series / observed.iloc[0] * 100,
                name=group['name'].iloc[0], mode='lines', connectgaps=False,
                line=dict(width=2.8, color=COLORS[position % len(COLORS)]),
                hovertemplate='%{y:.1f}<extra>%{fullData.name}</extra>'))
        st.plotly_chart(chart_layout(fig, '가격 지수'), width='stretch',
            config={'displayModeBar': False}, key='price_chart')
        if last_date < pd.Timestamp(end):
            st.caption('최근 관측일이 조회 종료일보다 앞섭니다. 휴장 또는 수집 지연 여부를 확인하세요.')

    with st.container(border=True, key='flow_card'):
        head, picker = st.columns([2, 2])
        with head:
            st.subheader('기관 · 외국인 순매수')
        ids = list(panel.instrument_id.unique())
        names = panel.drop_duplicates('instrument_id').set_index('instrument_id')['name'].to_dict()
        with picker:
            selected = st.selectbox('수급 확인 종목', ids,
                format_func=lambda value: names[value], label_visibility='collapsed')
        selected_rows = panel[panel.instrument_id.eq(selected)].set_index('date').sort_index()
        view = st.radio('표시 방식', ['일간', '누적'], horizontal=True, label_visibility='collapsed')
        available = selected_rows[['institution_net_buy', 'foreign_net_buy']].notna().any().any()
        if not available:
            st.info('이 종목의 투자자별 수급을 확보하지 못했습니다. 해외 수급 미지원 또는 KRX 인증·수집 상태를 확인하세요.')
        else:
            currency = selected_rows.currency.iloc[0]
            divisor = 100000000 if currency == 'KRW' else 1000000
            unit = '억원' if currency == 'KRW' else '백만 달러'
            flow = go.Figure()
            for column, name, color in [('institution_net_buy', '기관', '#1264C4'),
                                        ('foreign_net_buy', '외국인', '#17A398')]:
                values = selected_rows[column] / divisor
                if view == '누적':
                    values = cumulative_flow(values)
                    flow.add_trace(go.Scatter(x=values.index, y=values, name=name,
                        mode='lines', connectgaps=False, line=dict(color=color, width=2.5)))
                else:
                    flow.add_trace(go.Bar(x=values.index, y=values, name=name, marker_color=color))
            st.plotly_chart(chart_layout(flow, unit, height=290), width='stretch',
                config={'displayModeBar': False}, key='flow_chart')
            st.caption('양수는 순매수, 음수는 순매도입니다. 누적은 결측 이후 표시를 중단하며 국가 간 금액을 합산하지 않습니다.')

with stocks:
    st.subheader('구성 종목 현황')
    st.caption('가격 관측 정보를 보여줍니다. 수급 점수와 Leader / Laggard 순위는 아직 산출하지 않습니다.')
    summary = stock_summary(panel)
    st.dataframe(summary.drop(columns=['instrument_id']), hide_index=True, width='stretch',
        row_height=45, column_config={
            '종목명': st.column_config.TextColumn(width='medium'),
            '관측기간 등락 (%)': st.column_config.NumberColumn(format='%+.1f%%')})
    st.caption('등락률은 각 종목의 첫 유효 가격 대비 마지막 관측일 기준이며, 유효한 수정종가가 없으면 종가를 사용합니다. 배당·환율 기준은 통일하지 않았습니다.')

with details:
    st.subheader('데이터 수집 상태')
    if status is None:
        st.info('현재는 합성 데이터 데모입니다. 실제 공급자 연결 상태를 의미하지 않습니다.')
    else:
        st.dataframe(status.rename(columns={'instrument_id': '종목 ID', 'status': '상태',
            'rows': '관측수', 'last_date': '기준일', 'flow_coverage': '수급 관측률',
            'cap_coverage': '시총 관측률', 'cache_hit': '캐시 사용', 'issues': '상세 오류'}),
            hide_index=True, width='stretch')
    with st.expander('원본 데이터 및 출처'):
        st.dataframe(panel, hide_index=True, width='stretch')
    st.download_button('분석 데이터 CSV 다운로드', panel.to_csv(index=False).encode('utf-8-sig'),
        file_name='atf_demo_panel.csv' if mode == '데모' else 'atf_live_panel.csv')
    with st.expander('테마 정의 · 분석 범위'):
        st.write(config['notice'])
        st.caption('현재는 유니버스 및 수집 점검 단계입니다. Theme Flow Score, 베타, 백테스트는 아직 구현하지 않았습니다.')

st.caption('ATF · Theme Flow Monitor  |  예시 유니버스 기반 · 투자 추천 또는 확정 ETF 바스켓이 아닙니다.')
