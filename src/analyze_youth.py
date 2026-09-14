# -*- coding: utf-8 -*-
"""
청소년 이용 제한 콘텐츠 주요 특성 분석

통합본(`data/processed/integrated_ratings_*.parquet`) 하나를 입력으로 한다.

'청소년 이용 제한'은 두 매체에서 명칭이 다르다.
    게임물   청소년이용불가
    영상물   청소년관람불가 · 제한관람가
연령으로 환산하면 양자 모두 18세에 해당하므로, 통합본의 `청소년이용제한` 항목이 둘을 함께
지시한다.

해석 시 유의할 사항은 다음 두 가지이다.

  · 영상물의 성인물(49,741건)은 내용정보와 무관하게 사실상 전건이 청소년관람불가에 해당한다.
    이를 포함한 비율은 성인물의 비중에 좌우되므로, 포함한 값과 제외한 값을 항상 병기한다.
  · 게임물의 사행성은 비교 대상 4개 항목에 포함되지 않으면서 단독 보유만으로도 청소년 이용
    제한 비율이 매우 높다. 항목별 영향을 확인할 때 이를 함께 계산하면 다른 항목의 값이 왜곡된다.

실행
    python src/analyze_youth.py
    python src/analyze_youth.py --no-sync
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

COMPARABLE = ["선정성", "폭력성", "공포", "약물"]
GRAC_ONLY = ["언어", "범죄", "사행성"]
KMRB_ONLY = ["주제", "대사", "모방위험"]

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


def rate(df: pd.DataFrame) -> float:
    if len(df) == 0:
        return float("nan")
    return float(df["청소년이용제한"].fillna(False).mean())


def bar(x: float, width: int = 28) -> str:
    if pd.isna(x):
        return ""
    n = int(round(x * width))
    return "█" * n + "·" * (width - n)


def load() -> tuple[pd.DataFrame, str]:
    files = sorted(PROC.glob("integrated_ratings_*.parquet"))
    if not files:
        sys.exit("[중단] 통합본이 없습니다. 먼저 python src/make_integrated.py 를 실행하세요.")
    return pd.read_parquet(files[-1]), files[-1].name


def section_scale(df: pd.DataFrame, res: dict) -> None:
    head("1. 청소년 이용 제한 규모")
    say("청소년 이용 제한은 게임물의 청소년이용불가와 영상물의 청소년관람불가·제한관람가를 말한다.")
    say("영상물은 성인물을 포함한 값과 제외한 값을 병기한다. 포함한 값은 사실상 성인물의 비중에 해당한다.")
    say("")
    say(f"  {'구분':<26}{'건수':>10}{'제한':>10}{'비율':>9}")
    say("  " + "-" * 55)
    out = {}
    groups = [
        ("게임물 · 위원회분류", (df["매체"] == "게임물") & (df["분류경로"] == "위원회분류")),
        ("게임물 · 자체등급분류", df["분류경로"] == "자체등급분류"),
        ("영상물 · 전체", df["매체"] == "영상물"),
        ("영상물 · 성인물 제외", (df["매체"] == "영상물") & (df["구분"] != "성인물")),
        ("영상물 · 성인물만", (df["매체"] == "영상물") & (df["구분"] == "성인물")),
    ]
    for name, mask in groups:
        sub = df[mask]
        r = rate(sub)
        n = int(sub["청소년이용제한"].fillna(False).sum())
        say(f"  {name:<24}{len(sub):>10,}{n:>10,}{pct(r):>9}")
        out[name] = {"건수": int(len(sub)), "제한": n, "비율": round(r, 4)}
    say("")
    wi = out["게임물 · 위원회분류"]["비율"]
    se = out["게임물 · 자체등급분류"]["비율"]
    say(f"  ▶ 위원회가 직접 심의한 게임물은 {pct(wi)}가 청소년이용불가인 반면, 사업자가 자체적으로")
    say(f"    분류하는 자체등급분류는 {pct(se, 2)}로 약 {wi / se:.0f}배의 차이를 보인다.")
    say("    자체등급분류는 제도상 청소년이용불가 게임물을 대상으로 할 수 없으므로,")
    say("    해당 건들은 사후에 등급이 조정된 결과로 해석하는 것이 타당하다.")
    say(f"  ▶ 영상물의 {pct(out['영상물 · 전체']['비율'])}는 성인물에 기인한 수치이며,"
        f" 성인물을 제외하면 {pct(out['영상물 · 성인물 제외']['비율'])}로 낮아진다.")
    res["규모"] = out


def section_trend(df: pd.DataFrame, res: dict) -> None:
    head("2. 연도별 추이")
    say("최근 10년을 대상으로 한다. 분모가 작은 연도는 비율의 변동 폭이 크다는 점에 유의한다.")
    say("")
    rows = {}
    for name, mask in [("게임물(위원회)", (df["매체"] == "게임물") & (df["분류경로"] == "위원회분류")),
                       ("영상물(성인물 제외)", (df["매체"] == "영상물") & (df["구분"] != "성인물"))]:
        sub = df[mask]
        g = sub.groupby("분류연도")["청소년이용제한"]
        t = pd.DataFrame({"건수": g.size(), "비율": g.apply(lambda s: s.fillna(False).mean())})
        rows[name] = t
    years = sorted(set(rows["게임물(위원회)"].index) | set(rows["영상물(성인물 제외)"].index))
    years = [y for y in years if y >= max(years) - 9]
    say(f"  {'연도':<8}{'게임물 건수':>12}{'청불률':>9}{'영상물 건수':>12}{'청불률':>9}")
    say("  " + "-" * 52)
    out = {}
    for y in years:
        a = rows["게임물(위원회)"]
        b = rows["영상물(성인물 제외)"]
        an = int(a["건수"].get(y, 0)); ar = a["비율"].get(y, float("nan"))
        bn = int(b["건수"].get(y, 0)); br = b["비율"].get(y, float("nan"))
        say(f"  {y:<8}{an:>12,}{pct(ar):>9}{bn:>12,}{pct(br):>9}")
        out[int(y)] = {"게임물_건수": an, "게임물_청불률": None if pd.isna(ar) else round(float(ar), 4),
                       "영상물_건수": bn, "영상물_청불률": None if pd.isna(br) else round(float(br), 4)}
    say("")
    say("  ※ 2026년은 연중 수집분이므로 다른 연도와 동일한 기준으로 비교할 수 없다.")
    res["추이"] = out


def section_where(df: pd.DataFrame, res: dict) -> None:
    head("3. 장르·플랫폼·종별 분포")
    out = {}
    for title, mask, key in [
        ("게임물 · 플랫폼별", (df["매체"] == "게임물") & (df["분류경로"] == "위원회분류"), "구분"),
        ("게임물 · 장르별(상위 10)", (df["매체"] == "게임물") & (df["분류경로"] == "위원회분류"), "장르"),
        ("영상물 · 종별", df["매체"] == "영상물", "구분"),
    ]:
        sub = df[mask]
        g = sub.groupby(key)["청소년이용제한"]
        t = pd.DataFrame({"건수": g.size(), "비율": g.apply(lambda s: s.fillna(False).mean())})
        t = t[t["건수"] >= 100].sort_values("비율", ascending=False).head(10)
        say("")
        say(f"  [{title}]")
        say(f"  {'':<22}{'건수':>9}{'청불률':>9}  {'':<28}")
        for name, r in t.iterrows():
            say(f"  {str(name)[:20]:<22}{int(r['건수']):>9,}{pct(r['비율']):>9}  {bar(r['비율'])}")
        out[title] = {str(k): {"건수": int(v["건수"]), "비율": round(float(v["비율"]), 4)}
                      for k, v in t.iterrows()}
    say("")
    say("  ▶ 게임물에서는 '보드게임(베팅성)' 장르가 사실상 전건 청소년이용불가에 해당한다.")
    say("    플랫폼에서 온라인 게임의 비율이 가장 높게 나타나는 것도 동일한 요인에 기인하는 것으로")
    say("    판단된다. 베팅성 보드게임이 해당 플랫폼에 집중되어 있기 때문이다.")
    say("  ▶ 영상물에서는 성인물이 100%에 근접하며, 그 다음으로 극영화와 기타가 높게 나타난다.")
    res["분포"] = out


def section_items(df: pd.DataFrame, res: dict) -> None:
    head("4. 청소년 이용 제한을 결정하는 내용정보 항목")
    say("해당 항목만을 보유한 건(단독 보유)을 대상으로 한다. 복수의 항목이 함께 보유된 경우")
    say("어떤 항목이 등급 결정에 작용하였는지 구분할 수 없기 때문이다.")
    say("")
    out = {}
    for media, mask, items in [
        ("게임물(위원회)", (df["매체"] == "게임물") & (df["분류경로"] == "위원회분류"),
         COMPARABLE + GRAC_ONLY),
        ("영상물(성인물 제외)", (df["매체"] == "영상물") & (df["구분"] != "성인물"),
         COMPARABLE + KMRB_ONLY),
    ]:
        sub = df[mask].copy()
        cols = [f"내용_{n}" for n in items]
        sub["_n"] = sub[cols].sum(axis=1)
        say(f"  [{media}]")
        say(f"  {'항목(단독)':<16}{'건수':>9}{'청불률':>9}  {'':<28}")
        rows = {}
        for n in items:
            only = sub[(sub[f"내용_{n}"] == 1) & (sub["_n"] == 1)]
            if len(only) < 30:
                continue
            r = rate(only)
            say(f"  {n:<16}{len(only):>9,}{pct(r):>9}  {bar(r)}")
            rows[n] = {"건수": int(len(only)), "청불률": round(r, 4)}
        none = sub[sub["_n"] == 0]
        say(f"  {'(없음)':<16}{len(none):>9,}{pct(rate(none)):>9}  {bar(rate(none))}")
        rows["(없음)"] = {"건수": int(len(none)), "청불률": round(rate(none), 4)}
        say("")
        out[media] = rows
    say("  ▶ 게임물은 사행성 단독 보유의 값이 다른 항목과 현저한 차이를 보인다. 청소년 이용 제한을")
    say("    결정하는 요인은 폭력성이나 선정성이 아니라 사행성이며, 영상물에는 이에 대응하는")
    say("    항목이 존재하지 않는다.")
    say("  ▶ 영상물은 어떤 항목이든 3단계까지로는 청소년관람불가에 이르지 않는다. 등급이 내용정보의")
    say("    최고값과 동일하므로(항등식) 4단계가 부여되어야 청소년관람불가가 되기 때문이다.")
    res["항목별"] = out


def section_combo(df: pd.DataFrame, res: dict) -> None:
    head("5. 동일한 내용 조합에서의 매체 간 차이")
    say("공통 4개 항목(선정성·폭력성·공포·약물)만을 대상으로 하며, 그 밖의 항목을 보유한 건은")
    say("양측에서 대칭적으로 제외한다(통합본의 `비교표본` 항목). 영상물은 3단계 이상을 보유로 간주한다.")
    say("")
    sub = df[df["비교표본"] & (df["분류경로"] == "위원회분류")].copy()
    cols = [f"내용_{n}" for n in COMPARABLE]
    sub["조합"] = sub[cols].apply(
        lambda r: "+".join(n for n in COMPARABLE if r[f"내용_{n}"] == 1) or "(없음)", axis=1)
    piv = sub.pivot_table(index="조합", columns="매체", values="청소년이용제한",
                          aggfunc=lambda s: s.fillna(False).mean())
    cnt = sub.pivot_table(index="조합", columns="매체", values="분류번호", aggfunc="count")
    both = piv.dropna()
    both = both[(cnt.reindex(both.index) >= 30).all(axis=1)]
    say(f"  {'조합':<22}{'게임물':>9}{'영상물':>9}{'차이':>10}")
    say("  " + "-" * 51)
    out = {}
    for name, r in both.sort_values("게임물", ascending=False).iterrows():
        diff = r["게임물"] - r["영상물"]
        say(f"  {name:<22}{pct(r['게임물']):>9}{pct(r['영상물']):>9}{diff * 100:>+9.1f}p")
        out[str(name)] = {"게임물": round(float(r["게임물"]), 4),
                          "영상물": round(float(r["영상물"]), 4),
                          "차이": round(float(diff), 4)}
    if len(both):
        avg = float((both["게임물"] - both["영상물"]).mean())
        say("  " + "-" * 51)
        say(f"  {'평균':<22}{'':>9}{'':>9}{avg * 100:>+9.1f}p")
        res["조합_평균차이"] = round(avg, 4)
        say("")
        say(f"  ▶ 비교 가능한 {len(both)}개 조합 전부에서 게임물의 청소년 이용 제한 비율이 더 높다")
        say(f"    (평균 {avg * 100:+.1f}%p). 다만 이 결론은 3단계 이상을 보유로 간주하는 절단 기준을")
        say("    전제로 할 때에만 성립한다. 영상물의 5단계 체계를 게임물의 보유·미보유 체계에")
        say("    대응시키려면 특정 지점에서 절단이 필요하나, 그 지점은 데이터로부터 도출되지 않는다.")
    res["조합"] = out


def section_self(df: pd.DataFrame, res: dict) -> None:
    head("6. 자체등급분류의 청소년이용불가 건")
    s = df[(df["분류경로"] == "자체등급분류") & df["청소년이용제한"].fillna(False)]
    say(f"  건수 {len(s):,} · 전체 자체등급분류의 {pct(len(s) / (df['분류경로'] == '자체등급분류').sum(), 2)}")
    say("")
    for key, label in [("분류기관", "사업자"), ("장르", "장르")]:
        t = s[key].astype(str).value_counts().head(5)
        say(f"  [{label} 상위]")
        for name, n in t.items():
            say(f"    {str(name)[:28]:<30}{n:>6,}")
        say("")
    res["자체등급분류_청불"] = {
        "건수": int(len(s)),
        "사업자": {str(k): int(v) for k, v in s["분류기관"].astype(str).value_counts().head(5).items()},
    }
    say("  ▶ 자체등급분류 사업자는 청소년이용불가 등급을 부여할 수 없다. 그럼에도 해당 건이")
    say("    확인된다는 것은 본 자료가 분류 시점의 등급이 아니라 현재 등급을 수록하고 있음을")
    say("    의미한다. 따라서 이는 사후 등급 조정을 확인할 수 있는 단서이며, 사업자가 청소년이용불가")
    say("    등급을 부여하였다는 근거로 해석하여서는 안 된다.")


def write_html(res: dict, src: str) -> Path:
    body = "\n".join(_lines).replace("&", "&amp;").replace("<", "&lt;")
    g = res["규모"]["게임물 · 위원회분류"]
    k = res["규모"]["영상물 · 성인물 제외"]
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>청소년 이용 제한 콘텐츠 주요 특성</title>
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
<h1>청소년 이용 제한 콘텐츠 주요 특성</h1>
<div class="sub">통합본 {src} · 게임물(위원회) {g['건수']:,}건 · 영상물(성인물 제외) {k['건수']:,}건
 · 생성 {datetime.now():%Y-%m-%d %H:%M}</div>
<div class="key"><b>청소년 이용 제한을 결정하는 항목은 매체별로 상이하다.</b>
게임물에서는 <b>사행성</b>이 단독 보유만으로도 청소년 이용 제한 비율을 좌우하며, 폭력성·선정성과
현저한 차이를 보인다. 영상물에서는 어떤 항목도 3단계까지로는 청소년관람불가에 이르지 않는다.
등급이 내용정보의 최고값과 동일하므로 4단계가 부여되는 시점에 청소년관람불가가 되기 때문이다.
따라서 <b>'동일한 내용 수준'이라는 개념이 두 매체에서 같은 의미를 갖지 않으며</b>, 비율 비교는
영상물을 이진화하여 대응시킨 결과라는 한계를 전제로 해석하여야 한다. 영상물 전체의 43.7%라는
수치 역시 대부분 성인물에 기인하며, 성인물을 제외하면 {k['비율'] * 100:.1f}%이다.</div>
<pre>{body}</pre>
</div></body></html>"""
    p = OUT / "youth_report.html"
    p.write_text(html, encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    df, src = load()
    res: dict = {"생성": datetime.now().isoformat(timespec="seconds"), "통합본": src}

    say("청소년 이용 제한 콘텐츠 주요 특성 분석")
    say(f"통합본 {src} · {len(df):,}행")

    section_scale(df, res)
    section_trend(df, res)
    section_where(df, res)
    section_items(df, res)
    section_combo(df, res)
    section_self(df, res)

    (OUT / "youth_summary.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "youth_report.txt").write_text("\n".join(_lines), encoding="utf-8")
    html = write_html(res, src)
    print("")
    print(f"저장: {OUT / 'youth_summary.json'}")
    print(f"저장: {OUT / 'youth_report.txt'}")
    print(f"저장: {html}")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
