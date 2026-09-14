# -*- coding: utf-8 -*-
"""
통합 분석 Dataset 생성 — 게임물 + 영상물을 한 표로

세 갈래로 흩어져 있던 정제본을 같은 모양으로 맞춰 붙인다.

    게임물 · 위원회 분류   grac_game_clean_*.parquet    29,417건
    게임물 · 자체등급분류  grac_self_clean_*.parquet    76,409건
    영상물 · 위원회 분류   kmrb_video_clean_*.parquet  134,464건

붙이면서 지킨 원칙 세 가지.

1) 내용정보는 명칭이 동일한 항목만 통합한다
   선정성·폭력성·공포·약물 4개 항목만 두 매체가 동일한 명칭을 사용한다.
   대사(영상물) ↔ 언어(게임물), 주제·모방위험(영상물) ↔ 범죄·사행성(게임물)은 측정 대상이
   상이하므로 통합하지 않고 각 매체의 열에 유지한다. 통합할 경우 존재하지 않는 값을 생성하게 된다.

2) 영상물의 1~5단계는 3단계 이상을 보유로 간주한다
   게임물은 수준 없이 항목명만 제공하므로 보유·미보유 체계로 대응시켜야 비교가 가능하다.
   4단계 기준은 사용할 수 없다. 영상물은 등급이 내용정보의 최고값과 동일하므로(일치율 99.9%)
   4단계 이상이 곧 청소년관람불가가 되어 정의상 성립하기 때문이다. 원 단계값은 `단계_*` 열에
   그대로 수록한다.

3) 비교 대상에서 제외할 건은 표시만 하고 삭제하지 않는다
   `비교대상밖_보유` 는 비교 대상 4개 항목 외의 항목을 보유한 건을 의미한다.
   `비교표본` 은 해당 건과 등급취소·성인물·등급 미부여 건을 제외한 나머지를 의미한다.
   삭제하지 않는 이유는 통합본의 활용 목적이 분석마다 다르기 때문이며, 제외 기준은 활용 시점에
   결정한다.

실행
    python src/make_integrated.py
    python src/make_integrated.py --no-sync
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
STAMP = datetime.now().strftime("%y%m%d")

# 영상물 이진화 기준 (3단계=다소높음 이상을 보유로 본다)
THRESHOLD = 3

COMPARABLE = ["선정성", "폭력성", "공포", "약물"]          # 두 매체 공통
GRAC_ONLY = ["언어", "범죄", "사행성"]                      # 게임물에만 있는 항목
KMRB_ONLY = ["주제", "대사", "모방위험"]                    # 영상물에만 있는 항목
ITEMS = COMPARABLE + GRAC_ONLY + KMRB_ONLY

KMRB_LV = {"주제": "rtStdName1_lv", "선정성": "rtStdName2_lv", "폭력성": "rtStdName3_lv",
           "대사": "rtStdName4_lv", "공포": "rtStdName5_lv", "약물": "rtStdName6_lv",
           "모방위험": "rtStdName7_lv"}

COLS = ["매체", "분류경로", "분류기관", "분류번호", "제목", "구분", "장르",
        "등급명", "등급연령", "청소년이용제한",
        "분류일자", "분류연도", "분류월",
        *[f"내용_{n}" for n in ITEMS],
        *[f"단계_{n}" for n in KMRB_LV],
        "항목수", "비교대상밖_보유", "비교표본", "등급취소", "원본"]


def latest(pattern: str) -> Path:
    files = sorted(PROC.glob(pattern))
    if not files:
        sys.exit(f"[중단] {pattern} 정제본이 없습니다.")
    return files[-1]


def blank(n: int, names: list[str], df: pd.DataFrame) -> None:
    """해당 매체에 존재하지 않는 항목은 0이 아니라 결측으로 처리한다. 0으로 둘 경우 미보유로 해석된다."""
    for name in names:
        df[f"내용_{name}"] = pd.Series([pd.NA] * n, dtype="Int64")


def load_grac() -> pd.DataFrame:
    p = latest("grac_game_clean_*.parquet")
    g = pd.read_parquet(p).reset_index(drop=True)
    d = pd.DataFrame(index=g.index)
    d["매체"] = "게임물"
    d["분류경로"] = "위원회분류"
    d["분류기관"] = g["agency"].astype(str)
    d["분류번호"] = g["rateno"].astype(str)
    d["제목"] = g["gametitle"].astype(str)
    d["구분"] = g["platform"].astype(str)
    d["장르"] = g["genre"].astype(str)
    d["등급명"] = g["givenrate"].astype(str)
    d["등급연령"] = g["grade_age"].astype("Float64")
    d["청소년이용제한"] = g["is_youth_restricted"].astype("boolean")
    d["분류일자"] = g["rated_date"]
    d["분류연도"] = g["rated_year"].astype("Int64")
    d["분류월"] = g["rated_month"].astype(str)
    for name in COMPARABLE + GRAC_ONLY:
        d[f"내용_{name}"] = g[f"내용_{name}"].astype("Int64")
    blank(len(g), KMRB_ONLY, d)
    for name in KMRB_LV:
        d[f"단계_{name}"] = pd.Series([pd.NA] * len(g), dtype="Int64")
    d["비교대상밖_보유"] = g[[f"내용_{n}" for n in GRAC_ONLY]].sum(axis=1).gt(0)
    d["등급취소"] = g["is_canceled"].astype("boolean")
    # 등급취소 건은 신청 내용과 실제가 달라 내용정보가 그 게임물을 설명하지 못한다.
    d["비교표본"] = (~d["비교대상밖_보유"]) & (~g["is_canceled"]) & g["grade_age"].notna()
    d["원본"] = p.name
    return d


def load_self() -> pd.DataFrame:
    p = latest("grac_self_clean_*.parquet")
    s = pd.read_parquet(p).reset_index(drop=True)
    d = pd.DataFrame(index=s.index)
    d["매체"] = "게임물"
    d["분류경로"] = "자체등급분류"
    d["분류기관"] = s["provider"].astype(str)
    d["분류번호"] = s["rateno"].astype(str)
    d["제목"] = s["gametitle"].astype(str)
    d["구분"] = "자체등급분류"
    d["장르"] = s["genre"].astype(str)
    d["등급명"] = s["grade"].astype(str)
    d["등급연령"] = s["grade_age"].astype("Float64")
    d["청소년이용제한"] = s["is_youth_restricted"].astype("boolean")
    d["분류일자"] = s["rated_date"]
    d["분류연도"] = s["rated_year"].astype("Int64")
    d["분류월"] = s["rated_month"].astype(str)
    for name in COMPARABLE + GRAC_ONLY:
        d[f"내용_{name}"] = s[f"내용_{name}"].astype("Int64")
    blank(len(s), KMRB_ONLY, d)
    for name in KMRB_LV:
        d[f"단계_{name}"] = pd.Series([pd.NA] * len(s), dtype="Int64")
    d["비교대상밖_보유"] = s[[f"내용_{n}" for n in GRAC_ONLY]].sum(axis=1).gt(0)
    d["등급취소"] = pd.Series([False] * len(s), dtype="boolean")
    d["비교표본"] = (~d["비교대상밖_보유"]) & s["grade_age"].notna()
    d["원본"] = p.name
    return d


def load_kmrb() -> pd.DataFrame:
    p = latest("kmrb_video_clean_*.parquet")
    k = pd.read_parquet(p).reset_index(drop=True)
    d = pd.DataFrame(index=k.index)
    d["매체"] = "영상물"
    d["분류경로"] = "위원회분류"
    d["분류기관"] = k["agency"].astype(str)
    d["분류번호"] = k["rtNo"].astype(str)
    d["제목"] = k["useTitle"].astype(str)
    d["구분"] = k["kindName"].astype(str)
    d["장르"] = k["rightMediPurpName"].astype(str)
    d["등급명"] = k["gradeName"].astype(str)
    d["등급연령"] = k["grade_age"].astype("Float64")
    d["청소년이용제한"] = k["is_youth_restricted"].astype("boolean")
    d["분류일자"] = k["rt_date"]
    d["분류연도"] = k["rt_year"].astype("Int64")
    d["분류월"] = k["rt_month"].astype(str)
    for name in COMPARABLE + KMRB_ONLY:
        lv = k[KMRB_LV[name]]
        col = (lv >= THRESHOLD).astype("Int64")
        col[lv.isna()] = pd.NA
        d[f"내용_{name}"] = col
    blank(len(k), GRAC_ONLY, d)
    for name, col in KMRB_LV.items():
        d[f"단계_{name}"] = k[col].astype("Int64")
    d["비교대상밖_보유"] = (k[[KMRB_LV[n] for n in KMRB_ONLY]] >= THRESHOLD).any(axis=1)
    d["등급취소"] = pd.Series([False] * len(k), dtype="boolean")
    # 성인물은 내용정보와 무관하게 사실상 전건 청소년관람불가라 비교를 왜곡한다.
    d["비교표본"] = ((~d["비교대상밖_보유"]) & k["kindName"].astype(str).ne("성인물")
                  & k["grade_age"].notna()
                  & d[[f"내용_{n}" for n in COMPARABLE]].notna().all(axis=1))
    d["원본"] = p.name
    return d


def dictionary_html(df: pd.DataFrame, meta: dict) -> Path:
    desc = {
        "매체": "게임물 / 영상물",
        "분류경로": "위원회분류 / 자체등급분류",
        "분류기관": "게임물관리위원회·게임콘텐츠등급분류위원회·영상물등급위원회 또는 자체등급분류 사업자",
        "분류번호": "기관이 부여한 등급분류 번호",
        "제목": "게임물명 / 비디오물 제목(useTitle)",
        "구분": "게임물=플랫폼, 영상물=종별(kindName), 자체등급분류=고정값",
        "장르": "게임물=장르, 영상물=이용매체·목적(rightMediPurpName)",
        "등급명": "기관이 표기한 등급 명칭",
        "등급연령": "등급을 이용 가능 연령(0/12/15/18)으로 환산한 값",
        "청소년이용제한": "게임물 청소년이용불가 / 영상물 청소년관람불가·제한관람가",
        "분류일자": "등급분류 결정일", "분류연도": "분류일자의 연", "분류월": "분류일자의 연-월",
        "항목수": "보유한 내용정보 항목 수(해당 매체에 존재하는 항목 기준)",
        "비교대상밖_보유": "공통 4개 항목 외의 항목(게임물=언어·범죄·사행성 / 영상물=주제·대사·모방위험) 보유 여부",
        "비교표본": "매체 간 비교에 사용 가능한 건 여부(비교대상 외 항목 보유·등급취소·성인물·등급 미부여 건 제외)",
        "등급취소": "게임물 등급취소 여부",
        "원본": "해당 행의 출처 정제본 파일명",
    }
    rows = []
    for c in df.columns:
        if c.startswith("내용_"):
            d = "보유 1 / 미보유 0 / 해당 매체에 존재하지 않는 항목은 결측"
            if c[3:] in COMPARABLE + KMRB_ONLY:
                d += f" (영상물은 {THRESHOLD}단계 이상을 보유로 간주한 값)"
        elif c.startswith("단계_"):
            d = "영상물 원 단계값 1~5 (게임물은 수준 개념이 없으므로 결측)"
        else:
            d = desc.get(c, "")
        rows.append(f"<tr><td class=c>{c}</td><td class=t>{df[c].dtype}</td><td>{d}</td></tr>")
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>통합 분석 Dataset 데이터 사전</title>
<style>
 body {{ margin:0; padding:32px; background:#f7f7f5; color:#1f2328;
        font-family:"맑은 고딕","Malgun Gothic",system-ui,sans-serif;
        word-break:keep-all; overflow-wrap:break-word; }}
 .wrap {{ max-width:1040px; margin:0 auto; background:#fff; padding:36px 40px;
          border:1px solid #e3e3e0; border-radius:8px; }}
 h1 {{ font-size:20px; margin:0 0 4px; color:#1f3864; }}
 h2 {{ font-size:15px; margin:28px 0 10px; color:#1f3864; }}
 .sub {{ color:#6b7280; font-size:13px; margin-bottom:20px; }}
 .key {{ background:#fff4e0; border:1px solid #f0d9a8; border-radius:6px;
         padding:14px 18px; font-size:14px; margin-bottom:24px; line-height:1.7; }}
 table {{ border-collapse:collapse; width:100%; font-size:13px; }}
 th,td {{ border:1px solid #e6e6e3; padding:7px 10px; text-align:left; vertical-align:top; }}
 th {{ background:#f4f4f2; }}
 td.c {{ font-family:Consolas,monospace; white-space:nowrap; }}
 td.t {{ color:#6b7280; font-family:Consolas,monospace; white-space:nowrap; }}
</style></head><body><div class="wrap">
<h1>게임·영상물 등급분류 통합 분석 Dataset — 데이터 사전</h1>
<div class="sub">{meta['행']:,}행 · {meta['열']}열 · {meta['기간']} · 생성 {meta['생성']}</div>
<div class="key"><b>세 개의 자료원을 단일 표로 통합하였다.</b> 게임물 위원회분류
{meta['게임물_위원회']:,}건, 게임물 자체등급분류 {meta['게임물_자체']:,}건,
영상물 {meta['영상물']:,}건이다. <b>명칭이 동일한 내용정보 4개 항목(선정성·폭력성·공포·약물)만
통합 대상으로 하였으며</b>, 그 밖의 항목은 각 매체의 열에 그대로 유지하였다. 영상물의 1~5단계는
{THRESHOLD}단계 이상을 보유로 간주한 이진값과 원 단계값을 함께 수록한다.
제외 대상 건은 삭제하지 않고 <code>비교표본</code> 열에 표시하였다. 제외 기준은 분석 목적에 따라
달라지기 때문이다. 해당 열이 참인 건은 {meta['비교표본']:,}건이다.</div>
<h2>열 정의</h2>
<table><tr><th>열</th><th>형</th><th>정의</th></tr>{''.join(rows)}</table>
<h2>파일</h2>
<table><tr><th>산출물</th><th>경로</th></tr>
<tr><td>통합본 (분석용)</td><td class=c>{meta['parquet']}</td></tr>
<tr><td>통합본 (열람용)</td><td class=c>{meta['csv']}</td></tr>
<tr><td>생성 스크립트</td><td class=c>src\\make_integrated.py</td></tr></table>
</div></body></html>"""
    p = OUT / "integrated_dataset_dictionary.html"
    p.write_text(html, encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    df = pd.concat([load_grac(), load_self(), load_kmrb()], ignore_index=True)
    df["항목수"] = df[[f"내용_{n}" for n in ITEMS]].sum(axis=1).astype("Int64")
    df = df[COLS].sort_values(["분류일자", "매체", "분류번호"], na_position="last")
    df = df.reset_index(drop=True)

    pq = PROC / f"integrated_ratings_{STAMP}.parquet"
    csv = OUT / f"integrated_ratings_{STAMP}.csv"
    df.to_parquet(pq, index=False)
    df.to_csv(csv, index=False, encoding="utf-8-sig")

    meta = {
        "생성": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "행": int(len(df)), "열": int(len(df.columns)),
        "게임물_위원회": int(((df["매체"] == "게임물") & (df["분류경로"] == "위원회분류")).sum()),
        "게임물_자체": int((df["분류경로"] == "자체등급분류").sum()),
        "영상물": int((df["매체"] == "영상물").sum()),
        "비교표본": int(df["비교표본"].sum()),
        "청소년이용제한": int(df["청소년이용제한"].fillna(False).sum()),
        "이진화기준": THRESHOLD,
        "기간": f"{df['분류연도'].min()}~{df['분류연도'].max()}",
        "parquet": str(pq.relative_to(ROOT)), "csv": str(csv.relative_to(ROOT)),
    }
    (OUT / "integrated_dataset_summary.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = dictionary_html(df, meta)

    print(f"통합본 {meta['행']:,}행 × {meta['열']}열 · {meta['기간']}")
    print(f"  게임물(위원회) {meta['게임물_위원회']:,} · 게임물(자체) {meta['게임물_자체']:,}"
          f" · 영상물 {meta['영상물']:,}")
    print(f"  매체 비교에 쓸 수 있는 건 {meta['비교표본']:,} · 청소년 이용 제한 {meta['청소년이용제한']:,}")
    for p in (pq, csv, OUT / "integrated_dataset_summary.json", doc):
        print(f"저장: {p}")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
