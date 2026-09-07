"""
0단계 — 영등위 비디오물 등급분류 API 응답 필드 검증

PRD 4.5절의 가정 A-1~A-5를 실제 응답으로 확인하기 위한 스크립트다.
전량 수집이 아니라 소량(기본 10건)만 불러 필드 구조만 본다.

실행:
    python src/probe_kmrb.py              # 10건
    python src/probe_kmrb.py --rows 50    # 건수 조절
    python src/probe_kmrb.py --param 등급분류일자=2024        # 옵션 파라미터 추가

※ 필수값만 넣으면 대량 조회로 타임아웃(99, UNKNOWN_ERROR)이 날 수 있다고
  API 안내에 적혀 있다. 그 경우 --param 으로 조건을 하나 걸어 좁힌다.
"""
from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

load_dotenv(ROOT / ".env")
ENDPOINT = os.getenv("KMRB_VIDEO_ENDPOINT", "").strip()
SERVICE_KEY = os.getenv("DATA_GO_KR_KEY", "").strip()


def check_env() -> None:
    missing = [
        name
        for name, value in (
            ("KMRB_VIDEO_ENDPOINT", ENDPOINT),
            ("DATA_GO_KR_KEY", SERVICE_KEY),
        )
        if not value
    ]
    if missing:
        print("[중단] .env 에 다음 값이 비어 있습니다: " + ", ".join(missing))
        print(f"       {ROOT / '.env.example'} 를 .env 로 복사한 뒤 채워주세요.")
        sys.exit(1)


def mask(text: str) -> str:
    """로그·에러 메시지에 인증키가 새어나가지 않게 가린다."""
    return text.replace(SERVICE_KEY, "<SERVICE_KEY>") if SERVICE_KEY else text


def fetch(rows: int, extra: dict[str, str]) -> tuple[str, str]:
    """API를 호출하고 (응답본문, 저장경로)를 돌려준다.

    HTTP 400이어도 본문에 원인이 담겨 오므로 예외를 던지지 않고 그대로 넘긴다.
    """
    params = {"serviceKey": SERVICE_KEY, "pageNo": 1, "numOfRows": rows, **extra}
    resp = requests.get(ENDPOINT, params=params, timeout=60)
    if resp.status_code != 200:
        print(f"[HTTP {resp.status_code}] 오류 응답이지만 본문을 확인합니다.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%y%m%d_%H%M%S")
    saved = RAW_DIR / f"probe_kmrb_{stamp}.xml"
    saved.write_text(resp.text, encoding="utf-8")
    return resp.text, str(saved)


def find_items(root: ET.Element) -> list[ET.Element]:
    """<item> 이름이 무엇이든 잎사귀 반복 요소를 찾아낸다."""
    items = root.findall(".//item")
    if items:
        return items
    # item 태그가 아닐 경우: 같은 태그명이 2회 이상 반복되는 부모를 찾는다
    for parent in root.iter():
        names = [child.tag for child in parent]
        if names:
            tag, count = Counter(names).most_common(1)[0]
            if count >= 2:
                return [c for c in parent if c.tag == tag]
    return []


def report(body: str) -> None:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        print("[경고] XML로 파싱되지 않았습니다. 응답 앞부분을 그대로 출력합니다.\n")
        print(body[:2000])
        return

    # 포털 공통 오류(cmmMsgHeader)를 먼저 걸러낸다
    err = root.find(".//errMsg")
    if err is not None:
        code = root.find(".//returnReasonCode")
        why = root.find(".//returnAuthMsg")
        print("── 포털 오류 응답 ──")
        print(f"  {err.text} (코드 {code.text if code is not None else '?'})")
        print(f"  {why.text if why is not None else ''}")
        hints = {
            "30": "인증키가 아직 등록·반영되지 않았습니다. 발급 직후면 1~2시간 기다린 뒤 재시도하세요.",
            "12": "해당 서비스 경로가 없습니다. 엔드포인트 주소를 다시 확인하세요.",
            "20": "키는 정상이나 이 서비스에는 활용신청이 되어 있지 않습니다.",
            "22": "일일 트래픽(개발계정 1,000건)을 초과했습니다. 내일 다시 시도하세요.",
        }
        if code is not None and code.text in hints:
            print(f"  → {hints[code.text]}")
        return

    # 결과 코드 · 총건수
    print("── 응답 헤더 ──")
    for tag in ("resultCode", "resultMsg", "returnAuthMsg", "errMsg", "totalCount"):
        found = root.find(f".//{tag}")
        if found is not None and found.text:
            print(f"  {tag}: {found.text.strip()}")

    items = find_items(root)
    print(f"\n── 수신 건수: {len(items)}건 ──")
    if not items:
        print("  항목이 없습니다. 인증키 반영 대기(1~2시간) 중이거나 조건이 맞지 않을 수 있습니다.")
        print("\n  응답 원문 앞부분:")
        print("  " + body[:800].replace("\n", "\n  "))
        return

    # 필드 목록 — 전체 항목에서 등장한 태그를 모은다
    seen: Counter[str] = Counter()
    for item in items:
        for child in item:
            seen[child.tag] += 1

    print(f"\n── 응답 필드 {len(seen)}개 (등장 건수 / 전체 {len(items)}건) ──")
    for tag, count in seen.most_common():
        flag = "" if count == len(items) else "   ← 일부 항목에만 존재"
        print(f"  {tag:<28} {count}{flag}")

    # 첫 건 전체 값
    print("\n── 첫 번째 항목의 실제 값 ──")
    for child in items[0]:
        value = (child.text or "").strip()
        if len(value) > 120:
            value = value[:120] + " …"
        print(f"  {child.tag:<28} {value!r}")

    # 내용정보 후보 필드의 값 분포 — A-1(순서형 척도인지) 판단용
    keywords = ("선정", "폭력", "공포", "약물", "주제", "대사", "모방", "등급", "content", "rat", "grade")
    targets = [t for t in seen if any(k in t.lower() for k in keywords)]
    if targets:
        print("\n── 등급·내용정보 후보 필드의 값 분포 (A-1 판단용) ──")
        for tag in targets:
            values = Counter(
                (item.find(tag).text or "").strip()
                for item in items
                if item.find(tag) is not None
            )
            preview = ", ".join(f"{v!r}×{c}" for v, c in values.most_common(6))
            print(f"  {tag:<28} {preview}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=10, help="가져올 건수 (기본 10)")
    ap.add_argument("--param", action="append", default=[], help="추가 파라미터 key=value")
    args = ap.parse_args()

    check_env()
    extra = dict(p.split("=", 1) for p in args.param)

    print(f"호출: {mask(ENDPOINT)}")
    print(f"파라미터: numOfRows={args.rows}" + (f", {extra}" if extra else "") + "\n")

    try:
        body, saved = fetch(args.rows, extra)
    except requests.RequestException as exc:
        print(f"[중단] 요청 실패: {mask(str(exc))}")
        sys.exit(1)
    print(f"원문 저장: {saved}\n")
    report(body)


if __name__ == "__main__":
    main()
