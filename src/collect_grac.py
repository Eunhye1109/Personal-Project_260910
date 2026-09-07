# -*- coding: utf-8 -*-
"""
1단계 - 게임물관리위원회 게임 정보 전량 수집

영등위 수집(collect_kmrb.py)에서 약 99,000건 지점부터 깊은 페이지 조회가
거부됐다. 같은 일을 피하려고, 여기서는 처음부터 기간(startdate/enddate)으로
잘라서 받는다. 한 조각을 월 단위로 두면 페이지 번호가 깊어지지 않는다.

    2016-01 -> 페이지 1,2,3...
    2016-02 -> 페이지 1,2,3...
    ...

받은 XML 은 손대지 않고 data/raw/grac_game/ 에 그대로 쌓는다.
이미 받은 조각은 건너뛰므로 중단 후 다시 실행하면 이어서 받는다.

실행
    python src/probe_grac.py                    # 반드시 먼저 (0단계 검증)
    python src/collect_grac.py --months 1       # 한 달치만 시험
    python src/collect_grac.py                  # 전량
    python src/collect_grac.py --merge-only     # 이미 받은 것만 합치기

주의 - 이 스크립트는 집이나 테더링에서 실행할 것
    이 API 는 LINK(연계) 방식이라 게임위 서버를 직접 호출한다.
    2026-09 현재 사무실 IP 는 게임위에 차단돼 있어 사무실에서는 동작하지 않는다.
"""
from __future__ import annotations

import argparse
import calendar
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apikey  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "grac_game"
OUT_DIR = ROOT / "data" / "processed"

DEFAULT_ENDPOINT = "https://www.grac.or.kr/WebService/GameSearchSvc.asmx/game"
DEFAULT_START = "2016-01"          # PRD 4.1절 대상 기간 시작
ROWS_PER_PAGE = 1000               # probe 에서 실제 수신 건수를 확인하고 조정할 것
DELAY_SEC = 1.5
MAX_RETRY = 3

# ---- 안전장치 -------------------------------------------------------------
# 2026-08 게임위 홈페이지 크롤링에서 8병렬/누적 1만+ POST 로 사무실 IP 가
# 차단된 전례가 있다. 같은 일을 반복하지 않도록 아래를 코드에 박아 둔다.
#
#   1) 절대 병렬로 돌리지 않는다. 요청은 항상 순차 1개.
#   2) 한 번 실행에서 보내는 요청 수에 상한을 둔다(버그로 인한 폭주 방지).
#   3) 한 조각이 MAX_RETRY 회 실패하면 재시도를 반복하지 않고 즉시 전체를 멈춘다.
#   4) 기간 조건이 무시되고 있으면(같은 tcount 가 계속 나오면) 바로 멈춘다.
#      조건이 안 먹는 채로 계속 돌면 같은 페이지를 수천 번 긁는 꼴이 된다.
#
# 상한에 걸려 멈춰도 받은 조각은 남으므로, 다시 실행하면 건너뛰고 이어서 받는다.
MAX_REQUESTS_PER_RUN = 300

_sent = 0


def guard() -> None:
    global _sent
    if _sent >= MAX_REQUESTS_PER_RUN:
        raise RuntimeError(
            f"안전장치 작동: 한 번 실행 상한 {MAX_REQUESTS_PER_RUN}회에 도달했습니다. "
            "받은 조각은 보존되므로 다시 실행하면 이어서 받습니다."
        )
    _sent += 1


def months_between(start: str, end: str) -> list[tuple[str, str, str]]:
    """'2016-01','2026-08' -> [('2016-01','2016-01-01','2016-01-31'), ...]"""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        last_day = calendar.monthrange(y, m)[1]
        out.append((f"{y:04d}-{m:02d}",
                    date(y, m, 1).isoformat(),
                    date(y, m, last_day).isoformat()))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def request(endpoint: str, params: dict, key: str) -> str:
    last = ""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            guard()
            resp = requests.get(endpoint, params=params, timeout=120)
            if resp.status_code == 200 and "<result" in resp.text:
                return resp.text
            last = f"HTTP {resp.status_code} / {apikey.mask(resp.text, key)[:200]}"
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < MAX_RETRY:
            time.sleep(2 * attempt)
    raise RuntimeError(f"{MAX_RETRY}회 실패 - {last}")


def parse_count(xml_text: str) -> int:
    text = ET.fromstring(xml_text).findtext(".//tcount")
    return int(text) if text and text.strip().isdigit() else 0


