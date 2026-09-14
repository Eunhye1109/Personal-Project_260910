# -*- coding: utf-8 -*-
"""
NAS(공유 드라이브) 사본 갱신

`Y:\\2. 정책기획팀\\기타\\rating_analysis` 로 프로젝트를 복사한다.
다른 스크립트가 끝날 때 호출해 산출물이 자동으로 NAS에 올라가게 한다.

인증키 파일(.env)은 반드시 제외한다. 그 폴더는 정책기획팀 공유 폴더라
키가 팀 전체에 노출된다.

    ※ robocopy 의 /XF 는 파일 이름만 주면 먹지 않는다. 전체 경로로 줘야 한다.
      (2026-09-02 에 이것 때문에 인증키가 공유 폴더로 새어 나갔다)

복사 후 .env 가 실제로 없는지 확인하고, 없으면 실패로 처리한다.

실행
    python src/sync_nas.py            # 직접 실행
    from sync_nas import sync; sync() # 다른 스크립트에서
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAS = Path(r"Y:\2. 정책기획팀\기타\rating_analysis")
SECRET = ".env"


def sync(dest: Path = NAS, quiet: bool = False) -> bool:
    """NAS로 복사한다. 성공하면 True."""
    if not shutil.which("robocopy"):
        print("[건너뜀] robocopy 를 찾지 못했습니다.")
        return False

    if not dest.parent.exists():
        print(f"[건너뜀] NAS 경로에 접근할 수 없습니다: {dest.parent}")
        print("  집에서 실행 중이거나 드라이브가 연결되지 않은 상태로 보입니다.")
        return False

    cmd = ["robocopy", str(ROOT), str(dest), "/E",
           "/XF", str(ROOT / SECRET),
           "/XD", "__pycache__",
           "/R:1", "/W:2", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    # robocopy 는 0~7 이 정상이다. 8 이상이 진짜 실패다.
    if proc.returncode >= 8:
        print(f"[실패] robocopy 종료코드 {proc.returncode}")
        print(proc.stdout[-500:])
        return False

    leaked = dest / SECRET
    if leaked.exists():
        print(f"[경고] 인증키 파일이 공유 폴더에 올라갔습니다: {leaked}")
        print("  즉시 삭제하고 제외 옵션을 확인하세요.")
        return False

    if not quiet:
        print(f"NAS 동기화 완료: {dest}")
        print(f"  인증키({SECRET}) 제외 확인함")
    return True


if __name__ == "__main__":
    sys.exit(0 if sync() else 1)
