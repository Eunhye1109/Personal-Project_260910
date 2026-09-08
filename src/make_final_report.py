# -*- coding: utf-8 -*-
"""
최종 EDA 보고서 생성 — 흩어져 있던 다섯 개 리포트를 한 문서로

지금까지 분석을 할 때마다 리포트가 하나씩 생겨 다섯 개가 됐다. 순서대로 읽으면
흐름은 맞지만 남에게 건네기에는 불편하다. 이 스크립트가 그것을 한 편으로 합친다.

    영상물 현황 EDA        eda_report.html
    등급 결정 구조         stage4_report.html
    게임물 현황 EDA        eda_grac_report.html
    매체 간 비교           compare_media_report.html
    누가 매기는가          compare_rater_report.html
        ↓
    최종 보고서            outputs/final_report.html

값은 전부 정제본에서 다시 계산한다. 원본이 갱신되면 이 스크립트만 다시 돌리면 된다.

실행
    python src/make_final_report.py
    python src/make_final_report.py --no-sync
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_nas  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"

NAMES = {1: "주제", 2: "선정성", 3: "폭력성", 4: "대사", 5: "공포", 6: "약물", 7: "모방위험"}
LV = [f"rtStdName{i}_lv" for i in range(1, 8)]
GRADES = ["전체관람가", "12세", "15세", "청소년관람불가", "제한관람가"]
AGES = [0, 12, 15, 18, 19]
LEVEL_TO_AGE = {1: 0, 2: 12, 3: 15, 4: 18, 5: 19}
DESC = ["사행성", "폭력성", "선정성", "언어", "약물", "공포", "범죄"]
COMPARABLE = ["선정성", "폭력성", "공포", "약물"]
KMRB_COL = {"선정성": "rtStdName2_lv", "폭력성": "rtStdName3_lv",
            "공포": "rtStdName5_lv", "약물": "rtStdName6_lv"}
KMRB_OTHER = ["rtStdName1_lv", "rtStdName4_lv", "rtStdName7_lv"]
GRAC_OTHER = ["사행성", "언어", "범죄"]


def ym(ts) -> str:
    """2009년 1월. 윈도우에서는 %-m 이 안 먹어 직접 만든다."""
    return f"{ts.year}년 {ts.month}월"


def ymd(ts) -> str:
    return f"{ts.year}년 {ts.month}월 {ts.day}일"


def latest(pattern: str) -> Path:
    files = sorted(PROC.glob(pattern))
    if not files:
        sys.exit(f"[중단] {pattern} 정제본이 없습니다.")
    return files[-1]


def js(o) -> str:
    return json.dumps(o, ensure_ascii=False)


# ══════════════════════════════════════════════ 값 계산
def compute() -> dict:
    k = pd.read_parquet(latest("kmrb_video_clean_*.parquet")).dropna(subset=LV + ["grade_age"]).copy()
    g = pd.read_parquet(latest("grac_game_clean_*.parquet"))
    s = pd.read_parquet(latest("grac_self_clean_*.parquet"))
    v: dict = {}

    # ── 영상물
    k["cmax"] = k[LV].max(axis=1).astype(int)
    v["kmrb_n"] = len(k)
    v["kmrb_from"] = ym(k["rt_date"].min())
    v["kmrb_to"] = ym(k["rt_date"].max())

    rule = []
    for lv in range(1, 6):
        sub = k[k["cmax"] == lv]
        rule.append([lv] + [int((sub["grade_age"] == a).sum()) for a in AGES])
    v["rule"] = rule
    ok = (k["cmax"].map(LEVEL_TO_AGE) == k["grade_age"])
    v["rule_rate"] = round(float(ok.mean()) * 100, 2)
    v["rule_miss"] = int((~ok).sum())
    by_nota = {}
    for nota, sub in k.groupby("content_notation"):
        if len(sub) < 100:
            continue
        r = float((sub["cmax"].map(LEVEL_TO_AGE) == sub["grade_age"]).mean())
        by_nota[str(nota)] = [len(sub), round(r * 100, 3)]
    v["rule_nota"] = by_nota

    year = []
    for y, sub in k.groupby(k["rt_date"].dt.year):
        if len(sub) < 100:
            continue
        year.append([int(y), len(sub)] + [round(float((sub["grade_age"] == a).mean()) * 100, 1) for a in AGES])
    v["year"] = year

    kind = k["kindName"].value_counts().head(6)
    v["kind"] = [[str(n), int(c), round(float(k.loc[k["kindName"] == n, "grade_age"].ge(18).mean()) * 100, 1)]
                 for n, c in kind.items()]
    v["adult_share"] = round(float((k["kindName"] == "성인물").mean()) * 100, 1)

    reason = k[k["rtCoreHarmRsnNm"].notna() & (k["rtCoreHarmRsnNm"].astype(str).str.strip() != "")]
    ex = reason.assign(r=reason["rtCoreHarmRsnNm"].astype(str).str.split(",")).explode("r")
    ex["r"] = ex["r"].str.strip()
    ex = ex[ex["r"] != ""]
    order = list(ex["r"].value_counts().index)
    heat = []
    for kd in reason["kindName"].value_counts().head(5).index:
        base = reason[reason["kindName"] == kd]
        sub = ex[ex["kindName"] == kd]
        heat.append([str(kd)] + [round(float((sub["r"] == n).sum()) / len(base) * 100, 1) for n in order])
    v["reason_names"], v["heat"] = order, heat
    v["reason_n"] = len(reason)
    v["reason_span"] = [int(reason["rt_date"].dt.year.min()), int(reason["rt_date"].dt.year.max())]

    adj = k.dropna(subset=["hope_grade_age"])
    d = adj["grade_age"] - adj["hope_grade_age"]
    v["adjust"] = [["신청대로", int((d == 0).sum()), round(float((d == 0).mean()) * 100, 1)],
                   ["위원회가 올림", int((d > 0).sum()), round(float((d > 0).mean()) * 100, 1)],
                   ["위원회가 내림", int((d < 0).sum()), round(float((d < 0).mean()) * 100, 1)]]

    # ── 게임물
    ga = g[~g["is_canceled"]].dropna(subset=["grade_age"]).copy()
    v["grac_n"] = len(g)
    v["grac_from"], v["grac_to"] = f"{g['rated_date'].min():%Y}", f"{g['rated_date'].max():%Y}"
    v["grac_empty"] = int((~g["has_descriptor"]).sum())
    v["grac_empty_pct"] = round(float((~g["has_descriptor"]).mean()) * 100, 1)
    v["grac_empty_yr"] = round(float(g.loc[~g["has_descriptor"], "is_youth_restricted"].dropna().mean()) * 100, 2)
    solo = []
    for n in DESC:
        sub = ga[(ga[f"내용_{n}"] == 1) & (ga["n_descriptors"] == 1)]
        if len(sub) < 20:
            continue
        solo.append([n, len(sub), round(float(sub["is_youth_restricted"].mean()) * 100, 1)])
    v["grac_solo"] = sorted(solo, key=lambda r: -r[2])
    v["grac_grade"] = [[str(n), int(c)] for n, c in g["givenrate"].value_counts().items()]
    v["grac_cancel"] = int(g["is_canceled"].sum())

    # ── 매체 비교 (3점 이상을 '있음'으로)
    kk = k[~k["kindName"].astype(str).eq("성인물")].copy()
    keep = ~(kk[KMRB_OTHER] >= 3).any(axis=1)
    kk = kk[keep]
    gg = ga[ga[[f"내용_{n}" for n in GRAC_OTHER]].sum(axis=1) == 0]
    cmp_rows = []
    for n in COMPARABLE:
        ksub = kk[(kk[KMRB_COL[n]] >= 3) &
                  (kk[[KMRB_COL[m] for m in COMPARABLE if m != n]].lt(3).all(axis=1))]
        gsub = gg[(gg[f"내용_{n}"] == 1) & (gg["n_descriptors"] == 1)]
        if len(ksub) < 30 or len(gsub) < 30:
            continue
        cmp_rows.append([n, len(ksub), round(float(ksub["grade_age"].ge(18).mean()) * 100, 1),
                         len(gsub), round(float(gsub["is_youth_restricted"].mean()) * 100, 1)])
    v["compare"] = sorted(cmp_rows, key=lambda r: -(r[4] - r[2]))
    v["cmp_kn"], v["cmp_gn"] = len(kk), len(gg)

    # ── 누가 매기는가
    lo, hi = s["rated_date"].min(), s["rated_date"].max()
    same = ga[(ga["rated_date"] >= lo) & (ga["rated_date"] <= hi)]
    v["rater"] = {"from": ymd(lo), "to": ymd(hi),
                  "days": (hi - lo).days,
                  "com_n": len(same), "self_n": len(s),
                  "com_yr": round(float(same["is_youth_restricted"].mean()) * 100, 1),
                  "self_yr": round(float(s["is_youth_restricted"].mean()) * 100, 2),
                  "ratio": round(len(s) / max(len(same), 1)),
                  "share": round(len(same) / (len(same) + len(s)) * 100, 2),
                  "com_gam": round(float(ga["내용_사행성"].mean()) * 100, 1),
                  "self_gam": round(float(s["내용_사행성"].mean()) * 100, 2)}
    return v


# ══════════════════════════════════════════════ 문서
def render(v: dict) -> str:
    r = v["rater"]
    step_n, step_r = v["rule_nota"].get("단계표기", [0, 0])
    gr_n, gr_r = v["rule_nota"].get("등급표기", [0, 0])
    top = v["grac_solo"][0]
    bot = v["grac_solo"][-1]

    return f"""<title>등급분류 데이터 분석 보고</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Sans+KR:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --ground:#F6F7F9; --surface:#FFFFFF; --sunk:#EDEFF3;
  --ink:#141922; --ink2:#3D4654; --muted:#5C6675;
  --line:#E2E6EC; --line2:#CBD2DC;
  --accent:#1F3864;
  --s1:#E3E9F2; --s2:#B9C9E1; --s3:#8AA6CE; --s4:#5A7CB0; --s5:#2C4B7C;
  --c1:#2E5FA3; --c2:#A8761C; --c3:#B03A5B;
  --shadow:0 1px 2px rgba(20,25,34,.04), 0 10px 30px -22px rgba(20,25,34,.4);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#111418; --surface:#181C22; --sunk:#1F242B;
    --ink:#EDF0F4; --ink2:#C3CAD4; --muted:#8D97A5;
    --line:#272D35; --line2:#39414C;
    --accent:#9DB8E0;
    --s1:#24344A; --s2:#33507A; --s3:#4A73A8; --s4:#7099CE; --s5:#A9C4E6;
    --c1:#5C90CE; --c2:#BC8A33; --c3:#C86680;
    --shadow:0 1px 2px rgba(0,0,0,.5), 0 12px 34px -24px rgba(0,0,0,.9);
  }}
}}
:root[data-theme="dark"] {{
  --ground:#111418; --surface:#181C22; --sunk:#1F242B;
  --ink:#EDF0F4; --ink2:#C3CAD4; --muted:#8D97A5;
  --line:#272D35; --line2:#39414C;
  --accent:#9DB8E0;
  --s1:#24344A; --s2:#33507A; --s3:#4A73A8; --s4:#7099CE; --s5:#A9C4E6;
  --c1:#5C90CE; --c2:#BC8A33; --c3:#C86680;
  --shadow:0 1px 2px rgba(0,0,0,.5), 0 12px 34px -24px rgba(0,0,0,.9);
}}
*{{box-sizing:border-box}}
body{{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:'IBM Plex Sans KR','Malgun Gothic',system-ui,sans-serif;
  font-weight:300; font-size:16px; line-height:1.8;
  padding:0 24px 120px;
  /* 한글은 기본값이면 단어 중간에서 잘린다(예: '점수를 매 / 긴다').
     keep-all 로 띄어쓰기에서만 줄을 바꾸고, 아주 긴 낱말만 예외로 쪼갠다. */
  word-break: keep-all;
  overflow-wrap: break-word;
}}
.wrap{{max-width:1080px;margin:0 auto}}
.col{{max-width:660px}}
h1,h2,h3{{font-family:'Gowun Batang','Batang',serif;font-weight:700;line-height:1.35;text-wrap:balance;margin:0}}
.mono{{font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.num{{font-variant-numeric:tabular-nums}}

header{{padding:96px 0 48px;border-bottom:2px solid var(--line2)}}
.kicker{{font-family:'IBM Plex Mono',monospace;font-size:11.5px;letter-spacing:.18em;
  text-transform:uppercase;color:var(--muted);margin-bottom:20px}}
h1{{font-size:clamp(32px,5.4vw,52px);margin-bottom:20px;letter-spacing:-.01em}}
.lede{{font-size:18px;color:var(--ink2);max-width:640px;line-height:1.75}}
.meta{{display:flex;flex-wrap:wrap;gap:0;margin-top:40px;border:1px solid var(--line);
  border-radius:4px;overflow:hidden;background:var(--surface)}}
.meta div{{flex:1 1 170px;padding:16px 20px;border-right:1px solid var(--line)}}
.meta div:last-child{{border-right:0}}
.meta dt{{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);margin-bottom:7px}}
.meta dd{{margin:0;font-size:21px;font-weight:500;font-variant-numeric:tabular-nums}}
.meta dd small{{font-size:13px;font-weight:300;color:var(--muted)}}

section{{padding:64px 0;border-bottom:1px solid var(--line)}}
.shead{{display:flex;gap:18px;align-items:baseline;margin-bottom:14px}}
.snum{{font-family:'IBM Plex Mono',monospace;font-size:11.5px;letter-spacing:.12em;
  color:var(--muted);border:1px solid var(--line2);border-radius:3px;padding:3px 9px;flex:none;
  text-transform:uppercase}}
h2{{font-size:27px}}
h3{{font-size:19px;margin:36px 0 10px}}
p{{margin:0 0 16px}}
.sdesc{{color:var(--ink2);max-width:640px}}

.finds{{display:grid;gap:1px;background:var(--line);border:1px solid var(--line);
  border-radius:4px;overflow:hidden;margin-top:32px}}
.find{{background:var(--surface);padding:24px 26px;display:grid;
  grid-template-columns:auto 1fr;gap:20px;align-items:start}}
.find b{{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent);
  font-weight:500;padding-top:4px}}
