# -*- coding: utf-8 -*-
"""
최종 보고서 생성: 인사이트 순서로

처음에는 작업한 순서(수집 → 규칙 확인 → 비교)대로 썼다. 그렇게 하니 읽고 나서도
"그래서 무슨 뜻인가"가 남지 않는다는 지적을 받았다. 맞는 지적이라 다시 짰다.

    바꾸기 전                            바꾼 뒤
    등급은 무엇으로 정해지는가            청소년이용불가를 만드는 것
    1부 영상물 → 2부 게임물 → 3부 비교     결론 세 가지를 차례로, 근거는 각 장 안에
    규칙·이진화 설명이 맨 앞               "어떻게 확인했나"로 묶어 맨 뒤로

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

LV = [f"rtStdName{i}_lv" for i in range(1, 8)]
GRADES = ["전체관람가", "12세", "15세", "청소년관람불가", "제한관람가"]
AGES = [0, 12, 15, 18, 19]
LEVEL_TO_AGE = {1: 0, 2: 12, 3: 15, 4: 18, 5: 19}
DESC = ["사행성", "폭력성", "선정성", "언어", "약물", "공포", "범죄"]


def ymd(ts) -> str:
    return f"{ts.year}년 {ts.month}월 {ts.day}일"


def latest(p: str) -> Path:
    f = sorted(PROC.glob(p))
    if not f:
        sys.exit(f"[중단] {p} 정제본이 없습니다.")
    return f[-1]


def js(o) -> str:
    return json.dumps(o, ensure_ascii=False)


# ══════════════════════════════════════════ 값 계산
def compute() -> dict:
    k = pd.read_parquet(latest("kmrb_video_clean_*.parquet")).dropna(subset=LV + ["grade_age"]).copy()
    g = pd.read_parquet(latest("grac_game_clean_*.parquet"))
    s = pd.read_parquet(latest("grac_self_clean_*.parquet"))
    ga = g[~g["is_canceled"]].dropna(subset=["grade_age"]).copy()
    v: dict = {}

    # ── 결론 1. 게임물: 무엇이 청소년이용불가를 만드나
    yr = ga[ga["is_youth_restricted"] == True]          # noqa: E712
    v["g_n"], v["g_yr_n"] = len(ga), len(yr)
    v["g_yr_pct"] = round(len(yr) / len(ga) * 100, 1)
    v["compose"] = sorted(
        [[n, int(yr[f"내용_{n}"].sum()), round(float(yr[f"내용_{n}"].mean()) * 100, 1)] for n in DESC],
        key=lambda r: -r[1])
    has, no = ga[ga["내용_사행성"] == 1], ga[ga["내용_사행성"] == 0]
    v["gam"] = {"has_n": len(has), "has_yr": round(float(has["is_youth_restricted"].mean()) * 100, 1),
                "no_n": len(no), "no_yr": round(float(no["is_youth_restricted"].mean()) * 100, 1)}
    solo = []
    for n in DESC:
        sub = ga[(ga[f"내용_{n}"] == 1) & (ga["n_descriptors"] == 1)]
        if len(sub) >= 20:
            solo.append([n, len(sub), round(float(sub["is_youth_restricted"].mean()) * 100, 1)])
    v["solo"] = sorted(solo, key=lambda r: -r[2])
    plat = []
    for p, sub in ga.groupby("platform"):
        if len(sub) < 300:
            continue
        plat.append([str(p), len(sub), round(float(sub["내용_사행성"].mean()) * 100, 1),
                     round(float(sub["is_youth_restricted"].mean()) * 100, 1)])
    v["plat"] = sorted(plat, key=lambda r: -r[2])

    # 조합별: 선정성·폭력성·사행성 세 가지의 조합만 본다.
    # 나머지 항목(언어·약물·공포·범죄)은 섞여 있을 수 있다. 세 가지가 등급을 좌우하기 때문이다.
    def masks(df):
        S, V, G = df["내용_선정성"], df["내용_폭력성"], df["내용_사행성"]
        return [("선정성만", (S == 1) & (V == 0) & (G == 0), False),
                ("폭력성만", (S == 0) & (V == 1) & (G == 0), False),
                ("선정+폭력", (S == 1) & (V == 1) & (G == 0), False),
                ("사행성만", (S == 0) & (V == 0) & (G == 1), True),
                ("선정+사행", (S == 1) & (V == 0) & (G == 1), True),
                ("사행+폭력", (S == 0) & (V == 1) & (G == 1), True)]

    combo = []
    for name, m, gam in masks(ga):
        sub = ga[m]
        if len(sub) < 20:
            continue
        combo.append([name, len(sub), round(float(sub["is_youth_restricted"].mean()) * 100, 1), gam])
    v["combo"] = sorted(combo, key=lambda r: -r[2])
    v["combo_names"] = [c[0] for c in v["combo"]]

    pc_rows = []
    for p, sub in ga.groupby("platform"):
        if len(sub) < 300:
            continue
        cells = []
        by = {n: (m, gam) for n, m, gam in masks(sub)}
        for name in v["combo_names"]:
            m = by[name][0]
            t = sub[m]
            cells.append([round(float(t["is_youth_restricted"].mean()) * 100, 1), len(t)]
                         if len(t) >= 20 else [None, len(t)])
        pc_rows.append([str(p), len(sub), cells,
                        round(float(sub["is_youth_restricted"].mean()) * 100, 1)])
    v["platcombo"] = sorted(pc_rows, key=lambda r: -r[3])

    # 사행성이 어디에 몰려 있나: 장르와 업체
    gam_only = ga[ga["내용_사행성"] == 1]
    base_g = ga["genre"].value_counts(normalize=True)
    genre = []
    for name, n in gam_only["genre"].value_counts().head(6).items():
        genre.append([str(name), int(n), round(n / len(gam_only) * 100, 1),
                      round(float(base_g.get(name, 0)) * 100, 1)])
    v["gam_genre"] = genre
    v["gam_n"] = len(gam_only)

    ent = []
    for name, n in gam_only["entname"].value_counts().head(10).items():
        tot = int((ga["entname"] == name).sum())
        if tot < 30:
            continue
        ent.append([str(name), int(n), tot, round(n / tot * 100, 1)])
    v["gam_ent"] = sorted(ent, key=lambda r: -r[3])
    v["gam_ent_n"] = int(gam_only["entname"].nunique())
    v["ent_n"] = int(ga["entname"].nunique())

    # 등급취소
    c = g[g["is_canceled"]]
    v["cancel"] = {"n": len(c), "pct": round(float(g["is_canceled"].mean()) * 100, 1),
                   "gam": round(float(c["내용_사행성"].mean()) * 100, 1),
                   "gam_all": round(float(g["내용_사행성"].mean()) * 100, 1)}
    cg = []
    for name, n in c["genre"].value_counts().head(6).items():
        cg.append([str(name), int(n), round(n / len(c) * 100, 1),
                   round(float(base_g.get(name, 0)) * 100, 1)])
    v["cancel_genre"] = cg
    gap = (pd.to_datetime(c["canceleddate"], errors="coerce")
           - pd.to_datetime(c["rateddate"], errors="coerce")).dt.days.dropna()
    v["cancel_gap"] = {"median": int(gap.median()), "within1y": round(float((gap <= 365).mean()) * 100)}

    # ── 결론 2. 그 심의망의 크기
    lo, hi = s["rated_date"].min(), s["rated_date"].max()
    same = ga[(ga["rated_date"] >= lo) & (ga["rated_date"] <= hi)]
    v["rater"] = {"from": ymd(lo), "to": ymd(hi), "days": (hi - lo).days,
                  "com_n": len(same), "self_n": len(s),
                  "com_yr": round(float(same["is_youth_restricted"].mean()) * 100, 1),
                  "self_yr": round(float(s["is_youth_restricted"].mean()) * 100, 2),
                  "ratio": round(len(s) / max(len(same), 1)),
                  "share": round(len(same) / (len(same) + len(s)) * 100, 2),
                  "self_gam": round(float(s["내용_사행성"].mean()) * 100, 2),
                  "com_gam": round(float(ga["내용_사행성"].mean()) * 100, 1),
                  "self_all": round(float((s["grade_age"] == 0).mean()) * 100, 1)}

    # ── 결론 3. 영상물: 판단이 들어가는 곳
    k["cmax"] = k[LV].max(axis=1).astype(int)
    v["k_n"] = len(k)
    ok = (k["cmax"].map(LEVEL_TO_AGE) == k["grade_age"])
    v["rule_rate"], v["rule_miss"] = round(float(ok.mean()) * 100, 2), int((~ok).sum())
    v["rule"] = [[lv] + [int(((k["cmax"] == lv) & (k["grade_age"] == a)).sum()) for a in AGES]
                 for lv in range(1, 6)]
    v["rule_nota"] = {str(n): [len(sub),
                               round(float((sub["cmax"].map(LEVEL_TO_AGE) == sub["grade_age"]).mean()) * 100, 3)]
                      for n, sub in k.groupby("content_notation") if len(sub) > 100}
    adj = k.dropna(subset=["hope_grade_age"])
    d = adj["grade_age"] - adj["hope_grade_age"]
    v["adj"] = {"same": round(float((d == 0).mean()) * 100, 1),
                "up": round(float((d > 0).mean()) * 100, 1),
                "down": round(float((d < 0).mean()) * 100, 1),
                "n": len(adj)}
    hope = []
    for gr, sub in adj.groupby("hope_grade_age"):
        if len(sub) < 500:
            continue
        up = float(((sub["grade_age"] - sub["hope_grade_age"]) > 0).mean())
        hope.append([f"{int(gr)}세" if gr else "전체관람가", len(sub), round(up * 100, 1)])
    v["hope"] = hope
    v["adult_share"] = round(float((k["kindName"] == "성인물").mean()) * 100, 1)

    reason = k[k["rtCoreHarmRsnNm"].notna() & (k["rtCoreHarmRsnNm"].astype(str).str.strip() != "")]
    ex = reason.assign(r=reason["rtCoreHarmRsnNm"].astype(str).str.split(",")).explode("r")
    ex["r"] = ex["r"].str.strip()
    ex = ex[ex["r"] != ""]
    order = list(ex["r"].value_counts().index)
    v["reason_names"] = order
    v["heat"] = [[str(kd)] + [round(float((ex[ex["kindName"] == kd]["r"] == n).sum())
                                    / len(reason[reason["kindName"] == kd]) * 100, 1) for n in order]
                 for kd in reason["kindName"].value_counts().head(5).index]
    v["reason_n"] = len(reason)
    return v


# ══════════════════════════════════════════ 문서
def render(v: dict) -> str:
    r, gm = v["rater"], v["gam"]
    top = v["compose"][0]
    gr_n, gr_r = v["rule_nota"].get("등급표기", [0, 0])
    st_n, st_r = v["rule_nota"].get("단계표기", [0, 0])
    hope12 = next((h for h in v["hope"] if h[0] == "12세"), ["12세", 0, 0])
    adj_total = round(v["adj"]["up"] + v["adj"]["down"], 1)
    cmb = {c[0]: c[2] for c in v["combo"]}
    cmb_sv, cmb_s = cmb.get("선정+폭력", 0), cmb.get("선정성만", 0)

    return f"""<title>청소년이용불가를 만드는 것</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Sans+KR:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --ground:#F6F7F9; --surface:#FFFFFF; --sunk:#EDEFF3;
  --ink:#141922; --ink2:#3D4654; --muted:#5C6675;
  --line:#E2E6EC; --line2:#CBD2DC; --accent:#1F3864;
  --s1:#E3E9F2; --s2:#B9C9E1; --s3:#8AA6CE; --s4:#5A7CB0; --s5:#2C4B7C;
  --c1:#2E5FA3; --c2:#A8761C; --c3:#B03A5B;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#111418; --surface:#181C22; --sunk:#1F242B;
    --ink:#EDF0F4; --ink2:#C3CAD4; --muted:#8D97A5;
    --line:#272D35; --line2:#39414C; --accent:#9DB8E0;
    --s1:#24344A; --s2:#33507A; --s3:#4A73A8; --s4:#7099CE; --s5:#A9C4E6;
    --c1:#5C90CE; --c2:#BC8A33; --c3:#C86680;
  }}
}}
:root[data-theme="dark"] {{
  --ground:#111418; --surface:#181C22; --sunk:#1F242B;
  --ink:#EDF0F4; --ink2:#C3CAD4; --muted:#8D97A5;
  --line:#272D35; --line2:#39414C; --accent:#9DB8E0;
  --s1:#24344A; --s2:#33507A; --s3:#4A73A8; --s4:#7099CE; --s5:#A9C4E6;
  --c1:#5C90CE; --c2:#BC8A33; --c3:#C86680;
}}
*{{box-sizing:border-box}}
body{{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:'IBM Plex Sans KR','Malgun Gothic',system-ui,sans-serif;
  font-weight:300; font-size:16px; line-height:1.8; padding:0 24px 120px;
  word-break:keep-all; overflow-wrap:break-word;
}}
.wrap{{max-width:1060px;margin:0 auto}}
.col{{max-width:660px}}
h1,h2,h3{{font-family:'Gowun Batang','Batang',serif;font-weight:700;line-height:1.35;
  text-wrap:balance;margin:0;word-break:keep-all}}
