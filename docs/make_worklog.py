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
    "집에서 받아둔 수집 결과를 사무실 저장소로 옮기고 커밋했다. "
    "게임물 29,417건, 영상물 134,464건으로 두 기관 모두 전량이다.",

    "영상물을 전량 기준으로 다시 정제했다. 9,900건만 보던 때의 판단 두 가지가 뒤집혔다.",

    "게임물 정제와 현황 파악을 새로 만들었다. "
    "내용정보가 점수가 아니라 이름 나열이라 항목별 보유 여부로 펼쳤다.",

    "두 매체를 나란히 놓고 비교했다. 이름이 같은 4개 항목으로만 비교하고, "
    "비교 대상 밖의 항목이 붙은 건은 양쪽에서 똑같이 뺐다.",

    "사업자가 스스로 매긴 등급 자료를 비교용으로 들여왔다. "
    "같은 기간으로 맞추니 공개 API로 볼 수 있는 것은 게임물 등급분류의 0.27%였다.",

    "분석 스크립트가 옛 데이터를 파일명으로 직접 가리키고 있어 걷어냈다. "
    "다시 수집하고도 예전 것을 보고 있었다.",

    "흩어져 있던 보고서 다섯 개를 하나로 합쳤다. "
    "처음에는 작업한 순서대로 썼다가, 결론이 앞에 오도록 다시 짰다.",

    "기획서(PRD)를 v1.3에서 v1.6까지 갱신하고, 강사님 회신 자료를 문서로 작성했다.",
]

FOUND = [
    ["게임물", "청소년이용불가를 만드는 것은 폭력성이 아니라 사행성이었다. "
               "사행성이 붙으면 95.3%, 없으면 8.9%다."],
    ["게임물", "사행성이 붙은 게임의 73.5%가 '보드게임(베팅성)' 한 장르였다."],
    ["영상물", "등급은 내용정보 7개 항목의 최고값과 같다(99.93%). "
               "판단이 들어가는 곳은 신청 등급을 조정하는 12.2%뿐이다."],
]

ISSUES = [
    "등급취소 1,040건의 사유가 자료에 없어 위반인지 자진 반납인지 가릴 수 없다.",
    "두 매체 비교는 영상물을 몇 점부터 '있음'으로 볼지에 따라 결과가 달라진다. "
    "3점 기준에서만 성립하므로 결론에 기준을 함께 적어야 한다.",
    "남은 것은 대시보드와 최종 리포트다.",
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