.find h3{{margin:0 0 6px;font-size:18px}}
.find p{{margin:0;font-size:15px;color:var(--ink2);line-height:1.7}}

figure{{margin:32px 0 0}}
figcaption{{font-size:14px;color:var(--muted);margin-top:14px;max-width:660px;line-height:1.7}}
.scroll{{overflow-x:auto;padding-bottom:6px}}
.legend{{display:flex;flex-wrap:wrap;gap:8px 20px;margin-bottom:14px;font-size:13px;color:var(--ink2)}}
.legend span{{display:inline-flex;align-items:center;gap:8px}}
.sw{{width:11px;height:11px;border-radius:2px;flex:none}}

table{{border-collapse:collapse;width:100%;font-size:14px;margin-top:8px}}
th,td{{padding:9px 12px;text-align:right;border-bottom:1px solid var(--line);
  font-variant-numeric:tabular-nums}}
th:first-child,td:first-child{{text-align:left}}
thead th{{color:var(--muted);font-weight:500;font-size:11.5px;letter-spacing:.06em;
  text-transform:uppercase;border-bottom:1px solid var(--line2)}}

.note{{background:var(--sunk);border-left:3px solid var(--accent);border-radius:0 3px 3px 0;
  padding:18px 22px;margin:26px 0;font-size:15px;color:var(--ink2);max-width:700px}}
