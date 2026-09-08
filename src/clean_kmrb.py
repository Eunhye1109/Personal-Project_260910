"""
2단계 — 영등위 비디오물 등급분류 정제·통합

수집 원본(raw parquet)을 읽어 분석용 표로 바꾼다.
원본 컬럼은 지우지 않고 파생 컬럼을 덧붙이는 방식이라, 나중에 되짚어볼 수 있다.

실행:
    python src/clean_kmrb.py
    python src/clean_kmrb.py --input data/processed/kmrb_video_raw_260902.parquet
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# 윈도우 콘솔(cp949)에서 em dash 같은 글자에 죽지 않도록. 저장되는 파일에는 영향 없다.
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "processed"

# 관람등급 → 연령 하한. 순서형으로 쓰기 위한 표준화 (정제 규칙)
GRADE_TO_AGE = {
    "전체관람가": 0,
    "12세이상관람가": 12,
    "15세이상관람가": 15,
    "청소년관람불가": 18,
    "제한관람가": 19,          # 비디오물의 제한 등급(영화의 제한상영가에 해당)
    "제한상영가": 19,          # 영화 쪽 표기. 게임물·영화와 통합할 때 대비
}

# 내용정보 7종. API가 이름표를 주지 않아 번호로만 온다.
# 번호-이름 대응은 2026-09-07 확정 — 같은 응답의 rtCoreHarmRsnNm(결정사유)이 등급을 결정한
# 항목을 이름으로 담고 있어 그것으로 밝혔다. src/verify_stdname.py 로 재현된다.
# ※ 공공데이터포털 메타데이터의 항목 순서는 4·5·6번이 실제와 다르므로 따르지 말 것.
CONTENT_COLS = [f"rtStdName{i}" for i in range(1, 8)]
CONTENT_NAMES = {1: "주제", 2: "선정성", 3: "폭력성", 4: "대사", 5: "공포", 6: "약물", 7: "모방위험"}

# Y/N 플래그
FLAG_COLS = ["pokFlag", "yakSmkFlag", "yakDrkFlag", "yakDrgFlag", "moSuiFlag", "moHarmFlag"]


def latest_raw() -> Path:
    files = sorted(OUT_DIR.glob("kmrb_video_raw_*.parquet"))
    if not files:
        raise SystemExit("정제할 원본이 없습니다. 먼저 src/collect_kmrb.py 를 실행하세요.")
    return files[-1]


# 내용정보 표기 체계는 2017년 5월을 경계로 바뀐다. 둘 다 5단계 순서형이라 1~5로 통합한다.
#   ~2017.04  단계표기: 1단계-낮음 … 5단계-매우높음
#   2017.05~  등급표기: 전체관람가 … 제한상영가
# 대응 검증: 2016년(단계표기)과 2018년(등급표기)의 항목별 평균 차이가 -0.06~-0.21로 거의 같다.
CONTENT_GRADE_LEVEL = {
    "전체관람가": 1,
    "12세이상관람가": 2,
    "15세이상관람가": 3,
    "청소년관람불가": 4,
    "제한상영가": 5,
}


def level_to_int(value: str) -> float:
    """'3단계-다소높음' → 3.0 / '15세이상관람가' → 3.0 / 알 수 없으면 NaN"""
    if not isinstance(value, str):
        return float("nan")
    text = value.strip()
    m = re.match(r"(\d)\s*단계", text)
    if m:
        return float(m.group(1))
    return float(CONTENT_GRADE_LEVEL.get(text, float("nan")))


def content_notation(value: str) -> str:
    """어느 표기 체계로 기록됐는지. 시기별 비교 시 통제 변수로 쓴다."""
    if not isinstance(value, str) or not value.strip():
        return "없음"
    return "단계표기" if "단계" in value else "등급표기"


def runtime_to_min(value: str) -> float:
    """'24분 초' / '1시간 30분' / '95분 20초' 같은 표기를 분 단위 실수로."""
    if not isinstance(value, str) or not value.strip():
        return float("nan")
    hour = re.search(r"(\d+)\s*시간", value)
    minute = re.search(r"(\d+)\s*분", value)
    second = re.search(r"(\d+)\s*초", value)
    if not (hour or minute or second):
        return float("nan")
    total = 0.0
    if hour:
        total += int(hour.group(1)) * 60
    if minute:
        total += int(minute.group(1))
    if second:
        total += int(second.group(1)) / 60
    return round(total, 2)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # 빈 문자열은 결측으로 통일
    out = out.replace(r"^\s*$", pd.NA, regex=True)

    # 매체 구분 (게임물과 통합할 때 쓰는 키)
    out["media"] = "영상물"
    out["agency"] = "영상물등급위원회"

    # 등급분류일자
    out["rt_date"] = pd.to_datetime(out["rtDate"], format="%Y%m%d", errors="coerce")
    out["rt_year"] = out["rt_date"].dt.year
    out["rt_month"] = out["rt_date"].dt.month

    # 관람등급 표준화
    out["grade_age"] = out["gradeName"].map(GRADE_TO_AGE)
    out["is_youth_restricted"] = out["grade_age"].ge(18)          # 청소년 이용 제한 여부
    out["hope_grade_age"] = out["hopeGradeName"].map(GRADE_TO_AGE)
    # 신청등급과 결정등급이 다른 건 = 위원회가 등급을 조정한 사례
    out["grade_adjusted"] = (
        out["grade_age"].notna() & out["hope_grade_age"].notna()
        & out["grade_age"].ne(out["hope_grade_age"])
    )

    # 내용정보 7종 → 1~5 정수 (검증된 5단계 순서형 척도)
    for col in CONTENT_COLS:
        if col in out.columns:
            out[f"{col}_lv"] = out[col].map(level_to_int)
    out["content_notation"] = out["rtStdName1"].map(content_notation)
    lv_cols = [f"{c}_lv" for c in CONTENT_COLS if f"{c}_lv" in out.columns]
    if lv_cols:
        out["content_max"] = out[lv_cols].max(axis=1)      # 가장 높은 내용요소
        out["content_sum"] = out[lv_cols].sum(axis=1)      # 내용요소 총합(조합 효과 분석용)
        out["content_over3"] = (out[lv_cols] >= 3).sum(axis=1)   # 3단계 이상인 항목 수

    # Y/N 플래그 → 불리언
    for col in FLAG_COLS:
        if col in out.columns:
            out[f"{col}_yn"] = out[col].eq("Y")

    # 상영시간
    if "screTime" in out.columns:
        out["runtime_min"] = out["screTime"].map(runtime_to_min)

    # 제작연도
    if "prodYear" in out.columns:
        out["prod_year"] = pd.to_numeric(out["prodYear"], errors="coerce")

    return out


def report(df: pd.DataFrame) -> None:
    print(f"\n{'─'*60}\n정제 결과\n{'─'*60}")
    print(f"행 {len(df):,} × 열 {len(df.columns)}")

    if df["rt_date"].notna().any():
        print(f"등급분류일자: {df['rt_date'].min():%Y-%m-%d} ~ {df['rt_date'].max():%Y-%m-%d}")

    print("\n[관람등급]")
    for name, n in df["gradeName"].value_counts().items():
        print(f"  {name:<16} {n:>7,}  ({n/len(df)*100:4.1f}%)")
    bad = df["gradeName"].notna() & df["grade_age"].isna()
    if bad.any():
        print(f"  ⚠ 표준화 실패 {bad.sum()}건: {sorted(df.loc[bad, 'gradeName'].unique())[:5]}")

    print(f"\n[청소년 이용 제한] {df['is_youth_restricted'].sum():,}건 "
          f"({df['is_youth_restricted'].mean()*100:.1f}%)")
    print(f"[신청등급과 다르게 결정] {df['grade_adjusted'].sum():,}건 "
          f"({df['grade_adjusted'].mean()*100:.1f}%)")

    lv_cols = [c for c in df.columns if c.endswith("_lv")]
    print("\n[내용정보 1~5 변환 결과 — 평균 / 결측]")
    for col in lv_cols:
        s = df[col]
        print(f"  {col:<18} 평균 {s.mean():.2f}   결측 {s.isna().sum():,}건")

    print("\n[Y/N 플래그 — 'Y' 비율]")
    for col in [c for c in df.columns if c.endswith("_yn")]:
        print(f"  {col:<18} {df[col].sum():,}건 ({df[col].mean()*100:.2f}%)")

    if "runtime_min" in df.columns:
        rt = df["runtime_min"]
        print(f"\n[상영시간] 평균 {rt.mean():.1f}분 / 중앙값 {rt.median():.1f}분 / "
              f"결측 {rt.isna().sum():,}건")
        long_n = (rt > 300).sum()
        if long_n:
            print(f"  ※ 300분 초과 {long_n:,}건 — 합본·박스세트로 보이나 확인 필요")

    print("\n[결측률 상위 10개 원본 컬럼]")
    orig = [c for c in df.columns if not c.endswith(("_lv", "_yn"))
            and c not in ("media", "agency", "rt_date", "rt_year", "rt_month")]
    miss = df[orig].isna().mean().sort_values(ascending=False).head(10)
    for col, rate in miss.items():
        mark = "   ← 분석 제외 검토" if rate > 0.8 else ""
        print(f"  {col:<20} {rate*100:5.1f}%{mark}")


def add_named_levels(df: pd.DataFrame) -> pd.DataFrame:
    """rtStdNameN_lv 에 이름을 붙인 별칭 컬럼을 덧붙인다(내용_선정성 등).

    번호 컬럼을 지우지 않고 더하기만 한다. 기존 스크립트는 그대로 돌아가고,
    새로 쓰는 분석에서는 이름으로 바로 집을 수 있다.
    """
    for i, name in CONTENT_NAMES.items():
        col = f"rtStdName{i}_lv"
        if col in df.columns:
            df[f"내용_{name}"] = df[col]
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="", help="원본 parquet 경로 (기본: 가장 최근 것)")
    args = ap.parse_args()

    src = Path(args.input) if args.input else latest_raw()
    print(f"원본: {src}")
    df = pd.read_parquet(src)
    print(f"  {len(df):,}행 × {len(df.columns)}열 읽음")

    out = add_named_levels(clean(df))
    report(out)

    dest = OUT_DIR / f"kmrb_video_clean_{datetime.now():%y%m%d}.parquet"
    out.to_parquet(dest, index=False)
    print(f"\n저장: {dest}")


if __name__ == "__main__":
    main()
