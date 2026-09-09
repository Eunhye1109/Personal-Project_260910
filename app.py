# -*- coding: utf-8 -*-
"""
게임·영상물 등급분류 분석 대시보드 (PRD 6.1)

**화면 하나가 질문 하나에 답한다.** 강사 피드백에서 나온 원칙이다.
그 질문에 답하지 않는 그래프는 넣지 않는다.

  1 등급 결정 규칙      등급은 무엇으로 정해지는가
  2 무엇이 등급을 올렸나  등급을 끌어올린 항목은 무엇이고 종별로 다른가
  3 신청 대비 조정      신청등급과 결정등급은 어디서 갈리는가
  4 매체 비교          같은 내용 수준에서 매체에 따라 등급이 달라지는가
  5 누가 매기는가       공개된 데이터는 게임물 전체의 얼마만큼인가
  6 원자료             특정 조건의 개별 건을 직접 확인하고 싶다

숫자는 전부 `src/dashboard_calc.py` 에서 계산한다. 화면은 그리기만 한다.
그래야 리포트와 화면이 같은 숫자를 말한다.

실행
    streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import dashboard_calc as calc  # noqa: E402

st.set_page_config(page_title="게임·영상물 등급분류 분석", page_icon="🎬", layout="wide")

# 두 매체를 항상 같은 색으로 둔다. 화면을 옮겨도 눈이 다시 적응하지 않아도 되게.
COLOR = {"영상물": "#3B6FB6", "게임물": "#C2603F",
         "위원회": "#3B6FB6", "자체등급분류": "#C2603F"}


@st.cache_data(show_spinner="데이터를 읽는 중…")
def load_all():
    return calc.load("kmrb"), calc.load("grac"), calc.load("self")


def pct(x: float, d: int = 1) -> str:
    return "—" if pd.isna(x) else f"{x * 100:.{d}f}%"


def note(text: str) -> None:
    """화면 상단 모집단 표기. 지금 무엇을 보고 있는지 늘 적어 둔다 (PRD 6.1 공통)."""
    st.caption(f"📌 {text}")


def empty_guard(df, msg: str = "조건에 해당하는 건이 없습니다. 왼쪽 필터를 넓혀 보세요.") -> bool:
    """N-4 — 빈 화면 대신 안내 문구."""
    if df is None or len(df) == 0:
        st.info(msg)
        return True
    return False


# ───────────────────────────────────────── 사이드바
kmrb, grac, selfd = load_all()

st.sidebar.title("게임·영상물 등급분류")
screen = st.sidebar.radio(
    "화면",
    ["1. 등급 결정 규칙", "2. 무엇이 등급을 올렸나", "3. 신청 대비 조정",
     "4. 매체 비교", "5. 누가 매기는가", "6. 원자료"],
    label_visibility="collapsed")

st.sidebar.divider()
st.sidebar.subheader("공통 필터")

yr_lo = int(min(kmrb["rt_year"].min(), grac["rated_year"].min()))
yr_hi = int(max(kmrb["rt_year"].max(), grac["rated_year"].max()))
years = st.sidebar.slider("기간 (등급분류 연도)", yr_lo, yr_hi, (yr_lo, yr_hi))

kinds = st.sidebar.multiselect(
    "영상물 종별", sorted(kmrb["kindName"].astype(str).unique()),
    help="비우면 전체")
platforms = st.sidebar.multiselect(
    "게임물 플랫폼", sorted(grac["platform"].astype(str).unique()),
    help="비우면 전체")
drop_adult = st.sidebar.checkbox(
    "성인물 제외", value=False,
    help="성인물은 내용정보와 무관하게 사실상 전건 청소년관람불가라 다른 종별을 가린다 (PRD 5.3 함정3)")

K = calc.filter_kmrb(kmrb, years=years, kinds=kinds, drop_adult=drop_adult)
G = calc.filter_grac(grac, years=years, platforms=platforms)

st.sidebar.divider()
st.sidebar.caption(
    f"영상물 {len(K):,} / {len(kmrb):,}건\n\n"
    f"게임물 {len(G):,} / {len(grac):,}건")
st.sidebar.caption(
    "영등위·게임위 Open API 전량 수집분. "
    "자체등급분류(76,409건)는 분석 대상이 아니라 비교군이며 화면 5 에서만 쓴다.")


# ───────────────────────────────────────── 화면 1
def screen_rule() -> None:
    st.header("등급은 무엇으로 정해지는가")
    st.markdown(
        "**영상물의 관람등급은 내용정보 7개 항목의 최고값 그 자체다.** 둘은 서로를 설명하는 관계가 "
        "아니라 같은 값이다. 그래서 '폭력성이 높으면 청불' 같은 분석은 동어반복이 된다.")
    note(f"영상물 {len(K):,}건 · {years[0]}~{years[1]}"
         + (" · 성인물 제외" if drop_adult else "")
         + (f" · 종별 {', '.join(kinds)}" if kinds else ""))
    if empty_guard(K):
        return

    m = calc.rule_match(K)
    tot = m[m["표기 체계"] == "전체"].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("전체 일치율", pct(tot["일치율"], 2), help="최고값이 가리키는 등급과 실제 결정등급이 같은 비율")
    for _, r in m[m["표기 체계"] != "전체"].iterrows():
        (c2 if r["표기 체계"] == "단계표기" else c3).metric(
            f"{r['표기 체계']} ({int(r['건수']):,}건)", pct(r["일치율"], 3))

    st.subheader("내용정보 최고값 × 결정 등급")
    ct = calc.rule_crosstab(K)
    if not empty_guard(ct):
        fig = px.imshow(ct, text_auto=",d", aspect="auto",
                        color_continuous_scale="Blues",
                        labels={"x": "결정 등급", "y": "내용정보 최고값", "color": "건수"})
        fig.update_layout(height=380, coloraxis_showscale=False, margin=dict(t=10, b=0))
        st.plotly_chart(fig, width="stretch")
        st.caption("대각선만 채워진다. 규칙이 아니라 항등식이라는 뜻이다.")

    st.subheader("규칙은 언제부터 예외 없이 지켜졌나")
    by = calc.rule_by_year(K)
    if not empty_guard(by):
        fig = px.line(by, x="rt_year", y="일치율", markers=True,
                      labels={"rt_year": "등급분류 연도", "일치율": "일치율"})
        fig.update_yaxes(tickformat=".1%", range=[0.985, 1.001])
        fig.update_traces(line_color=COLOR["영상물"])
        fig.update_layout(height=300, margin=dict(t=10, b=0))
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "표기 체계가 `1단계~5단계` 에서 `전체관람가~제한상영가` 로 바뀐 2017-05 이후로는 예외가 없다. "
            "표기가 바뀐 시점과 규칙이 완전해진 시점이 같다.")

    ex = calc.rule_exceptions(K)
    if len(ex):
        with st.expander(f"어긋난 {int(ex['건수'].sum()):,}건은 어떤 건인가"):
            st.dataframe(ex, width="stretch", hide_index=True)
            st.caption("대부분 최고값이 5단계인데 제한상영가가 아니라 청소년관람불가로 결정된 건이다.")


# ───────────────────────────────────────── 화면 2
def screen_reason() -> None:
    st.header("등급을 끌어올린 항목은 무엇이고, 종별로 다른가")
    st.markdown(
        "등급이 최고값이라면 남는 질문은 **그 최고값을 무엇이 차지하는가**다. "
        "결정사유(`rtCoreHarmRsnNm`) 필드가 그것을 이름으로 알려준다.")
    cov = calc.reason_coverage(K)
    note(f"영상물 중 결정사유가 기록된 {cov['기록건수']:,}건 "
         f"({pct(cov['기록률'])}) · 기록 구간 {cov['시작']}~{cov['끝']}")
    if cov["기록건수"] == 0:
        st.info("이 조건에는 결정사유가 기록된 건이 없습니다. 기간을 넓혀 보세요.")
        return
    st.warning(
        "이 필드는 전 기간에 채워져 있지 않다. 아래 결과는 전 기간이 아니라 **기록된 구간의 이야기**로 읽어야 한다.",
        icon="⚠️")

    freq = calc.reason_freq(K)
    fig = px.bar(freq, x="항목", y="비율", text=freq["비율"].map(lambda v: pct(v)),
                 labels={"비율": "지목된 비율"})
    fig.update_traces(marker_color=COLOR["영상물"], textposition="outside")
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(height=320, margin=dict(t=10, b=0))
    st.plotly_chart(fig, width="stretch")

    st.subheader("종별로 갈리는가")
    tab = calc.reason_by_kind(K)
    if not empty_guard(tab, "표본 100건 이상인 종별이 없습니다 (N-5)."):
        fig = px.imshow(tab, text_auto=".0%", aspect="auto", color_continuous_scale="Oranges",
                        labels={"x": "결정 항목", "y": "종별", "color": "지목률"})
        fig.update_layout(height=60 + 42 * len(tab), coloraxis_showscale=False, margin=dict(t=10, b=0))
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "성인물은 선정성, 극영화·애니메이션은 폭력성, 뮤직비디오는 약물이 등급을 정한다. "
            "최고값 규칙에서 자동으로 따라 나오는 결과가 아니라 콘텐츠 성격의 차이다. "
            "표본 100건 미만인 종별은 싣지 않는다.")

    st.subheader("시기에 따라 달라졌나")
    byy = calc.reason_by_year(K)
    if not empty_guard(byy, "표본 100건 이상인 연도가 없습니다 (N-5)."):
        long = byy.reset_index().melt(id_vars="rt_year", var_name="항목", value_name="지목률")
        fig = px.line(long, x="rt_year", y="지목률", color="항목", markers=True,
                      labels={"rt_year": "등급분류 연도"})
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(height=340, margin=dict(t=10, b=0))
        st.plotly_chart(fig, width="stretch")


# ───────────────────────────────────────── 화면 3
def screen_adjust() -> None:
    st.header("신청등급과 결정등급은 어디서 갈리는가")
    st.markdown(
        "내용정보와 결정등급은 같은 값이라 서로를 설명하지 못한다. 그러나 **신청등급은 다르다.** "
        "신청사가 스스로 매긴 값이고, 결정등급은 위원회가 매긴 값이다. "
        "둘이 갈리는 지점이 이 데이터에서 판단이 개입하는 유일한 곳이다.")
    note(f"영상물 중 신청등급이 있는 건 · {years[0]}~{years[1]}"
         + (" · 성인물 제외" if drop_adult else ""))
    if empty_guard(K):
        return

    s = calc.adjust_summary(K)
    if empty_guard(s):
        return
    cols = st.columns(3)
    for col, (_, r) in zip(cols, s.iterrows()):
        col.metric(r["구분"], f"{int(r['건수']):,}건", pct(r["비율"]), delta_color="off")

    st.subheader("종별로 조정률이 다른가")
    bk = calc.adjust_by_kind(K)
    if not empty_guard(bk, "표본 200건 이상인 종별이 없습니다 (N-5)."):
        fig = go.Figure()
        fig.add_bar(x=bk["종별"], y=bk["상향"], name="상향", marker_color="#C2603F")
        fig.add_bar(x=bk["종별"], y=bk["하향"], name="하향", marker_color="#6E8CA0")
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(barmode="group", height=340, margin=dict(t=10, b=0))
        st.plotly_chart(fig, width="stretch")
        st.caption("부가영상만 하향이 상향보다 많다.")

    st.subheader("낮게 신청할수록 올라가는가")
    bh = calc.adjust_by_hope(K)
    if not empty_guard(bh, "표본 200건 이상인 신청등급이 없습니다 (N-5)."):
        fig = px.bar(bh, x="신청등급", y="상향", text=bh["상향"].map(lambda v: pct(v)),
                     hover_data={"건수": ":,"})
        fig.update_traces(marker_color="#C2603F", textposition="outside")
        fig.update_yaxes(tickformat=".0%", title="상향률")
        fig.update_layout(height=340, margin=dict(t=10, b=0))
        st.plotly_chart(fig, width="stretch")

    st.subheader("조정된 건은 내용정보가 어떻게 다른가")
    prof = calc.adjust_profile(K)
    if not empty_guard(prof):
        long = prof.reset_index(names="항목").melt(id_vars="항목", var_name="조정", value_name="평균 단계")
        fig = px.bar(long, x="항목", y="평균 단계", color="조정", barmode="group",
                     color_discrete_map={"신청대로": "#9AA7B1", "상향": "#C2603F", "하향": "#3B6FB6"})
        fig.update_layout(height=340, margin=dict(t=10, b=0))
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "상향은 곧 '최고값 > 신청등급'이므로 신청등급 자체를 설명 변수로 쓰면 다시 항등식이 된다. "
            "여기서 보는 것은 신청사가 어느 항목에서 자기 등급을 낮게 예상하는가다.")


# ───────────────────────────────────────── 화면 4
def screen_media() -> None:
    st.header("같은 내용 수준에서 매체에 따라 등급이 달라지는가")
    st.markdown(
        "두 기관은 내용정보를 다른 형태로 준다. 영등위는 항목마다 1~5단계, 게임위는 해당 항목 이름만 "
        "나열한다. 수준끼리는 비교할 수 없으므로 **영상물을 이진화해 맞춘다.** "
        "이름이 같은 4개(선정성·폭력성·공포·약물)로만 비교한다.")

    th_label = st.radio(
        "영상물 이진화 기준",
        ["3단계(다소높음) 이상을 '보유'로 본다", "4단계(높음) 이상을 '보유'로 본다"],
        horizontal=True)
    th = int(th_label[0])
    if th == 4:
        st.error(
            "**4단계 기준은 비교로 쓸 수 없다.** 영상물은 4단계가 곧 청소년관람불가라, 이진화하면 "
            "영상물 쪽이 정의상 100%가 된다. 비교가 아니라 항등식을 다시 보는 것이다 (PRD R-10). "
            "아래 숫자는 그 사실을 확인하는 용도로만 본다.", icon="🚫")

    both, info = calc.media_frame(K, G, th)
    note(f"영상물 {info['영상물_비교표본']:,}건 (성인물·주제/대사/모방위험 보유 {info['영상물_제외']:,}건 제외) · "
         f"게임물 {info['게임물_비교표본']:,}건 (등급취소·언어/범죄/사행성 보유 {info['게임물_제외']:,}건 제외) · "
         f"{years[0]}~{years[1]}")
    st.caption(
        "비교 대상 밖 항목이 붙은 건은 **양쪽 대칭으로 뺀다.** 안 빼면 사행성 하나로 청불이 되는 "
        "게임물(97.1%)이 '(없음)' 칸에 들어가 결과가 뒤집힌다.")
    if empty_guard(both):
        return

    st.subheader("보유 조합이 같은 건끼리 비교하면")
    cc = calc.combo_compare(both)
    if empty_guard(cc, "양쪽 모두 50건 이상인 조합이 없습니다 (N-5)."):
        return
    fig = go.Figure()
    for media in ["영상물", "게임물"]:
        fig.add_bar(x=cc["조합"], y=cc[media], name=media, marker_color=COLOR[media],
                    text=cc[media].map(lambda v: pct(v)), textposition="outside")
    fig.update_yaxes(tickformat=".0%", title="청소년 이용 제한 비율")
    fig.update_layout(barmode="group", height=400, margin=dict(t=10, b=0))
    st.plotly_chart(fig, width="stretch")

    harsher = int((cc["차이"] > 0).sum())
    c1, c2 = st.columns(2)
    c1.metric("비교 가능한 조합", f"{len(cc)}개", f"게임물이 더 엄한 조합 {harsher}개", delta_color="off")
    c2.metric("평균 차이", f"{cc['차이'].mean() * 100:+.1f}%p", "게임물 − 영상물", delta_color="off")

    st.dataframe(
        cc.style.format({"영상물": "{:.1%}", "게임물": "{:.1%}", "차이": "{:+.1%}",
                         "영상물 n": "{:,}", "게임물 n": "{:,}"}),
        width="stretch", hide_index=True)

    st.subheader("항목 하나만 가졌을 때")
    solo = calc.solo_compare(both)
    if not empty_guard(solo, "단독 보유 표본이 부족합니다 (N-5)."):
        long = solo.melt(id_vars="항목", value_vars=["영상물", "게임물"],
                         var_name="매체", value_name="청불률")
        fig = px.bar(long, x="항목", y="청불률", color="매체", barmode="group",
                     color_discrete_map=COLOR, text=long["청불률"].map(lambda v: pct(v)))
        fig.update_traces(textposition="outside")
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(height=340, margin=dict(t=10, b=0))
        st.plotly_chart(fig, width="stretch")

    with st.expander("항목별 보유율 — 이 값이 다른 것은 매체의 성격 차이다"):
        st.dataframe(
            calc.hold_rate(both).style.format({"영상물": "{:.1%}", "게임물": "{:.1%}", "차이": "{:+.1%}"}),
            width="stretch", hide_index=True)

    st.info(
        "**남는 한계** — '3단계'라는 절단 지점에 근거가 있는 것은 아니다. 영등위의 5단계를 게임위의 "
        "보유/미보유에 맞추려면 어딘가에서 잘라야 하고, 그 지점을 데이터가 정해주지 않는다. "
        "'게임물이 더 엄하다'는 이 절단 기준 위에서만 성립한다.", icon="ℹ️")


# ───────────────────────────────────────── 화면 5
def screen_rater() -> None:
    st.header("공개된 데이터는 게임물 등급분류의 얼마만큼인가")
    st.markdown(
        "게임물은 위원회가 직접 심의하는 것 말고 **사업자가 스스로 등급을 매기는 자체등급분류**가 있다. "
        "Open API 로 공개되는 것은 앞의 것뿐이다. 그 자리가 얼마나 큰지 비교군으로 재 본다.")

    same, lo, hi = calc.rater_period(grac, selfd)
    note(f"자체등급분류 비교군은 {lo:%Y-%m-%d}~{hi:%Y-%m-%d} 약 7주치 스냅숏뿐이라 "
         f"위원회 쪽도 같은 기간으로 잘라 비교한다 · 이 화면은 왼쪽 기간 필터를 쓰지 않는다")
    st.caption(
        "비교군은 이 프로젝트가 수집한 것이 아니라 별개 업무에서 확보된 파일이고 재수집이 불가능하다. "
        "추세가 아니라 **한 시점의 규모 비교**로만 쓴다 (PRD R-12).")

    vol = calc.rater_volume(grac, selfd)
    c1, c2, c3 = st.columns(3)
    c1.metric("위원회 심의", f"{int(vol.loc[0, '건수']):,}건")
    c2.metric("자체등급분류", f"{int(vol.loc[1, '건수']):,}건")
    ratio = vol.loc[1, "건수"] / vol.loc[0, "건수"] if vol.loc[0, "건수"] else float("nan")
    c3.metric("공개분이 차지하는 몫", pct(vol.loc[0, "비중"], 2), f"약 {ratio:,.0f}배 차이", delta_color="off")

    fig = px.bar(vol, x="건수", y="구분", orientation="h", log_x=True,
                 text=vol["건수"].map(lambda v: f"{v:,}건"), color="구분",
                 color_discrete_map=COLOR)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=240, showlegend=False, margin=dict(t=10, b=0),
                      xaxis_title="건수 (로그 눈금)")
    st.plotly_chart(fig, width="stretch")
    st.caption("19년치 위원회 물량(28,377건)보다 7주치 자체등급분류가 더 많다.")

    st.subheader("등급 분포가 얼마나 다른가")
    gr = calc.rater_grade(grac, selfd)
    long = gr.reset_index(names="등급").melt(id_vars="등급", var_name="매긴 주체", value_name="비중")
    fig = px.bar(long, x="등급", y="비중", color="매긴 주체", barmode="group",
                 color_discrete_map=COLOR, text=long["비중"].map(lambda v: pct(v)))
    fig.update_traces(textposition="outside")
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(height=360, margin=dict(t=10, b=0))
    st.plotly_chart(fig, width="stretch")

    st.subheader("내용정보는 어떻게 다른가")
    cn = calc.rater_content(grac, selfd)
    long = cn.reset_index(names="항목").melt(id_vars="항목", var_name="매긴 주체", value_name="보유율")
    fig = px.bar(long, x="항목", y="보유율", color="매긴 주체", barmode="group",
                 color_discrete_map=COLOR)
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(height=360, margin=dict(t=10, b=0))
    st.plotly_chart(fig, width="stretch")

    st.error(
        "**이 차이를 심의 엄격도로 읽으면 안 된다.** 자체등급분류에는 사행성이 사실상 없다(0.05% 대 23.2%). "
        "사행성은 단독으로도 청소년이용불가율이 97.1%라, 등급 분포 차이의 상당 부분이 여기서 온다. "
        "장르 표기 체계도 달라(단일 19종 대 복합 294종) 장르를 맞춘 통제가 불가능하다.", icon="🚫")


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
    st.header("개별 건을 직접 확인한다")
    media = st.radio("매체", ["영상물", "게임물"], horizontal=True)
    d = (K if media == "영상물" else G)[RAW_COLS[media]]

    q = st.text_input("제목 검색", placeholder="제목의 일부를 입력하세요")
    if q:
        col = "useTitle" if media == "영상물" else "gametitle"
        d = d[d[col].astype(str).str.contains(q, case=False, na=False)]

    note(f"{media} {len(d):,}건 · {years[0]}~{years[1]}"
         + (" · 성인물 제외" if media == "영상물" and drop_adult else ""))
    if empty_guard(d):
        return

    st.dataframe(d.head(1000), width="stretch", hide_index=True)
    if len(d) > 1000:
        st.caption(f"화면에는 앞 1,000건만 보인다. 내려받기는 조건에 맞는 {len(d):,}건 전부다.")

    st.download_button(
        f"조건에 맞는 {len(d):,}건 내려받기 (CSV)",
        d.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{'kmrb' if media == '영상물' else 'grac'}_{years[0]}_{years[1]}.csv",
        mime="text/csv")


# ───────────────────────────────────────── 실행
{"1. 등급 결정 규칙": screen_rule,
 "2. 무엇이 등급을 올렸나": screen_reason,
 "3. 신청 대비 조정": screen_adjust,
 "4. 매체 비교": screen_media,
 "5. 누가 매기는가": screen_rater,
 "6. 원자료": screen_raw}[screen]()

st.divider()
st.caption(
    "게임물관리위원회·영상물등급위원회 Open API 전량 수집분 "
    f"(영상물 {len(kmrb):,}건 2009~2026 · 게임물 {len(grac):,}건 2007~2026). "
    "BI 분석가 과정 개인 프로젝트 — 최은혜.")
