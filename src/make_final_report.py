# -*- coding: utf-8 -*-
"""
최종 보고서 생성 — 인사이트 순서로

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

    # ── 결론 1. 게임물 — 무엇이 청소년이용불가를 만드나
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

    # 조합별 — 선정성·폭력성·사행성 세 가지의 조합만 본다.
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

    # 사행성이 어디에 몰려 있나 — 장르와 업체
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

    # ── 결론 3. 영상물 — 판단이 들어가는 곳
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
  <h1>청소년이용불가를<br>만드는 것</h1>
  <p class="lede">게임과 영상물의 등급분류 결과를 전량 받아, 무엇이 청소년 이용을 막는 등급을
  만드는지 확인했다. 통념과 다른 답이 나왔다.</p>

  <div class="summary">
    <div class="srow"><span class="tag">결론 1</span>
      <p>게임에서 청소년이용불가를 만드는 것은 폭력이나 선정성이 아니라 <b>도박성</b>이다.
      청소년이용불가 게임의 <b>{top[2]}%</b>가 사행성을 갖고 있다.</p></div>
    <div class="srow"><span class="tag">결론 2</span>
      <p>그런데 그 심의망에 걸리는 것은 게임 전체의 <b>{r['share']}%</b>뿐이다. 나머지는 사업자가
      스스로 등급을 매기고, 거기서는 청소년이용불가가 <b>{r['self_yr']}%</b>다.</p></div>
    <div class="srow"><span class="tag">결론 3</span>
      <p>영상물은 등급에 <b>사람의 판단이 거의 없다</b>. 항목 점수 중 가장 높은 값이 그대로 등급이
      된다({v['rule_rate']}%). 판단이 들어가는 곳은 신청 등급을 조정하는 {adj_total}%뿐이다.</p></div>
  </div>
</header>

<section>
  <div class="shead">
    <div class="eyebrow">결론 1 · 게임물 {v['g_n']:,}건</div>
    <h2>게임 규제의 실체는 도박성이다</h2>
  </div>
  <p class="sdesc">게임을 규제한다고 하면 보통 폭력성이나 선정성을 떠올린다. 청소년이용불가를 받은
  게임 {v['g_yr_n']:,}건이 실제로 무엇을 갖고 있었는지 보면 다르다.</p>
  <figure>
    <div class="scroll"><svg id="c-compose" width="1000" height="{50 + len(v['compose']) * 38}"
      role="img" aria-label="청소년이용불가 게임물이 가진 내용정보 항목"></svg></div>
    <figcaption>청소년이용불가 게임 넷 중 셋이 사행성을 갖고 있다. 폭력성과 선정성은 각각 다섯에
    하나꼴이다. 한 게임이 항목을 여러 개 가질 수 있어 합은 100%를 넘는다.</figcaption>
  </figure>

  <h3>사행성이 있고 없고로 갈린다</h3>
  <figure>
    <div class="scroll"><svg id="c-gam" width="1000" height="150" role="img"
      aria-label="사행성 보유 여부에 따른 청소년이용불가 비율"></svg></div>
    <figcaption>사행성이 붙은 게임은 {gm['has_yr']}%가 청소년이용불가다. 사행성이 없으면
    {gm['no_yr']}%로 떨어진다. 다른 어떤 항목도 이만한 힘을 갖지 않는다.</figcaption>
  </figure>

  <h3>항목 하나만 붙었을 때</h3>
  <figure>
    <div class="scroll"><svg id="c-solo" width="1000" height="{50 + len(v['solo']) * 36}" role="img"
      aria-label="항목 하나만 가진 게임물의 청소년이용불가 비율"></svg></div>
    <figcaption>다른 항목이 섞이지 않은 경우만 모았다. 같은 '항목 하나'인데 결과가 전혀 다르다.
    사행성만 붙어도 사실상 청소년이용불가가 확정되는 반면, 폭력성만 붙은 게임은 열에 아홉이
    청소년도 이용할 수 있다.</figcaption>
  </figure>

  <h3>항목이 섞였을 때도 사행성이 갈랐다</h3>
  <p class="col">등급을 좌우하는 세 가지(선정성·폭력성·사행성)의 조합으로 나눠 보았다.
  나머지 항목이 섞인 경우는 그대로 두었다. 세 가지가 결과를 결정하기 때문이다.</p>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c2)"></i>사행성이 들어간 조합</span>
      <span><i class="sw" style="background:var(--s3)"></i>사행성이 없는 조합</span>
    </div>
    <div class="scroll"><svg id="c-combo" width="1000" height="{50 + len(v['combo']) * 38}" role="img"
      aria-label="내용정보 조합별 청소년이용불가 비율"></svg></div>
    <figcaption>사행성이 들어간 조합 셋이 위쪽에, 없는 조합 셋이 아래쪽에 그대로 갈린다.
    눈에 띄는 것은 <b>선정+폭력({cmb_sv}%)이 선정성만({cmb_s}%)보다 낮다</b>는 점이다.
    폭력성이 더해지면 등급이 오히려 내려간다. 폭력성이 붙는 게임이 주로 콘솔·PC 액션물이라
    성인물과는 다른 부류이기 때문으로 보인다.</figcaption>
  </figure>

  <h3>플랫폼까지 나눠 보면</h3>
  <figure>
    <div class="scroll"><svg id="c-platcombo" width="1000"
      height="{70 + len(v['platcombo']) * 42}" role="img"
      aria-label="플랫폼별 내용정보 조합별 청소년이용불가 비율"></svg></div>
    <figcaption>칸의 값은 그 플랫폼에서 그 조합을 가진 게임의 청소년이용불가 비율이다.
    표본이 20건 미만인 칸은 비워 두었다. 사행성이 들어간 세 열이 플랫폼을 가리지 않고 진하다.
    반면 같은 '선정성만'인데도 모바일과 콘솔의 값이 크게 다르다. 마우스를 올리면 건수가 나온다.</figcaption>
  </figure>

  <h3>사행성 비율과 청소년이용불가 비율은 붙어 다닌다</h3>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c2)"></i>사행성이 붙은 비율</span>
      <span><i class="sw" style="background:var(--c1)"></i>청소년이용불가 비율</span>
    </div>
    <div class="scroll"><svg id="c-plat" width="1000" height="{50 + len(v['plat']) * 52}" role="img"
      aria-label="플랫폼별 사행성 비율과 청소년이용불가 비율"></svg></div>
    <figcaption>웹보드 게임이 많은 온라인 게임은 사행성도 청소년이용불가도 가장 높고, 흔히
    폭력적이라 여겨지는 콘솔(비디오 게임)은 양쪽 다 가장 낮다. 등급을 가르는 것이 폭력이 아니라
    도박성이라는 뜻이다.</figcaption>
  </figure>

  <h3>사행성 게임은 한 장르에 몰려 있다</h3>
  <p class="col">사행성이 붙은 {v['gam_n']:,}건이 어떤 장르인지 보면, 사실상 한 장르의 이야기다.</p>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c2)"></i>사행성 게임 중 이 장르의 비중</span>
      <span><i class="sw" style="background:var(--s2)"></i>전체 게임 중 이 장르의 비중</span>
    </div>
    <div class="scroll"><svg id="c-gamgenre" width="1000"
      height="{50 + len(v['gam_genre']) * 50}" role="img"
      aria-label="사행성 게임의 장르 구성"></svg></div>
    <figcaption>사행성 게임의 {v['gam_genre'][0][2]}%가 {v['gam_genre'][0][0]} 한 장르다.
    전체 게임에서 이 장르가 차지하는 몫은 {v['gam_genre'][0][3]}%에 지나지 않는다.
    즉 게임 심의에서 청소년이용불가를 만드는 것은 사실상 웹보드·베팅성 보드게임이다.</figcaption>
  </figure>

  <h3>만드는 곳도 따로 있다</h3>
  <p class="col">신청사는 모두 {v['ent_n']:,}곳이고 그중 {v['gam_ent_n']:,}곳이 사행성 게임을 냈다.
  다만 건수로 보면 특별히 한두 곳에 쏠려 있지는 않다. 눈에 띄는 것은 다른 쪽이다.
  <b>어떤 업체는 자기가 낸 게임이 거의 전부 사행성이다.</b></p>
  <figure>
    <div class="scroll"><svg id="c-gament" width="1000"
      height="{50 + len(v['gam_ent']) * 34}" role="img"
      aria-label="업체별 자사 게임 중 사행성 비율"></svg></div>
    <figcaption>막대는 그 업체가 낸 게임 가운데 사행성이 붙은 비율이다(30건 이상 낸 곳만).
    100%인 곳이 여럿 있다. 웹보드 게임만 만드는 회사가 따로 존재한다는 뜻이며,
    이는 합법적인 사업 영역이다. 게임 심의가 특정 장르·특정 업체에 집중되는 구조임을 보여준다.</figcaption>
  </figure>

  <h3>등급을 준 뒤 취소된 {v['cancel']['n']:,}건</h3>
  <p class="col">등급분류를 받은 뒤 취소된 건이 {v['cancel']['n']:,}건({v['cancel']['pct']}%) 있다.
  이 건들도 사행성 쪽으로 기울어 있다. 사행성 보유율이 {v['cancel']['gam']}%로 전체
  {v['cancel']['gam_all']}%의 두 배가 넘는다.</p>
  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--c3)"></i>취소된 건 중 이 장르의 비중</span>
      <span><i class="sw" style="background:var(--s2)"></i>전체 게임 중 이 장르의 비중</span>
    </div>
    <div class="scroll"><svg id="c-cancel" width="1000"
      height="{50 + len(v['cancel_genre']) * 50}" role="img"
      aria-label="등급취소된 게임의 장르 구성"></svg></div>
    <figcaption>베팅성 보드게임이 {v['cancel_genre'][0][2]}%로 가장 많은 것은 앞의 흐름과 같다.
    뜻밖인 것은 두 번째다. {v['cancel_genre'][1][0]}이 {v['cancel_genre'][1][2]}%를 차지하는데
    전체에서는 {v['cancel_genre'][1][3]}%에 지나지 않는다. 등급을 받은 뒤 취소되기까지는
    중앙값 {v['cancel_gap']['median']}일이 걸렸고, {v['cancel_gap']['within1y']}%가 1년 안에 취소됐다.</figcaption>
  </figure>
  <div class="note"><b>취소 사유는 자료에 없다.</b> 게임산업법상 등급취소는 신청 내용과 다르게
  유통한 경우 등에 이뤄지지만, 사업자가 서비스를 접으며 스스로 반납하는 경우도 취소로 기록될 수
  있다. 이 자료로는 둘을 가를 수 없으므로 위 수치를 위반 건수로 읽어서는 안 된다.
  분석에서는 이 건들을 빼되, 어떤 게임이 취소되는지는 따로 볼 거리가 있어 기록해 둔다.</div>
</section>

<section>
  <div class="shead">
    <div class="eyebrow">결론 2 · 같은 기간 비교</div>
    <h2>그 심의망에 걸리는 것은 {r['share']}%뿐이다</h2>
  </div>
  <p class="sdesc">앞의 이야기는 위원회가 직접 심의한 게임에만 해당한다. 게임 등급은 두 갈래로
  매겨진다. 위원회가 심의하는 것과, 구글·애플 같은 사업자가 스스로 매기는 것이다.
  같은 기간({r['from']} ~ {r['to']}, 약 {r['days']}일)으로 견줘 보았다.</p>
  <div class="big-line">
    <div class="big">{r['share']}<span style="font-size:.42em">%</span></div>
    <p>같은 기간에 위원회 심의가 차지한 몫이다. 위원회 {r['com_n']:,}건 대 사업자 자체 분류
    {r['self_n']:,}건, 약 {r['ratio']}배 차이다.</p>
  </div>
  <figure>
    <div class="scroll"><svg id="c-rater" width="1000" height="200" role="img"
      aria-label="같은 기간 위원회 심의와 사업자 자체 분류의 건수"></svg></div>
    <figcaption>19년치 위원회 물량보다 7주치 자체 분류가 더 많다. 그리고 자체 분류에서
    청소년이용불가는 {r['self_yr']}%, 전체이용가가 {r['self_all']}%다.</figcaption>
  </figure>
  <div class="note"><b>이 차이를 심의의 엄격함으로 읽어서는 안 된다.</b> 두 갈래에 들어오는 게임이
  애초에 다르다. 사업자 자체 분류에는 사행성 게임이 사실상 없다({r['self_gam']}%, 위원회 쪽은
  {r['com_gam']}%). 결론 1에서 보았듯 사행성만 붙어도 청소년이용불가가 {gm['has_yr']}%이니,
  등급 분포의 차이는 상당 부분 여기서 온다.</div>
  <p class="col">그래도 이 숫자는 중요하다. 공개 자료만 보고 "게임물의 청소년이용불가가
  {v['g_yr_pct']}%"라고 말하면 실제와 크게 어긋난다. 두 갈래를 합치면 그 값은 1% 아래로 내려간다.
  <b>한국 게임 등급분류의 실질은 심의가 아니라 자율규제이고, 위원회 심의는 도박성이 문제 되는
  좁은 영역에 집중되어 있다.</b></p>
</section>

<section>
  <div class="shead">
    <div class="eyebrow">결론 3 · 영상물 {v['k_n']:,}건</div>
    <h2>영상물 등급에는 판단이 거의 없다</h2>
  </div>
  <p class="sdesc">영상물은 주제·선정성·폭력성·대사·공포·약물·모방위험 일곱 가지에 각각 1점부터
  5점까지 점수를 매긴다. 그 점수 중 가장 높은 것을 그대로 등급으로 옮기면 어떻게 되는지 보았다.</p>
  <figure>
    <div class="scroll"><svg id="c-rule" width="1000" height="330" role="img"
      aria-label="내용정보 최고 점수와 관람등급의 대응"></svg></div>
    <figcaption>대각선에만 짙은 칸이 있다. 가장 높은 점수가 1점이면 전부 전체관람가, 2점이면 전부
    12세다. {v['k_n']:,}건 중 {v['rule_rate']}%가 이렇고, 표기가 바뀐 2017년 5월 이후 {gr_n:,}건은
    어긋난 것이 하나도 없다. 대각선을 벗어난 칸을 다 합쳐도 {v['rule_miss']}건이라 칠이 거의
    드러나지 않는다.</figcaption>
  </figure>
  <div class="note">등급은 계산해서 나오는 값이 아니라 옮겨 적은 값이다. 그래서 <b>내용정보로 등급을
  설명하는 분석은 성립하지 않는다.</b> 같은 값을 두 번 쓰는 셈이기 때문이다. 이 사실을 확인한 뒤
  질문을 아래로 옮겼다.</div>

  <h3>판단이 들어가는 유일한 곳</h3>
  <p class="col">신청 등급은 다르다. 신청사가 스스로 적어 낸 값이라 결정 등급과 같은 값이 아니다.
  전체 {v['adj']['n']:,}건 중 {adj_total}%에서 조정이 일어났다(위로 {v['adj']['up']}% ·
  아래로 {v['adj']['down']}%).</p>
  <figure>
    <div class="scroll"><svg id="c-hope" width="1000" height="{50 + len(v['hope']) * 44}" role="img"
      aria-label="신청 등급별 상향 조정 비율"></svg></div>
    <figcaption>{hope12[0]}로 신청한 건의 {hope12[2]}%가 위로 조정됐다. 신청사가 등급을 가장 많이
    낮게 예상하는 지점이다. 반대로 청소년관람불가로 신청하면 더 올라갈 자리가 거의 없어 조정이
    드물다.</figcaption>
  </figure>

  <h3>무엇이 가장 높은 점수를 차지했나</h3>
  <figure>
    <div class="scroll"><svg id="c-heat" width="1000" height="{70 + len(v['heat']) * 40}" role="img"
      aria-label="영상물 종류별로 등급을 결정한 항목"></svg></div>
    <figcaption>자료에는 등급을 정한 이유를 이름으로 적어 둔 칸이 있다({v['reason_n']:,}건).
    종류에 따라 뚜렷하게 갈린다. 성인물은 선정성, 극영화와 숏폼은 폭력성, 뮤직비디오는 약물이다.
    게임에서 사행성이 했던 역할을 영상물에서는 종류마다 다른 항목이 맡는다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead">
    <div class="eyebrow">부록</div>
    <h2>어떻게 확인했나, 무엇을 못 했나</h2>
  </div>

  <h3>자료</h3>
  <p class="col">두 기관이 공개하는 등급분류 결과를 각각 전량 받았다. 기관이 알려주는 총 건수와
  정확히 맞는다. 영상물 {v['k_n']:,}건(2009~2026), 게임물 {v['g_n']:,}건(2007~2026)이다.
  결론 2에 쓴 자체 분류 자료 {r['self_n']:,}건은 이 분석에서 수집한 것이 아니라 다른 일을 하다
  확보해 둔 것으로, 약 7주치가 전부이고 갱신이 불가능하다. 그래서 추세를 읽는 데는 쓰지 않고
  한 시점의 규모 비교로만 썼다.</p>

  <h3>두 매체를 견줄 때의 한계</h3>
  <p class="col">영상물은 항목마다 점수가 있고 게임물은 이름표만 있다. 같은 잣대로 재려면 영상물을
  "몇 점 이상이면 있는 것으로 친다"고 놓아야 하는데, 그 기준을 자료가 정해 주지 않는다. 3점으로
  놓으면 게임물이 더 엄하게 나오고, 4점으로 놓으면 영상물이 정의상 100%가 되어 비교가 성립하지
  않는다. 그래서 이 보고서는 두 매체의 엄격함을 견주는 결론을 내지 않았다.</p>

  <h3>표본의 치우침</h3>
  <p class="col">영상물은 성인물이 {v['adult_share']}%를 차지하고, 성인물은 내용정보와 상관없이
  거의 전부 청소년관람불가다. 이 치우침을 감안하지 않으면 결론이 뒤집힌다. 실제로 1차 분석에서
  "항목이 여러 개 겹칠수록 등급이 올라간다"는 결과를 냈다가 폐기했다. 성인물이 특정 구간에 몰려
  있어 생긴 착시였다.</p>

  <h3>아직 손대지 않은 것 — 두 개의 텍스트 칸</h3>
  <p class="col">두 자료 모두 사람이 쓴 설명문 칸을 갖고 있다. 이번 분석에서는 다루지 않았으나
  다음 단계의 재료가 된다.</p>
  <p class="col"><b>게임물 개요</b>는 29,417건 중 97.4%가 채워져 있고 중앙값 42자다.
  "스마트폰 환경에서 실행되는 슬롯머신을 모사한 단독형 베팅성 게임물"처럼 심의 관점의 표현이
  그대로 들어 있다. 내용정보 칸이 비어 있는 13,993건의 성격을 이 설명문으로 확인할 수 있을 것으로
  보인다.</p>
  <p class="col"><b>영상물 작품 내용</b>은 2018년 이후 100%가 채워져 있고(전체 84.6%)
  중앙값 92자의 실제 줄거리다. 다만 2013년 이전 구간은 "3매로구성: 1.아름다운만남"처럼 수록 목록만
  적혀 있거나 행정 메모가 섞여 있어, 쓰려면 2014년 이후로 잘라야 한다.</p>
  <div class="note"><b>바로잡음.</b> 이 절은 처음에 "줄거리 텍스트는 쓸 수 없다"고 적었다.
  2009~2010년 자료 몇 건만 보고 판단한 것이었고, 최근 구간을 확인하니 사실이 아니었다.</div>

  <h3>단계표기 시기의 예외</h3>
  <p class="col">결론 3의 규칙에서 어긋난 {v['rule_miss']}건은 모두 2017년 5월 이전이다. 그 시기
  ({st_n:,}건)에는 {st_r}%가 규칙대로였고, 표기를 등급 이름으로 바꾼 뒤로는 {gr_r}%다. 표기 방식이
  바뀐 시점과 규칙이 완전해진 시점이 겹친다.</p>
</section>

<section>
  <div class="shead">
    <div class="eyebrow">산출물</div>
    <h2>이 분석이 남긴 것</h2>
  </div>
  <p class="col">다섯 가지다. 모두 원본이 갱신되면 스크립트로 다시 만들 수 있다.</p>
  <table class="deliv">
    <tr><th>산출물</th><th>파일</th><th>만드는 스크립트</th></tr>
    <tr><td><b>통합 분석 Dataset</b><br><span class="dim">게임물·영상물 240,290건을 한 표로.
      이름이 같은 내용정보 4개만 같은 칸에 넣었다</span></td>
      <td><a href="integrated_dataset_dictionary.html">데이터 사전</a> ·
      <span class="mono">integrated_ratings_260914.csv</span></td>
      <td class="mono">src/make_integrated.py</td></tr>
    <tr><td><b>연령등급 및 내용정보 EDA</b></td>
      <td><a href="eda_report.html">영상물</a> · <a href="eda_grac_report.html">게임물</a></td>
      <td class="mono">src/make_eda_report.py · src/eda_grac.py</td></tr>
    <tr><td><b>청소년 이용 제한 콘텐츠 주요 특성</b></td>
      <td><a href="youth_report.html">분석 결과</a></td>
      <td class="mono">src/analyze_youth.py</td></tr>
    <tr><td><b>인터랙티브 대시보드</b><br><span class="dim">Streamlit · Plotly 6화면</span></td>
      <td><span class="mono">streamlit run app.py</span></td>
      <td class="mono">app.py · src/dashboard_calc.py</td></tr>
    <tr><td><b>주요 분석 인사이트 리포트</b><br><span class="dim">이 문서</span></td>
      <td><span class="mono">final_report.html</span></td>
      <td class="mono">src/make_final_report.py</td></tr>
  </table>
  <p class="col">곁가지로 매체 간 판정 차이(<a href="compare_media_report.html">compare_media</a>),
  누가 매기는가(<a href="compare_rater_report.html">compare_rater</a>), 등급과 내용정보의 관계
  (<a href="stage4_report.html">stage4</a>)를 따로 남겼다. 본문의 결론은 이 셋에서 나왔다.</p>
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

/* 결론1 — 청불 게임의 구성 */
hbar("c-compose",COMPOSE.map(([n,c,p])=>({{
  label:n, v:p, fill:n==="사행성"?"var(--c2)":"var(--s3)",
  right:`${{p}}%   (${{fmt(c)}}건)`,
  tip:`청소년이용불가 게임 ${{fmt(YRN)}}건 중 ${{n}}을 가진 것 ${{fmt(c)}}건 · ${{p}}%`}})),
  {{max:100,H:22,G:16}});

/* 결론1 — 사행성 유무 */
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

/* 결론1 — 항목 하나만 */
hbar("c-solo",SOLO.map(([n,c,p])=>({{
  label:n, v:p, fill:`var(${{RAMP[Math.min(4,Math.floor(p/22))]}})`,
  right:`${{p}}%   (${{fmt(c)}}건)`,
  tip:`${{n}}만 붙은 게임물 ${{fmt(c)}}건 중 ${{p}}%가 청소년이용불가`}})),
  {{max:100,H:22,G:14}});

/* 결론1 — 플랫폼 */
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

/* 결론1 — 조합별 */
hbar("c-combo",COMBO.map(([n,c,p,gam])=>({{
  label:n, v:p, fill:gam?"var(--c2)":"var(--s3)",
  right:`${{p}}%   (${{fmt(c)}}건)`,
  tip:`${{n}} ${{fmt(c)}}건 중 ${{p}}%가 청소년이용불가`}})),
  {{max:100,H:22,G:16,L:110,R:210}});

/* 결론1 — 플랫폼 x 조합 */
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

/* 결론1 — 사행성 장르 / 취소 장르 (같은 모양이라 함수로) */
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

/* 결론1 — 업체별 자사 게임 중 사행성 비율 */
hbar("c-gament",GAMENT.map(([name,n,tot,p])=>({{
  label:name.length>13?name.slice(0,13)+"…":name, v:p, fill:"var(--c2)",
  right:`${{p}}%   (${{fmt(tot)}}건 중 ${{fmt(n)}}건)`,
  tip:`${{name}} · 낸 게임 ${{fmt(tot)}}건 중 ${{fmt(n)}}건(${{p}}%)이 사행성`}})),
  {{max:100,H:20,G:14,L:150,R:250}});

/* 결론2 — 누가 매기나 */
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
  n.textContent="막대 길이 = 건수 · 같은 기간 " + RATER.from + " ~ " + RATER.to;
  svg.appendChild(n);
}})();

/* 결론3 — 최고 점수 x 등급 */
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
  n.textContent="가로 = 실제 관람등급 · 세로 = 항목 중 가장 높은 점수 · 칠이 진할수록 그 줄에서 차지하는 비중이 크다";
  svg.appendChild(n);
}})();

/* 결론3 — 신청 등급별 상향률 */
hbar("c-hope",HOPE.map(([g,n,p])=>({{
  label:g, v:p, fill:"var(--c1)",
  right:`${{p}}%   (${{fmt(n)}}건 중)`,
  tip:`${{g}}로 신청한 ${{fmt(n)}}건 중 ${{p}}%가 위로 조정됨`}})),
  {{max:30,H:22,G:22,L:120,R:230}});

/* 결론3 — 종류 x 결정 이유 */
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
  n.textContent="각 종류에서 그 항목이 등급 결정 이유로 지목된 비율";
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
