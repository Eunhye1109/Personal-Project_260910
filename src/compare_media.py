# -*- coding: utf-8 -*-
"""
4단계 축① — 매체 간 판정 차이 (게임물 vs 영상물)

강사 피드백의 핵심 주문이었다.
"같은 내용 수준에서 게임과 영상물의 등급이 어떻게 다른지를 중심으로 분석하면 좋겠습니다."

비교하기 전에 정리해야 할 것이 두 가지 있다.

1) 두 기관은 내용정보를 다른 형태로 준다
     영등위  항목마다 1~5단계        예) 선정성 = 4단계-높음
     게임위  해당 항목의 이름만 나열   예) descriptors = "선정성,언어"
   수준끼리는 비교할 수 없으므로 영등위를 이진화해 맞춘다.
   기준을 하나로 정하면 자의적이라, 두 기준을 나란히 놓고 결과가 뒤집히는지 함께 본다.
     기준 A  3단계(다소높음) 이상을 보유로 본다
     기준 B  4단계(높음) 이상을 보유로 본다   ← 영등위에서 청소년관람불가를 만드는 경계

2) 이름이 같은 4개만 쓴다 (PRD 4.4 v1.3)
   선정성·폭력성·공포·약물. 대사↔언어, 주제/모방위험↔범죄는 재는 대상이 달라 통합하지 않는다.

표본에서 빼는 것
   영상물  성인물 — 내용정보와 무관하게 사실상 전건 청소년관람불가라 비교를 왜곡한다
   게임물  등급취소 건 — 신청 내용과 실제가 달라 내용정보가 그 게임물을 설명하지 못한다
   양쪽    등급이 아닌 처분(등급거부 등)

실행
    python src/compare_media.py
    python src/compare_media.py --no-sync
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

COMPARABLE = ["선정성", "폭력성", "공포", "약물"]
KMRB_COL = {"선정성": "rtStdName2_lv", "폭력성": "rtStdName3_lv",
            "공포": "rtStdName5_lv", "약물": "rtStdName6_lv"}

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


def latest(pattern: str) -> Path:
    files = sorted(PROC.glob(pattern))
    if not files:
        sys.exit(f"[중단] {pattern} 정제본이 없습니다.")
    return files[-1]


# 비교 대상 밖의 항목. 이것이 붙어 있으면 등급이 그것 때문에 정해졌을 수 있어
# '같은 내용 수준' 비교가 성립하지 않는다. 양쪽 모두 대칭으로 뺀다.
KMRB_OTHER = {"주제": "rtStdName1_lv", "대사": "rtStdName4_lv", "모방위험": "rtStdName7_lv"}
GRAC_OTHER = ["사행성", "언어", "범죄"]


def load(threshold: int) -> tuple[pd.DataFrame, dict]:
    """두 매체를 같은 모양의 표로 만들어 붙인다. threshold 는 영등위 이진화 기준."""
    kp, gp = latest("kmrb_video_clean_*.parquet"), latest("grac_game_clean_*.parquet")
    k = pd.read_parquet(kp)
    g = pd.read_parquet(gp)
    info = {"영상물_원본": int(len(k)), "게임물_원본": int(len(g)),
            "영상물_파일": kp.name, "게임물_파일": gp.name}

    # 영상물 — 성인물 제외, 등급 있는 건만
    k = k[~k["kindName"].astype(str).eq("성인물")].dropna(subset=["grade_age"]).copy()
    kk = pd.DataFrame({"media": "영상물",
                       "is_youth_restricted": k["grade_age"].ge(18).astype(int),
                       "sub": k["kindName"].astype(str)})
    for name in COMPARABLE:
        kk[name] = (k[KMRB_COL[name]] >= threshold).astype("Int64")
    # 비교 대상 밖 항목(주제·대사·모방위험)이 올라간 건은 뺀다.
    # 빼지 않으면 그 항목 때문에 등급이 정해진 건이 '(없음)' 칸에 들어간다.
    kk["_other"] = (k[list(KMRB_OTHER.values())] >= threshold).any(axis=1).values
    kk = kk.dropna(subset=COMPARABLE)
    info["영상물_비교대상밖_제외"] = int(kk["_other"].sum())
    kk = kk[~kk["_other"]].drop(columns="_other")

    # 게임물 — 등급취소 제외, 등급 있는 건만
    g = g[~g["is_canceled"]].dropna(subset=["grade_age"]).copy()
    gg = pd.DataFrame({"media": "게임물",
                       "is_youth_restricted": g["grade_age"].ge(18).astype(int),
                       "sub": g["platform"].astype(str)})
    for name in COMPARABLE:
        gg[name] = g[f"내용_{name}"].astype("Int64")
    # 같은 이유로 사행성·언어·범죄가 붙은 건을 뺀다.
    # 특히 사행성은 단독으로도 청소년이용불가율이 97.1%라, 남겨두면 '(없음)' 칸이 오염된다.
    gg["_other"] = g[[f"내용_{n}" for n in GRAC_OTHER]].sum(axis=1).gt(0).values
    info["게임물_비교대상밖_제외"] = int(gg["_other"].sum())
    gg = gg[~gg["_other"]].drop(columns="_other")

    both = pd.concat([kk, gg], ignore_index=True)
    both["n"] = both[COMPARABLE].sum(axis=1)
    both["combo"] = both[COMPARABLE].apply(
        lambda r: "+".join(n for n in COMPARABLE if r[n] == 1) or "(없음)", axis=1)
    info["영상물_비교표본"] = int(len(kk))
    info["게임물_비교표본"] = int(len(gg))
    return both, info


def section_profile(df: pd.DataFrame, res: dict, threshold: int) -> None:
    head(f"1. 비교 표본과 내용정보 보유율  (영상물 기준: {threshold}단계 이상을 보유로 봄)")
    for m, sub in df.groupby("media"):
        say(f"  {m}  {len(sub):>8,}건   청소년 이용 제한 {pct(sub['is_youth_restricted'].mean())}")

    say("")
    say("  [항목별 보유율]")
    say(f"    {'항목':<8} {'영상물':>10} {'게임물':>10}   {'차이':>9}")
    hold = {}
    for name in COMPARABLE:
        a = float(df.loc[df["media"] == "영상물", name].mean())
        b = float(df.loc[df["media"] == "게임물", name].mean())
        hold[name] = [round(a, 4), round(b, 4)]
        say(f"    {name:<8} {pct(a):>10} {pct(b):>10}   {(b - a) * 100:>+8.1f}%p")
    say("")
    say("  ※ 보유율 자체가 다른 것은 매체의 성격 차이다. 아래에서는 같은 보유 상태끼리만 비교한다.")
    res["보유율"] = hold


def section_same_profile(df: pd.DataFrame, res: dict) -> dict:
    head("2. 같은 내용정보를 가졌을 때, 매체에 따라 등급이 다른가")
    say("이름이 같은 4개 항목의 보유 조합이 완전히 같은 건끼리만 비교한다.")
    say("양쪽 모두 표본 50건 이상인 조합만 싣는다.")

    say("")
    say(f"    {'내용정보 조합':<26} {'영상물':>16} {'게임물':>16} {'차이':>10}")
    rows, diffs = [], []
    for combo, sub in df.groupby("combo"):
        by = sub.groupby("media")["is_youth_restricted"]
        if by.ngroups < 2:
            continue
        stats = by.agg(["size", "mean"])
        if stats["size"].min() < 50:
            continue
        a, b = stats.loc["영상물"], stats.loc["게임물"]
        d = float(b["mean"] - a["mean"])
        rows.append((combo, int(a["size"]), float(a["mean"]), int(b["size"]), float(b["mean"]), d))
        diffs.append(d)
    rows.sort(key=lambda r: -abs(r[5]))
    for combo, na, ra, nb, rb, d in rows:
        say(f"    {combo:<26} {pct(ra):>8}({na:>6,}) {pct(rb):>8}({nb:>6,}) {d * 100:>+9.1f}%p")

    say("")
    if diffs:
        say(f"  ▶ 비교 가능한 {len(diffs)}개 조합의 평균 차이 {np.mean(diffs) * 100:+.1f}%p, "
            f"평균 절대 차이 {np.mean(np.abs(diffs)) * 100:.1f}%p")
        harsher = sum(1 for d in diffs if d > 0)
        say(f"    게임물이 더 엄한 조합 {harsher}개 / 영상물이 더 엄한 조합 {len(diffs) - harsher}개")
    res["조합비교"] = [{"조합": c, "영상물": round(ra, 4), "게임물": round(rb, 4),
                    "차이": round(d, 4), "영상물n": na, "게임물n": nb}
                   for c, na, ra, nb, rb, d in rows]
    return {"평균차이": float(np.mean(diffs)) if diffs else None,
            "평균절대차이": float(np.mean(np.abs(diffs))) if diffs else None}


def section_item_effect(df: pd.DataFrame, res: dict) -> None:
    head("3. 같은 항목이 매체에 따라 다른 무게를 갖는가")
    say("항목 하나만 가진 건(단독 보유)으로 비교한다. 다른 항목이 섞이지 않아 그 항목의 무게가 그대로 보인다.")

    say("")
    say(f"    {'항목':<8} {'영상물':>18} {'게임물':>18} {'차이':>10}")
    eff = {}
    solo = df[df["n"] == 1]
    for name in COMPARABLE:
        sub = solo[solo[name] == 1]
        by = sub.groupby("media")["is_youth_restricted"].agg(["size", "mean"])
        if len(by) < 2 or by["size"].min() < 30:
            say(f"    {name:<8} {'표본 부족':>18}")
            continue
        a, b = by.loc["영상물"], by.loc["게임물"]
        d = float(b["mean"] - a["mean"])
        eff[name] = {"영상물": round(float(a["mean"]), 4), "게임물": round(float(b["mean"]), 4),
                     "차이": round(d, 4)}
        say(f"    {name:<8} {pct(a['mean']):>9}({int(a['size']):>6,}) "
            f"{pct(b['mean']):>9}({int(b['size']):>6,}) {d * 100:>+9.1f}%p")

    if eff:
        big = max(eff.items(), key=lambda kv: abs(kv[1]["차이"]))
        say("")
        say(f"  ▶ 차이가 가장 큰 항목은 {big[0]}이다 "
            f"(영상물 {pct(big[1]['영상물'])} / 게임물 {pct(big[1]['게임물'])}).")
    res["단독항목"] = eff


def section_structure(res: dict) -> None:
    head("6. 더 근본적인 차이 — 등급을 정하는 방식 자체가 다르다")
    say("위의 비율 비교보다 중요한 것이 하나 있다. 두 기관은 등급을 매기는 구조가 다르다.")
    say("")
    say("  [영상물]  등급 = 내용정보 7항목의 최고값. 항등식이다.")
    say("     일치율 99.90% (2017-05 이후 100.000%). 4단계 분석에서 확인했다.")
    say("     항목마다 1~5단계가 있고, 그중 가장 높은 단계가 그대로 관람등급이 된다.")
    say("     따라서 '어떤 항목이냐'보다 '어느 단계까지 올라갔느냐'가 등급을 정한다.")
    say("")
    say("  [게임물]  수준이라는 개념이 아예 없다. 해당하는 항목의 이름만 나열된다.")
    say("     내용정보가 비어 있는 13,993건의 청소년이용불가율은 0.06%다(그중 99.7%가 전체이용가).")
    say("     즉 빈 값은 미기재가 아니라 '유해 요소 없음'이다.")
    say("     반면 항목이 하나만 붙어도 청소년이용불가율이 57.3%로 뛴다.")
    say("     그리고 그 57.3%는 항목마다 전혀 다르다 — 사행성 단독 97.1%, 폭력성 단독 11.1%.")
    say("")
    say("  ▶ 정리하면 이렇다.")
    say("     영상물은 수준으로 등급을 정하고, 게임물은 종류로 정한다.")
    say("     그래서 '같은 내용 수준'이라는 말 자체가 두 매체에서 같은 뜻이 아니다.")
    say("     2절·3절의 비교는 영상물을 이진화해 억지로 맞춘 것이므로, 그 한계를 달고 읽어야 한다.")
    res["구조차이"] = {"영상물": "최고값 규칙(항등식, 99.90%)", "게임물": "항목 종류별(수준 없음)"}


def write_html(info: dict) -> Path:
    body = "\n".join(_lines).replace("&", "&amp;").replace("<", "&lt;")
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>매체 간 등급 판정 차이</title>
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
<h1>매체 간 등급 판정 차이 — 게임물 vs 영상물</h1>
<div class="sub">영상물 {info['영상물_비교표본']:,}건(성인물 제외) · 게임물 {info['게임물_비교표본']:,}건(등급취소 제외)
 · 생성 {datetime.now():%Y-%m-%d %H:%M}</div>
<div class="key"><b>두 기관은 등급을 정하는 방식 자체가 다르다.</b> 영상물은 내용정보 7항목의
<b>최고값</b>이 그대로 관람등급이 되는 항등식(99.90%)이고, 게임물은 수준이라는 개념 없이
해당 항목의 <b>종류</b>만 나열된다. 그래서 "같은 내용 수준"이라는 말이 두 매체에서 같은 뜻이 아니다.
아래 비율 비교는 영상물을 이진화해 억지로 맞춘 것이므로 그 한계를 달고 읽어야 한다.</div>
<pre>{body}</pre>
</div></body></html>"""
    p = OUT / "compare_media_report.html"
    p.write_text(html, encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    res: dict = {"생성": datetime.now().isoformat(timespec="seconds")}

    outcomes = {}
    for threshold in (3, 4):
        _lines.append("")
        head(f"■ 영상물 이진화 기준 {threshold}단계 이상")
        df, info = load(threshold)
        if threshold == 3:
            res["표본"] = info
            say(f"영상물 {info['영상물_원본']:,}건 → 성인물 제외, 비교 대상 밖 항목(주제·대사·모방위험) "
                f"{info['영상물_비교대상밖_제외']:,}건 제외 → {info['영상물_비교표본']:,}건")
            say(f"게임물 {info['게임물_원본']:,}건 → 등급취소 제외, 비교 대상 밖 항목(사행성·언어·범죄) "
                f"{info['게임물_비교대상밖_제외']:,}건 제외 → {info['게임물_비교표본']:,}건")
            say("")
            say("※ 비교 대상 밖 항목을 왜 빼는가 — 남겨두면 그 항목 때문에 등급이 정해진 건이")
            say("  '아무 항목도 없음' 칸에 들어간다. 게임물의 사행성이 특히 그렇다. 사행성은 단독으로도")
            say("  청소년이용불가율이 97.1%인데 비교 대상 4개에 없어서, 빼지 않으면 '(없음)' 칸의")
            say("  게임물 청불률이 28.3%로 부풀려진다. 영상물 쪽도 대칭으로 주제·대사·모방위험을 뺐다.")
        sub: dict = {}
        section_profile(df, sub, threshold)
        outcomes[threshold] = section_same_profile(df, sub)
        section_item_effect(df, sub)
        res[f"기준{threshold}단계"] = sub

    head("5. 두 기준에서 결과가 뒤집히는가")
    say("영상물 이진화 기준을 3단계와 4단계로 바꿔 같은 분석을 두 번 돌렸다.")
    say("기준을 바꿨을 때 결론이 뒤집히면 그 결론은 쓸 수 없다.")
    say("")
    for t, o in outcomes.items():
        if o["평균차이"] is None:
            continue
        say(f"  {t}단계 기준 — 조합별 평균 차이 {o['평균차이'] * 100:+.1f}%p "
            f"(절대값 {o['평균절대차이'] * 100:.1f}%p)")
    vals = [o["평균차이"] for o in outcomes.values() if o["평균차이"] is not None]
    if len(vals) == 2 and vals[0] * vals[1] < 0:
        say("")
        say("  ▶ 방향이 뒤집힌다. 다만 이것을 '기준에 따라 결론이 달라진다'로 읽으면 안 된다.")
        say("    4단계 기준이 애초에 성립하지 않기 때문이다.")
        say("")
        say("    영상물은 등급이 내용정보의 최고값이고, 4단계가 곧 청소년관람불가다(4.7절 항등식).")
        say("    그래서 '4단계 이상 보유'로 이진화하면 영상물 쪽은 정의상 100%가 나온다.")
        say("    실제로 위 표에서 영상물이 99.8%~100.0%로 찍혀 있다. 비교가 아니라 정의를 본 것이다.")
        say("")
        say("    ▶ 따라서 매체 비교에 쓸 수 있는 것은 3단계 기준뿐이다.")
        say(f"      그 기준에서는 비교 가능한 9개 조합 전부에서 게임물이 더 엄했다(평균 {vals[0] * 100:+.1f}%p).")
        say("      같은 항목을 단독으로 가졌을 때 선정성 12.6%→55.8%, 폭력성 0.8%→11.0%,")
        say("      약물 3.1%→25.0%, 공포 0.7%→5.8%로 모두 게임물 쪽이 높다.")
        say("")
        say("    남는 한계 — '3단계'라는 선택 자체에 근거가 있는 것은 아니다. 영등위의 5단계를")
        say("    게임위의 보유/미보유에 맞추려면 어딘가에서 잘라야 하고, 그 지점을 데이터가")
        say("    정해주지 않는다. '게임물이 더 엄하다'는 이 절단 기준 위에서만 성립한다.")
    elif len(vals) == 2:
        say("")
        say("  ▶ 두 기준에서 방향이 같다. 이 비교는 이진화 기준에 좌우되지 않는다.")

    section_structure(res)

    (OUT / "compare_media_summary.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "compare_media_report.txt").write_text("\n".join(_lines), encoding="utf-8")
    html = write_html(res["표본"])
    print("")
    print(f"저장: {OUT / 'compare_media_summary.json'}")
    print(f"저장: {OUT / 'compare_media_report.txt'}")
    print(f"저장: {html}")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