.mono{{font-family:'IBM Plex Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums}}

header{{padding:92px 0 44px;border-bottom:2px solid var(--line2)}}
.kicker{{font-family:'IBM Plex Mono',monospace;font-size:11.5px;letter-spacing:.18em;
  text-transform:uppercase;color:var(--muted);margin-bottom:20px}}
h1{{font-size:clamp(32px,5.6vw,54px);margin-bottom:22px;letter-spacing:-.015em}}
.lede{{font-size:18.5px;color:var(--ink2);max-width:620px;line-height:1.75}}

.summary{{margin-top:44px;display:grid;gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:5px;overflow:hidden}}
.srow{{background:var(--surface);padding:22px 26px;display:grid;
  grid-template-columns:112px 1fr;gap:22px;align-items:baseline}}
.srow .tag{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted)}}
.srow p{{margin:0;font-size:16.5px;color:var(--ink);line-height:1.7}}
.srow b{{font-weight:600}}

section{{padding:68px 0;border-bottom:1px solid var(--line)}}
.shead{{margin-bottom:18px}}
.eyebrow{{font-family:'IBM Plex Mono',monospace;font-size:11.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent);margin-bottom:12px}}
h2{{font-size:30px;max-width:720px}}
h3{{font-size:19px;margin:44px 0 10px}}
p{{margin:0 0 16px}}
.sdesc{{color:var(--ink2);max-width:660px;font-size:17px}}

