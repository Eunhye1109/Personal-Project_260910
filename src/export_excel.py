# -*- coding: utf-8 -*-
"""
수집 원문을 엑셀로 내보낸다 — 전처리 전 상태 그대로

정제본(`*_clean_*.parquet`)이 아니라 **수집 원본**(`*_raw_*.parquet`)을 쓴다.
API 응답을 그대로 표로 옮긴 것이라 값 변환이 하나도 들어가 있지 않다.
`3단계-다소높음` 같은 문자열도, 빈 칸도 온 그대로다.

엑셀 파일마다 시트를 둘 둔다.

    [원문]      수집한 그대로. 첫 행 고정 + 자동 필터
    [컬럼 안내] 컬럼별 빈 값 비율·고유값 수·예시. 원문을 처음 열었을 때 어디를 볼지 정하는 용도

실행
    python src/export_excel.py
    python src/export_excel.py --open-dir      # 끝나고 폴더 열기
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"

# (원본 parquet 패턴, 엑셀 이름, 사람이 읽을 이름)
TARGETS = [
    ("kmrb_video_raw_*.parquet", "kmrb_video_raw", "영상물등급위원회 비디오물 등급분류"),
    ("grac_game_raw_*.parquet", "grac_game_raw", "게임물관리위원회 게임물 등급분류"),
]

EXCEL_ROW_LIMIT = 1_048_576


def column_guide(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼마다 무엇이 들어 있는지 한눈에 보이게 정리한다."""
    rows = []
    for c in df.columns:
        col = df[c]
        text = col.fillna("").astype(str).str.strip()
        filled = text.ne("")
        sample = text[filled].head(3).tolist()
        rows.append({
            "컬럼": c,
            "채워진 건수": int(filled.sum()),
            "빈 값 비율": round(float(1 - filled.mean()), 4),
            "고유값 수": int(col.nunique(dropna=True)),
            "예시 1": sample[0] if len(sample) > 0 else "",
            "예시 2": sample[1] if len(sample) > 1 else "",
            "예시 3": sample[2] if len(sample) > 2 else "",
        })
    return pd.DataFrame(rows)


def write_excel(df: pd.DataFrame, path: Path, title: str, source: Path) -> None:
    guide = column_guide(df)
    with pd.ExcelWriter(path, engine="xlsxwriter") as xw:
        df.to_excel(xw, sheet_name="원문", index=False)
        guide.to_excel(xw, sheet_name="컬럼 안내", index=False, startrow=3)

        book = xw.book
        head = book.add_format({"bold": True, "bg_color": "#DCE3EF", "border": 1, "valign": "vcenter"})
        note = book.add_format({"font_size": 10, "font_color": "#595959"})
        pctf = book.add_format({"num_format": "0.0%"})
        numf = book.add_format({"num_format": "#,##0"})

        ws = xw.sheets["원문"]
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, len(df), len(df.columns) - 1)
        for i, c in enumerate(df.columns):
            ws.write(0, i, c, head)
            width = max(len(str(c)) + 2, min(38, int(df[c].fillna("").astype(str).str.len().quantile(0.9)) + 2))
            ws.set_column(i, i, width)

        gs = xw.sheets["컬럼 안내"]
        gs.write(0, 0, f"{title} — 수집 원문", book.add_format({"bold": True, "font_size": 13}))
        gs.write(1, 0, f"원본 파일: {source.name}   /   {len(df):,}행 × {len(df.columns)}열", note)
        gs.write(2, 0, "전처리를 하지 않은 API 응답 그대로다. 값 변환·결측 정리·파생 컬럼이 전혀 들어가 있지 않다.", note)
        for i, c in enumerate(guide.columns):
            gs.write(3, i, c, head)
        gs.set_column(0, 0, 18)
        gs.set_column(1, 1, 12, numf)
        gs.set_column(2, 2, 11, pctf)
        gs.set_column(3, 3, 11, numf)
        gs.set_column(4, 6, 30)
        gs.freeze_panes(4, 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--open-dir", action="store_true", help="끝나고 outputs 폴더를 연다")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    made = []

    for pattern, name, title in TARGETS:
        files = sorted(PROC.glob(pattern))
        if not files:
            print(f"[건너뜀] {pattern} 에 해당하는 원본이 없습니다.")
            continue
        src = files[-1]                       # 가장 최근 수집분
        df = pd.read_parquet(src)

        if len(df) + 1 > EXCEL_ROW_LIMIT:
            print(f"[중단] {src.name} 이 {len(df):,}행으로 엑셀 한 시트 한도({EXCEL_ROW_LIMIT:,})를 넘습니다.")
            continue

        stamp = src.stem.split("_")[-1]
        out = OUT / f"{name}_{stamp}.xlsx"
        write_excel(df, out, title, src)
        size = out.stat().st_size / 1024 / 1024
        print(f"{title}")
        print(f"  {src.name}  {len(df):,}행 × {len(df.columns)}열")
        print(f"  -> {out.name}  ({size:.1f} MB)")
        made.append(out)

    if not made:
        sys.exit(1)

    print(f"\n{len(made)}개 저장: {OUT}")
    print("  시트 [원문] 수집 그대로 · 시트 [컬럼 안내] 컬럼별 빈값·고유값·예시")

    if args.open_dir:
        subprocess.run(["explorer", str(OUT)], check=False)


if __name__ == "__main__":
    main()