.note b{{color:var(--ink)}}

.hero-stat{{display:flex;flex-wrap:wrap;gap:36px;align-items:flex-end;margin:28px 0 8px}}
.hero-stat .big{{font-family:'IBM Plex Mono',monospace;font-size:clamp(46px,8vw,76px);
  font-weight:500;line-height:1;color:var(--accent);font-variant-numeric:tabular-nums}}
.hero-stat p{{margin:0;max-width:380px;font-size:15px;color:var(--ink2)}}

#tip{{position:fixed;pointer-events:none;opacity:0;transition:opacity .12s;
  background:var(--ink);color:var(--ground);font-size:12.5px;line-height:1.55;
  padding:8px 11px;border-radius:4px;z-index:60;max-width:250px;
  font-family:'IBM Plex Sans KR',sans-serif;font-variant-numeric:tabular-nums}}
svg text{{font-family:'IBM Plex Sans KR',sans-serif;font-variant-numeric:tabular-nums}}
.axis{{font-size:11.5px;fill:var(--muted)}}
.vlab{{font-size:11.5px;fill:var(--ink2)}}
.rowlab{{font-size:13px;fill:var(--ink2)}}
[data-tip]{{cursor:default}}
[data-tip]:focus-visible{{outline:2px solid var(--c1);outline-offset:2px}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
footer{{padding:52px 0 0;color:var(--muted);font-size:13.5px;max-width:700px}}
</style>
<div class="wrap">

<header>
  <div class="kicker">최종 보고 · {datetime.now():%Y년 %m월 %d일}</div>
  <h1>등급은 무엇으로 정해지는가</h1>
  <p class="lede">게임물관리위원회와 영상물등급위원회가 공개하는 등급분류 결과를 전량 받아
  분석했다. 두 기관이 등급을 정하는 방식이 서로 다르다는 것, 그리고 공개된 자료가
  전체의 얼마만큼인지를 정리한다.</p>
  <dl class="meta">
    <div><dt>영상물</dt><dd>{v['kmrb_n']:,}<small> 건</small></dd></div>
    <div><dt>게임물</dt><dd>{v['grac_n']:,}<small> 건</small></dd></div>
    <div><dt>비교용 자료</dt><dd>{r['self_n']:,}<small> 건</small></dd></div>
    <div><dt>수집 범위</dt><dd>전량<small> · 2007~2026</small></dd></div>
  </dl>
</header>

<section>
  <div class="shead"><span class="snum">요약</span><h2>네 가지 발견</h2></div>
  <p class="sdesc">아래 네 가지가 이 분석의 결론이다. 각각은 뒤의 해당 장에서 근거와 함께 다룬다.</p>
  <div class="finds">
    <div class="find"><b>발견 1</b><div>
      <h3>영상물은 등급을 계산하지 않는다</h3>
      <p>항목 일곱 가지에 각각 점수를 매기고, 그중 가장 높은 점수를 그대로 등급으로 옮긴다.
      {v['kmrb_n']:,}건 가운데 {v['rule_rate']}%가 이 규칙을 따르고, 표기가 바뀐 2017년 5월 이후
      {gr_n:,}건은 어긋난 건이 하나도 없다.</p></div></div>
    <div class="find"><b>발견 2</b><div>
      <h3>게임물은 점수가 없고 이름표만 붙는다</h3>
      <p>대신 어떤 이름표가 붙었느냐가 등급을 가른다. {top[0]}만 붙어도 {top[2]}%가
      청소년이용불가인데, {bot[0]}만 붙으면 {bot[2]}%다.</p></div></div>
    <div class="find"><b>발견 3</b><div>
      <h3>그래서 두 매체를 같은 잣대로 재기 어렵다</h3>
      <p>한쪽은 점수, 한쪽은 이름표다. 형식을 맞춰 견주면 게임물 쪽이 일관되게 엄하지만,
      맞추는 기준을 바꾸면 결과도 바뀐다.</p></div></div>
    <div class="find"><b>발견 4</b><div>
      <h3>공개된 게임 자료는 전체의 {r['share']}%다</h3>
      <p>나머지는 사업자가 스스로 매긴 등급이라 공개 목록에 없다. 같은 기간으로 견주면
      약 {r['ratio']}배 차이다.</p></div></div>
  </div>
</section>

<section>
  <div class="shead"><span class="snum">1부 · 영상물</span><h2>등급은 가장 높은 점수와 같다</h2></div>
  <p class="sdesc">영상물은 주제·선정성·폭력성·대사·공포·약물·모방위험 일곱 가지에 각각 1점부터
  5점까지 점수를 매긴다. 그 점수 중 가장 높은 것을 관람등급으로 옮기면 어떻게 되는지 보았다.</p>
  <figure>
    <div class="scroll"><svg id="c-rule" width="1000" height="330" role="img"
      aria-label="내용정보 최고 점수와 관람등급의 대응표"></svg></div>
    <figcaption>대각선에만 짙은 칸이 있다. 가장 높은 점수가 1점이면 전부 전체관람가, 2점이면 전부
    12세다. 계산해서 나오는 값이 아니라 옮겨 적은 값이라는 뜻이다. 대각선을 벗어난 칸에도 숫자가
    보이지만 전부 합쳐 {v['rule_miss']}건이라 칠이 거의 드러나지 않는다.</figcaption>
  </figure>
  <div class="note"><b>표기가 바뀐 시점과 규칙이 완전해진 시점이 겹친다.</b>
  단계로 적던 시기({step_n:,}건)는 {step_r}%가 규칙대로였고, 등급 이름으로 적기 시작한
  2017년 5월 이후({gr_n:,}건)는 {gr_r}%다. 어긋난 {v['rule_miss']}건은 모두 그 이전이다.</div>
  <p class="col">이 사실은 분석의 방향을 바꿨다. 내용정보로 등급을 설명하는 것은 같은 값을 두 번 쓰는
  일이 되기 때문이다. 그래서 답이 정해져 있지 않은 곳으로 질문을 옮겼다. 무엇이 가장 높은 점수를
  차지했는가, 그리고 신청한 등급과 결정된 등급이 어디서 갈리는가.</p>
</section>

<section>
  <div class="shead"><span class="snum">1부 · 영상물</span><h2>등급 구성은 크게 달라졌다</h2></div>
  <p class="sdesc">해마다 어떤 등급이 얼마나 나왔는지를 비율로 쌓았다. 막대 왼쪽 숫자는 그해 건수다.</p>
  <figure>
    <div class="legend" id="lg-grade"></div>
    <div class="scroll"><svg id="c-year" width="1000" height="{70 + len(v['year']) * 27}" role="img"
      aria-label="연도별 관람등급 구성 비율"></svg></div>
    <figcaption>2016년을 지나며 구성이 크게 움직인다. 심의가 관대해졌다기보다 등급분류를 신청하는
    대상 자체가 바뀐 것으로 보인다. 건수가 특정 해에 튀는 것은 그해 신청이 몰린 결과다.</figcaption>
  </figure>
  <h3>종류별로 보면</h3>
  <figure>
    <div class="scroll"><svg id="c-kind" width="1000" height="{40 + len(v['kind']) * 34}" role="img"
      aria-label="영상물 종류별 건수와 청소년관람불가 비율"></svg></div>
    <figcaption>성인물이 {v['adult_share']}%를 차지한다. 성인물은 내용정보와 상관없이 거의 전부
    청소년관람불가다. 이 치우침을 감안하지 않으면 결론이 뒤집힐 수 있어, 이후 분석에서는 종류를
    맞춘 뒤 비교했다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">1부 · 영상물</span><h2>무엇이 등급을 끌어올렸나</h2></div>
  <p class="sdesc">등급이 가장 높은 점수와 같다면, 남는 질문은 그 자리를 무엇이 차지했느냐다.
  자료에는 등급을 정한 이유를 이름으로 적어 둔 칸이 있다. 기록된 것은 {v['reason_n']:,}건,
  {v['reason_span'][0]}년부터 {v['reason_span'][1]}년까지다.</p>
  <figure>
    <div class="scroll"><svg id="c-heat" width="1000" height="{70 + len(v['heat']) * 40}" role="img"
      aria-label="영상물 종류별로 등급을 결정한 항목의 비율"></svg></div>
    <figcaption>종류에 따라 뚜렷하게 갈린다. 성인물은 선정성이, 극영화와 숏폼은 폭력성이,
    뮤직비디오는 약물이 등급을 끌어올린다. 이것은 앞의 규칙에서 저절로 나오는 결과가 아니라
    콘텐츠 성격의 차이다.</figcaption>
  </figure>
  <h3>신청한 등급과 결정된 등급</h3>
  <p class="col">내용정보와 결정 등급은 같은 값이라 서로를 설명하지 못한다. 그러나 신청 등급은 다르다.
  신청사가 스스로 적어 낸 값이기 때문이다. 이 자료에서 사람의 판단이 들어가는 곳은 여기뿐이다.</p>
  <figure>
    <div class="scroll"><svg id="c-adj" width="1000" height="130" role="img"
      aria-label="신청 등급 대비 결정 등급의 조정 비율"></svg></div>
    <figcaption>신청한 대로 결정된 것이 대부분이고, 조정된 경우는 올린 쪽이 내린 쪽보다 많다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">2부 · 게임물</span><h2>점수가 없고 이름표만 붙는다</h2></div>
  <p class="sdesc">게임물은 항목에 점수를 매기지 않는다. 해당하는 항목의 이름만 나열된다.
  {v['grac_n']:,}건 가운데 {v['grac_empty']:,}건({v['grac_empty_pct']}%)은 이 칸이 비어 있는데,
  그 건들의 청소년이용불가 비율이 {v['grac_empty_yr']}%였다. 적지 않은 것이 아니라 해당하는 것이
  없다는 뜻이다.</p>
  <figure>
    <div class="scroll"><svg id="c-solo" width="1000" height="{60 + len(v['grac_solo']) * 38}" role="img"
      aria-label="이름표 하나만 붙은 게임물의 청소년이용불가 비율"></svg></div>
    <figcaption>이름표가 하나만 붙은 게임물을 모았다. 같은 '하나'인데 결과가 전혀 다르다.
    {top[0]}이 붙으면 사실상 청소년이용불가가 확정되고, {v['grac_solo'][-2][0]}과 {bot[0]}은
    붙어도 열에 아홉은 그렇지 않다.</figcaption>
  </figure>
  <div class="note">등급을 준 뒤 취소된 건이 {v['grac_cancel']:,}건 있다. 신청 내용과 실제
  서비스가 다른 경우가 대표적이어서, 내용정보와 등급의 관계를 보는 분석에서는 제외했다.</div>
</section>

<section>
  <div class="shead"><span class="snum">3부 · 두 매체</span><h2>같은 이름표라도 무게가 다르다</h2></div>
  <p class="sdesc">이름이 똑같은 네 가지(선정성·폭력성·공포·약물)만 골라 비교했다. 영상물은 점수가
  있으므로 3점 이상이면 있는 것으로 놓아 형식을 맞췄다. 비교 대상 밖의 항목이 붙은 건은 양쪽 모두
  뺐다. 영상물 {v['cmp_kn']:,}건, 게임물 {v['cmp_gn']:,}건이 남았다.</p>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c1)"></i>영상물</span>
      <span><i class="sw" style="background:var(--c2)"></i>게임물</span>
    </div>
    <div class="scroll"><svg id="c-cmp" width="1000" height="{60 + len(v['compare']) * 52}" role="img"
      aria-label="같은 이름표를 가졌을 때 매체별 청소년 이용 제한 비율"></svg></div>
    <figcaption>네 가지 모두 게임물 쪽이 높다. 아무 이름표도 붙지 않은 건은 양쪽 다 0%에 가까워
    (영상물 0.0% · 게임물 0.1%) 비교가 제대로 짝지어졌음을 확인했다.</figcaption>
  </figure>
  <div class="note"><b>이 결론에는 조건이 붙는다.</b> '3점 이상이면 있는 것으로 친다'는 기준은
  분석자가 정한 것이지 자료가 정해 준 것이 아니다. 기준을 4점 이상으로 바꾸면 영상물 쪽이 100%가
  되어 비교 자체가 성립하지 않는다. 영상물은 4점이 곧 청소년관람불가이기 때문이다.
  그래서 이 결과를 말할 때는 기준을 반드시 함께 적는다.</div>
