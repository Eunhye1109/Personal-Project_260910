# -*- coding: utf-8 -*-
"""
5단계 대시보드 — 화면이 읽을 슬림 데이터셋 생성

정제본은 저장소에 넣지 않는다(.gitignore). 그런데 Streamlit Cloud 는 GitHub 저장소에
있는 파일만 읽으므로, 그대로는 배포한 화면이 볼 데이터가 없다.

그래서 화면이 실제로 쓰는 열만 남긴 사본을 따로 만들어 `data/dashboard/` 에 두고
이것만 저장소에 포함한다. 영상물 정제본이 36MB 인데 여기서는 몇 MB 로 떨어진다.

  빼는 것    감독·주연·제작사·줄거리·원제 등 화면 어디에서도 쓰지 않는 열,
             정제 전 원본 열(rtStdName1~7 같은 문자열 원문 — 이미 _lv 로 숫자화돼 있다)
  남기는 것  PRD 6.1 의 여섯 화면이 묻는 질문에 답하는 데 필요한 열 전부
             (원자료 화면에서 사람이 건을 알아볼 수 있어야 하므로 제목·번호는 남긴다)

원본 정제본이 바뀌면 다시 실행한다. 파일 이름에 날짜를 박지 않는다 — 260908 에
`_260902` 를 박아둔 탓에 재수집 후에도 옛 파일을 보던 일이 있었다.

실행
    python src/make_dashboard_data.py
    python src/make_dashboard_data.py --no-sync
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
DEST = ROOT / "data" / "dashboard"

KMRB_ITEMS = ["주제", "선정성", "폭력성", "대사", "공포", "약물", "모방위험"]
GRAC_ITEMS = ["선정성", "폭력성", "공포", "언어", "약물", "범죄", "사행성"]

# 화면이 쓰는 열만 적는다. 여기 없는 열은 대시보드에서 볼 수 없다.
KMRB_COLS = [
    "rtNo", "useTitle", "prodcNatnlName",          # 원자료 화면에서 건을 알아보는 데 필요
    "kindName", "rt_date", "rt_year", "rt_month",  # 공통 필터
    "gradeName", "grade_age", "is_youth_restricted",
    "hopeGradeName", "hope_grade_age", "grade_adjusted",   # 화면3 신청 대비 조정
    "rtCoreHarmRsnNm",                                     # 화면2 무엇이 등급을 올렸나
    "content_notation", "content_max", "content_over3",    # 화면1 결정 규칙
    "runtime_min", "media", "agency",
] + [f"내용_{n}" for n in KMRB_ITEMS]

GRAC_COLS = [
    "rateno", "gametitle", "entname",
    "genre", "platform", "rated_date", "rated_year", "rated_month",
    "givenrate", "grade_age", "is_youth_restricted", "is_grade_refused",
    "descriptors", "n_descriptors", "has_descriptor", "n_comparable",
    "is_canceled", "media", "agency",
] + [f"내용_{n}" for n in GRAC_ITEMS]

SELF_COLS = [
    "rateno", "gametitle", "genre", "rated_date", "rated_year", "rated_month",
    "grade", "grade_age", "is_youth_restricted",
    "content", "n_descriptors", "has_descriptor", "provider", "media", "rater",
] + [f"내용_{n}" for n in GRAC_ITEMS]

# 같은 값이 반복되는 열은 범주형으로 바꾼다. 파일이 눈에 띄게 작아진다.
CATEGORICAL = {
    "kmrb": ["kindName", "gradeName", "hopeGradeName", "rtCoreHarmRsnNm",
             "content_notation", "prodcNatnlName", "media", "agency"],
    "grac": ["genre", "platform", "givenrate", "descriptors", "entname", "media", "agency"],
    "self": ["genre", "grade", "content", "provider", "media", "rater"],
}


def latest(pattern: str) -> Path:
    files = sorted(PROC.glob(pattern))
    if not files:
        sys.exit(f"[중단] {pattern} 정제본이 없습니다. 먼저 정제 스크립트를 실행하세요.")
    return files[-1]


def shrink(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """열 타입을 줄인다. 값은 그대로 두고 담는 그릇만 바꾼다."""
    for col in CATEGORICAL[kind]:
        if col in df.columns:
            df[col] = df[col].astype("category")
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_float_dtype(s):
            # 내용정보 수준(1~5)·항목 보유(0/1)처럼 작은 정수는 결측을 살린 채 줄인다
            if s.dropna().mod(1).eq(0).all() and s.dropna().abs().lt(1000).all():
                df[col] = s.astype("Int16")
            else:
                df[col] = s.astype("float32")
        elif pd.api.types.is_integer_dtype(s) and s.abs().max() < 32000:
            df[col] = s.astype("int16")
    return df


def take(src: Path, cols: list[str], kind: str, out: str) -> dict:
    df = pd.read_parquet(src)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        sys.exit(f"[중단] {src.name} 에 없는 열: {missing}\n"
                 f"  정제 스크립트가 바뀐 것 같습니다. 열 목록을 맞춰주세요.")
    slim = shrink(df[cols].copy(), kind)
    path = DEST / out
    slim.to_parquet(path, index=False, compression="zstd")
    info = {"원본": src.name, "원본_행": int(len(df)), "원본_열": int(df.shape[1]),
            "사본": out, "사본_열": int(slim.shape[1]),
            "원본_MB": round(src.stat().st_size / 1e6, 1),
            "사본_MB": round(path.stat().st_size / 1e6, 1)}
    print(f"  {out:22s} {len(slim):>7,}행 × {slim.shape[1]:>2}열  "
          f"{info['원본_MB']:>5.1f}MB → {info['사본_MB']:>4.1f}MB")
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description="대시보드용 슬림 데이터셋 생성")
    ap.add_argument("--no-sync", action="store_true", help="NAS 동기화를 건너뛴다")
    args = ap.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    print("대시보드 데이터셋을 만듭니다 →", DEST)
    print("")

    meta = {"생성시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "파일": []}
    meta["파일"].append(take(latest("kmrb_video_clean_*.parquet"), KMRB_COLS, "kmrb", "kmrb.parquet"))
    meta["파일"].append(take(latest("grac_game_clean_*.parquet"), GRAC_COLS, "grac", "grac.parquet"))
    meta["파일"].append(take(latest("grac_self_clean_*.parquet"), SELF_COLS, "self", "self.parquet"))

    total = sum(f["사본_MB"] for f in meta["파일"])
    meta["합계_MB"] = round(total, 1)
    (DEST / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print(f"합계 {total:.1f}MB — 이 폴더는 .gitignore 예외로 저장소에 포함됩니다.")
    print(f"저장: {DEST / 'meta.json'}")
    if total > 90:
        print("[경고] 90MB 를 넘었습니다. GitHub 파일 한도(100MB)에 걸릴 수 있으니 열을 더 줄이세요.")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
