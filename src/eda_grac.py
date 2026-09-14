# -*- coding: utf-8 -*-
"""
3단계 — 게임물관리위원회 게임물 등급분류 현황 EDA

영등위 EDA(eda_kmrb.py)와 같은 자리에 놓이는 게임물 쪽 1차 분석이다.
다만 물어보는 것이 조금 다르다. 영등위는 등급이 내용정보의 최고값이라는 항등식이
확인됐지만(4단계 분석), 게임위는 내용정보에 수준이 없어 같은 질문을 할 수 없다.

답부터 말하면, 게임에서 청소년이용불가를 만드는 것은 폭력이나 선정성이 아니라 사행성이다.
그 근거를 §0 에 먼저 놓고 나머지 절에서 뒷받침한다.

    §0  결론 — 무엇이 청소년이용불가를 만드나
    §1  무엇이 얼마나 있나            등급·플랫폼·장르·기관·연도
    §2  내용정보는 어떻게 붙어 있나    항목별 보유율, 빈 값의 정체
    §3  무엇이 등급을 가르는가        항목별 조건부 청소년이용불가율
    §4  두 기관이 같은 규칙을 쓰는가   게임물관리위원회 vs 게임콘텐츠등급분류위원회
    §5  등급취소는 무엇인가

실행
    python src/eda_grac.py
    python src/eda_grac.py --no-sync
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_nas  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"

DESCRIPTORS = ["사행성", "폭력성", "선정성", "언어", "약물", "공포", "범죄"]
COMPARABLE = ["선정성", "폭력성", "공포", "약물"]

_lines: list[str] = []
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, OSError):
    pass


def say(t: str = "") -> None:
    print(t)
    _lines.append(t)


def head(t: str) -> None:
    say("")
    say("=" * 78)
    say(t)
    say("=" * 78)


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def load() -> pd.DataFrame:
    files = sorted(PROC.glob("grac_game_clean_*.parquet"))
    if not files:
        sys.exit("[중단] 정제본이 없습니다. 먼저 src/clean_grac.py 를 실행하세요.")
    df = pd.read_parquet(files[-1])
    say(f"정제본: {files[-1].name}  {len(df):,}행 × {len(df.columns)}열")
    return df


# ───────────────────────────────── §0 결론
def s0(df, res):
    head("0. 결론 — 게임물 등급 규제의 실질적 기준은 사행성이다")
    say("게임물 규제의 기준으로는 통상 폭력성과 선정성이 언급되나, 분석 결과는 이와 다르다.")

    d = df[~df["is_canceled"]].dropna(subset=["is_youth_restricted"]).copy()
    d["is_youth_restricted"] = d["is_youth_restricted"].astype(bool)
    yr = d[d["is_youth_restricted"]]

    say("")
    say(f"  [청소년이용불가 게임물 {len(yr):,}건의 내용정보 항목 구성]")
    say(f"    {'항목':<8} {'건수':>9} {'비중':>8}")
    compose = [[n, int(yr[f"내용_{n}"].sum()), float(yr[f"내용_{n}"].mean())] for n in DESCRIPTORS]
    for name, c, r in sorted(compose, key=lambda x: -x[1]):
        say(f"    {name:<8} {c:>9,} {pct(r):>8}  " + "█" * int(r * 40))
    say("")
    say("    ※ 한 건이 복수의 항목을 보유할 수 있으므로 합계는 100%를 초과한다.")

    has, no = d[d["내용_사행성"] == 1], d[d["내용_사행성"] == 0]
    say("")
    say("  [사행성 보유 여부에 따른 차이]")
    say(f"    사행성 있음  {len(has):>7,}건 중 청소년이용불가 {pct(has['is_youth_restricted'].mean())}")
    say(f"    사행성 없음  {len(no):>7,}건 중 청소년이용불가 {pct(no['is_youth_restricted'].mean())}")

    say("")
    say("  [플랫폼별 사행성 보유율과 청소년이용불가 비율]")
    say(f"    {'플랫폼':<16} {'건수':>8} {'사행성':>9} {'청불':>9}")
    plat = {}
    for name, sub in d.groupby("platform"):
        if len(sub) < 300:
            continue
        g, y = float(sub["내용_사행성"].mean()), float(sub["is_youth_restricted"].mean())
        plat[str(name)] = [len(sub), round(g, 4), round(y, 4)]
        say(f"    {str(name):<16} {len(sub):>8,} {pct(g):>9} {pct(y):>9}")

    say("")
    say("  ▶ 청소년이용불가 게임물의 약 4분의 3이 사행성을 보유한다. 사행성이 부여되면 사실상")
    say("    청소년이용불가가 확정되며, 미보유 시에는 한 자릿수로 낮아진다. 통상 규제 사유로")
    say("    인식되는 폭력성에서는 이와 같은 수준의 차이가 확인되지 않는다. 플랫폼별 결과도")
    say("    동일하다. 웹보드 게임의 비중이 높은 온라인 게임은 양 지표가 모두 높고, 폭력성이")
    say("    높다고 인식되는 콘솔(비디오 게임)은 양 지표가 모두 낮다.")
    say("")
    say("  ※ 다만 본 결과는 위원회가 직접 심의한 게임물에 한정된다. 게임물 등급분류의 대부분은")
    say("    사업자의 자체등급분류로 이루어지며, 해당 영역에는 사행성 게임물이 사실상 포함되지")
    say("    않는다(compare_rater.py 참조).")

    res["결론"] = {"청불건수": int(len(yr)),
                 "청불_항목구성": {n: [c, round(r, 4)] for n, c, r in compose},
                 "사행성있음": [len(has), round(float(has["is_youth_restricted"].mean()), 4)],
                 "사행성없음": [len(no), round(float(no["is_youth_restricted"].mean()), 4)],
                 "플랫폼": plat}


# ───────────────────────────────── §1 무엇이 얼마나 있나
def s1(df: pd.DataFrame, res: dict) -> None:
    head("1. 등급·플랫폼·장르별 현황")
    say(f"기간 {df['rated_date'].min():%Y-%m-%d} ~ {df['rated_date'].max():%Y-%m-%d}")

    say("")
    say("  [결정등급]")
    for name, n in df["givenrate"].value_counts().items():
        say(f"    {str(name):<14} {n:>7,}  {pct(n / len(df)):>7}")

    say("")
    say("  [플랫폼]  플랫폼별 청소년이용불가 비율 포함")
    say(f"    {'플랫폼':<16} {'건수':>8} {'비중':>8} {'청불':>8}")
    plat = {}
    for name, sub in df.groupby("platform"):
        if len(sub) < 50:
            continue
        r = float(sub["is_youth_restricted"].dropna().mean())
        plat[str(name)] = [len(sub), round(r, 4)]
        say(f"    {str(name):<16} {len(sub):>8,} {pct(len(sub) / len(df)):>8} {pct(r):>8}")

    say("")
    say("  [장르 상위 10]")
    say(f"    {'장르':<16} {'건수':>8} {'청불':>8}")
    for name, n in df["genre"].value_counts().head(10).items():
        r = float(df.loc[df["genre"] == name, "is_youth_restricted"].dropna().mean())
        say(f"    {str(name):<16} {n:>8,} {pct(r):>8}")

    say("")
    say("  [연도별 청소년이용불가 비중]")
    say(f"    {'연도':<8} {'건수':>8} {'청불':>8}   {'전체이용가':>10}")
    yr = {}
    for y, sub in df.groupby("rated_year"):
        if len(sub) < 100:
            continue
        r = float(sub["is_youth_restricted"].dropna().mean())
        allg = float((sub["grade_age"] == 0).mean())
        yr[int(y)] = [len(sub), round(r, 4), round(allg, 4)]
        bar = "█" * int(r * 30)
        say(f"    {int(y):<8} {len(sub):>8,} {pct(r):>8}   {pct(allg):>10}  {bar}")

    res["현황"] = {"등급": {str(k): int(v) for k, v in df["givenrate"].value_counts().items()},
                 "플랫폼": plat, "연도": yr}


# ───────────────────────────────── §2 내용정보의 모양
def s2(df: pd.DataFrame, res: dict) -> None:
    head("2. 내용정보의 기재 형태 — 미기재 47.6%의 성격")
    say("게임물관리위원회는 항목별 수준을 제공하지 않고 해당 항목의 명칭만 나열한다(예: 선정성,언어).")
    say("약 절반이 공란이므로, 이것이 '해당 요소 없음'인지 '미기재'인지를 먼저 확인할 필요가 있다.")

    empty = df[~df["has_descriptor"]]
    filled = df[df["has_descriptor"]]
    say("")
    say(f"  내용정보 있음  {len(filled):>7,}건   청소년이용불가 {pct(filled['is_youth_restricted'].dropna().mean())}")
    say(f"  내용정보 없음  {len(empty):>7,}건   청소년이용불가 {pct(empty['is_youth_restricted'].dropna().mean())}")

    er = float(empty["is_youth_restricted"].dropna().mean())
    say("")
    if er < 0.02:
        say(f"  ▶ 공란은 미기재가 아니라 '해당 요소 없음'으로 판단된다.")
        say(f"    공란인 건의 청소년이용불가 비율이 {pct(er, 2)}에 불과하여 미기재로 보기 어렵다.")
        say(f"    해당 건의 {pct(float((empty['grade_age'] == 0).mean()))}가 전체이용가에 해당한다.")
    else:
        say(f"  ▶ 공란의 청소년이용불가 비율이 {pct(er)}로 낮지 않아 미기재 가능성을 배제할 수 없다.")

    say("")
    say("  [항목별 보유 건수]  ★는 영상물과 명칭이 동일하여 매체 비교에 사용 가능한 항목")
    say(f"    {'항목':<8} {'건수':>8} {'전체 대비':>10} {'내용정보 있는 건 대비':>22}")
    hold = {}
    for name in DESCRIPTORS:
        col = f"내용_{name}"
        n = int(df[col].sum())
        mark = "★" if name in COMPARABLE else " "
        hold[name] = n
        say(f"  {mark} {name:<8} {n:>8,} {pct(n / len(df)):>10} {pct(n / len(filled)):>22}")

    say("")
    say("  [항목 개수 분포]")
    for n, sub in df.groupby("n_descriptors"):
        say(f"    {int(n)}개  {len(sub):>7,}건  {pct(len(sub) / len(df)):>7}")

    res["내용정보"] = {"보유건수": hold, "빈값건수": int(len(empty)),
                   "빈값_청불률": round(er, 4)}


# ───────────────────────────────── §3 무엇이 등급을 가르는가
def s3(df: pd.DataFrame, res: dict) -> None:
    head("3. 등급을 결정하는 요인")
    say("영상물은 등급이 내용정보의 최고값과 동일한 항등식 관계로 확인되었다(4단계 분석).")
    say("게임물은 수준 개념이 없어 동일한 방식의 확인이 불가능하므로 항목별로 구분하여 분석한다.")

    d = df.dropna(subset=["is_youth_restricted"]).copy()
    d["is_youth_restricted"] = d["is_youth_restricted"].astype(bool)

    say("")
    say("  [항목 보유 시 청소년이용불가 비율]")
    say(f"    {'항목':<8} {'보유 건수':>10} {'청불률':>9} {'미보유 청불률':>14} {'차이':>9}")
    eff = {}
    for name in DESCRIPTORS:
        col = f"내용_{name}"
        a = d.loc[d[col] == 1, "is_youth_restricted"]
        b = d.loc[d[col] == 0, "is_youth_restricted"]
        if len(a) < 30:
            continue
        eff[name] = [len(a), round(float(a.mean()), 4), round(float(b.mean()), 4)]
        say(f"    {name:<8} {len(a):>10,} {pct(a.mean()):>9} {pct(b.mean()):>14} "
            f"{(a.mean() - b.mean()) * 100:>+8.1f}%p")

    top = max(eff.items(), key=lambda kv: kv[1][1])
    say("")
    say(f"  ▶ {top[0]}을 보유한 게임물은 {pct(top[1][1])}가 청소년이용불가에 해당한다.")

    say("")
    say("  [단독 보유 시]  다른 항목이 혼재되지 않은 경우")
    say(f"    {'항목':<8} {'단독 건수':>10} {'청불률':>9}")
    solo = {}
    for name in DESCRIPTORS:
        col = f"내용_{name}"
        sub = d[(d[col] == 1) & (d["n_descriptors"] == 1)]
        if len(sub) < 30:
            continue
        r = float(sub["is_youth_restricted"].mean())
        solo[name] = [len(sub), round(r, 4)]
        bar = "█" * int(r * 30)
        say(f"    {name:<8} {len(sub):>10,} {pct(r):>9}  {bar}")

    say("")
    say("  ▶ 항목을 하나만 보유한 경우에도 등급 결과에 큰 차이가 나타난다. 영상물과 같이 수준의")
    say("    상승에 따라 등급이 결정되는 구조가 아니라, 어떤 항목이 부여되었는지가 등급을 결정하는")
    say("    구조로 판단된다.")

    say("")
    say("  [조합]  표본 100건 이상")
    combo = (d.assign(c=d["descriptors"].fillna("(없음)"))
               .groupby("c")["is_youth_restricted"].agg(["size", "mean"]))
    combo = combo[combo["size"] >= 100].sort_values("mean", ascending=False)
    for name, row in combo.head(14).iterrows():
        say(f"    {pct(row['mean']):>7}  {int(row['size']):>6,}건   {name}")

    res["등급결정"] = {"보유효과": eff, "단독효과": solo}


# ───────────────────────────────── §4 두 기관
def s4(df: pd.DataFrame, res: dict) -> None:
    head("4. 기관 간 판정 기준의 동일성 여부")
    say("게임물 등급분류는 게임물관리위원회와 게임콘텐츠등급분류위원회(GCRB)가 분담한다.")
    say("동일한 내용정보를 보유한 게임물이 기관에 따라 다른 등급을 받는지 확인한다.")

    d = df.dropna(subset=["is_youth_restricted"]).copy()
    d["is_youth_restricted"] = d["is_youth_restricted"].astype(bool)

    say("")
    say(f"    {'기관':<22} {'건수':>8} {'청불률':>9}")
    for name, sub in d.groupby("agency"):
        say(f"    {str(name):<22} {len(sub):>8,} {pct(sub['is_youth_restricted'].mean()):>9}")

    say("")
    say("  ※ 전체 청소년이용불가 비율의 차이는 두 기관이 담당하는 게임물의 성격 차이에서")
    say("    기인할 수 있으므로, 플랫폼과 내용정보를 통제한 후 비교하여야 한다.")

    say("")
    say("  [동일 플랫폼·동일 내용정보 조합의 청소년이용불가 비율]  양측 모두 표본 50건 이상")
    say(f"    {'플랫폼':<14} {'내용정보':<18} {'게임위':>16} {'GCRB':>16} {'차이':>9}")
    rows, diffs = [], []
    for (plat, desc), sub in d.groupby(["platform", d["descriptors"].fillna("(없음)")]):
        by = sub.groupby("agency")["is_youth_restricted"]
        if by.ngroups < 2:
            continue
        stats = by.agg(["size", "mean"])
        if stats["size"].min() < 50:
            continue
        names = list(stats.index)
        a = stats.loc[names[0]]
        b = stats.loc[names[1]]
        diff = float(a["mean"] - b["mean"])
        diffs.append(abs(diff))
        rows.append((str(plat), str(desc), int(a["size"]), float(a["mean"]),
                     int(b["size"]), float(b["mean"]), diff))
    rows.sort(key=lambda r: -abs(r[6]))
    for plat, desc, na, ra, nb, rb, diff in rows[:12]:
        say(f"    {plat:<14} {desc:<18} {pct(ra):>8}({na:>5,}) {pct(rb):>8}({nb:>5,}) "
            f"{diff * 100:>+8.1f}%p")

    if diffs:
        say("")
        say(f"  ▶ 비교 가능한 {len(diffs)}개 구간의 평균 절대 차이 {np.mean(diffs) * 100:.1f}%p "
            f"(최대 {max(diffs) * 100:.1f}%p)")
        if np.mean(diffs) < 0.05:
            say("    조건을 통제할 경우 두 기관의 판정 결과는 거의 동일하다.")
        else:
            say("    조건을 통제하여도 차이가 유지된다.")
        say("")
        say("  ※ 다만 이 결과를 기관에 따른 심의 기준의 차이로 해석하여서는 안 된다.")
        say("    게임산업법상 두 기관의 등급분류 대상 범위가 동일하지 않으며, 청소년이용불가 등급의")
        say("    부여 권한에 제약이 있었던 시기가 존재한다. 그러할 경우 위 차이는 심의 성향이")
        say("    아니라 역할 분담을 반영한 것이다. 내용정보가 동일하더라도 게임물 자체가 상이할 수")
        say("    있다. 결론으로 제시하려면 두 기관의 위탁 범위와 변경 시점을 문헌으로 확인하여야")
        say("    한다. 본 단계에서는 조건을 통제하여도 차이가 유지된다는 사실까지만 기술한다.")
    res["기관비교"] = {"구간수": len(diffs),
                   "평균절대차이": round(float(np.mean(diffs)), 4) if diffs else None}


# ───────────────────────────────── §5 등급취소
def s5(df: pd.DataFrame, res: dict) -> None:
    head("5. 등급취소 건의 성격")
    say("등급분류 후 취소된 건으로, 신청 내용과 실제 서비스가 상이한 경우가 대표적이다.")
    say("내용정보와 등급의 관계 분석에서 제외 여부를 결정하기 위하여 성격을 먼저 확인한다.")

    c = df[df["is_canceled"]]
    say("")
    say(f"  등급취소 {len(c):,}건 ({pct(df['is_canceled'].mean())})")
    if c["canceled_date"].notna().any():
        say(f"  취소일자 {c['canceled_date'].min():%Y-%m-%d} ~ {c['canceled_date'].max():%Y-%m-%d}")

    say("")
    say(f"  {'구분':<10} {'전체':>12} {'취소된 건':>12}")
    for name in ["전체이용가", "12세이용가", "15세이용가", "청소년이용불가"]:
        a = float((df["givenrate"] == name).mean())
        b = float((c["givenrate"] == name).mean()) if len(c) else 0.0
        say(f"  {name:<10} {pct(a):>12} {pct(b):>12}")

    say("")
    say("  [취소 건이 집중된 플랫폼]")
    rate = c["platform"].value_counts(normalize=True)
    base = df["platform"].value_counts(normalize=True)
    for name in base.head(6).index:
        say(f"    {str(name):<16} 전체 {pct(base[name]):>7}  취소 {pct(float(rate.get(name, 0))):>7}")

    say("")
    say("  [취소된 건의 내용정보 보유율]")
    say(f"    내용정보 있음  전체 {pct(df['has_descriptor'].mean())}  /  취소된 건 {pct(c['has_descriptor'].mean())}")

    say("")
    say("  ▶ 권고: 내용정보와 등급의 관계를 분석할 때에는 취소 건을 제외한다.")
    say(f"    신청 내용과 실제가 상이할 수 있어 내용정보가 해당 게임물을 설명하지 못하기 때문이며,")
    say(f"    제외 규모는 {len(c):,}건이다. 다만 취소 대상 게임물의 구성은 별도의 분석 가치가")
    say("    있으므로 관련 열은 유지한다.")

    res["등급취소"] = {"건수": int(len(c)), "비율": round(float(df["is_canceled"].mean()), 4)}


def write_html() -> Path:
    body = "\n".join(_lines).replace("&", "&amp;").replace("<", "&lt;")
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>게임물 등급분류 현황 EDA</title>
<style>
 body {{ margin:0; padding:32px; background:#f7f7f5; color:#1f2328;
        font-family:"맑은 고딕","Malgun Gothic",system-ui,sans-serif;
        word-break:keep-all; overflow-wrap:break-word; }}
 .wrap {{ max-width:1040px; margin:0 auto; background:#fff; padding:36px 40px;
          border:1px solid #e3e3e0; border-radius:8px; }}
 h1 {{ font-size:20px; margin:0 0 4px; color:#1f3864; }}
 .sub {{ color:#6b7280; font-size:13px; margin-bottom:20px; }}
 .key {{ background:#fff4e0; border:1px solid #f0d9a8; border-radius:6px;
         padding:14px 18px; font-size:14px; margin-bottom:24px; line-height:1.7; }}
 pre {{ font-family:"D2Coding",Consolas,monospace; font-size:12.5px; line-height:1.65;
        white-space:pre; overflow-x:auto; background:#fbfbfa; border:1px solid #ececea;
        border-radius:6px; padding:20px; }}
</style></head><body><div class="wrap">
<h1>게임물 등급분류 현황 EDA</h1>
<div class="sub">게임물관리위원회 Open API 수집분 29,417건 · 2007-04 ~ 2026-09 · 생성 {datetime.now():%Y-%m-%d %H:%M}</div>
<div class="key"><b>게임물의 청소년이용불가 등급을 결정하는 요인은 폭력성이나 선정성이 아니라 사행성이다.</b>
청소년이용불가 게임물의 76.3%가 사행성을 보유하며, 사행성이 부여된 경우 95.3%가 청소년이용불가에
해당한다. 미보유 시에는 8.9%이다. 영상물이 항목별 수준의 최고값으로 등급을 결정하는 것과 달리,
게임물은 수준 개념 없이 <b>어떤 항목이 부여되었는지</b>에 따라 등급이 결정된다.</div>
<pre>{body}</pre>
</div></body></html>"""
    p = OUT / "eda_grac_report.html"
    p.write_text(html, encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    df = load()
    res: dict = {"생성": datetime.now().isoformat(timespec="seconds"), "표본": int(len(df))}

    s0(df, res)
    s1(df, res)
    s2(df, res)
    s3(df, res)
    s4(df, res)
    s5(df, res)

    (OUT / "eda_grac_summary.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "eda_grac_report.txt").write_text("\n".join(_lines), encoding="utf-8")
    html = write_html()
    print("")
    print(f"저장: {OUT / 'eda_grac_summary.json'}")
    print(f"저장: {OUT / 'eda_grac_report.txt'}")
    print(f"저장: {html}")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