figure{{margin:34px 0 0}}
figcaption{{font-size:14px;color:var(--muted);margin-top:14px;max-width:680px;line-height:1.7}}
.scroll{{overflow-x:auto;padding-bottom:6px}}
.legend{{display:flex;flex-wrap:wrap;gap:8px 20px;margin-bottom:14px;font-size:13px;color:var(--ink2)}}
.legend span{{display:inline-flex;align-items:center;gap:8px}}
.sw{{width:11px;height:11px;border-radius:2px;flex:none}}

.note{{background:var(--sunk);border-left:3px solid var(--accent);border-radius:0 3px 3px 0;
  padding:18px 22px;margin:28px 0;font-size:15px;color:var(--ink2);max-width:720px}}
.note b{{color:var(--ink)}}

.big-line{{display:flex;flex-wrap:wrap;gap:32px;align-items:flex-end;margin:32px 0 4px}}
.big{{font-family:'IBM Plex Mono',monospace;font-size:clamp(44px,7.5vw,72px);font-weight:500;
  line-height:1;color:var(--accent);font-variant-numeric:tabular-nums}}
.big-line p{{margin:0;max-width:400px;font-size:15px;color:var(--ink2)}}

#tip{{position:fixed;pointer-events:none;opacity:0;transition:opacity .12s;
  background:var(--ink);color:var(--ground);font-size:12.5px;line-height:1.55;
  padding:8px 11px;border-radius:4px;z-index:60;max-width:260px;
  font-family:'IBM Plex Sans KR',sans-serif;font-variant-numeric:tabular-nums}}