</section>

<section>
  <div class="shead"><span class="snum">4부 · 자료의 한계</span><h2>공개된 것은 전체의 일부다</h2></div>
  <p class="sdesc">게임 등급은 두 갈래로 매겨진다. 위원회가 직접 심의하는 것과, 구글·애플 같은
  사업자가 스스로 매기는 것이다. 공개 자료로 받을 수 있는 것은 앞의 것뿐이다.
  같은 기간({r['from']} ~ {r['to']}, 약 {r['days']}일)으로 맞춰 크기를 재 보았다.</p>
  <div class="hero-stat">
    <div class="big">{r['share']}<span style="font-size:.42em">%</span></div>
    <p>같은 기간에 공개 자료로 볼 수 있었던 몫이다. 위원회 심의 {r['com_n']:,}건 대
    사업자 자체 분류 {r['self_n']:,}건, 약 {r['ratio']}배 차이다.</p>
  </div>
  <figure>
    <div class="scroll"><svg id="c-rater" width="1000" height="190" role="img"
      aria-label="같은 기간 위원회 심의와 사업자 자체 분류의 건수 비교"></svg></div>
    <figcaption>19년치 위원회 물량보다 7주치 자체 분류가 더 많다. 이 프로젝트의 게임물 분석 결과는
    '게임물 전체'가 아니라 '위원회가 직접 심의한 게임물'의 이야기로 읽어야 한다.</figcaption>
  </figure>
  <div class="note"><b>다만 이 차이를 심의의 엄격함으로 읽어서는 안 된다.</b> 두 갈래에 들어오는
  게임이 애초에 다르다. 사업자 자체 분류에는 사행성 게임이 사실상 없다({r['self_gam']}%,
  위원회 쪽은 {r['com_gam']}%). 그런데 사행성만 붙어도 청소년이용불가가 {top[2]}%다.
  등급 분포의 차이는 상당 부분 여기서 온다.</div>
  <h3>남는 한계</h3>
  <p class="col">영상물 자료에도 같은 성격의 문제가 있다. 성인물이 {v['adult_share']}%를 차지하는데
  성인물은 내용정보와 상관없이 거의 전부 청소년관람불가다. 실제로 이 치우침 때문에 1차 분석 결론이
  한 번 뒤집혔다. 비교용으로 쓴 자체 분류 자료는 약 7주치가 전부이고 갱신이 불가능해, 추세를 읽는
  데는 쓰지 않고 한 시점의 규모 비교로만 썼다.</p>
