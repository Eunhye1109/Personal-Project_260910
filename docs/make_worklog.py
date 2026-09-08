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
OUT_FILE = os.path.join(OUT_DIR, "[BI 분석가 과정] 작업기록_260908_최은혜.docx")

DONE = [
    "집 수집분 회수·커밋 — 게임물 29,417건 · 영상물 134,464건, 두 기관 전량",
    "영등위 전량 재정제 (99,000 → 134,462행, 표본으로 내렸던 판단 2건 정정)",
    "게임물 정제·현황 EDA 신설 — 내용정보를 항목별 보유 여부로 전개",
    "매체 간 비교 — 이름이 같은 4개 항목만, 대상 밖 항목은 양쪽 대칭 제외",
    "자체등급분류 비교군 편입 — 같은 기간 위원회 207건 대 자체 76,409건",
    "하드코딩된 데이터 경로 제거 (재수집 후에도 옛 정제본을 보고 있었음)",
    "리포트 5종 통합 — 작업 순서가 아니라 결론이 앞에 오도록 재작성",
    "PRD v1.3 → v1.6 갱신, 강사 회신 문서 작성",
]

FOUND = [
    ["게임물", "청소년이용불가를 만드는 것은 폭력성이 아니라 사행성 — 있으면 95.3%, 없으면 8.9%"],
    ["게임물", "사행성 게임의 73.5%가 '보드게임(베팅성)' 한 장르"],
    ["영상물", "등급 = 내용정보 7항목의 최고값(99.93%), 판단은 신청등급 조정 12.2%뿐"],
    ["공통", "공개 API로 볼 수 있는 것은 게임물 등급분류의 0.27%"],
]

ISSUES = [
    "등급취소 1,040건의 사유가 자료에 없어 위반과 자진 반납을 가를 수 없음",
    "매체 비교는 영상물 3점 기준에서만 성립 — 결론에 기준을 함께 적을 것",
    "남은 것은 대시보드와 최종 리포트",
]


def build():
    doc = init_doc()

    p = doc.add_paragraph()
    r = p.add_run("20260908 - 최은혜")
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