svg text{{font-family:'IBM Plex Sans KR',sans-serif;font-variant-numeric:tabular-nums}}
.axis{{font-size:11.5px;fill:var(--muted)}}
.vlab{{font-size:11.5px;fill:var(--ink2)}}
.rowlab{{font-size:13px;fill:var(--ink2)}}
[data-tip]{{cursor:default}}
[data-tip]:focus-visible{{outline:2px solid var(--c1);outline-offset:2px}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
footer{{padding:52px 0 0;color:var(--muted);font-size:13.5px;max-width:720px}}
table.deliv{{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0 6px}}
table.deliv th,table.deliv td{{border:1px solid var(--line);padding:9px 11px;text-align:left;vertical-align:top}}
table.deliv th{{background:var(--sunk);font-weight:600;font-size:13px}}
table.deliv .dim{{color:var(--muted);font-size:12.5px}}
</style>
<div class="wrap">

<header>
  <div class="kicker">등급분류 공공데이터 분석 · {datetime.now():%Y년 %m월 %d일}</div>
  <h1>청소년 이용 제한 등급의<br>결정 요인</h1>
  <p class="lede">게임물과 영상물의 등급분류 결과를 전량 수집하여, 청소년 이용을 제한하는 등급이
  어떤 요인에 의해 결정되는지 분석하였다. 분석 결과는 통상적인 인식과 상이하였다.</p>

  <div class="summary">
    <div class="srow"><span class="tag">결론 1</span>
      <p>게임물의 청소년이용불가 등급을 결정하는 요인은 폭력성이나 선정성이 아니라
      <b>사행성</b>이다. 청소년이용불가 게임물의 <b>{top[2]}%</b>가 사행성을 보유하고 있다.</p></div>
    <div class="srow"><span class="tag">결론 2</span>
      <p>다만 위원회 심의 대상은 게임물 전체의 <b>{r['share']}%</b>에 불과하다. 나머지는 사업자의
      자체등급분류로 처리되며, 해당 영역의 청소년이용불가 비율은 <b>{r['self_yr']}%</b>이다.</p></div>
    <div class="srow"><span class="tag">결론 3</span>
      <p>영상물 등급 결정에는 <b>재량적 판단이 거의 개입하지 않는다</b>. 내용정보 항목의 최고값이
      그대로 등급이 된다({v['rule_rate']}%). 판단이 개입하는 영역은 신청등급을 조정하는
      {adj_total}% 구간에 한정된다.</p></div>
  </div>
</header>

<section>
  <div class="shead">
    <div class="eyebrow">결론 1 · 게임물 {v['g_n']:,}건</div>
    <h2>게임물 등급 규제의 실질적 기준은 사행성이다</h2>
  </div>
  <p class="sdesc">게임물 규제의 기준으로는 통상 폭력성과 선정성이 언급된다. 그러나 청소년이용불가
  등급을 받은 게임물 {v['g_yr_n']:,}건이 실제로 보유한 내용정보 항목을 확인하면 결과는 다르다.</p>
  <figure>
    <div class="scroll"><svg id="c-compose" width="1000" height="{50 + len(v['compose']) * 38}"
      role="img" aria-label="청소년이용불가 게임물이 가진 내용정보 항목"></svg></div>
    <figcaption>청소년이용불가 게임물의 약 4분의 3이 사행성을 보유한다. 폭력성과 선정성은 각각
    약 5분의 1 수준이다. 한 건이 복수의 항목을 보유할 수 있으므로 합계는 100%를 초과한다.</figcaption>
  </figure>

  <h3>사행성 보유 여부에 따른 차이</h3>
  <figure>
    <div class="scroll"><svg id="c-gam" width="1000" height="150" role="img"
      aria-label="사행성 보유 여부에 따른 청소년이용불가 비율"></svg></div>
    <figcaption>사행성을 보유한 게임물은 {gm['has_yr']}%가 청소년이용불가에 해당한다. 사행성을
    보유하지 않은 경우 {gm['no_yr']}%로 낮아진다. 다른 항목에서는 이와 같은 수준의 차이가
    확인되지 않는다.</figcaption>
  </figure>

  <h3>단독 보유 항목별 비교</h3>
  <figure>
    <div class="scroll"><svg id="c-solo" width="1000" height="{50 + len(v['solo']) * 36}" role="img"
      aria-label="항목 하나만 가진 게임물의 청소년이용불가 비율"></svg></div>
    <figcaption>다른 항목이 혼재되지 않은 건만을 대상으로 하였다. 동일하게 항목을 하나만
    보유한 경우에도 결과는 크게 다르다. 사행성 단독 보유만으로 사실상 청소년이용불가가 확정되는
    반면, 폭력성 단독 보유 게임물은 약 90%가 청소년 이용이 가능하다.</figcaption>
  </figure>

  <h3>복수 항목 보유 시에도 사행성이 결과를 좌우한다</h3>
  <p class="col">등급에 영향이 큰 세 항목(선정성·폭력성·사행성)의 조합을 기준으로 구분하였다.
  그 밖의 항목이 함께 보유된 경우는 별도로 제외하지 않았다. 결과를 결정하는 것은 위 세 항목이기
  때문이다.</p>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c2)"></i>사행성이 들어간 조합</span>
      <span><i class="sw" style="background:var(--s3)"></i>사행성이 없는 조합</span>
    </div>
    <div class="scroll"><svg id="c-combo" width="1000" height="{50 + len(v['combo']) * 38}" role="img"
      aria-label="내용정보 조합별 청소년이용불가 비율"></svg></div>
    <figcaption>사행성을 포함한 조합 3개와 포함하지 않은 조합 3개가 명확히 구분된다.
    특기할 점은 <b>선정성·폭력성 동시 보유({cmb_sv}%)가 선정성 단독 보유({cmb_s}%)보다 낮다</b>는
    것이다. 폭력성이 추가될 경우 오히려 등급이 낮아진다. 폭력성이 부여되는 게임물이 주로
    콘솔·PC 액션물로서 성인물과는 성격이 다른 데 따른 것으로 판단된다.</figcaption>
  </figure>

  <h3>플랫폼별 세부 비교</h3>
  <figure>
    <div class="scroll"><svg id="c-platcombo" width="1000"
      height="{70 + len(v['platcombo']) * 42}" role="img"
      aria-label="플랫폼별 내용정보 조합별 청소년이용불가 비율"></svg></div>
    <figcaption>각 칸의 값은 해당 플랫폼에서 해당 조합을 보유한 게임물의 청소년이용불가
    비율이다. 표본이 20건 미만인 칸은 표시하지 않았다. 사행성을 포함한 3개 열은 플랫폼과 무관하게
    높은 값을 보인다. 반면 동일한 선정성 단독 보유에서도 모바일과 콘솔의 값은 큰 차이를 보인다.
    개별 건수는 마우스를 올리면 확인할 수 있다.</figcaption>
  </figure>

  <h3>사행성 보유율과 청소년이용불가 비율의 관계</h3>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c2)"></i>사행성이 붙은 비율</span>
      <span><i class="sw" style="background:var(--c1)"></i>청소년이용불가 비율</span>
    </div>
    <div class="scroll"><svg id="c-plat" width="1000" height="{50 + len(v['plat']) * 52}" role="img"
      aria-label="플랫폼별 사행성 비율과 청소년이용불가 비율"></svg></div>
    <figcaption>웹보드 게임의 비중이 높은 온라인 게임은 사행성 보유율과 청소년이용불가 비율이
    모두 가장 높은 반면, 통상 폭력성이 높다고 인식되는 콘솔(비디오 게임)은 양쪽 모두 가장 낮다.
    등급을 결정하는 요인이 폭력성이 아니라 사행성임을 보여준다.</figcaption>
  </figure>

  <h3>사행성 게임물의 장르 집중</h3>
  <p class="col">사행성을 보유한 {v['gam_n']:,}건의 장르 구성을 확인하면 특정 장르에 집중되어 있다.</p>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c2)"></i>사행성 게임 중 이 장르의 비중</span>
      <span><i class="sw" style="background:var(--s2)"></i>전체 게임 중 이 장르의 비중</span>
    </div>
    <div class="scroll"><svg id="c-gamgenre" width="1000"
      height="{50 + len(v['gam_genre']) * 50}" role="img"
      aria-label="사행성 게임의 장르 구성"></svg></div>
    <figcaption>사행성 게임물의 {v['gam_genre'][0][2]}%가 {v['gam_genre'][0][0]} 장르에
    해당한다. 전체 게임물에서 해당 장르가 차지하는 비중은 {v['gam_genre'][0][3]}%에 그친다.
    게임물 심의에서 청소년이용불가 등급을 발생시키는 것은 사실상 웹보드·베팅성 보드게임이다.</figcaption>
  </figure>

  <h3>사행성 게임물의 신청 주체</h3>
  <p class="col">신청 사업자는 총 {v['ent_n']:,}곳이며, 그중 {v['gam_ent_n']:,}곳이 사행성 게임물을
  신청하였다. 건수 기준으로는 특정 사업자에 대한 집중은 뚜렷하지 않다. 주목할 점은 다른 지표에
  있다. <b>일부 사업자는 신청 게임물의 거의 전부가 사행성에 해당한다.</b></p>
  <figure>
    <div class="scroll"><svg id="c-gament" width="1000"
      height="{50 + len(v['gam_ent']) * 34}" role="img"
      aria-label="업체별 자사 게임 중 사행성 비율"></svg></div>
    <figcaption>막대는 해당 사업자가 신청한 게임물 중 사행성이 부여된 비율이다(30건 이상 신청한
    사업자에 한정). 100%에 해당하는 사업자가 다수 존재한다. 이는 웹보드 게임물을 전문으로 하는
    사업자가 별도로 존재함을 의미하며, 해당 영역은 합법적인 사업 범위에 속한다. 게임물 심의가
    특정 장르 및 특정 사업자에 집중되는 구조임을 보여준다.</figcaption>
  </figure>

  <h3>등급분류 후 취소된 {v['cancel']['n']:,}건</h3>
  <p class="col">등급분류를 받은 후 취소된 건은 {v['cancel']['n']:,}건({v['cancel']['pct']}%)이다.
  해당 건들 역시 사행성 비중이 높다. 사행성 보유율이 {v['cancel']['gam']}%로 전체
  {v['cancel']['gam_all']}%의 2배를 상회한다.</p>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c3)"></i>취소된 건 중 이 장르의 비중</span>
      <span><i class="sw" style="background:var(--s2)"></i>전체 게임 중 이 장르의 비중</span>
    </div>
    <div class="scroll"><svg id="c-cancel" width="1000"
      height="{50 + len(v['cancel_genre']) * 50}" role="img"
      aria-label="등급취소된 게임의 장르 구성"></svg></div>
    <figcaption>베팅성 보드게임이 {v['cancel_genre'][0][2]}%로 가장 높은 비중을 차지하는 것은
    앞의 결과와 일치한다. 특기할 점은 두 번째 항목이다. {v['cancel_genre'][1][0]}이
    {v['cancel_genre'][1][2]}%를 차지하나 전체에서의 비중은 {v['cancel_genre'][1][3]}%에 그친다.
    등급분류일부터 취소일까지의 기간은 중앙값 {v['cancel_gap']['median']}일이며,
    {v['cancel_gap']['within1y']}%가 1년 이내에 취소되었다.</figcaption>
  </figure>
  <div class="note"><b>취소 사유는 자료에 기록되어 있지 않다.</b> 게임산업법상 등급취소는 신청
  내용과 다르게 유통한 경우 등에 이루어지나, 사업자가 서비스를 종료하며 자진 반납한 경우도
  취소로 기록될 수 있다. 본 자료로는 양자를 구분할 수 없으므로 위 수치를 위반 건수로 해석하여서는
  안 된다. 분석에서는 해당 건을 제외하되, 취소 대상 게임물의 구성은 별도의 분석 가치가 있어
  기록하였다.</div>
</section>