</section>

<footer>
  영상물등급위원회 비디오물 등급분류정보 조회 서비스 · 게임물관리위원회 게임물 등급분류 정보
  (공공데이터포털) 전량 수집분 기준 · {datetime.now():%Y년 %m월 %d일} 산출<br>
  이 페이지는 <span class="mono">src/make_final_report.py</span> 로 다시 만들 수 있다.
  원본이 갱신되면 값이 자동으로 반영된다.
</footer>
</div>
<div id="tip" role="status" aria-live="polite"></div>

<script>
const NS="http://www.w3.org/2000/svg";
const el=(n,a={{}})=>{{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e;}};
const fmt=n=>n.toLocaleString("ko-KR");
const GRADES={js(GRADES)};
const RAMP=["--s1","--s2","--s3","--s4","--s5"];
const RULE={js(v['rule'])};
const YEAR={js(v['year'])};
const KIND={js(v['kind'])};
const REASONS={js(v['reason_names'])};
const HEAT={js(v['heat'])};
const ADJ={js(v['adjust'])};
const SOLO={js(v['grac_solo'])};
const CMP={js(v['compare'])};
const RATER={js(v['rater'])};

const tip=document.getElementById("tip");
function bindTip(node,text){{
  node.setAttribute("data-tip",text); node.setAttribute("tabindex","0");
  const show=e=>{{tip.textContent=text;tip.style.opacity="1";
    const r=node.getBoundingClientRect();
    tip.style.left=Math.min(window.innerWidth-260,(e.clientX||r.left)+14)+"px";
    tip.style.top=((e.clientY||r.top)-16)+"px";}};
  node.addEventListener("mousemove",show); node.addEventListener("focus",show);
  node.addEventListener("mouseleave",()=>tip.style.opacity="0");
  node.addEventListener("blur",()=>tip.style.opacity="0");
}}

