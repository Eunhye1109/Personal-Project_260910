# -*- coding: utf-8 -*-
"""
인증키·엔드포인트를 찾아오는 공통 도우미.

이 프로젝트 폴더는 NAS(공유 드라이브)에도 사본이 올라간다.
따라서 인증키를 프로젝트 폴더의 .env 에 쓰면 공유 폴더로 새어 나간다.
그래서 키를 찾는 순서를 이렇게 둔다.

    1) OS 환경변수
    2) 프로젝트 폴더의 .env        ← 사무실 PC에서 쓰던 기존 방식(있으면 그대로 사용)
    3) 개인 PC의 홈 폴더 파일       ← ~/.gucc_rating_analysis.env  (NAS로 복사되지 않음)
    4) 없으면 화면에서 물어보고, 답을 3)에 저장한다

집에서 NAS 폴더를 열어 그대로 실행하면 4)가 뜬다. 한 번 붙여넣으면
키는 그 PC의 홈 폴더에만 남고 NAS에는 올라가지 않는다.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ENV = ROOT / ".env"
HOME_ENV = Path.home() / ".gucc_rating_analysis.env"


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _append_home_env(name: str, value: str) -> None:
    HOME_ENV.touch(exist_ok=True)
    existing = _read_env_file(HOME_ENV)
    existing[name] = value
    body = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    HOME_ENV.write_text(
        "# gucc_rating_analysis 개인 설정 — 이 파일은 NAS로 복사되지 않는다.\n" + body,
        encoding="utf-8",
    )
    try:                                   # 다른 사용자가 못 읽게 (윈도우에서는 무시될 수 있음)
        HOME_ENV.chmod(0o600)
    except OSError:
        pass


def get(name: str, prompt: str | None = None, default: str = "") -> str:
    """설정값 하나를 찾아온다. 못 찾으면 물어보고 홈 폴더에 저장한다."""
    for source in (os.environ, _read_env_file(PROJECT_ENV), _read_env_file(HOME_ENV)):
        value = (source.get(name) or "").strip()
        if value:
            return value

    # 물어볼 문구가 없으면 조용히 기본값(또는 빈 값)을 쓴다.
    if prompt is None:
        return default

    print(f"\n[{name}] 값이 설정돼 있지 않습니다.")
    print(f"  {prompt}")
    if default:
        print(f"  그냥 엔터를 치면 기본값을 씁니다: {default}")
    value = input(f"  {name} = ").strip()

    if not value:
        if default:
            print("  기본값을 씁니다.\n")
            return default
        raise SystemExit("[중단] 값이 비어 있습니다.")

    _append_home_env(name, value)
    print(f"  저장했습니다: {HOME_ENV}  (이 PC에만 남습니다)\n")
    return value


def mask(text: str, secret: str) -> str:
    """로그·오류 메시지에서 인증키를 가린다."""
    return text.replace(secret, "<SERVICE_KEY>") if secret else text