<section>
  <div class="shead">
    <div class="eyebrow">결론 2 · 같은 기간 비교</div>
    <h2>위원회 심의 대상은 전체의 {r['share']}%에 불과하다</h2>
  </div>
  <p class="sdesc">앞의 분석 결과는 위원회가 직접 심의한 게임물에 한정된다. 게임물 등급분류는
  위원회 심의와 사업자 자체등급분류의 두 경로로 이루어진다. 동일 기간({r['from']} ~ {r['to']},
  약 {r['days']}일)을 기준으로 양자를 비교하였다.</p>
  <div class="big-line">
    <div class="big">{r['share']}<span style="font-size:.42em">%</span></div>
    <p>동일 기간 위원회 심의가 차지하는 비중이다. 위원회 {r['com_n']:,}건 대 자체등급분류
    {r['self_n']:,}건으로 약 {r['ratio']}배의 차이가 있다.</p>
  </div>
  <figure>
    <div class="scroll"><svg id="c-rater" width="1000" height="200" role="img"
      aria-label="같은 기간 위원회 심의와 사업자 자체 분류의 건수"></svg></div>
    <figcaption>19년간의 위원회 분류 건수보다 7주간의 자체등급분류 건수가 더 많다. 또한
    자체등급분류에서 청소년이용불가는 {r['self_yr']}%, 전체이용가는 {r['self_all']}%이다.</figcaption>
  </figure>
  <div class="note"><b>이 차이를 심의 엄격도의 차이로 해석하여서는 안 된다.</b> 두 경로에
  접수되는 게임물의 성격이 상이하기 때문이다. 자체등급분류에는 사행성 게임물이 사실상 포함되지
  않는다({r['self_gam']}%, 위원회는 {r['com_gam']}%). 결론 1에서 확인한 바와 같이 사행성 단독
  보유만으로 청소년이용불가 비율이 {gm['has_yr']}%에 이르므로, 등급 분포의 차이는 상당 부분
  이 구성 차이에서 기인한다.</div>
  <p class="col">그럼에도 이 수치는 중요한 의미를 갖는다. 공개 자료만을 근거로 게임물의
  청소년이용불가 비율을 {v['g_yr_pct']}%로 제시할 경우 실제와 큰 차이가 발생한다. 두 경로를
  합산하면 해당 값은 1% 미만으로 낮아진다. <b>국내 게임물 등급분류의 실질은 심의가 아니라
  자율규제이며, 위원회 심의는 사행성이 문제가 되는 제한된 영역에 집중되어 있다.</b></p>
</section>

<section>
  <div class="shead">
    <div class="eyebrow">결론 3 · 영상물 {v['k_n']:,}건</div>
    <h2>영상물 등급 결정에는 재량적 판단이 거의 개입하지 않는다</h2>
  </div>
  <p class="sdesc">영상물은 주제·선정성·폭력성·대사·공포·약물·모방위험 7개 항목에 대하여 각각
  1단계부터 5단계까지의 수준을 부여한다. 이 중 최고값을 그대로 등급으로 대응시킨 결과를
  확인하였다.</p>
  <figure>
    <div class="scroll"><svg id="c-rule" width="1000" height="330" role="img"
      aria-label="내용정보 최고 점수와 관람등급의 대응"></svg></div>
    <figcaption>값이 대각선에만 분포한다. 최고값이 1단계이면 전체관람가, 2단계이면 12세이용가로
    결정된다. 전체 {v['k_n']:,}건 중 {v['rule_rate']}%가 이에 해당하며, 표기 체계가 변경된
    2017년 5월 이후 {gr_n:,}건에서는 예외가 확인되지 않는다. 대각선을 벗어난 건은 합계
    {v['rule_miss']}건에 불과하다.</figcaption>
  </figure>
  <div class="note">등급은 별도의 산정 과정을 거쳐 도출되는 값이 아니라 최고값을 그대로 반영한
  값이다. 따라서 <b>내용정보로 등급을 설명하는 분석은 성립하지 않는다.</b> 동일한 값을 두 번
  사용하는 것과 같기 때문이다. 이를 확인한 후 분석의 초점을 아래 항목으로 전환하였다.</div>

  <h3>판단이 개입하는 유일한 영역: 신청등급 조정</h3>
  <p class="col">신청등급은 결정등급과 성격이 다르다. 신청인이 자체적으로 판단하여 기재한 값이므로
  결정등급과 동일한 값이 아니다. 전체 {v['adj']['n']:,}건 중 {adj_total}%에서 조정이 발생하였다
  (상향 {v['adj']['up']}% · 하향 {v['adj']['down']}%).</p>
  <figure>
    <div class="scroll"><svg id="c-hope" width="1000" height="{50 + len(v['hope']) * 44}" role="img"
      aria-label="신청 등급별 상향 조정 비율"></svg></div>
    <figcaption>{hope12[0]}로 신청한 건의 {hope12[2]}%가 상향 조정되었다. 신청인이 등급을 가장
    낮게 예측하는 구간이다. 반면 청소년관람불가로 신청한 경우에는 상향 여지가 거의 없어 조정이
    드물게 발생한다.</figcaption>
  </figure>

  <h3>최고값을 차지한 항목의 구성</h3>
  <figure>
    <div class="scroll"><svg id="c-heat" width="1000" height="{70 + len(v['heat']) * 40}" role="img"
      aria-label="영상물 종류별로 등급을 결정한 항목"></svg></div>
    <figcaption>자료에는 등급 결정 사유를 항목명으로 기록한 필드가 존재한다
    ({v['reason_n']:,}건). 종별에 따라 구성이 뚜렷하게 구분되며, 성인물은 선정성, 극영화와 숏폼은
    폭력성, 뮤직비디오는 약물이 주된 사유이다. 게임물에서 사행성이 수행한 역할을 영상물에서는
    종별에 따라 서로 다른 항목이 수행한다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead">
    <div class="eyebrow">부록</div>
    <h2>분석 방법 및 한계</h2>
  </div>

  <h3>자료</h3>
  <p class="col">두 기관이 공개하는 등급분류 결과를 각각 전량 수집하였으며, 수집 건수는 기관이
  제공하는 총 건수와 일치한다. 영상물 {v['k_n']:,}건(2009~2026), 게임물 {v['g_n']:,}건
  (2007~2026)이다. 결론 2에 사용한 자체등급분류 자료 {r['self_n']:,}건은 본 분석에서 수집한 것이
  아니라 별도 업무 과정에서 확보된 자료로서, 약 7주간의 자료에 한정되며 갱신이 불가능하다.
  따라서 추세 분석에는 사용하지 않고 특정 시점의 규모 비교에만 사용하였다.</p>

  <h3>매체 간 비교의 한계</h3>
  <p class="col">영상물은 항목별 수준값을 제공하는 반면 게임물은 항목명만을 제공한다. 동일한
  기준으로 비교하려면 영상물에 대하여 특정 단계 이상을 보유로 간주하는 절단 기준을 설정하여야
  하나, 그 기준은 자료로부터 도출되지 않는다. 3단계를 기준으로 할 경우 게임물의 판정이 더
  엄격한 것으로 나타나고, 4단계를 기준으로 할 경우 영상물이 정의상 100%가 되어 비교가 성립하지
  않는다. 따라서 본 보고서는 두 매체의 심의 엄격도를 비교하는 결론을 제시하지 않는다.</p>

  <h3>표본 구성의 편중</h3>
  <p class="col">영상물은 성인물이 {v['adult_share']}%를 차지하며, 성인물은 내용정보와 무관하게
  대부분 청소년관람불가에 해당한다. 이 편중을 통제하지 않을 경우 결론이 반대로 도출될 수 있다.
  실제로 1차 분석에서 도출한 '보유 항목 수가 많을수록 등급이 상승한다'는 결과는 폐기하였다.
  성인물이 특정 구간에 집중되어 발생한 착시였기 때문이다.</p>

  <h3>미분석 영역: 서술형 필드 2종</h3>
  <p class="col">두 자료 모두 서술형 설명 필드를 포함하고 있다. 본 분석에서는 다루지 않았으나
  후속 분석의 대상이 될 수 있다.</p>
  <p class="col"><b>게임물 개요</b>는 29,417건 중 97.4%가 기록되어 있으며 중앙값은 42자이다.
  "스마트폰 환경에서 실행되는 슬롯머신을 모사한 단독형 베팅성 게임물"과 같이 심의 관점의 표현이
  포함되어 있다. 내용정보가 기재되지 않은 13,993건의 성격을 해당 필드를 통해 확인할 수 있을
  것으로 판단된다.</p>
  <p class="col"><b>영상물 작품 내용</b>은 2018년 이후 100%가 기록되어 있으며(전체 84.6%)
  중앙값 92자의 줄거리에 해당한다. 다만 2013년 이전 구간은 "3매로구성: 1.아름다운만남"과 같이
  수록 목록만 기재되어 있거나 행정 기록이 혼재되어 있어, 활용 시 2014년 이후로 범위를 한정할
  필요가 있다.</p>
  <div class="note"><b>정정 사항.</b> 본 절은 최초 작성 시 줄거리 텍스트를 활용할 수 없다고
  기술하였다. 2009~2010년 자료 일부만을 근거로 한 판단이었으며, 최근 구간을 확인한 결과 사실과
  다른 것으로 확인되어 정정하였다.</div>

  <h3>단계표기 구간의 예외</h3>
  <p class="col">결론 3의 규칙과 불일치하는 {v['rule_miss']}건은 모두 2017년 5월 이전에 해당한다.
  해당 구간({st_n:,}건)의 일치율은 {st_r}%이며, 표기 체계를 등급명으로 변경한 이후에는
  {gr_r}%이다. 표기 방식의 변경 시점과 규칙이 예외 없이 적용된 시점이 일치한다.</p>