/* 1. 최고 점수 x 관람등급 */
(function(){{
  const svg=document.getElementById("c-rule"),L=104,T=52,CW=168,CH=46,G=3;
  GRADES.forEach((g,c)=>{{
    const t=el("text",{{x:L+c*CW+CW/2,y:T-16,class:"axis","text-anchor":"middle"}});
    t.textContent=g;svg.appendChild(t);
  }});
  RULE.forEach(([lv,...cells],rI)=>{{
    const t=el("text",{{x:0,y:T+rI*CH+CH/2+5,class:"rowlab"}});
    t.textContent=lv+"점";svg.appendChild(t);
    const rowTotal=cells.reduce((a,b)=>a+b,0)||1;
    cells.forEach((n,c)=>{{
      const share=n/rowTotal;
      /* 바탕은 항상 깔고, 그 위에 건수 비중만큼 진하게 덧칠한다.
         1건과 58,377건이 같은 농도로 보이면 대각선이라는 사실 자체가 가려진다. */
      const bg=el("rect",{{x:L+c*CW,y:T+rI*CH,width:CW-G,height:CH-G,rx:3,fill:"var(--sunk)"}});
      svg.appendChild(bg);
      if(n>0){{
        const rect=el("rect",{{x:L+c*CW,y:T+rI*CH,width:CW-G,height:CH-G,rx:3,
          fill:"var(--s5)","fill-opacity":Math.max(share,0.07).toFixed(3)}});
        bindTip(rect,`가장 높은 점수 ${{lv}}점 → ${{GRADES[c]}} · ${{fmt(n)}}건 (그 줄의 ${{(share*100).toFixed(share<1?2:0)}}%)`);
        svg.appendChild(rect);
        const tx=el("text",{{x:L+c*CW+(CW-G)/2,y:T+rI*CH+CH/2+5,
          "text-anchor":"middle","font-size":"12.5",
          fill:share>=0.55?"var(--surface)":"var(--ink2)","font-weight":"500"}});
        tx.textContent=fmt(n);svg.appendChild(tx);
      }}
    }});
  }});
  const n=el("text",{{x:L,y:T+RULE.length*CH+26,class:"axis"}});
  n.textContent="가로 = 실제 관람등급 · 세로 = 내용정보 항목 중 가장 높은 점수 · 칠이 진할수록 그 줄에서 차지하는 비중이 크다";
  svg.appendChild(n);
}})();