def to_rows(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    return [{c.tag: (c.text or "").strip() for c in item} for item in root.findall(".//item")]


def collect(endpoint: str, key: str, key_param: str, slices, verbose: bool = True) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seen_counts: list[int] = []

    for label, start, end in slices:
        page = 1
        total = None
        while True:
            path = RAW_DIR / f"{label}_p{page:03d}.xml"
            if path.exists():
                if verbose and page == 1:
                    print(f"  {label}  건너뜀(이미 있음)")
                # 이미 있는 조각에서 총 건수를 읽어 다음 페이지 필요 여부를 판단
                total = total if total is not None else parse_count(path.read_text(encoding="utf-8"))
                if page * ROWS_PER_PAGE >= total:
                    break
                page += 1
                continue

            params = {"gametitle": "", "entname": "", "rateno": "",
                      "startdate": start, "enddate": end,
                      "display": str(ROWS_PER_PAGE), "pageno": str(page)}
            if key and key_param:
                params[key_param] = key

            body = request(endpoint, params, key)
            path.write_text(body, encoding="utf-8")

            if total is None:
                total = parse_count(body)
                seen_counts.append(total)
                # 기간 조건이 무시되는지 점검 - 서로 다른 달의 총 건수가 계속 같으면 이상하다
                if len(seen_counts) >= 4 and len(set(seen_counts[-4:])) == 1 and seen_counts[-1] > 0:
                    raise RuntimeError(
                        f"안전장치 작동: 최근 4개 달의 총 건수가 모두 {seen_counts[-1]}건으로 같습니다. "
                        "기간 조건(startdate/enddate)이 무시되고 있을 가능성이 큽니다. "
                        "src/probe_grac.py 로 다시 확인하세요."
                    )
                if verbose:
                    print(f"  {label}  총 {total:,}건")

            got = len(to_rows(body))
            if verbose:
                print(f"    p{page:03d}  {got:,}건 저장")
            time.sleep(DELAY_SEC)

            if got < ROWS_PER_PAGE or page * ROWS_PER_PAGE >= (total or 0):
                break
            page += 1


def merge() -> None:
    files = sorted(RAW_DIR.glob("*.xml"))
    if not files:
        print("합칠 원본이 없습니다.")
        return
    print(f"\n원본 {len(files)}개를 하나로 합치는 중...")
    rows: list[dict[str, str]] = []
    for path in files:
        rows.extend(to_rows(path.read_text(encoding="utf-8")))

    df = pd.DataFrame(rows)
    before = len(df)
    if "rateno" in df.columns:
        df = df.drop_duplicates(subset=["rateno"], keep="first")
    print(f"  {before:,}행 -> 중복 제거 후 {len(df):,}행 (기준: 등급분류번호 rateno)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%y%m%d")
    out = OUT_DIR / f"grac_game_raw_{stamp}.parquet"
    df.to_parquet(out, index=False)
    print(f"\n저장 완료: {out}")
    print(f"  {len(df):,}행 x {len(df.columns)}열")
    if "rateddate" in df.columns:
        dates = df["rateddate"].replace("", pd.NA).dropna()
        if len(dates):
            print(f"  등급분류일자: {dates.min()} ~ {dates.max()}")
    if "descriptors" in df.columns:
        filled = (df["descriptors"].fillna("").str.strip() != "").mean()
        print(f"  내용정보(descriptors) 채워진 비율: {filled:.1%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=DEFAULT_START, help="시작 연월 (기본 2016-01)")
    ap.add_argument("--end", default=date.today().strftime("%Y-%m"), help="종료 연월")
    ap.add_argument("--months", type=int, default=0, help="앞에서 N개 달만 (0이면 전량)")
    ap.add_argument("--key-param", default="", help="인증키 파라미터 이름. 비우면 키를 안 붙인다")
    ap.add_argument("--merge-only", action="store_true", help="수집 없이 합치기만")
    args = ap.parse_args()

    if args.merge_only:
        merge()
        return

    endpoint = apikey.get("GRAC_GAME_ENDPOINT", default=DEFAULT_ENDPOINT)
    key = apikey.get("DATA_GO_KR_KEY", prompt=None)

    slices = months_between(args.start, args.end)
    if args.months:
        slices = slices[: args.months]

    print(f"엔드포인트 : {endpoint}")
    print(f"수집 구간  : {slices[0][0]} ~ {slices[-1][0]}  ({len(slices)}개 달)")
    print(f"인증키     : {('설정됨, ' + args.key_param) if (key and args.key_param) else '안 붙임'}")
    print(f"안전장치   : 순차 1개 / 실행당 최대 {MAX_REQUESTS_PER_RUN}회 / 간격 {DELAY_SEC}초\n")

    try:
        collect(endpoint, key, args.key_param, slices)
    except RuntimeError as exc:
        print(f"\n[멈춤] {exc}")
        print(f"  이번 실행에서 보낸 요청 {_sent}회. 받은 조각은 그대로 남아 있습니다.")
        merge()
        sys.exit(1)

    print(f"\n수집 끝. 이번 실행에서 보낸 요청 {_sent}회.")
    merge()


if __name__ == "__main__":
    main()
