# -*- coding: utf-8 -*-
"""
2단계 — 자체등급분류 공표 정보 정제 (비교군)

이 데이터는 위원회가 매긴 등급이 아니라 **사업자가 스스로 매긴 등급**이다.
그래서 위원회 API 데이터(clean_grac.py)와 한 표로 합치지 않는다.
따로 정제해 두고, 비교할 때만 나란히 놓는다(compare_rater.py).

원본과 그 한계는 data/external/README.md 에 적어 두었다. 요약하면 이렇다.

    · 기간이 2026-07-01 ~ 2026-08-19 로 약 7주뿐이다
    · 장르 표기 체계가 API 쪽과 달라(단일 19종 vs 복합 294종) 장르를 맞춘 비교는 못 한다
    · 내용정보 결측이 API 쪽보다 많다
    · 이 프로젝트가 수집한 것이 아니라 별개 업무에서 확보돼 있던 파일이다

실행
    python src/clean_self.py
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "data" / "external"
OUT_DIR = ROOT / "data" / "processed"

GRADE_TO_AGE = {"전체이용가": 0, "12세이용가": 12, "15세이용가": 15, "청소년이용불가": 18}

# 위원회 API(clean_grac.py)와 같은 7종. 이름도 같게 온다.
DESCRIPTORS = ["선정성", "폭력성", "공포", "언어", "약물", "범죄", "사행성"]


def latest_raw() -> Path:
    files = sorted(EXTERNAL.glob("grac_self_*.csv"))
    if not files:
        raise SystemExit("data/external 에 grac_self_*.csv 가 없습니다.")
    return files[-1]


def read_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 알 수 없습니다: {path}")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA})

    out["rated_date"] = pd.to_datetime(out["rateddate"], errors="coerce")
    out["rated_year"] = out["rated_date"].dt.year
    out["rated_month"] = out["rated_date"].dt.to_period("M").astype(str)

    out["grade_age"] = out["grade"].map(GRADE_TO_AGE)
    out["is_youth_restricted"] = out["grade_age"].ge(18)
    out.loc[out["grade_age"].isna(), "is_youth_restricted"] = pd.NA

    # 내용정보 — 위원회 데이터와 같은 방식으로 항목별 보유 여부로 펼친다
    tokens = out["content"].fillna("").astype(str).str.split(",").apply(
        lambda xs: {t.strip() for t in xs if t.strip()})
    for name in DESCRIPTORS:
        out[f"내용_{name}"] = tokens.apply(lambda s, n=name: int(n in s))
    out["n_descriptors"] = out[[f"내용_{n}" for n in DESCRIPTORS]].sum(axis=1)
    out["has_descriptor"] = out["n_descriptors"] > 0

    unknown = sorted({t for s in tokens for t in s} - set(DESCRIPTORS))
    if unknown:
        print(f"  ⚠ 알려지지 않은 내용정보 토큰: {unknown}")

    # 사업자 구분 — 등급분류번호 앞부분이 사업자를 나타낸다 (GOOG, AAPL 등)
    out["provider"] = out["rateno"].astype(str).str.split("-").str[0]

    out["media"] = "게임물"
    out["rater"] = "자체등급분류"          # 위원회 데이터와 구분하는 키
    return out


def report(df: pd.DataFrame) -> None:
    line = "-" * 62
    print(f"\n{line}\n정제 결과\n{line}")
    print(f"행 {len(df):,} × 열 {len(df.columns)}")
    print(f"등급분류일자: {df['rated_date'].min():%Y-%m-%d} ~ {df['rated_date'].max():%Y-%m-%d} "
          f"(약 {(df['rated_date'].max() - df['rated_date'].min()).days}일)")

    print("\n[결정등급]")
    for name, n in df["grade"].value_counts().items():
        print(f"  {str(name):<14} {n:>7,}  ({n/len(df)*100:5.1f}%)")
    yr = df["is_youth_restricted"]
    print(f"\n[청소년이용불가] {int(yr.sum()):,}건 ({yr.mean()*100:.2f}%)")

    print("\n[내용정보 — 항목별 보유 건수]")
    for name in DESCRIPTORS:
        col = f"내용_{name}"
        print(f"  {name:<8} {int(df[col].sum()):>7,}  ({df[col].mean()*100:5.2f}%)")
    print(f"\n[내용정보 비어 있음] {int((~df['has_descriptor']).sum()):,}건 "
          f"({(~df['has_descriptor']).mean()*100:.1f}%)")

    print("\n[사업자 상위]")
    for name, n in df["provider"].value_counts().head(8).items():
        r = df.loc[df["provider"] == name, "is_youth_restricted"].dropna().mean()
        print(f"  {str(name):<8} {n:>7,}  청소년이용불가 {r*100:5.2f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="")
    args = ap.parse_args()

    src = Path(args.input) if args.input else latest_raw()
    print(f"원본: {src}")
    df = read_csv(src)
    print(f"  {len(df):,}행 × {len(df.columns)}열 읽음")

    out = clean(df)
    report(out)

    dest = OUT_DIR / f"grac_self_clean_{datetime.now():%y%m%d}.parquet"
    out.to_parquet(dest, index=False)
    print(f"\n저장: {dest}")


if __name__ == "__main__":
    main()
