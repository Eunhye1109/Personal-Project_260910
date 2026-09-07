"""
3단계 — 현황 EDA

정제본을 읽어 기초 분포와 관계를 계산한다.
결과는 화면에 출력하고, 시각화에 쓸 수 있도록 outputs/eda_summary.json 으로도 저장한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CONTENT_LV = [f"rtStdName{i}_lv" for i in range(1, 8)]
GRADE_ORDER = ["전체관람가", "12세이상관람가", "15세이상관람가", "청소년관람불가", "제한관람가"]


def load() -> pd.DataFrame:
    files = sorted((ROOT / "data" / "processed").glob("kmrb_video_clean_*.parquet"))
    if not files:
        raise SystemExit("정제본이 없습니다. src/clean_kmrb.py 를 먼저 실행하세요.")
    return pd.read_parquet(files[-1])


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df = load()
    res: dict = {}

    print(f"{'='*64}\n영상물등급위원회 비디오물 등급분류 — 현황 EDA\n{'='*64}")
    print(f"대상 {len(df):,}건 · {df['rt_date'].min():%Y-%m} ~ {df['rt_date'].max():%Y-%m}")
    res["n"] = len(df)
    res["period"] = [f"{df['rt_date'].min():%Y-%m}", f"{df['rt_date'].max():%Y-%m}"]

    # 1. 연도별 건수와 등급 구성
    print(f"\n{'─'*64}\n1. 연도별 등급분류 건수와 등급 구성\n{'─'*64}")
    yr = pd.crosstab(df["rt_year"], df["gradeName"])
    yr = yr.reindex(columns=[g for g in GRADE_ORDER if g in yr.columns], fill_value=0)
    share = yr.div(yr.sum(axis=1), axis=0) * 100
    print(f"  {'연도':<6}{'건수':>8}   " + "".join(f"{g[:6]:>10}" for g in yr.columns))
    for y in yr.index:
        bar = "".join(f"{share.loc[y, g]:>9.1f}%" for g in yr.columns)
        print(f"  {int(y):<6}{int(yr.loc[y].sum()):>8,}   {bar}")
    res["by_year"] = {"index": [int(i) for i in yr.index],
                      "columns": list(yr.columns),
                      "counts": yr.values.tolist()}

    # 2. 관람등급 · 종별 분포
    print(f"\n{'─'*64}\n2. 관람등급 · 종별 분포\n{'─'*64}")
    g = df["gradeName"].value_counts().reindex([x for x in GRADE_ORDER if x in df["gradeName"].values])
    for name, n in g.items():
        print(f"  {name:<14}{n:>8,}  ({n/len(df)*100:5.1f}%)  " + "█" * int(n/len(df)*40))
    res["grade"] = {str(k): int(v) for k, v in g.items()}

    k = df["kindName"].value_counts().head(8)
    print()
    for name, n in k.items():
        print(f"  {str(name):<14}{n:>8,}  ({n/len(df)*100:5.1f}%)")
    res["kind"] = {str(a): int(b) for a, b in k.items()}

    # 3. 내용정보 항목별 평균 (표기 체계별로 나눠 봄)
    print(f"\n{'─'*64}\n3. 내용정보 7항목 — 표기 체계별 평균\n{'─'*64}")
    print("  ※ 항목명(주제·선정성·폭력성 등)과의 대응은 아직 미확정")
    print(f"\n  {'항목':<14}{'단계표기':>10}{'등급표기':>10}{'전체':>10}")
    means = {}
    for col in CONTENT_LV:
        a = df.loc[df["content_notation"] == "단계표기", col].mean()
        b = df.loc[df["content_notation"] == "등급표기", col].mean()
        c = df[col].mean()
        means[col] = {"단계표기": round(a, 3), "등급표기": round(b, 3), "전체": round(c, 3)}
        print(f"  {col.replace('_lv',''):<14}{a:>10.2f}{b:>10.2f}{c:>10.2f}")
    res["content_means"] = means

    # 4. 등급별 내용정보 프로파일 — 핵심
    print(f"\n{'─'*64}\n4. 관람등급별 내용정보 프로파일 (핵심)\n{'─'*64}")
    prof = df.groupby("gradeName")[CONTENT_LV].mean().reindex(
        [x for x in GRADE_ORDER if x in df["gradeName"].values])
    print(f"  {'등급':<14}" + "".join(f"{c.replace('rtStdName','').replace('_lv',''):>8}" for c in CONTENT_LV))
    for name, row in prof.iterrows():
        print(f"  {name:<14}" + "".join(f"{v:>8.2f}" for v in row))
    res["profile_by_grade"] = {str(i): [round(v, 3) for v in r] for i, r in prof.iterrows()}

    # 5. 내용요소 조합 효과 실마리
    print(f"\n{'─'*64}\n5. 내용요소 조합과 등급 (축② 실마리)\n{'─'*64}")
    tab = df.groupby("content_over3").agg(
        건수=("rtNo", "size"), 청불비율=("is_youth_restricted", "mean"),
        최고값평균=("content_max", "mean"))
    print(f"  {'3단계이상 항목수':<16}{'건수':>9}{'청불비율':>10}{'최고값':>9}")
    for n, r in tab.iterrows():
        print(f"  {int(n):<16}{int(r['건수']):>9,}{r['청불비율']*100:>9.1f}%{r['최고값평균']:>9.2f}")
    res["combo"] = {int(i): {"n": int(r["건수"]), "youth_restricted": round(r["청불비율"], 4)}
                    for i, r in tab.iterrows()}

    # 6. 신청등급 vs 결정등급
    print(f"\n{'─'*64}\n6. 신청등급과 결정등급의 차이\n{'─'*64}")
    sub = df[df["grade_age"].notna() & df["hope_grade_age"].notna()].copy()
    sub["diff"] = sub["grade_age"] - sub["hope_grade_age"]
    up, down, same = (sub["diff"] > 0).sum(), (sub["diff"] < 0).sum(), (sub["diff"] == 0).sum()
    print(f"  동일        {same:>8,}  ({same/len(sub)*100:5.1f}%)")
    print(f"  상향 조정   {up:>8,}  ({up/len(sub)*100:5.1f}%)   신청보다 높은 등급으로 결정")
    print(f"  하향 조정   {down:>8,}  ({down/len(sub)*100:5.1f}%)")
    res["adjust"] = {"same": int(same), "up": int(up), "down": int(down)}

    print("\n  [상향 조정된 건의 신청등급 분포]")
    for name, n in sub.loc[sub["diff"] > 0, "hopeGradeName"].value_counts().head(5).items():
        print(f"    {name:<14}{n:>7,}")

    # 7. 내용정보 항목 간 상관
    print(f"\n{'─'*64}\n7. 내용정보 항목 간 상관계수\n{'─'*64}")
    corr = df[CONTENT_LV].corr().round(2)
    labels = [c.replace("rtStdName", "").replace("_lv", "") for c in CONTENT_LV]
    print("       " + "".join(f"{l:>7}" for l in labels))
    for lab, (_, row) in zip(labels, corr.iterrows()):
        print(f"  {lab:<5}" + "".join(f"{v:>7.2f}" for v in row))
    res["corr"] = corr.values.tolist()

    (OUT / "eda_summary.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n요약 저장: {OUT / 'eda_summary.json'}")


if __name__ == "__main__":
    main()
