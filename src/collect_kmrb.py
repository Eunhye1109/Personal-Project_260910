"""
1단계 — 영등위 비디오물 등급분류 전량 수집

페이지를 순서대로 돌며 원본 XML을 data/raw/ 에 그대로 쌓고,
전부 받은 뒤 하나의 표로 합쳐 data/processed/ 에 parquet으로 저장한다.

이미 받은 페이지는 건너뛴다(중단 후 재실행해도 이어서 받음).

260907 — 약 99,000건(페이지 100)부터 resultCode 99(깊은 페이지 거부)가 나서
전량을 pageNo만으로는 받을 수 없다. stDate/edDate(YYYYMMDD, 등급분류기간)를
찾아 월 단위로 나눠 받는 --by-date 모드를 추가했다(collect_grac.py와 같은 방식).
이미 받은 2009-01~2023-03(99,000건, page_*.xml)은 그대로 두고, 그 이후 구간만
새로 받는다. merge() 는 두 종류 파일을 모두 합쳐 rtNo 기준 중복 제거한다.

실행:
    python src/collect_kmrb.py                          # 기존 방식 전량(페이지 100 근처에서 막힘)
    python src/collect_kmrb.py --max-pages 5             # 시험 삼아 5페이지만
    python src/collect_kmrb.py --by-date --start 2023-03 # 날짜 슬라이스로 이어받기
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
RAW_DIR = ROOT / "data" / "raw" / "kmrb_video"
OUT_DIR = ROOT / "data" / "processed"

ENDPOINT = apikey.get("KMRB_VIDEO_ENDPOINT", prompt="영등위 비디오물 등급분류정보 조회 서비스 엔드포인트 (예: https://apis.data.go.kr/B551008/video_search_v2)")
SERVICE_KEY = apikey.get("DATA_GO_KR_KEY", prompt="공공데이터포털 일반 인증키(Decoding)")

ROWS_PER_PAGE = 1000
DELAY_SEC = 1.0          # 호출 간격(초)
MAX_RETRY = 3

# ─── 안전장치 ────────────────────────────────────────────────
# 과거 게임물관리위원회 크롤링에서 8병렬·누적 1만+ 요청으로 사무실 IP가
# 차단된 전례가 있다. 같은 일이 반복되지 않도록 아래를 지킨다.
#
#   1) 절대 병렬로 돌리지 않는다. 요청은 항상 순차 1개.
#   2) 한 번 실행에서 보내는 요청 수에 상한을 둔다(버그로 인한 폭주 방지).
#   3) 페이지가 MAX_RETRY 회 실패하면 재시도를 반복하지 않고 즉시 전체를 중단한다.
#   4) 개발계정 일 한도(1,000회) 대비 여유를 남긴다. 전량은 약 135회면 끝난다.
#
# 상한에 걸려 멈추면 이미 받은 페이지는 그대로 남으므로, 다음 날 다시 실행하면
# 건너뛰고 이어서 받는다.
MAX_REQUESTS_PER_RUN = 200

_sent = 0                # 이번 실행에서 실제로 보낸 요청 수


def guard() -> None:
    """요청 상한을 넘으면 더 보내지 않고 멈춘다."""
    global _sent
    if _sent >= MAX_REQUESTS_PER_RUN:
        raise RuntimeError(
            f"안전장치 작동: 한 번 실행 상한 {MAX_REQUESTS_PER_RUN}회에 도달했습니다. "
            "받은 데이터는 보존되므로 다시 실행하면 이어서 받습니다."
        )
    _sent += 1


def mask(text: str) -> str:
    return text.replace(SERVICE_KEY, "<SERVICE_KEY>") if SERVICE_KEY else text


def request_page(page: int) -> str:
    """한 페이지를 받아 XML 본문을 돌려준다. 실패 시 재시도."""
    params = {"serviceKey": SERVICE_KEY, "pageNo": page, "numOfRows": ROWS_PER_PAGE}
    last = ""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            guard()
            resp = requests.get(ENDPOINT, params=params, timeout=120)
            if resp.status_code == 200 and "<item>" in resp.text:
                return resp.text
            last = f"HTTP {resp.status_code} / {resp.text[:200]}"
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < MAX_RETRY:
            time.sleep(2 * attempt)
    raise RuntimeError(f"{page}페이지 {MAX_RETRY}회 실패 — {mask(last)}")


def total_count() -> int:
    """총 건수를 읽는다.

    ※ numOfRows 를 너무 작게(1 등) 주면 이 API는 resultCode 99(UNKNOWN_ERROR)를
      돌려준다. 실제로 쓰는 크기와 같은 값으로 물어봐야 안정적이다.
    """
    last = ""
    for attempt in range(1, MAX_RETRY + 1):
        guard()
        resp = requests.get(
            ENDPOINT,
            params={"serviceKey": SERVICE_KEY, "pageNo": 1, "numOfRows": ROWS_PER_PAGE},
            timeout=120,
        )
        text = ET.fromstring(resp.text).findtext(".//totalCount")
        if text and text.strip():
            return int(text)
        last = resp.text[:300]
        if attempt < MAX_RETRY:
            time.sleep(3 * attempt)
    raise RuntimeError(f"총 건수를 읽지 못했습니다 — {mask(last)}")


def to_rows(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    return [
        {child.tag: (child.text or "").strip() for child in item}
        for item in root.findall(".//item")
    ]


def months_between(start: str, end: str) -> list[tuple[str, str, str]]:
    """'2023-03','2026-09' -> [('2023-03','20230301','20230331'), ...] (YYYYMMDD, stDate/edDate용)"""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        last_day = calendar.monthrange(y, m)[1]
        out.append((f"{y:04d}-{m:02d}",
                    date(y, m, 1).strftime("%Y%m%d"),
                    date(y, m, last_day).strftime("%Y%m%d")))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def request_by_date(st_date: str, ed_date: str, page: int) -> str:
    params = {"serviceKey": SERVICE_KEY, "pageNo": page, "numOfRows": ROWS_PER_PAGE,
              "stDate": st_date, "edDate": ed_date}
    last = ""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            guard()
            resp = requests.get(ENDPOINT, params=params, timeout=120)
            if resp.status_code == 200 and "resultCode" in resp.text:
                return resp.text
            last = f"HTTP {resp.status_code} / {resp.text[:200]}"
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < MAX_RETRY:
            time.sleep(2 * attempt)
    raise RuntimeError(f"{st_date}~{ed_date} p{page} {MAX_RETRY}회 실패 — {mask(last)}")


def collect_by_date(slices: list[tuple[str, str, str]]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for label, st_date, ed_date in slices:
        page = 1
        total = None
        while True:
            path = RAW_DIR / f"{label}_p{page:03d}.xml"
            if path.exists():
                if page == 1:
                    print(f"  {label}  건너뜀(이미 있음)")
                root = ET.fromstring(path.read_text(encoding="utf-8"))
                total = total if total is not None else int(root.findtext(".//totalCount") or 0)
                if page * ROWS_PER_PAGE >= total:
                    break
                page += 1
                continue

            body = request_by_date(st_date, ed_date, page)
            root = ET.fromstring(body)
            code = root.findtext(".//resultCode")
            if code != "00":
                raise RuntimeError(f"{label} p{page} resultCode={code} — {root.findtext('.//resultMsg')}")
            path.write_text(body, encoding="utf-8")

            if total is None:
                total = int(root.findtext(".//totalCount") or 0)
                print(f"  {label}  총 {total:,}건")

            got = len(root.findall(".//item"))
            print(f"    p{page:03d}  {got:,}건 저장")
            time.sleep(DELAY_SEC)

            if got < ROWS_PER_PAGE or page * ROWS_PER_PAGE >= total:
                break
            page += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=0, help="0이면 전량 (기존 방식, 페이지 100 근처에서 막힘)")
    ap.add_argument("--by-date", action="store_true", help="stDate/edDate로 월 단위 슬라이스하여 수집")
    ap.add_argument("--start", default="2023-03", help="--by-date 시작 연월 (기본 2023-03, 기존 수집분과 겹쳐도 중복 제거됨)")
    ap.add_argument("--end", default=date.today().strftime("%Y-%m"), help="--by-date 종료 연월")
    ap.add_argument("--months", type=int, default=0, help="--by-date 앞에서 N개 달만 (0이면 전량)")
    ap.add_argument("--merge-only", action="store_true", help="수집 없이 합치기만")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.merge_only:
        merge()
        return

    if args.by_date:
        slices = months_between(args.start, args.end)
        if args.months:
            slices = slices[: args.months]
        print(f"수집 구간  : {slices[0][0]} ~ {slices[-1][0]}  ({len(slices)}개 달)")
        print(f"안전장치   : 순차 1개 / 실행당 최대 {MAX_REQUESTS_PER_RUN}회 / 간격 {DELAY_SEC}초\n")
        try:
            collect_by_date(slices)
        except RuntimeError as exc:
            print(f"\n[멈춤] {exc}")
            print(f"  이번 실행에서 보낸 요청 {_sent}회. 받은 조각은 그대로 남아 있습니다.")
            merge()
            sys.exit(1)
        print(f"\n수집 끝. 이번 실행에서 보낸 요청 {_sent}회.")
        merge()
        return

    total = total_count()
    pages = -(-total // ROWS_PER_PAGE)          # 올림 나눗셈
    if args.max_pages:
        pages = min(pages, args.max_pages)
    print(f"총 {total:,}건 / {pages}페이지 (페이지당 {ROWS_PER_PAGE}건)\n")

    for page in range(1, pages + 1):
        path = RAW_DIR / f"page_{page:04d}.xml"
        if path.exists():
            print(f"  {page:>4}/{pages}  건너뜀(이미 있음)")
            continue
        body = request_page(page)
        path.write_text(body, encoding="utf-8")
        print(f"  {page:>4}/{pages}  저장 {len(body):,}바이트")
        time.sleep(DELAY_SEC)

    merge()


def merge() -> None:
    print("\n원본을 하나로 합치는 중…")
    rows: list[dict[str, str]] = []
    files = sorted(RAW_DIR.glob("page_*.xml")) + sorted(RAW_DIR.glob("2*_p*.xml"))
    for path in files:
        rows.extend(to_rows(path.read_text(encoding="utf-8")))

    df = pd.DataFrame(rows)
    if "RNUM" in df.columns:
        df = df.drop(columns=["RNUM"])           # 페이지 내 순번이라 합치면 의미 없음

    before = len(df)
    if "rtNo" in df.columns:
        df = df.drop_duplicates(subset=["rtNo"], keep="first")
    print(f"  {before:,}행 → 중복 제거 후 {len(df):,}행 (기준: 등급분류번호 rtNo)")

    stamp = datetime.now().strftime("%y%m%d")
    out = OUT_DIR / f"kmrb_video_raw_{stamp}.parquet"
    df.to_parquet(out, index=False)
    print(f"\n저장 완료: {out}")
    print(f"  {len(df):,}행 × {len(df.columns)}열")
    if "rtDate" in df.columns:
        dates = df["rtDate"].replace("", pd.NA).dropna()
        print(f"  등급분류일자: {dates.min()} ~ {dates.max()}")


if __name__ == "__main__":
    main()
