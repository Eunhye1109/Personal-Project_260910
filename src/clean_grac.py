# -*- coding: utf-8 -*-
"""
2단계 — 게임물관리위원회 게임물 등급분류 정제

수집 원본(raw parquet)을 읽어 분석용 표로 바꾼다.
원본 컬럼은 지우지 않고 파생 컬럼을 덧붙이는 방식이라 나중에 되짚어볼 수 있다.
(clean_kmrb.py 와 같은 방식)

영등위와 결정적으로 다른 점 — 내용정보의 형태
    영등위: 항목마다 1~5단계가 온다.        예) rtStdName2 = "4단계-높음"
    게임위: 해당하는 항목의 이름만 나열된다.  예) descriptors = "선정성,언어"

    수준이 없으므로 두 매체를 같은 척도로 비교할 수 없다.
    매체 간 비교는 영등위 값을 이진화해서 맞추는 수밖에 없다(PRD 4.4 척도 정렬 대안).
    여기서는 게임위 쪽을 항목별 보유 여부(0/1)로 펼친다.

    또 하나. descriptors 가 비어 있는 건이 47.6%다. 이것을 '유해 요소 없음'으로 읽을지
    '미기재'로 읽을지는 데이터만으로 정할 수 없다. 그래서 판단하지 않고
    has_descriptor 플래그만 만들어 두고, 해석은 분석 단계로 넘긴다.

실행
    python src/clean_grac.py
    python src/clean_grac.py --input data/processed/grac_game_raw_260907.parquet
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(errors="replace")   # 윈도우 콘솔(cp949) 보호
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "processed"

# 결정등급 → 연령 하한. 영등위(clean_kmrb.py)와 같은 축으로 맞춘다.
GRADE_TO_AGE = {
    "전체이용가": 0,
    "12세이용가": 12,
    "15세이용가": 15,
    "청소년이용불가": 18,
}
# 등급이 아니라 처분에 해당하는 값. 연령 축에 올릴 수 없어 따로 표시한다.
NON_GRADE = {"등급거부", "등급취소", "등급취소예정"}

# descriptors 에 실제로 등장하는 토큰 7종 (29,417건 전수 확인).
# 명세는 '언어의부적절성'·'범죄및반사회성'이라고 적고 있으나 실제 값은 '언어'·'범죄'로 온다.
DESCRIPTORS = ["선정성", "폭력성", "공포", "언어", "약물", "범죄", "사행성"]

# 영등위와 이름이 같아 매체 간 비교에 쓸 수 있는 항목 (PRD 4.4 v1.3).
# 언어↔대사, 범죄↔주제/모방위험은 재는 대상이 달라 통합하지 않는다.
COMPARABLE = ["선정성", "폭력성", "공포", "약물"]


def latest_raw() -> Path:
    files = sorted(OUT_DIR.glob("grac_game_raw_*.parquet"))
    if not files:
        raise SystemExit("정제할 원본이 없습니다. 먼저 src/collect_grac.py 를 실행하세요.")
    return files[-1]


def to_bool(series: pd.Series) -> pd.Series:
    """'True'/'False' 문자열과 실제 bool 을 모두 받아 bool 로 만든다."""
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin({"true", "y", "1"})


def clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # 빈 문자열은 결측으로 통일
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "<NA>": pd.NA})

    # ── 날짜
    out["rated_date"] = pd.to_datetime(out["rateddate"], errors="coerce")
    out["rated_year"] = out["rated_date"].dt.year
    out["rated_month"] = out["rated_date"].dt.to_period("M").astype(str)

    # ── 등급 표준화
    out["grade_age"] = out["givenrate"].map(GRADE_TO_AGE)
    out["is_youth_restricted"] = out["grade_age"].ge(18)
    out.loc[out["grade_age"].isna(), "is_youth_restricted"] = pd.NA
    out["is_grade_refused"] = out["givenrate"].isin(NON_GRADE)

    # ── 내용정보: 이름 나열을 항목별 보유 여부로 펼친다
    desc = out["descriptors"].fillna("")
    tokens = desc.str.split(",").apply(lambda xs: {t.strip() for t in xs if t.strip()})
    for name in DESCRIPTORS:
        out[f"내용_{name}"] = tokens.apply(lambda s, n=name: int(n in s))
    out["n_descriptors"] = out[[f"내용_{n}" for n in DESCRIPTORS]].sum(axis=1)
    out["has_descriptor"] = out["n_descriptors"] > 0
    # 매체 간 비교에 쓸 수 있는 4개만 따로 센 것
    out["n_comparable"] = out[[f"내용_{n}" for n in COMPARABLE]].sum(axis=1)

    # 명세에 없는 토큰이 섞여 들어오면 알린다
    unknown = sorted({t for s in tokens for t in s} - set(DESCRIPTORS))
    if unknown:
        print(f"  ⚠ 알려지지 않은 내용정보 토큰: {unknown}")

    # ── 등급취소
    out["is_canceled"] = to_bool(out["cancelstatus"])
    out["canceled_date"] = pd.to_datetime(out["canceleddate"], errors="coerce")

    # ── 매체 구분 (영등위와 통합할 키)
    out["media"] = "게임물"
    out["agency"] = out["orgname"]

    return out


def report(df: pd.DataFrame) -> None:
    line = "-" * 62
    print(f"\n{line}\n정제 결과\n{line}")
    print(f"행 {len(df):,} × 열 {len(df.columns)}")
    if df["rated_date"].notna().any():
        print(f"등급분류일자: {df['rated_date'].min():%Y-%m-%d} ~ {df['rated_date'].max():%Y-%m-%d}")

    print("\n[결정등급]")
    for name, n in df["givenrate"].value_counts().items():
        mark = "   ← 연령 축에 올리지 않음" if name in NON_GRADE else ""
        print(f"  {str(name):<14} {n:>7,}  ({n/len(df)*100:5.1f}%){mark}")
    yr = df["is_youth_restricted"]
    print(f"\n[청소년 이용 제한] {int(yr.sum()):,}건 ({yr.mean()*100:.1f}%)")
    print(f"[등급거부·취소예정]  {int(df['is_grade_refused'].sum()):,}건")
    print(f"[등급취소된 건]      {int(df['is_canceled'].sum()):,}건 "
          f"({df['is_canceled'].mean()*100:.1f}%)  ※ 분석 제외 여부 결정 필요")

    print("\n[내용정보 — 항목별 보유 건수]")
    for name in DESCRIPTORS:
        col = f"내용_{name}"
        mark = "  (영등위와 이름이 같음)" if name in COMPARABLE else ""
        print(f"  {name:<8} {int(df[col].sum()):>7,}  ({df[col].mean()*100:5.1f}%){mark}")

    print(f"\n[내용정보가 비어 있는 건] {int((~df['has_descriptor']).sum()):,}건 "
          f"({(~df['has_descriptor']).mean()*100:.1f}%)")
    print("  ※ '유해 요소 없음'인지 '미기재'인지는 데이터로 정할 수 없다. 분석 단계에서 판단한다.")

    print("\n[항목 개수별 청소년이용불가 비율]")
    g = df.dropna(subset=["is_youth_restricted"]).groupby("n_descriptors")["is_youth_restricted"]
    for n, sub in g:
        print(f"  {int(n)}개  {len(sub):>7,}건   {sub.mean()*100:5.1f}%")

    print("\n[플랫폼]")
    for name, n in df["platform"].value_counts().head(8).items():
        print(f"  {str(name):<16} {n:>7,}")
    print("\n[등급분류기관]")
    for name, n in df["agency"].value_counts().items():
        print(f"  {str(name):<20} {n:>7,}")

    print("\n[결측률 상위]")
    orig = [c for c in df.columns if not c.startswith("내용_")]
    for col, rate in df[orig].isna().mean().sort_values(ascending=False).head(6).items():
        print(f"  {col:<16} {rate*100:5.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="", help="원본 parquet 경로 (기본: 가장 최근 것)")
    args = ap.parse_args()

    src = Path(args.input) if args.input else latest_raw()
    print(f"원본: {src}")
    df = pd.read_parquet(src)
    print(f"  {len(df):,}행 × {len(df.columns)}열 읽음")

    out = clean(df)
    report(out)

    dest = OUT_DIR / f"grac_game_clean_{datetime.now():%y%m%d}.parquet"
    out.to_parquet(dest, index=False)
    print(f"\n저장: {dest}")


if __name__ == "__main__":
    main()