</section>

<section>
  <div class="shead">
    <div class="eyebrow">산출물</div>
    <h2>산출물 목록</h2>
  </div>
  <p class="col">산출물은 5종이다. 모두 원자료가 갱신될 경우 스크립트를 통해 재생성할 수 있다.</p>
  <table class="deliv">
    <tr><th>산출물</th><th>파일</th><th>만드는 스크립트</th></tr>
    <tr><td><b>통합 분석 Dataset</b><br><span class="dim">게임물·영상물 240,290건을 단일 표로
      통합. 명칭이 동일한 내용정보 4개 항목만 통합 대상으로 하였다</span></td>
      <td><a href="integrated_dataset_dictionary.html">데이터 사전</a> ·
      <span class="mono">integrated_ratings_260914.csv</span></td>
      <td class="mono">src/make_integrated.py</td></tr>
    <tr><td><b>연령등급 및 내용정보 EDA</b></td>
      <td><a href="eda_report.html">영상물</a> · <a href="eda_grac_report.html">게임물</a></td>
      <td class="mono">src/make_eda_report.py · src/eda_grac.py</td></tr>
    <tr><td><b>청소년 이용 제한 콘텐츠 주요 특성</b></td>
      <td><a href="youth_report.html">분석 결과</a></td>
      <td class="mono">src/analyze_youth.py</td></tr>
    <tr><td><b>인터랙티브 대시보드</b><br><span class="dim">Streamlit · Plotly 6개 화면 · 조건을
      변경하며 직접 조회 가능</span></td>
      <td><a href="https://gucc-rating-analysis-260910.streamlit.app/">gucc-rating-analysis-260910.streamlit.app</a></td>
      <td class="mono">app.py · src/dashboard_calc.py</td></tr>
    <tr><td><b>주요 분석 인사이트 리포트</b><br><span class="dim">본 문서</span></td>
      <td><span class="mono">final_report.html</span></td>
      <td class="mono">src/make_final_report.py</td></tr>
  </table>
  <p class="col">대시보드는 일정 시간 사용되지 않으면 대기 상태로 전환되며, 최초 접속 시 화면이
  표시되기까지 다소 시간이 소요될 수 있다. 발표 등 사전 확인이 필요한 경우 미리 접속하여
  구동해 두는 것이 바람직하다.</p>
  <p class="col">이 밖에 매체 간 판정 차이(<a href="compare_media_report.html">compare_media</a>),
  분류 주체별 비교(<a href="compare_rater_report.html">compare_rater</a>), 등급과 내용정보의 관계
  (<a href="stage4_report.html">stage4</a>)를 별도 보고서로 작성하였다. 본문의 결론은 위 3종의
  분석 결과에 근거한다.</p>
</section>

<footer>
  영상물등급위원회 비디오물 등급분류정보 조회 서비스 · 게임물관리위원회 게임물 등급분류 정보
  (공공데이터포털) 전량 수집분 기준 · {datetime.now():%Y년 %m월 %d일} 산출<br>
  본 문서는 <span class="mono">src/make_final_report.py</span> 로 재생성할 수 있으며,
  원자료가 갱신되면 수치가 자동으로 반영된다.
</footer>
</div>
<div id="tip" role="status" aria-live="polite"></div>

<script>
const NS="http://www.w3.org/2000/svg";
const el=(n,a={{}})=>{{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e;}};
const fmt=n=>n.toLocaleString("ko-KR");
const GRADES={js(GRADES)};
const RAMP=["--s1","--s2","--s3","--s4","--s5"];
const COMPOSE={js(v['compose'])};
const GAM={js(v['gam'])};
const SOLO={js(v['solo'])};
const PLAT={js(v['plat'])};
const RATER={js(v['rater'])};
const COMBO={js(v['combo'])};
const COMBONAMES={js(v['combo_names'])};
const PLATCOMBO={js(v['platcombo'])};
const GAMGENRE={js(v['gam_genre'])};
const GAMENT={js(v['gam_ent'])};
const CANCELGENRE={js(v['cancel_genre'])};
const RULE={js(v['rule'])};
const HOPE={js(v['hope'])};
const REASONS={js(v['reason_names'])};
const HEAT={js(v['heat'])};
const YRN={v['g_yr_n']};

const tip=document.getElementById("tip");
function bindTip(node,text){{
  node.setAttribute("data-tip",text); node.setAttribute("tabindex","0");
  const show=e=>{{tip.textContent=text;tip.style.opacity="1";
    const b=node.getBoundingClientRect();
    tip.style.left=Math.min(window.innerWidth-270,(e.clientX||b.left)+14)+"px";
    tip.style.top=((e.clientY||b.top)-16)+"px";}};
  node.addEventListener("mousemove",show); node.addEventListener("focus",show);
  node.addEventListener("mouseleave",()=>tip.style.opacity="0");
  node.addEventListener("blur",()=>tip.style.opacity="0");
}}
function hbar(id,rows,opt){{
  const svg=document.getElementById(id); if(!svg) return;
  const L=opt.L||100,R=opt.R||210,W=1000-L-R,H=opt.H||24,G=opt.G||14;
  const max=opt.max||Math.max(...rows.map(r=>r.v));
  rows.forEach((row,i)=>{{
    const y=10+i*(H+G);
    const t=el("text",{{x:0,y:y+17,class:"rowlab"}});t.textContent=row.label;svg.appendChild(t);
    const w=Math.max(W*row.v/max,2);
    const rect=el("rect",{{x:L,y:y,width:w,height:H,rx:2,fill:row.fill}});
    bindTip(rect,row.tip); svg.appendChild(rect);
    const lb=el("text",{{x:L+w+12,y:y+17,class:"vlab"}});lb.textContent=row.right;svg.appendChild(lb);
  }});
}}