/* 2. 연도별 등급 구성 */
(function(){{
  const lg=document.getElementById("lg-grade");
  GRADES.forEach((g,i)=>{{const s=document.createElement("span");
    s.innerHTML=`<i class="sw" style="background:var(${{RAMP[i]}})"></i>${{g}}`;lg.appendChild(s);}});
  const svg=document.getElementById("c-year"),L=120,R=40,W=1000-L-R,H=22,G=5;
  YEAR.forEach(([y,n,...p],rI)=>{{
    const yy=8+rI*(H+G);
    const t=el("text",{{x:0,y:yy+16,class:"rowlab"}});t.textContent=y;svg.appendChild(t);
    const c=el("text",{{x:L-12,y:yy+16,class:"axis","text-anchor":"end"}});
    c.textContent=fmt(n);svg.appendChild(c);
    let x=L;
    p.forEach((val,i)=>{{
      if(val<=0)return;
      const w=W*val/100;
      const rect=el("rect",{{x:x,y:yy,width:Math.max(w-2,1),height:H,rx:2,fill:`var(${{RAMP[i]}})`}});
      bindTip(rect,`${{y}}년 · ${{GRADES[i]}} ${{val}}% (약 ${{fmt(Math.round(n*val/100))}}건)`);
      svg.appendChild(rect);
      if(val>=11){{
        const lb=el("text",{{x:x+7,y:yy+15,class:"vlab",fill:i>=3?"var(--surface)":"var(--ink)"}});
        lb.textContent=val.toFixed(0)+"%";svg.appendChild(lb);
      }}
      x+=w;
    }});
  }});
}})();

