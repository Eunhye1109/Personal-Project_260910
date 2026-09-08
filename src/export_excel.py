# -*- coding: utf-8 -*-
"""가장 최신 grac_game_raw_*.parquet / kmrb_video_raw_*.parquet 를 엑셀로 내보낸다."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

for pattern, name in [("grac_game_raw_*.parquet", "grac_game"), ("kmrb_video_raw_*.parquet", "kmrb_video")]:
    files = sorted(PROC.glob(pattern))
    if not files:
        print(f"[건너뜀] {pattern} 없음")
        continue
    src = files[-1]
    df = pd.read_parquet(src)
    out = OUT / f"{name}_{src.stem.split('_')[-1]}.xlsx"
    df.to_excel(out, index=False, engine="openpyxl")
    print(f"{src.name} ({len(df):,}행) -> {out}")
