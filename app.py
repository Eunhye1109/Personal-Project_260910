# -*- coding: utf-8 -*-
"""
게임·영상물 등급분류 분석 대시보드 (PRD 6.1)

화면 하나가 하나의 분석 질문에 대응하도록 구성하였다.
해당 질문에 답하지 않는 그래프는 포함하지 않는다.

  1 등급 결정 기준          등급은 무엇을 기준으로 결정되는가
  2 등급 상향 요인 항목      등급 상향을 유발한 항목은 무엇이며 종별로 차이가 있는가
  3 신청등급 대비 조정       신청등급과 결정등급은 어느 지점에서 달라지는가
  4 매체 간 판정 차이        동일한 내용 수준에서 매체에 따라 등급이 달라지는가
  5 공개 데이터의 포괄 범위   공개된 데이터는 게임물 등급분류 전체의 어느 정도인가
  6 개별 건 조회            특정 조건에 해당하는 개별 건을 직접 확인한다

수치와 해석 문장은 모두 `src/dashboard_calc.py` 에서 산출한다. 화면은 표현만 담당한다.
리포트와 화면이 동일한 수치를 제시하도록 하기 위한 구조이다.

**색은 역할로 정한다** (검증된 기본 팔레트, 색맹 대비 검사 통과)
  · 영상물·위원회 = 파랑, 게임물 = 주황, 자체등급분류 = 보라. 화면을 옮겨도 색이 바뀌지 않는다
  · 크기(교차표·히트맵)는 한 색의 밝기 단계로만. 무지개 배색을 쓰지 않는다
  · 상향/하향처럼 방향이 있는 것만 빨강↔파랑에 중립 회색

실행
    streamlit run app.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import dashboard_calc as calc  # noqa: E402

st.set_page_config(page_title="게임·영상물 등급분류 분석", page_icon="🎬", layout="wide")

# ───────────────────────────────────────── 색·마크 규칙
SURFACE = "#fcfcfb"      # 그래프 바탕
INK = "#0b0b0b"          # 본문 글자
SECOND = "#52514e"       # 보조 글자
MUTED = "#898781"        # 축·눈금
GRID = "#e1e0d9"         # 격자 (실선 헤어라인)
AXIS = "#c3c2b7"

BLUE, ORANGE, VIOLET, RED = "#2a78d6", "#eb6834", "#4a3aa7", "#e34948"
COLOR = {"영상물": BLUE, "게임물": ORANGE, "위원회": ORANGE, "자체등급분류": VIOLET}
# 방향이 있는 것: 두 극은 빨강↔파랑, 가운데는 중립 회색
ADJUST_COLOR = {"신청대로": MUTED, "상향": RED, "하향": BLUE}

# 크기를 나타내는 색은 한 색의 밝기 단계로만 (무지개 금지)
BLUE_SCALE = ["#f4f8fe", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#104281"]
ORANGE_SCALE = ["#fdf3ee", "#fad9c8", "#f6bb9d", "#f19a70", "#eb6834", "#c3521f", "#8f3a15"]

FONT = 'system-ui, -apple-system, "Segoe UI", "Malgun Gothic", sans-serif'

_axis = dict(showgrid=False, zeroline=False, linecolor=AXIS, linewidth=1,
             ticks="outside", tickcolor=AXIS, ticklen=4,
             tickfont=dict(color=MUTED, size=12), title_font=dict(color=SECOND, size=12))
pio.templates["report"] = go.layout.Template(layout=go.Layout(
    font=dict(family=FONT, size=13, color=INK),
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
    colorway=[BLUE, ORANGE, "#1baf7a", "#eda100", "#e87ba4", "#008300", VIOLET, RED],
    xaxis=_axis,
    yaxis={**_axis, "showgrid": True, "gridcolor": GRID, "gridwidth": 1},
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text="",
                font=dict(color=SECOND, size=12)),
    hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font=dict(family=FONT, size=12, color=INK)),
    margin=dict(t=12, b=8, l=8, r=8),
    bargap=0.3, bargroupgap=0.06, barcornerradius=4,
    colorscale=dict(sequential=BLUE_SCALE),
))
pio.templates.default = "report"

st.markdown(f"""<style>
  .block-container {{ padding-top: 2.2rem; max-width: 1180px; }}
  h1, h2, h3 {{ letter-spacing: -0.02em; }}
  /* 인사이트: 해당 화면의 분석 결과 요약 */
  .insight {{
      background: #f6f8fc; border: 1px solid #e3e9f3; border-left: 3px solid {BLUE};
      border-radius: 8px; padding: 0.95rem 1.15rem; margin: 0.2rem 0 1.4rem;
      color: {INK}; font-size: 0.95rem; line-height: 1.75;
  }}
  .insight .cap {{
      color: {MUTED}; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
      text-transform: uppercase; display: block; margin-bottom: 0.35rem;
  }}
  .insight p {{ margin: 0 0 0.45rem; }}
  .insight p:last-child {{ margin-bottom: 0; }}
  .insight code {{ background: #e8eef8; color: {SECOND}; padding: 0 .25em; }}
  /* 지표 카드 */
  div[data-testid="stMetric"] {{
      background: {SURFACE}; border: 1px solid {GRID}; border-radius: 10px;
      padding: 0.8rem 1rem;
  }}
  div[data-testid="stMetricValue"] {{ font-size: 1.6rem; }}
  div[data-testid="stMetricLabel"] p {{ color: {SECOND}; font-size: 0.85rem; }}
  section[data-testid="stSidebar"] {{ border-right: 1px solid {GRID}; }}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner="데이터를 불러오는 중입니다…")
def load_all():
    return calc.load("kmrb"), calc.load("grac"), calc.load("self")


def pct(x: float, d: int = 1) -> str:
    return "해당 없음" if pd.isna(x) else f"{x * 100:.{d}f}%"


def note(text: str) -> None:
    """화면 상단 모집단 표기. 현재 보고 있는 대상을 항상 명시한다 (PRD 6.1 공통)."""
    st.caption(f"📌 {text}")


def insight(lines: list[str]) -> None:
    """해당 화면의 분석 결과 요약. 고정 문구가 아니라 현재 필터 조건으로 재산출한 문장이다."""
    if not lines:
        return

    def md(s: str) -> str:
        """산출부가 반환한 문장의 강조·코드 표기만 HTML 로 변환한다."""
        s = re.sub(r"[*][*](.+?)[*][*]", lambda m: f"<strong>{m.group(1)}</strong>", s)
        return re.sub(r"[`](.+?)[`]", lambda m: f"<code>{m.group(1)}</code>", s)

    body = "".join(f"<p>{md(line)}</p>" for line in lines)
    st.markdown(f'<div class="insight"><span class="cap">분석 결과 요약</span>{body}</div>',
                unsafe_allow_html=True)


def show(fig, height: int = 360) -> None:
    """공통 표현 규칙(선 두께·마커 크기·여백)을 적용하여 출력한다."""
    fig.update_layout(height=height, barcornerradius=4)
    fig.update_traces(selector=dict(type="scatter"), line_width=2, marker_size=8)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def empty_guard(df, msg: str = "해당 조건에 부합하는 건이 없습니다. 좌측 필터의 범위를 확대하시기 바랍니다.") -> bool:
    """N-4: 빈 화면 대신 안내 문구."""
    if df is None or len(df) == 0:
        st.info(msg)
        return True
    return False


# ───────────────────────────────────────── 사이드바
kmrb, grac, selfd = load_all()

st.sidebar.title("게임·영상물 등급분류")
screen = st.sidebar.radio(
    "화면",
    ["① 등급 결정 기준", "② 등급 상향 요인", "③ 신청등급 대비 조정",
     "④ 매체 간 판정 차이", "⑤ 공개 데이터 포괄 범위", "⑥ 개별 건 조회"],
    label_visibility="collapsed")

st.sidebar.divider()
st.sidebar.subheader("공통 필터")

yr_lo = int(min(kmrb["rt_year"].min(), grac["rated_year"].min()))
yr_hi = int(max(kmrb["rt_year"].max(), grac["rated_year"].max()))
years = st.sidebar.slider("기간 (등급분류 연도)", yr_lo, yr_hi, (yr_lo, yr_hi))

kinds = st.sidebar.multiselect(
    "영상물 종별", sorted(kmrb["kindName"].dropna().astype(str).unique()), help="비우면 전체")
platforms = st.sidebar.multiselect(
    "게임물 플랫폼", sorted(grac["platform"].dropna().astype(str).unique()), help="비우면 전체")
drop_adult = st.sidebar.checkbox(
    "성인물 제외", value=False,
    help="성인물은 내용정보와 무관하게 사실상 전건이 청소년관람불가에 해당하므로, "
         "제외하지 않으면 다른 종별의 특성이 드러나지 않는다 (PRD 5.3 함정 3)")

K = calc.filter_kmrb(kmrb, years=years, kinds=kinds, drop_adult=drop_adult)
G = calc.filter_grac(grac, years=years, platforms=platforms)

st.sidebar.divider()
st.sidebar.caption(f"영상물 {len(K):,} / {len(kmrb):,}건\n\n게임물 {len(G):,} / {len(grac):,}건")
st.sidebar.caption("영상물등급위원회·게임물관리위원회 Open API 전량 수집분이다. "
                   "자체등급분류(76,409건)는 분석 대상이 아닌 비교군이며 화면 ⑤ 에서만 사용한다.")


def scope_line(media: str = "영상물") -> str:
    parts = [f"{media} {len(K if media == '영상물' else G):,}건", f"{years[0]}년부터 {years[1]}년까지"]
    if media == "영상물":
        if drop_adult:
            parts.append("성인물 제외")
        if kinds:
            parts.append("종별 " + ", ".join(kinds))
    elif platforms:
        parts.append("플랫폼 " + ", ".join(platforms))
    return " · ".join(parts)


# ───────────────────────────────────────── 화면 1
def screen_rule() -> None:
    st.header("등급 결정 기준: 등급은 무엇을 기준으로 결정되는가")
    note(scope_line())
    if empty_guard(K):
        return
    insight(calc.insight_rule(K))

    m = calc.rule_match(K)
    tot = m[m["표기 체계"] == "전체"].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("전체 일치율", pct(tot["일치율"], 2),
              help="내용정보 최고값에 대응하는 등급과 실제 결정등급이 일치하는 비율")
    for _, r in m[m["표기 체계"] != "전체"].iterrows():
        (c2 if r["표기 체계"] == "단계표기" else c3).metric(
            f"{r['표기 체계']} ({int(r['건수']):,}건)", pct(r["일치율"], 3))

    st.subheader("내용정보 최고값 × 결정 등급")
    ct = calc.rule_crosstab(K)
    if not empty_guard(ct):
        fig = px.imshow(ct, aspect="auto", color_continuous_scale=BLUE_SCALE,
                        labels={"x": "결정 등급", "y": "", "color": "건수"})
        txt = ct.map(lambda v: f"{v:,}" if v else "")
        fig.update_traces(xgap=2, ygap=2, text=txt.values, texttemplate="%{text}",
                          textfont_size=13,
                          hovertemplate="최고값 %{y} · %{x}<br>%{z:,}건<extra></extra>")
        fig.update_xaxes(side="bottom", ticks="")
        fig.update_yaxes(ticks="")
        fig.update_layout(coloraxis_showscale=False)
        show(fig, 360)
        st.caption("대각선에만 값이 분포한다. 이는 설명 관계가 아니라 두 값이 동일함을 의미한다.")

    st.subheader("규칙이 예외 없이 적용된 시점")
    by = calc.rule_by_year(K)
    if not empty_guard(by):
        fig = px.line(by, x="rt_year", y="일치율", markers=True,
                      labels={"rt_year": "등급분류 연도", "일치율": "일치율"})
        fig.update_traces(line_color=BLUE, marker_color=BLUE,
                          hovertemplate="%{x}년<br>일치율 %{y:.2%}<extra></extra>")
        fig.update_yaxes(tickformat=".1%", range=[0.985, 1.002])
        show(fig, 300)
        st.caption("표기 체계가 `1단계~5단계` 에서 `전체관람가~제한상영가` 로 변경된 "
                   "2017년 5월 이후에는 예외가 확인되지 않는다.")

    ex = calc.rule_exceptions(K)
    if len(ex):
        with st.expander(f"규칙과 불일치한 {int(ex['건수'].sum()):,}건의 구성 (표)"):
            st.dataframe(ex, width="stretch", hide_index=True)


# ───────────────────────────────────────── 화면 2
def screen_reason() -> None:
    st.header("등급 상향 요인 항목: 종별에 따른 차이")
    cov = calc.reason_coverage(K)
    note(f"{scope_line()} · 결정사유가 기록된 {cov['기록건수']:,}건({pct(cov['기록률'])}) · "
         f"기록 구간 {cov['시작']}년부터 {cov['끝']}년까지")
    if cov["기록건수"] == 0:
        st.info("해당 조건에는 결정사유가 기록된 건이 없습니다. 대상 기간을 확대하시기 바랍니다.")
        return
    insight(calc.insight_reason(K))

    freq = calc.reason_freq(K)
    st.subheader("등급 결정 항목으로 지목된 비율")
    fig = px.bar(freq, x="항목", y="비율", labels={"비율": "", "항목": ""})
    fig.update_traces(marker_color=BLUE,
                      hovertemplate="%{x}<br>%{y:.1%} · %{customdata[0]:,}건<extra></extra>",
                      customdata=freq[["건수"]])
    fig.update_yaxes(tickformat=".0%")
    show(fig, 300)

    st.subheader("종별 차이")
    tab = calc.reason_by_kind(K)
    if not empty_guard(tab, "표본이 100건 이상인 종별이 존재하지 않습니다 (N-5)."):
        fig = px.imshow(tab, aspect="auto", color_continuous_scale=ORANGE_SCALE,
                        labels={"x": "결정 항목", "y": "", "color": "지목률"})
        txt = tab.map(lambda v: f"{v:.0%}" if v >= 0.005 else "")
        fig.update_traces(xgap=2, ygap=2, text=txt.values, texttemplate="%{text}",
                          textfont_size=13,
                          hovertemplate="%{y} · %{x}<br>지목률 %{z:.1%}<extra></extra>")
        fig.update_xaxes(side="bottom", ticks="")
        fig.update_yaxes(ticks="")
        fig.update_layout(coloraxis_showscale=False)
        show(fig, 80 + 44 * len(tab))
        st.caption("표본이 100건 미만인 종별은 제시하지 않는다 (N-5).")

    st.subheader("시기별 변화")
    byy = calc.reason_by_year(K)
    if not empty_guard(byy, "표본이 100건 이상인 연도가 존재하지 않습니다 (N-5)."):
        long = byy.reset_index().melt(id_vars="rt_year", var_name="항목", value_name="지목률")
        order = calc.reason_freq(K)["항목"].tolist()
        fig = px.line(long, x="rt_year", y="지목률", facet_col="항목", facet_col_wrap=4,
                      category_orders={"항목": order}, markers=True,
                      labels={"rt_year": ""})
        fig.update_traces(line_color=BLUE, marker_color=BLUE,
                          hovertemplate="%{x}년 %{y:.1%}<extra></extra>")
        fig.update_yaxes(tickformat=".0%", matches="y")
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1], font_size=12))
        show(fig, 420)
        st.caption("항목별로 구분하여 제시한다. 일곱 개 계열을 한 축에 중첩할 경우 판독이 어렵다.")


