# -*- coding: utf-8 -*-
"""
영등위 내용정보 항목명(rtStdName1~7) 대응 확정

문제
    API는 내용정보 7개를 rtStdName1 ~ rtStdName7 로 번호로만 준다.
    어느 번호가 주제·선정성·폭력성·공포·약물·대사·모방위험인지 알려주지 않는다.
    항목명이 확정되지 않으면 항목별 해석을 한 줄도 쓸 수 없다.

근거 — 같은 응답 안에 답이 있다
    rtCoreHarmRsnNm(결정사유) 필드가 "이 작품의 등급을 결정한 내용요소"를 이름으로
    담고 있다. 전체의 19%(18,896건)에서 채워져 있다.
    결정사유가 '주제' 하나뿐인 건들만 모아 항목1~7의 평균을 내면, 대응되는
    항목 하나만 뚜렷하게 높고 나머지는 바닥에 깔린다. 7개 이름에 대해 이것을
    반복하면 번호-이름 대응이 그대로 드러난다.

    조합 사유(예: '공포,약물')로 교차 검증도 한다. 이름이 두 개면 대응되는
    두 항목이 동시에 높아야 한다.

실행
    python src/verify_stdname.py
    python src/verify_stdname.py --data data/processed/kmrb_video_clean_260902.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "processed" / "kmrb_video_clean_260902.parquet"
OUT_DIR = ROOT / "outputs"

LV_COLS = [f"rtStdName{i}_lv" for i in range(1, 8)]
REASON_COL = "rtCoreHarmRsnNm"

# 결정사유에 등장하는 이름 7종. '주제 및 내용'은 데이터에 '주제'로 들어온다.
NAMES = ["주제", "선정성", "폭력성", "대사", "공포", "약물", "모방위험"]

# 공공데이터포털 메타데이터(DCAT)에 적힌 순서. 이것이 맞는지가 검증 대상이다.
PORTAL_ORDER = ["주제", "선정성", "폭력성", "공포", "약물", "대사", "모방위험"]


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"[중단] 정제본이 없습니다: {path}\n  먼저 src/clean_kmrb.py 를 실행하세요.")
    df = pd.read_parquet(path)
    missing = [c for c in LV_COLS + [REASON_COL] if c not in df.columns]
    if missing:
        sys.exit(f"[중단] 필요한 컬럼이 없습니다: {missing}")
    return df


def single_reason_table(df: pd.DataFrame) -> pd.DataFrame:
    """결정사유가 이름 하나뿐인 건만 모아 항목별 평균을 낸다."""
    sub = df.dropna(subset=[REASON_COL] + LV_COLS).copy()
    sub["reason"] = sub[REASON_COL].str.strip()
    single = sub[sub["reason"].isin(NAMES)]
    out = single.groupby("reason")[LV_COLS].mean()
    out.insert(0, "건수", single.groupby("reason").size())
    return out.reindex([n for n in NAMES if n in out.index])


def combo_table(df: pd.DataFrame, top: int = 12) -> pd.DataFrame:
    """결정사유가 둘 이상인 조합. 대응되는 항목들이 동시에 높아야 한다."""
    sub = df.dropna(subset=[REASON_COL] + LV_COLS).copy()
    sub["reason"] = sub[REASON_COL].str.strip()
    multi = sub[sub["reason"].str.contains(",", na=False)]
    counts = multi["reason"].value_counts().head(top).index
    out = multi[multi["reason"].isin(counts)].groupby("reason")[LV_COLS].mean()
    out.insert(0, "건수", multi[multi["reason"].isin(counts)].groupby("reason").size())
    return out.loc[counts]


def decide(single: pd.DataFrame) -> dict[int, str]:
    """이름별로 가장 높은 항목 번호를 골라 대응을 확정한다."""
    mapping: dict[int, str] = {}
    for name, row in single.iterrows():
        best = row[LV_COLS].astype(float).idxmax()
        idx = int(best.replace("rtStdName", "").replace("_lv", ""))
        mapping[idx] = name
    return mapping


def check(mapping: dict[int, str], single: pd.DataFrame) -> list[str]:
    """확정 결과가 신뢰할 만한지 스스로 점검한다."""
    problems = []
    if len(mapping) != 7:
        problems.append(f"7개 이름이 서로 다른 항목에 배정되지 않았습니다 (배정 {len(mapping)}개). "
                        "같은 항목에 두 이름이 몰렸다는 뜻입니다.")
    for name, row in single.iterrows():
        vals = row[LV_COLS].astype(float).sort_values(ascending=False)
        top1, top2 = vals.iloc[0], vals.iloc[1]
        if top1 - top2 < 0.5:
            problems.append(f"'{name}': 1위({top1:.2f})와 2위({top2:.2f}) 차이가 작아 단정하기 어렵습니다.")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--save", action="store_true", help="outputs/ 에 매핑표 csv 저장")
    args = ap.parse_args()

    df = load(Path(args.data))
    filled = df[REASON_COL].notna().sum()
    print(f"전체 {len(df):,}행 / 결정사유 채워진 건 {filled:,}행 ({filled / len(df):.1%})\n")

    single = single_reason_table(df)
    print("── 결정사유가 이름 하나뿐인 건의 항목별 평균 (굵은 값이 대응 항목) ──")
    print(single.round(2).to_string())
    print()

    mapping = decide(single)
    print("── 확정된 대응 ──")
    for i in range(1, 8):
        print(f"  rtStdName{i}  →  {mapping.get(i, '?')}")
    print()

    print("── 교차 검증: 조합 사유 (이름 개수만큼 항목이 동시에 높아야 함) ──")
    print(combo_table(df).round(2).to_string())
    print()

    problems = check(mapping, single)
    if problems:
        print("── 점검에서 걸린 것 ──")
        for p in problems:
            print(f"  · {p}")
    else:
        print("── 점검 통과: 7개 이름이 서로 다른 항목에 1:1로 배정됐고, 1·2위 차이도 충분합니다. ──")
    print()

    derived = [mapping.get(i, "?") for i in range(1, 8)]
    print(f"확정 순서   : {' · '.join(derived)}")
    print(f"포털 메타데이터: {' · '.join(PORTAL_ORDER)}")
    if derived != PORTAL_ORDER:
        diff = [f"{i+1}번(포털 {p} → 실제 {d})"
                for i, (p, d) in enumerate(zip(PORTAL_ORDER, derived)) if p != d]
        print(f"  ※ 불일치: {', '.join(diff)}")
        print("  포털 메타데이터의 항목 순서는 실제 응답 순서와 다릅니다. 데이터를 따릅니다.")

    if args.save:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / "content_item_mapping.csv"
        pd.DataFrame({"필드": [f"rtStdName{i}" for i in range(1, 8)],
                      "항목명": derived,
                      "근거": ["rtCoreHarmRsnNm 단일 사유 평균 최댓값"] * 7}).to_csv(
            out, index=False, encoding="utf-8-sig")
        print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
