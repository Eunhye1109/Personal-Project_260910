# -*- coding: utf-8 -*-
"""
특강 제출용 작업기록(docx) 생성

WORKLOG.md 의 그날 항목은 상세본이라 그대로 두고, 제출용은 여기서 따로 만든다.
번호를 매긴 짧은 문장만 남기고, 근거·경위·시행착오는 넣지 않는다.

실행
    python docs/make_worklog.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_prd import (init_doc, h, para, bullet, table,
                      set_run_font, ACCENT, MUTED)                   # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH                        # noqa: E402

OUT_DIR = r"C:\Users\User\gucc_rating_analysis\docs"
OUT_FILE = os.path.join(OUT_DIR, "[BI 분석가 과정] 작업기록_260909_최은혜.docx")

DONE = [
    "대시보드 6개 화면 제작 — 화면 하나가 질문 하나에 답하도록 구성",
    "화면용 데이터셋 분리 — 쓰는 열만 남겨 35.9MB → 3.6MB, 배포 저장소에 포함",
    "계산부 분리 — 화면 숫자를 분석 스크립트와 같은 규칙으로 산출, 리포트 값과 전부 일치",
    "화면별 인사이트 문장 자동 생성 — 필터를 바꾸면 문장의 숫자도 다시 계산",
    "배색 정리 — 매체별 고정 색, 색맹 대비 검사 통과값만 사용",
    "여섯 화면 브라우저 확인 및 자동 렌더링 시험",
    "GitHub 비공개 저장소 준비 — 인증키 노출 점검 완료(커밋 24개)",
]

FOUND = [
    ["대시보드", "화면 이름이 '1.' 로 시작하면 번호목록으로 읽혀 번호가 사라짐"],
    ["대시보드", "설명문 안의 물결표 두 개가 취소선으로 바뀜 — 연도 범위 표기를 교체"],
    ["설계", "정제본은 저장소에 없어 배포 화면이 읽지 못함 — 슬림 사본으로 해결"],
]

ISSUES = [
    "GitHub 로그인 대기 — 이후 저장소 생성·전체 히스토리 푸시",
    "Streamlit Cloud 배포는 계정 연결이 한 번 더 필요",
    "확인은 로컬 실행으로만 진행, 공개 URL 은 아직 없음",
]


def build():
    doc = init_doc()

    p = doc.add_paragraph()
    r = p.add_run("20260909 - 최은혜")
    set_run_font(r, size=16, bold=True, color=ACCENT)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = 14
    r = p.add_run("주제: 게임·영상물 등급분류 공공데이터 기반 "
                  "청소년 이용 부적합 콘텐츠 특성 분석 및 시각화")
    set_run_font(r, size=10, color=MUTED)

    h(doc, "오늘 한 일", 1)
    for i, t in enumerate(DONE, 1):
        para(doc, "%d. %s" % (i, t))

    h(doc, "오늘 나온 것", 1)
    table(doc, ["매체", "내용"], FOUND, widths=[2.0, 14.0])

    h(doc, "이슈", 1)
    for t in ISSUES:
        bullet(doc, t)

    doc.save(OUT_FILE)
    print("saved:", OUT_FILE)


if __name__ == "__main__":
    build()