# ───────────────────────────────────────── 화면 3
def screen_adjust() -> None:
    st.header("신청등급 대비 조정: 신청등급과 결정등급의 차이")
    note(f"{scope_line()} · 신청등급이 기록된 건")
    if empty_guard(K):
        return
    insight(calc.insight_adjust(K))

    s = calc.adjust_summary(K)
    if empty_guard(s):
        return
    for col, (_, r) in zip(st.columns(3), s.iterrows()):
        col.metric(r["구분"], f"{int(r['건수']):,}건", pct(r["비율"]), delta_color="off")

    st.subheader("종별 조정률")
    bk = calc.adjust_by_kind(K)
    if not empty_guard(bk, "표본이 200건 이상인 종별이 존재하지 않습니다 (N-5)."):
        fig = go.Figure()
        for name, color in (("상향", RED), ("하향", BLUE)):
            fig.add_bar(x=bk["종별"], y=bk[name], name=name, marker_color=color,
                        hovertemplate="%{x} " + name + " %{y:.1%}<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(barmode="group")
        show(fig, 340)

    st.subheader("신청등급 수준별 상향률")
    bh = calc.adjust_by_hope(K)
    if not empty_guard(bh, "표본이 200건 이상인 신청등급이 존재하지 않습니다 (N-5)."):
        fig = px.bar(bh, x="신청등급", y="상향", labels={"상향": ""})
        fig.update_traces(marker_color=RED, customdata=bh[["건수"]],
                          hovertemplate="%{x} 신청<br>상향률 %{y:.1%} · %{customdata[0]:,}건<extra></extra>")
        fig.update_yaxes(tickformat=".0%", title="상향률")
        show(fig, 320)

    st.subheader("조정된 건의 내용정보 구성")
    prof = calc.adjust_profile(K)
    if not empty_guard(prof):
        long = prof.reset_index(names="항목").melt(id_vars="항목", var_name="조정", value_name="평균 단계")
        fig = px.bar(long, x="항목", y="평균 단계", color="조정", barmode="group",
                     color_discrete_map=ADJUST_COLOR,
                     category_orders={"조정": ["신청대로", "상향", "하향"]})
        fig.update_traces(hovertemplate="%{x} · %{fullData.name}<br>평균 %{y:.2f}단계<extra></extra>")
        show(fig, 340)
        st.caption("상향은 '내용정보 최고값 > 신청등급'과 동치이므로, 신청등급 자체를 설명 변수로 "
                   "사용할 경우 항등식이 된다. 여기에서 확인하는 것은 신청인이 어느 항목에서 "
                   "등급을 낮게 예측하는 경향이 있는가이다.")


# ───────────────────────────────────────── 화면 4
def screen_media() -> None:
    st.header("매체 간 판정 차이: 동일한 내용 수준에서의 등급 비교")
    st.markdown(
        "두 기관은 내용정보를 서로 다른 형태로 제공한다. 영상물등급위원회는 항목별 1~5단계 수준을, "
        "게임물관리위원회는 해당 항목의 명칭만을 제시한다. 두 체계는 직접 비교가 불가능하므로 "
        "**영상물을 이진화하여 기준을 맞추고**, 명칭이 동일한 4개 항목"
        "(선정성·폭력성·공포·약물)에 한정하여 비교한다.")

    th_label = st.radio(
        "영상물 이진화 기준",
        ["3단계(다소높음) 이상을 보유로 간주", "4단계(높음) 이상을 보유로 간주"],
        horizontal=True)
    th = int(th_label[0])
    if th == 4:
        st.error("**4단계 기준은 비교 목적으로 사용할 수 없다.** 영상물은 4단계가 곧 "
                 "청소년관람불가에 해당하므로, 이 기준으로 이진화하면 영상물의 비율이 정의상 "
                 "100%로 산출된다. 이는 비교가 아니라 항등식을 재확인하는 것에 지나지 않는다 "
                 "(PRD R-10).", icon="🚫")

    both, info = calc.media_frame(K, G, th)
    note(f"영상물 {info['영상물_비교표본']:,}건(성인물·주제/대사/모방위험 보유 {info['영상물_제외']:,}건 제외) · "
         f"게임물 {info['게임물_비교표본']:,}건(등급취소·언어/범죄/사행성 보유 {info['게임물_제외']:,}건 제외) · "
         f"{years[0]}년부터 {years[1]}년까지")
    if empty_guard(both):
        return
    cc = calc.combo_compare(both)
    insight(calc.insight_media(both, cc, th))
    st.caption("비교 대상에 포함되지 않은 항목을 보유한 건은 **양측에서 대칭적으로 제외한다.** "
               "제외하지 않을 경우 사행성 단독으로 청소년 이용 제한에 해당하는 게임물(97.1%)이 "
               "'(없음)' 구간에 포함되어 결과가 왜곡된다.")

    st.subheader("동일한 보유 조합 간 비교")
    if empty_guard(cc, "양측 모두 50건 이상인 조합이 존재하지 않습니다 (N-5)."):
        return
    fig = go.Figure()
    for media in ["영상물", "게임물"]:
        fig.add_bar(x=cc["조합"], y=cc[media], name=media, marker_color=COLOR[media],
                    customdata=cc[[f"{media} n"]],
                    hovertemplate="%{x} · " + media +
                                  "<br>청소년 이용 제한 %{y:.1%} · %{customdata[0]:,}건<extra></extra>")
    fig.update_yaxes(tickformat=".0%", title="청소년 이용 제한 비율")
    fig.update_layout(barmode="group")
    show(fig, 380)

    c1, c2 = st.columns(2)
    c1.metric("비교 가능한 조합", f"{len(cc)}개",
              f"게임물의 제한 비율이 높은 조합 {int((cc['차이'] > 0).sum())}개", delta_color="off")
    c2.metric("평균 차이", f"{cc['차이'].mean() * 100:+.1f}%p", "게임물 − 영상물", delta_color="off")

    st.subheader("단독 보유 항목별 비교")
    solo = calc.solo_compare(both)
    if not empty_guard(solo, "단독 보유 표본이 충분하지 않습니다 (N-5)."):
        fig = go.Figure()
        for media in ["영상물", "게임물"]:
            fig.add_bar(x=solo["항목"], y=solo[media], name=media, marker_color=COLOR[media],
                        text=solo[media].map(lambda v: pct(v)), textposition="outside",
                        hovertemplate="%{x} 단독 · " + media + " %{y:.1%}<extra></extra>")
        fig.update_yaxes(tickformat=".0%", title="청소년 이용 제한 비율")
        fig.update_layout(barmode="group", uniformtext=dict(minsize=10, mode="hide"))
        show(fig, 340)
        st.caption("다른 항목이 혼재되지 않으므로 해당 항목 단독의 영향을 확인할 수 있다.")

    with st.expander("조합별 수치 및 항목별 보유율 (표)"):
        st.dataframe(cc.style.format({"영상물": "{:.1%}", "게임물": "{:.1%}", "차이": "{:+.1%}",
                                      "영상물 n": "{:,}", "게임물 n": "{:,}"}),
                     width="stretch", hide_index=True)
        st.caption("보유율 자체의 차이는 매체의 성격 차이에서 기인한다. 위 비교는 보유 상태가 "
                   "동일한 건에 한정한 결과이다.")
        st.dataframe(calc.hold_rate(both).style.format(
            {"영상물": "{:.1%}", "게임물": "{:.1%}", "차이": "{:+.1%}"}),
            width="stretch", hide_index=True)

    st.info("**한계**: 3단계라는 절단 기준 자체에 실증적 근거가 있는 것은 아니다. 영상물의 "
            "5단계 체계를 게임물의 보유·미보유 체계에 대응시키려면 특정 지점에서 절단이 "
            "필요하나, 그 지점은 데이터로부터 도출되지 않는다. 따라서 '게임물의 판정이 더 "
            "엄격하다'는 결론은 이 절단 기준을 전제로 할 때에만 성립한다.", icon="ℹ️")


# ───────────────────────────────────────── 화면 5
def screen_rater() -> None:
    st.header("공개 데이터의 포괄 범위: 게임물 등급분류 전체 대비 비중")
    same, lo, hi = calc.rater_period(grac, selfd)
    note(f"자체등급분류 비교군은 {lo:%Y-%m-%d}부터 {hi:%Y-%m-%d}까지 약 7주간의 자료에 한정되므로 "
         f"위원회 분류분도 동일 기간으로 한정하여 비교한다 · 본 화면은 좌측 기간 필터를 적용하지 않는다")
    insight(calc.insight_rater(grac, selfd))

    vol = calc.rater_volume(grac, selfd)
    n_a, n_s = int(vol.loc[0, "건수"]), int(vol.loc[1, "건수"])
    c1, c2, c3 = st.columns(3)
    c1.metric("위원회 심의", f"{n_a:,}건", "같은 기간", delta_color="off")
    c2.metric("자체등급분류", f"{n_s:,}건", f"약 {n_s / n_a:,.0f}배", delta_color="off")
    c3.metric("공개분의 비중", pct(vol.loc[0, "비중"], 2), "Open API 로 확인 가능한 범위",
              delta_color="off")

    fig = go.Figure()
    for name, n in (("위원회", n_a), ("자체등급분류", n_s)):
        fig.add_bar(y=[""], x=[n], name=name, orientation="h", marker_color=COLOR[name],
                    hovertemplate=name + " %{x:,}건<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.55, showlegend=True)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    show(fig, 150)
    st.caption(f"동일 기간 전체를 100으로 할 때 위원회 심의분은 {pct(vol.loc[0, '비중'], 2)}에 해당한다.")

    st.subheader("분류 주체별 등급 분포")
    gr = calc.rater_grade(grac, selfd)
    long = gr.reset_index(names="등급").melt(id_vars="등급", var_name="매긴 주체", value_name="비중")
    fig = px.bar(long, x="등급", y="비중", color="매긴 주체", barmode="group",
                 color_discrete_map=COLOR, labels={"비중": ""})
    fig.update_traces(hovertemplate="%{x} · %{fullData.name}<br>%{y:.1%}<extra></extra>")
    fig.update_yaxes(tickformat=".0%")
    show(fig, 340)

    st.subheader("분류 주체별 내용정보 보유율")
    cn = calc.rater_content(grac, selfd)
    long = cn.reset_index(names="항목").melt(id_vars="항목", var_name="매긴 주체", value_name="보유율")
    fig = px.bar(long, x="항목", y="보유율", color="매긴 주체", barmode="group",
                 color_discrete_map=COLOR, labels={"보유율": ""})
    fig.update_traces(hovertemplate="%{x} · %{fullData.name}<br>보유율 %{y:.1%}<extra></extra>")
    fig.update_yaxes(tickformat=".0%")
    show(fig, 340)

    st.caption("비교군 자료는 본 분석에서 수집한 것이 아니라 별도 업무 과정에서 확보된 파일이며 "
               "재수집이 불가능하다. 따라서 추세 분석에는 사용하지 않고 특정 시점의 규모 비교에만 "
               "사용한다 (PRD R-12).")


# ───────────────────────────────────────── 화면 6
RAW_COLS = {
    "영상물": ["rtNo", "useTitle", "kindName", "rt_date", "gradeName", "hopeGradeName",
            "rtCoreHarmRsnNm", "content_max", "prodcNatnlName", "runtime_min"]
    + [f"내용_{n}" for n in calc.KMRB_ITEMS],
    "게임물": ["rateno", "gametitle", "entname", "genre", "platform", "rated_date",
            "givenrate", "descriptors", "is_canceled"]
    + [f"내용_{n}" for n in calc.GRAC_ITEMS],
}


def screen_raw() -> None:
    st.header("개별 건 조회")
    c1, c2 = st.columns([1, 2])
    media = c1.radio("매체", ["영상물", "게임물"], horizontal=True)
    q = c2.text_input("제목 검색", placeholder="제목의 일부를 입력하십시오")

    d = (K if media == "영상물" else G)[RAW_COLS[media]]
    if q:
        col = "useTitle" if media == "영상물" else "gametitle"
        d = d[d[col].astype(str).str.contains(q, case=False, na=False)]

    note(scope_line(media) + (f" · 제목에 '{q}' 포함 {len(d):,}건" if q else ""))
    if empty_guard(d):
        return

    st.dataframe(d.head(1000), width="stretch", hide_index=True)
    if len(d) > 1000:
        st.caption(f"화면에는 상위 1,000건만 표시된다. 내려받기에는 조건에 해당하는 {len(d):,}건 전체가 포함된다.")
    st.download_button(
        f"조건에 해당하는 {len(d):,}건 내려받기 (CSV)",
        d.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{'kmrb' if media == '영상물' else 'grac'}_{years[0]}_{years[1]}.csv",
        mime="text/csv")


# ───────────────────────────────────────── 실행
{"① 등급 결정 기준": screen_rule,
 "② 등급 상향 요인": screen_reason,
 "③ 신청등급 대비 조정": screen_adjust,
 "④ 매체 간 판정 차이": screen_media,
 "⑤ 공개 데이터 포괄 범위": screen_rater,
 "⑥ 개별 건 조회": screen_raw}[screen]()

st.divider()
st.caption(
    "게임물관리위원회·영상물등급위원회 Open API 전량 수집분 "
    f"(영상물 {len(kmrb):,}건 2009~2026 · 게임물 {len(grac):,}건 2007~2026). "
    "BI 분석가 과정 개인 프로젝트. 작성자 최은혜.")