/* 3. 종류별 */
(function(){{
  const svg=document.getElementById("c-kind"),L=110,R=210,W=1000-L-R,H=24,G=10;
  const max=Math.max(...KIND.map(k=>k[1]));
  KIND.forEach(([name,n,yr],i)=>{{
    const y=8+i*(H+G);
    const t=el("text",{{x:0,y:y+17,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    const w=Math.max(W*n/max,2);
    const rect=el("rect",{{x:L,y:y,width:w,height:H,rx:2,fill:"var(--c1)"}});
    bindTip(rect,`${{name}} · ${{fmt(n)}}건 · 청소년관람불가 ${{yr}}%`);
    svg.appendChild(rect);
    const v=el("text",{{x:L+w+12,y:y+17,class:"vlab"}});
    v.textContent=`${{fmt(n)}}건   청소년관람불가 ${{yr}}%`;svg.appendChild(v);
  }});
}})();

/* 4. 종류 x 결정 이유 */
(function(){{
  const svg=document.getElementById("c-heat"),L=110,T=48,
        CW=Math.min(118,(1000-L)/REASONS.length),CH=36,G=3;
  REASONS.forEach((n,c)=>{{
    const t=el("text",{{x:L+c*CW+CW/2,y:T-14,class:"axis","text-anchor":"middle"}});
    t.textContent=n;svg.appendChild(t);
  }});
  HEAT.forEach(([kind,...vals],rI)=>{{
    const t=el("text",{{x:0,y:T+rI*CH+CH/2+5,class:"rowlab"}});t.textContent=kind;svg.appendChild(t);
    vals.forEach((val,c)=>{{
      const step=Math.min(4,Math.floor(val/20));
      const rect=el("rect",{{x:L+c*CW,y:T+rI*CH,width:CW-G,height:CH-G,rx:2,
        fill:`var(${{RAMP[step]}})`}});
      bindTip(rect,`${{kind}} · ${{REASONS[c]}} ${{val}}%`);
      svg.appendChild(rect);
      const tx=el("text",{{x:L+c*CW+(CW-G)/2,y:T+rI*CH+CH/2+5,class:"vlab","text-anchor":"middle",
        fill:step>=3?"var(--surface)":"var(--ink)"}});
      tx.textContent=val.toFixed(0)+"%";svg.appendChild(tx);
    }});
  }});
  const n=el("text",{{x:L,y:T+HEAT.length*CH+24,class:"axis"}});
  n.textContent="각 종류에서 그 항목이 등급 결정 이유로 지목된 비율";
  svg.appendChild(n);
}})();

/* 5. 신청 대비 조정 */
(function(){{
  const svg=document.getElementById("c-adj"),W=1000,H=38;
  const colors=["var(--s2)","var(--c1)","var(--c3)"];
  let x=0;
  ADJ.forEach(([name,n,pct],i)=>{{
    const w=W*pct/100;
    const rect=el("rect",{{x:x,y:34,width:Math.max(w-2,1),height:H,rx:3,fill:colors[i]}});
    bindTip(rect,`${{name}} · ${{fmt(n)}}건 · ${{pct}}%`);
    svg.appendChild(rect);
    const t=el("text",{{x:x,y:24,class:"vlab"}});
    t.textContent=`${{name}} ${{pct}}%`;svg.appendChild(t);
    const c=el("text",{{x:x,y:92,class:"axis"}});c.textContent=fmt(n)+"건";svg.appendChild(c);
    x+=w;
  }});
}})();

/* 6. 게임물 이름표별 */
(function(){{
  const svg=document.getElementById("c-solo"),L=100,R=190,W=1000-L-R,H=26,G=12;
  SOLO.forEach(([name,n,pct],i)=>{{
    const y=10+i*(H+G);
    const t=el("text",{{x:0,y:y+18,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    const w=Math.max(W*pct/100,2);
    const step=Math.min(4,Math.floor(pct/22));
    const rect=el("rect",{{x:L,y:y,width:w,height:H,rx:2,fill:`var(${{RAMP[step]}})`}});
    bindTip(rect,`${{name}}만 붙은 게임물 ${{fmt(n)}}건 중 ${{pct}}%가 청소년이용불가`);
    svg.appendChild(rect);
    const v=el("text",{{x:L+w+12,y:y+18,class:"vlab"}});
    v.textContent=`${{pct}}%   (${{fmt(n)}}건)`;svg.appendChild(v);
  }});
  const n=el("text",{{x:L,y:10+SOLO.length*(H+G)+16,class:"axis"}});
  n.textContent="가로축 = 청소년이용불가 비율 (0~100%)";svg.appendChild(n);
}})();

/* 7. 매체 비교 */
(function(){{
  const svg=document.getElementById("c-cmp"),L=100,R=200,W=1000-L-R,H=19,G=5,ROW=52;
  const max=Math.max(...CMP.map(c=>Math.max(c[2],c[4])),10);
  CMP.forEach(([name,kn,kp,gn,gp],i)=>{{
    const y=14+i*ROW;
    const t=el("text",{{x:0,y:y+22,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    [[kp,kn,"var(--c1)","영상물"],[gp,gn,"var(--c2)","게임물"]].forEach(([pct,n,col,lab],j)=>{{
      const yy=y+j*(H+G);
      const w=Math.max(W*pct/max,2);
      const rect=el("rect",{{x:L,y:yy,width:w,height:H,rx:2,fill:col}});
      bindTip(rect,`${{lab}} · ${{name}}만 있는 ${{fmt(n)}}건 중 ${{pct}}%`);
      svg.appendChild(rect);
      const v=el("text",{{x:L+w+11,y:yy+14,class:"vlab"}});
      v.textContent=`${{lab}} ${{pct}}%`;svg.appendChild(v);
    }});
  }});
}})();

/* 8. 누가 매기는가 */
(function(){{
  const svg=document.getElementById("c-rater"),L=150,R=180,W=1000-L-R,H=42,G=26;
  const max=RATER.self_n;
  [["위원회 심의",RATER.com_n,RATER.com_yr,"var(--c1)"],
   ["사업자 자체 분류",RATER.self_n,RATER.self_yr,"var(--c3)"]].forEach(([name,n,yr,col],i)=>{{
    const y=22+i*(H+G);
    const t=el("text",{{x:0,y:y+26,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    const w=Math.max(W*n/max,3);
    const rect=el("rect",{{x:L,y:y,width:w,height:H,rx:3,fill:col}});
    bindTip(rect,`${{name}} · ${{fmt(n)}}건 · 청소년이용불가 ${{yr}}%`);
    svg.appendChild(rect);
    const v=el("text",{{x:L+w+13,y:y+26,class:"vlab"}});
    v.textContent=`${{fmt(n)}}건`;svg.appendChild(v);
  }});
  const n=el("text",{{x:L,y:22+2*(H+G)+14,class:"axis"}});
  n.textContent="같은 기간 " + RATER.from + " ~ " + RATER.to;
  svg.appendChild(n);
}})();
</script>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    v = compute()
    print(f"영상물 {v['kmrb_n']:,}건 / 게임물 {v['grac_n']:,}건 / 비교용 {v['rater']['self_n']:,}건")
    print(f"  최고 점수 규칙 일치율 {v['rule_rate']}%")
    print(f"  공개 자료 몫 {v['rater']['share']}%")

    dest = OUT / "final_report.html"
    dest.write_text(render(v), encoding="utf-8")
    print(f"\n저장: {dest}  ({dest.stat().st_size/1024:.0f} KB)")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
