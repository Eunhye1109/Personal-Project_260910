# -*- coding: utf-8 -*-
"""
0단계 - 게임물관리위원회 게임 정보 Open API 응답 검증

이 스크립트는 데이터를 모으지 않는다. "무엇이 오는지"만 확인한다.
확인하는 것은 아래 다섯 가지다.

    (1) 게임위 서버에 닿는가            - 사무실 IP 차단 여부를 여기서 가른다
    (2) 인증키가 필요한가 / 어떤 이름인가
    (3) 응답 필드가 무엇인가
    (4) descriptors(내용정보)가 어떤 형태인가   - PRD 가정 A-1 의 게임물 쪽
    (5) 기간(startdate/enddate)과 페이징이 먹는가

배경
    이 API 는 공공데이터포털의 LINK(연계) 방식이다. 포털이 중계하지 않고
    게임위 자체 서버(www.grac.or.kr)를 직접 호출한다. 그래서 게임위에
    IP 가 차단돼 있으면 인증키가 멀쩡해도 한 건도 받을 수 없다.
    2026-09 현재 사무실 IP 가 차단된 상태이므로, 이 스크립트는 집이나
    휴대폰 테더링에서 실행해야 한다.

실행
    python src/probe_grac.py
"""
from __future__ import annotations

import socket
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apikey  # noqa: E402

DEFAULT_ENDPOINT = "https://www.grac.or.kr/WebService/GameSearchSvc.asmx/game"
TIMEOUT = 30
DELAY = 1.5
MAX_REQUESTS = 15          # 검증용이므로 상한을 낮게 둔다
_sent = 0


def guard() -> None:
    global _sent
    if _sent >= MAX_REQUESTS:
        raise SystemExit(f"[중단] 검증 요청 상한 {MAX_REQUESTS}회에 도달했습니다.")
    _sent += 1


def section(title: str) -> None:
    print("\n" + "-" * 66)
    print(title)
    print("-" * 66)


# --------------------------------------------------- (1) 연결 확인
def check_reachable(endpoint: str) -> bool:
    host = urlparse(endpoint).hostname or ""
    section(f"(1) 게임위 서버에 닿는가   [{host}]")
    try:
        ip = socket.gethostbyname(host)
        print(f"  이름 풀이 OK : {host} -> {ip}")
    except OSError as exc:
        print(f"  이름 풀이 실패: {exc}")
        print("  -> DNS 문제입니다. 네트워크를 먼저 확인하세요.")
        return False

    start = time.time()
    try:
        sock = socket.create_connection((ip, 443), timeout=15)
        sock.close()
        print(f"  접속 OK      : 443 포트 연결 {time.time() - start:.1f}초")
        return True
    except socket.timeout:
        print("  접속 실패    : 15초 무응답")
        print("  -> 거부(refused)가 아니라 '무응답'입니다. 방화벽이 조용히 버리는 전형적인 모습으로,")
        print("     현재 IP 가 게임위에 차단돼 있을 가능성이 높습니다.")
        print("     집 회선이나 휴대폰 테더링에서 다시 실행해 보세요. 거기서 되면 IP 차단이 확정됩니다.")
        return False
    except OSError as exc:
        print(f"  접속 실패    : {exc}")
        return False


# --------------------------------------------------- (2) 인증키
def try_key_styles(endpoint: str, key: str):
    """키를 어떤 이름으로 넘겨야 하는지 찾는다. 이 API 는 키가 없어도 될 수 있다."""
    section("(2) 인증키가 필요한가 / 파라미터 이름은 무엇인가")
    base = {"gametitle": "", "entname": "", "rateno": "", "display": "5", "pageno": "1"}
    styles = [("키 없이", {}),
              ("serviceKey", {"serviceKey": key}),
              ("key", {"key": key}),
              ("ServiceKey", {"ServiceKey": key})]
    for label, extra in styles:
        if extra and not key:
            continue
        params = dict(base)
        params.update(extra)
        try:
            guard()
            resp = requests.get(endpoint, params=params, timeout=TIMEOUT)
            body = apikey.mask(resp.text, key)
            ok = resp.status_code == 200 and "<item" in body
            print(f"  {label:12} HTTP {resp.status_code}  item포함={'예' if ok else '아니오'}  "
                  f"({len(resp.content):,}바이트)")
            if ok:
                print(f"  -> 이 방식으로 진행합니다: {label}")
                return body, params
            if resp.status_code == 200:
                print(f"     응답 앞부분: {body[:200]}")
        except requests.RequestException as exc:
            print(f"  {label:12} 실패 - {type(exc).__name__}: {exc}")
        time.sleep(DELAY)
    print("  -> 어떤 방식으로도 목록을 받지 못했습니다.")
    return None