/* 결론1: 청불 게임의 구성 */
hbar("c-compose",COMPOSE.map(([n,c,p])=>({{
  label:n, v:p, fill:n==="사행성"?"var(--c2)":"var(--s3)",
  right:`${{p}}%   (${{fmt(c)}}건)`,
  tip:`청소년이용불가 게임 ${{fmt(YRN)}}건 중 ${{n}}을 가진 것 ${{fmt(c)}}건 · ${{p}}%`}})),
  {{max:100,H:22,G:16}});

/* 결론1: 사행성 유무 */
(function(){{
  const svg=document.getElementById("c-gam"),L=150,R=230,W=1000-L-R,H=34,G=22;
  [["사행성 있음",GAM.has_n,GAM.has_yr,"var(--c2)"],
   ["사행성 없음",GAM.no_n,GAM.no_yr,"var(--s2)"]].forEach(([name,n,pct,col],i)=>{{
    const y=16+i*(H+G);
    const t=el("text",{{x:0,y:y+23,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    const w=Math.max(W*pct/100,2);
    const rect=el("rect",{{x:L,y:y,width:w,height:H,rx:3,fill:col}});
    bindTip(rect,`${{name}} ${{fmt(n)}}건 중 ${{pct}}%가 청소년이용불가`);
    svg.appendChild(rect);
    const lb=el("text",{{x:L+w+13,y:y+23,class:"vlab"}});
    lb.textContent=`${{pct}}%   (${{fmt(n)}}건 중)`;svg.appendChild(lb);
  }});
  const n=el("text",{{x:L,y:16+2*(H+G)+10,class:"axis"}});
  n.textContent="가로축 = 청소년이용불가 비율 (0~100%)";svg.appendChild(n);
}})();

/* 결론1: 항목 하나만 */
hbar("c-solo",SOLO.map(([n,c,p])=>({{
  label:n, v:p, fill:`var(${{RAMP[Math.min(4,Math.floor(p/22))]}})`,
  right:`${{p}}%   (${{fmt(c)}}건)`,
  tip:`${{n}}만 붙은 게임물 ${{fmt(c)}}건 중 ${{p}}%가 청소년이용불가`}})),
  {{max:100,H:22,G:14}});

/* 결론1: 플랫폼 */
(function(){{
  const svg=document.getElementById("c-plat"),L=130,R=210,W=1000-L-R,H=17,G=5,ROW=52;
  PLAT.forEach(([name,n,gam,yr],i)=>{{
    const y=14+i*ROW;
    const t=el("text",{{x:0,y:y+22,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    [[gam,"var(--c2)","사행성"],[yr,"var(--c1)","청소년이용불가"]].forEach(([pct,col,lab],j)=>{{
      const yy=y+j*(H+G);
      const w=Math.max(W*pct/100,2);
      const rect=el("rect",{{x:L,y:yy,width:w,height:H,rx:2,fill:col}});
      bindTip(rect,`${{name}} ${{fmt(n)}}건 · ${{lab}} ${{pct}}%`);
      svg.appendChild(rect);
      const lb=el("text",{{x:L+w+11,y:yy+13,class:"vlab"}});
      lb.textContent=`${{lab}} ${{pct}}%`;svg.appendChild(lb);
    }});
  }});
}})();

/* 결론1: 조합별 */
hbar("c-combo",COMBO.map(([n,c,p,gam])=>({{
  label:n, v:p, fill:gam?"var(--c2)":"var(--s3)",
  right:`${{p}}%   (${{fmt(c)}}건)`,
  tip:`${{n}} ${{fmt(c)}}건 중 ${{p}}%가 청소년이용불가`}})),
  {{max:100,H:22,G:16,L:110,R:210}});

/* 결론1: 플랫폼 x 조합 */
(function(){{
  const svg=document.getElementById("c-platcombo"); if(!svg) return;
  const L=130,T=52,CW=Math.min(128,(1000-L-60)/COMBONAMES.length),CH=38,G=3;
  COMBONAMES.forEach((n,c)=>{{
    const t=el("text",{{x:L+c*CW+CW/2,y:T-14,class:"axis","text-anchor":"middle"}});
    t.textContent=n;svg.appendChild(t);
  }});
  const tot=el("text",{{x:L+COMBONAMES.length*CW+30,y:T-14,class:"axis","text-anchor":"middle"}});
  tot.textContent="전체";svg.appendChild(tot);
  PLATCOMBO.forEach(([name,n,cells,all],rI)=>{{
    const y=T+rI*CH;
    const t=el("text",{{x:0,y:y+CH/2+5,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    cells.forEach(([pct,cn],c)=>{{
      const x=L+c*CW;
      if(pct===null){{
        svg.appendChild(el("rect",{{x:x,y:y,width:CW-G,height:CH-G,rx:2,fill:"var(--sunk)"}}));
        const tx=el("text",{{x:x+(CW-G)/2,y:y+CH/2+5,class:"axis","text-anchor":"middle"}});
        tx.textContent="·";svg.appendChild(tx);
        return;
      }}
      const step=Math.min(4,Math.floor(pct/20));
      const rect=el("rect",{{x:x,y:y,width:CW-G,height:CH-G,rx:2,fill:`var(${{RAMP[step]}})`}});
      bindTip(rect,`${{name}} · ${{COMBONAMES[c]}} ${{fmt(cn)}}건 중 ${{pct}}%가 청소년이용불가`);
      svg.appendChild(rect);
      const tx=el("text",{{x:x+(CW-G)/2,y:y+CH/2+5,class:"vlab","text-anchor":"middle",
        fill:step>=3?"var(--surface)":"var(--ink)"}});
      tx.textContent=pct.toFixed(0)+"%";svg.appendChild(tx);
    }});
    const a=el("text",{{x:L+COMBONAMES.length*CW+30,y:y+CH/2+5,class:"vlab","text-anchor":"middle"}});
    a.textContent=all.toFixed(0)+"%";svg.appendChild(a);
  }});
  const note=el("text",{{x:L,y:T+PLATCOMBO.length*CH+24,class:"axis"}});
  note.textContent="칸 = 그 플랫폼에서 그 조합을 가진 게임의 청소년이용불가 비율 · 점(·)은 표본 20건 미만";
  svg.appendChild(note);
}})();

/* 결론1: 사행성 장르 / 취소 장르 (같은 모양이라 함수로) */
function pairBars(id,rows,colA,labA,labB){{
  const svg=document.getElementById(id); if(!svg) return;
  const L=150,R=210,W=1000-L-R,H=17,G=5,ROW=50;
  rows.forEach(([name,n,a,b],i)=>{{
    const y=14+i*ROW;
    const t=el("text",{{x:0,y:y+22,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    [[a,colA,labA],[b,"var(--s2)",labB]].forEach(([pct,col,lab],j)=>{{
      const yy=y+j*(H+G);
      const w=Math.max(W*pct/100,2);
      const rect=el("rect",{{x:L,y:yy,width:w,height:H,rx:2,fill:col}});
      bindTip(rect,`${{name}} · ${{lab}} ${{pct}}%` + (j===0?` (${{fmt(n)}}건)`:""));
      svg.appendChild(rect);
      const lb=el("text",{{x:L+w+11,y:yy+13,class:"vlab"}});
      lb.textContent=`${{lab}} ${{pct}}%`;svg.appendChild(lb);
    }});
  }});
}}
pairBars("c-gamgenre",GAMGENRE,"var(--c2)","사행성 중","전체 중");
pairBars("c-cancel",CANCELGENRE,"var(--c3)","취소 중","전체 중");

/* 결론1: 업체별 자사 게임 중 사행성 비율 */
hbar("c-gament",GAMENT.map(([name,n,tot,p])=>({{
  label:name.length>13?name.slice(0,13)+"…":name, v:p, fill:"var(--c2)",
  right:`${{p}}%   (${{fmt(tot)}}건 중 ${{fmt(n)}}건)`,
  tip:`${{name}} · 낸 게임 ${{fmt(tot)}}건 중 ${{fmt(n)}}건(${{p}}%)이 사행성`}})),
  {{max:100,H:20,G:14,L:150,R:250}});

/* 결론2: 누가 매기나 */
(function(){{
  const svg=document.getElementById("c-rater"),L=160,R=200,W=1000-L-R,H=44,G=28;
  [["위원회 심의",RATER.com_n,RATER.com_yr,"var(--c1)"],
   ["사업자 자체 분류",RATER.self_n,RATER.self_yr,"var(--c3)"]].forEach(([name,n,yr,col],i)=>{{
    const y=24+i*(H+G);
    const t=el("text",{{x:0,y:y+27,class:"rowlab"}});t.textContent=name;svg.appendChild(t);
    const w=Math.max(W*n/RATER.self_n,3);
    const rect=el("rect",{{x:L,y:y,width:w,height:H,rx:3,fill:col}});
    bindTip(rect,`${{name}} · ${{fmt(n)}}건 · 청소년이용불가 ${{yr}}%`);
    svg.appendChild(rect);
    const lb=el("text",{{x:L+w+13,y:y+27,class:"vlab"}});
    lb.textContent=`${{fmt(n)}}건`;svg.appendChild(lb);
  }});
  const n=el("text",{{x:L,y:24+2*(H+G)+12,class:"axis"}});
  n.textContent="막대 길이는 건수를 나타낸다 · 대상 기간 " + RATER.from + " ~ " + RATER.to;
  svg.appendChild(n);
}})();

/* 결론3: 최고 점수 x 등급 */
(function(){{
  const svg=document.getElementById("c-rule"),L=104,T=52,CW=168,CH=46,G=3;
  GRADES.forEach((g,c)=>{{
    const t=el("text",{{x:L+c*CW+CW/2,y:T-16,class:"axis","text-anchor":"middle"}});
    t.textContent=g;svg.appendChild(t);
  }});
  RULE.forEach(([lv,...cells],rI)=>{{
    const t=el("text",{{x:0,y:T+rI*CH+CH/2+5,class:"rowlab"}});
    t.textContent=lv+"점";svg.appendChild(t);
    const total=cells.reduce((a,b)=>a+b,0)||1;
    cells.forEach((n,c)=>{{
      const share=n/total;
      svg.appendChild(el("rect",{{x:L+c*CW,y:T+rI*CH,width:CW-G,height:CH-G,rx:3,fill:"var(--sunk)"}}));
      if(n>0){{
        const rect=el("rect",{{x:L+c*CW,y:T+rI*CH,width:CW-G,height:CH-G,rx:3,
          fill:"var(--s5)","fill-opacity":Math.max(share,0.07).toFixed(3)}});
        bindTip(rect,`가장 높은 점수 ${{lv}}점 → ${{GRADES[c]}} · ${{fmt(n)}}건 (그 줄의 ${{(share*100).toFixed(share<1?2:0)}}%)`);
        svg.appendChild(rect);
        const tx=el("text",{{x:L+c*CW+(CW-G)/2,y:T+rI*CH+CH/2+5,"text-anchor":"middle",
          "font-size":"12.5",fill:share>=0.55?"var(--surface)":"var(--ink2)","font-weight":"500"}});
        tx.textContent=fmt(n);svg.appendChild(tx);
      }}
    }});
  }});
  const n=el("text",{{x:L,y:T+RULE.length*CH+26,class:"axis"}});
  n.textContent="가로축은 실제 관람등급, 세로축은 내용정보 항목의 최고값이다 · 색이 진할수록 해당 행에서 차지하는 비중이 크다";
  svg.appendChild(n);
}})();

/* 결론3: 신청 등급별 상향률 */
hbar("c-hope",HOPE.map(([g,n,p])=>({{
  label:g, v:p, fill:"var(--c1)",
  right:`${{p}}%   (${{fmt(n)}}건 중)`,
  tip:`${{g}}로 신청한 ${{fmt(n)}}건 중 ${{p}}%가 위로 조정됨`}})),
  {{max:30,H:22,G:22,L:120,R:230}});

/* 결론3: 종류 x 결정 이유 */
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
      const rect=el("rect",{{x:L+c*CW,y:T+rI*CH,width:CW-G,height:CH-G,rx:2,fill:`var(${{RAMP[step]}})`}});
      bindTip(rect,`${{kind}} · ${{REASONS[c]}} ${{val}}%`);
      svg.appendChild(rect);
      const tx=el("text",{{x:L+c*CW+(CW-G)/2,y:T+rI*CH+CH/2+5,class:"vlab","text-anchor":"middle",
        fill:step>=3?"var(--surface)":"var(--ink)"}});
      tx.textContent=val.toFixed(0)+"%";svg.appendChild(tx);
    }});
  }});
  const n=el("text",{{x:L,y:T+HEAT.length*CH+24,class:"axis"}});
  n.textContent="종별로 해당 항목이 등급 결정 사유로 지목된 비율";
  svg.appendChild(n);
}})();
</script>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    v = compute()
    print(f"게임물 {v['g_n']:,}건 (청소년이용불가 {v['g_yr_n']:,}건 · {v['g_yr_pct']}%)")
    print(f"  청불 중 사행성 보유 {v['compose'][0][2]}%")
    print(f"  사행성 있음 {v['gam']['has_yr']}% / 없음 {v['gam']['no_yr']}%")
    print(f"영상물 {v['k_n']:,}건 · 최고 점수 규칙 {v['rule_rate']}%")
    print(f"공개 심의 몫 {v['rater']['share']}%")

    dest = OUT / "final_report.html"
    dest.write_text(render(v), encoding="utf-8")
    print(f"\n저장: {dest}  ({dest.stat().st_size/1024:.0f} KB)")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