# --------------------------------------------------- (3)(4) 응답 구조
def describe(body: str) -> None:
    section("(3) 응답 필드")
    root = ET.fromstring(body)
    tcount = root.findtext(".//tcount") or root.findtext(".//totalCount") or "?"
    print(f"  총 건수(tcount): {tcount}")
    items = root.findall(".//item")
    if not items:
        print("  item 이 없습니다.")
        return
    first = items[0]
    print(f"  item 당 필드 {len(list(first))}개")
    for child in first:
        val = (child.text or "").strip()
        print(f"    {child.tag:16} = {val[:70]}")

    section("(4) descriptors(내용정보)가 어떤 형태인가")
    vals = []
    for item in items:
        v = (item.findtext("descriptors") or "").strip()
        if v:
            vals.append(v)
    if not vals:
        print("  descriptors 가 비어 있습니다.")
        print("  -> 목록 조회에는 안 실려 오는 것일 수 있습니다. PRD 가정 A-2 를 다시 확인해야 합니다.")
        return
    for v in vals[:5]:
        print(f"    - {v}")
    sample = vals[0]
    has_digit = any(ch.isdigit() for ch in sample)
    print()
    print(f"  구분자 추정   : {'쉼표' if ',' in sample else '미상'}")
    print(f"  단계 표기 여부: {'있음(숫자 포함)' if has_digit else '없음 - 이름만 나열'}")
    if not has_digit:
        print("  -> 영등위(1~5단계 순서형)와 달리 게임물은 '해당 요소 보유 여부'만 주는 형태로 보입니다.")
        print("     이 경우 두 매체를 같은 척도로 직접 비교할 수 없습니다.")
        print("     영등위 값을 '3단계 이상 = 보유'로 이진화해 맞추는 방식이 현실적이며,")
        print("     PRD 4.4절 척도 정렬 규칙과 5.4절 축(1)의 설계를 이에 맞춰 고쳐야 합니다.")


# --------------------------------------------------- (5) 기간/페이징
def check_paging(endpoint: str, params: dict, key: str) -> None:
    section("(5) 기간(startdate/enddate)과 페이징이 먹는가")

    def tcount_of(extra: dict) -> str:
        guard()
        merged = dict(params)
        merged.update(extra)
        resp = requests.get(endpoint, params=merged, timeout=TIMEOUT)
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            return "파싱실패(" + apikey.mask(resp.text, key)[:80] + ")"
        return root.findtext(".//tcount") or "?"

    base = tcount_of({})
    print(f"  조건 없음                   tcount = {base}")
    time.sleep(DELAY)
    month = tcount_of({"startdate": "2024-01-01", "enddate": "2024-01-31"})
    print(f"  2024-01-01 ~ 2024-01-31     tcount = {month}")
    time.sleep(DELAY)
    year = tcount_of({"startdate": "2024-01-01", "enddate": "2024-12-31"})
    print(f"  2024-01-01 ~ 2024-12-31     tcount = {year}")

    if base == month == year:
        print()
        print("  -> 기간 조건이 무시되고 있습니다(세 값이 같음).")
        print("     영등위에서 겪은 '깊은 페이지 거부'가 여기서도 나오면 우회 수단이 없습니다.")
    else:
        print()
        print("  -> 기간 조건이 먹습니다. 월 단위로 잘라 받으면 페이징 한계를 피할 수 있습니다.")

    time.sleep(DELAY)
    guard()
    merged = dict(params)
    merged.update({"display": "1000", "pageno": "1"})
    resp = requests.get(endpoint, params=merged, timeout=60)
    try:
        n = len(ET.fromstring(resp.text).findall(".//item"))
        print(f"  display=1000 요청 -> 실제 {n}건 수신")
        if n < 1000:
            print("     한 번에 1,000건은 안 오는 것으로 보입니다. 수집 스크립트의 페이지 크기를 낮추세요.")
    except ET.ParseError:
        print("  display=1000 실패 - " + apikey.mask(resp.text, key)[:150])


def main() -> None:
    endpoint = apikey.get(
        "GRAC_GAME_ENDPOINT",
        prompt=("게임물관리위원회 게임 정보 API 호출주소.\n"
                f"   기본값을 쓰려면 그대로 두세요: {DEFAULT_ENDPOINT}"),
        default=DEFAULT_ENDPOINT,
    )
    key = apikey.get("DATA_GO_KR_KEY", prompt=None)   # 없어도 진행 (키 불필요일 수 있음)

    print(f"엔드포인트 : {endpoint}")
    print(f"인증키     : {'설정됨' if key else '없음 (키 없이 되는지부터 확인합니다)'}")

    if not check_reachable(endpoint):
        print("\n[중단] 서버에 닿지 못했습니다. 위 안내를 확인하세요.")
        sys.exit(1)

    got = try_key_styles(endpoint, key)
    if not got:
        print("\n[중단] 응답을 받지 못했습니다.")
        print("  공공데이터포털에서 '게임물관리위원회_게임 정보'(15120667) 활용신청을 했는지 확인하세요.")
        sys.exit(1)

    body, params = got
    describe(body)
    check_paging(endpoint, params, key)

    print("\n" + "-" * 66)
    print(f"검증 끝. 이번 실행에서 보낸 요청 {_sent}회.")
    print("다음: python src/collect_grac.py --months 1   (먼저 한 달치만 시험)")


if __name__ == "__main__":
    main()
