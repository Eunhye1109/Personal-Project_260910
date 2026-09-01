# -*- coding: utf-8 -*-
"""
게임·영상물 등급분류 분석 프로젝트 PRD 생성 스크립트
- 수정 시 이 파일만 고쳐 다시 실행하면 docx가 재생성됩니다.
"""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT_DIR = r"C:\Users\User\gucc_rating_analysis\docs"
OUT_FILE = os.path.join(OUT_DIR, "PRD_게임영상물_등급분류_분석_v1.1_260901.docx")

KO_FONT = "맑은 고딕"
ACCENT = RGBColor(0x1F, 0x38, 0x64)
MUTED = RGBColor(0x59, 0x5959 >> 8 & 0xFF, 0x59)


# ---------------------------------------------------------------- 기본 설정
def set_run_font(run, name=KO_FONT, size=None, bold=None, color=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def init_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.4)
    sec.right_margin = Cm(2.4)

    normal = doc.styles["Normal"]
    normal.font.name = KO_FONT
    normal.font.size = Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), KO_FONT)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.35

    for i, sz in [(1, 15), (2, 12), (3, 10.5)]:
        st = doc.styles[f"Heading {i}"]
        st.font.name = KO_FONT
        st.font.size = Pt(sz)
        st.font.bold = True
        st.font.color.rgb = ACCENT
        st.element.rPr.rFonts.set(qn("w:eastAsia"), KO_FONT)
        st.paragraph_format.space_before = Pt(14 if i == 1 else 10)
        st.paragraph_format.space_after = Pt(6 if i == 1 else 4)
    return doc


def add_page_number_footer(doc):
    p = doc.sections[0].footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for el, attr in [("w:fldChar", ("w:fldCharType", "begin")),
                     ("w:instrText", None),
                     ("w:fldChar", ("w:fldCharType", "end"))]:
        e = OxmlElement(el)
        if el == "w:instrText":
            e.set(qn("xml:space"), "preserve")
            e.text = " PAGE "
        elif attr:
            e.set(qn(attr[0]), attr[1])
        run._element.append(e)
    set_run_font(run, size=9, color=MUTED)


# ---------------------------------------------------------------- 빌딩 블록
def h(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    for r in p.runs:
        set_run_font(r, size={1: 15, 2: 12, 3: 10.5}[level], bold=True, color=ACCENT)
    return p


def para(doc, text, bold=False, size=10, space_after=4, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    r = p.add_run(text)
    set_run_font(r, size=size, bold=bold, color=color)
    return p


def bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.6 + 0.6 * level)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    set_run_font(r, size=10)
    return p


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hex_color)
    tcPr.append(el)


def table(doc, header, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, txt in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(txt)
        c.paragraphs[0].paragraph_format.space_after = Pt(2)
        set_run_font(r, size=9.5, bold=True)
        shade(c, "DCE3EF")
    for row in rows:
        cells = t.add_row().cells
        for i, txt in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(str(txt))
            set_run_font(r, size=9.5)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def callout(doc, label, text):
    """검증 필요 / 유의사항 강조 박스 역할."""
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    shade(c, "FFF4E0")
    c.text = ""
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r1 = p.add_run(f"[{label}] ")
    set_run_font(r1, size=9.5, bold=True, color=RGBColor(0x9C, 0x5A, 0x00))
    r2 = p.add_run(text)
    set_run_font(r2, size=9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


# ---------------------------------------------------------------- 문서 본문
def build():
    os.makedirs(OUT_DIR, exist_ok=True)
    doc = init_doc()
    add_page_number_footer(doc)

    # 표지 성격의 제목
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("게임·영상물 등급분류 공공데이터 기반\n청소년 이용 부적합 콘텐츠 특성 분석 및 시각화")
    set_run_font(r, size=17, bold=True, color=ACCENT)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(14)
    r = p.add_run("제품 요구사항 정의서 (PRD)")
    set_run_font(r, size=11, color=MUTED)

    table(doc,
          ["항목", "내용"],
          [["문서 버전", "v1.1"],
           ["작성자", "최은혜"],
           ["작성일", "2026-09-01"],
           ["변경 이력", "v1.0 최초 작성 / v1.1 분석 대상을 Open API 제공 데이터로 한정, 자체등급분류 데이터 제외"],
           ["문서 상태", "초안 — 4.5절 검증 항목 확정 시 v1.2로 갱신"],
           ["프로젝트 유형", "개인 프로젝트 (데이터 분석 및 대시보드 구축)"]],
          widths=[4.0, 12.0])

    # 1
    h(doc, "1. 배경 및 문제 정의", 1)
    h(doc, "1.1 배경", 2)
    bullet(doc, "게임물관리위원회와 영상물등급위원회는 각각 등급분류 결과를 Open API로 개방하고 있으며, 등급 판정의 근거가 되는 내용정보(선정성·폭력성·공포·약물 등)를 함께 제공한다.")
    bullet(doc, "두 기관은 서로 다른 분류 체계와 용어를 사용하고 있어, 매체를 가로지르는 비교 분석이 이루어진 사례가 드물다.")
    bullet(doc, "게임 분야는 자체등급분류사업자 제도 도입 이후 분류 주체와 물량이 크게 변화하여, 단순 시계열 비교만으로는 실태 파악이 어렵다.")

    h(doc, "1.2 문제 정의", 2)
    bullet(doc, "매체별 등급분류 특성 차이를 정량적으로 정리한 자료가 부족하다.")
    bullet(doc, "어떤 내용요소 또는 그 조합이 청소년 이용 제한으로 이어지는지에 대한 데이터 기반 근거가 없다.")
    bullet(doc, "두 기관 모두 개별 건 조회는 가능하나, 조건을 바꿔가며 탐색적으로 비교할 수 있는 도구가 없다.")

    # 2
    h(doc, "2. 목표 및 성공 기준", 1)
    h(doc, "2.1 목표", 2)
    table(doc,
          ["ID", "목표"],
          [["G1", "두 기관 등급분류 데이터를 통합한 비교 가능 Dataset 구축"],
           ["G2", "청소년 이용 제한 콘텐츠에 반복적으로 나타나는 내용정보 특성 규명"],
           ["G3", "동일 내용요소가 게임과 영상물에서 등급에 미치는 영향의 차이 규명"],
           ["G4", "사용자가 조건을 직접 바꿔 탐색할 수 있는 인터랙티브 대시보드 제공"]],
          widths=[1.6, 14.4])

    h(doc, "2.2 성공 기준", 2)
    table(doc,
          ["목표", "측정 지표", "달성 기준"],
          [["G1", "통합 Dataset 구축", "게임·영상물 각 대상 기간 전량 수집, 필드별 결측률 문서화"],
           ["G1", "내용정보 매핑표 확정", "매체 공통 내용요소 4개 이상 매핑 및 근거 문서화"],
           ["G2", "등급별 내용요소 분포 산출", "4개 연령등급 × 공통 내용요소 전체에 대한 분포 제시"],
           ["G3", "매체 간 판정 차이 정량화", "동일 내용 프로필 기준 매체별 등급 분포 차이 제시"],
           ["G4", "대시보드 배포", "5개 탭 정상 동작, 공개 URL 접근 가능"],
           ["공통", "분석 리포트", "주요 인사이트 및 방법론·한계 명시"]],
          widths=[1.6, 5.0, 9.4])

    h(doc, "2.3 비목표 (Non-goals)", 2)
    bullet(doc, "등급분류 결과의 적정성 평가나 심의 기준에 대한 비판을 목적으로 하지 않는다.")
    bullet(doc, "개별 콘텐츠의 등급을 예측하는 모델을 실무에 적용하는 것을 목표로 하지 않는다. 예측 모델은 설명 도구로만 사용한다.")
    bullet(doc, "극장 개봉 영화 등 비디오물 범위를 벗어나는 영상물은 다루지 않는다.")
    bullet(doc, "실시간 자동 갱신 파이프라인은 구축하지 않는다. 특정 시점 스냅샷 기준으로 분석한다.")

    # 3
    h(doc, "3. 범위", 1)
    table(doc,
          ["구분", "내용"],
          [["포함 (In scope)",
            "두 기관 Open API 데이터 수집 · 정제 · 통합 / 연령등급 및 내용정보 EDA / "
            "청소년 이용 제한 콘텐츠 특성 분석 / Streamlit 대시보드 구현 및 배포 / 분석 리포트 작성"],
           ["제외 (Out of scope)",
            "자체등급분류 데이터 / 비디오물 외 영상물(극장 개봉작 등) / 해외 등급분류 기관 데이터 / "
            "이용자 반응·매출 등 등급분류 외 데이터 / 실시간 갱신 및 운영 자동화 / 사용자 인증 및 권한 관리"]],
          widths=[3.4, 12.6])

    # 4
    h(doc, "4. 데이터 요구사항", 1)
    h(doc, "4.1 데이터 소스", 2)
    table(doc,
          ["구분", "제공 기관", "데이터", "수집 방식"],
          [["게임물", "게임물관리위원회", "게임물 등급분류 결과", "Open API (공공데이터포털)"],
           ["영상물", "영상물등급위원회", "비디오물 등급분류 결과", "Open API (공공데이터포털)"]],
          widths=[2.2, 4.0, 5.0, 4.8])
    para(doc, "대상 기간: 2016-01-01 ~ 2025-12-31 (10년). 등급 체계 및 내용정보 항목의 일관성이 확보되는 구간을 기준으로 하며, "
              "4.5절 검증 결과에 따라 조정될 수 있다.")
    para(doc, "데이터 범위: 두 기관이 Open API로 제공하는 데이터로 한정한다. 자체등급분류 데이터는 Open API 제공 대상이 아니므로 "
              "본 프로젝트에서 다루지 않으며, 별도 수집도 수행하지 않는다. 이로 인해 발생하는 해석상의 제약은 5.5절에 기술한다.")

    h(doc, "4.2 수집 항목", 2)
    table(doc,
          ["매체", "수집 항목"],
          [["게임물", "게임물명, 결정등급, 등급분류일자, 장르, 플랫폼, 등급분류기관(제공 시 수록 범위 확인용), "
                     "내용정보 세부 항목(선정성, 폭력성, 공포, 언어의 부적절성, 약물, 범죄 및 반사회성, 사행성)"],
           ["영상물", "제명, 관람등급, 등급분류일자, 영상물 유형, "
                     "내용정보 세부 항목(주제, 선정성, 폭력성, 공포, 약물, 대사, 모방위험)"]],
          widths=[2.2, 13.8])
    callout(doc, "검증 필요",
            "게임물 내용정보 세부 항목의 명칭과 개수는 확정 전이다. 또한 두 API 모두 목록 조회 응답에 내용정보가 포함되는지, "
            "상세 조회를 별도로 호출해야 하는지가 미확인 상태이며, 후자일 경우 수집 호출량이 크게 증가한다. 4.5절 참조.")

    h(doc, "4.3 수집 요구사항", 2)
    table(doc,
          ["ID", "요구사항"],
          [["D-1", "원본 응답은 가공 없이 raw 계층에 보존하고, 모든 정제는 raw로부터 재실행 가능해야 한다."],
           ["D-2", "수집 시 요청 파라미터, 수집 일시, 응답 건수를 로그로 기록한다."],
           ["D-3", "수집 중단 시 재개 가능하도록 체크포인트를 유지한다."],
           ["D-4", "API 호출 제한을 준수하며, 요청 간격과 동시 실행 수를 설정으로 조절할 수 있어야 한다."],
           ["D-5", "수집 완료 후 연도별 건수를 대조하여 누락 구간을 점검한다."]],
          widths=[1.6, 14.4])

    h(doc, "4.4 데이터 정제·통합 규칙", 2)
    table(doc,
          ["항목", "규칙"],
          [["매체 구분", "게임물/영상물을 구분하는 변수를 생성한다."],
           ["연령등급 표준화", "전체이용가 / 12세이용가 / 15세이용가 / 청소년이용불가 4단계로 통일한다. "
                            "제한상영가는 별도 표기하되 매체 간 비교 분석에서는 제외한다."],
           ["기간 변환", "등급분류일자를 연·분기·월 단위 파생 변수로 변환한다."],
           ["내용정보 매핑", "두 기관 항목 중 비교 가능한 요소를 매핑한다. 매핑표는 코드가 아닌 별도 파일로 관리하고 "
                          "매핑 근거를 함께 기록한다."],
           ["척도 정렬", "기관별 척도 단계 수가 다를 경우 순서형 정수로 변환하며, 변환 기준을 문서에 명시한다."],
           ["중복 처리", "재분류 및 플랫폼별 중복 등록을 식별할 수 있는 키를 설계하고, 중복 정의를 문서화한다."],
           ["결측 처리", "필드별·등급분류기관별 결측률을 산출한다. 내용정보 결측 건은 분석 대상에서 제외하되 "
                        "제외 건수와 사유를 리포팅한다."]],
          widths=[3.0, 13.0])
    para(doc, "내용정보 매핑 방향 (잠정)", bold=True)
    table(doc,
          ["구분", "게임물", "영상물", "비고"],
          [["공통", "선정성", "선정성", "직접 대응"],
           ["공통", "폭력성", "폭력성", "직접 대응"],
           ["공통", "공포", "공포", "직접 대응"],
           ["공통", "약물", "약물", "직접 대응"],
           ["유사", "언어의 부적절성", "대사", "개념 범위 차이 있음, 매핑 근거 기록 필요"],
           ["유사", "범죄 및 반사회성", "주제", "대응 관계가 느슨함, 해석 시 유의"],
           ["단독", "사행성", "—", "게임물 전용, 매체 특성 분석 소재로 활용"],
           ["단독", "—", "모방위험", "영상물 전용, 매체 특성 분석 소재로 활용"]],
          widths=[1.8, 4.4, 4.4, 5.4])

    h(doc, "4.5 미검증 가정 및 검증 계획", 2)
    para(doc, "본 문서의 데이터·분석 요구사항은 아래 가정 위에 작성되었다. 착수 직후 검증 단계(0단계)를 통해 확인하며, "
              "결과에 따라 해당 절을 갱신한다.")
    table(doc,
          ["ID", "가정", "검증 방법", "미충족 시 대응"],
          [["A-1", "두 API가 내용정보를 순서형 척도로 제공한다.",
            "각 API 샘플 10건 호출 후 응답 필드 확인",
            "플래그 형태일 경우 조합 분석을 보유 여부 기준으로 축소"],
           ["A-2", "목록 조회 응답에 내용정보가 포함된다.",
            "샘플 응답 스키마 확인",
            "상세 조회 필요 시 대상 기간을 5년으로 축소"],
           ["A-3", "대상 기간(2016~2025) 전체 이력이 제공된다.",
            "API 명세 및 최초 등급분류일자 확인",
            "제공 범위에 맞춰 기간 재설정"],
           ["A-4", "일일 호출 제한 내에서 전량 수집이 가능하다.",
            "명세상 제한 및 페이징 한도 확인",
            "수집 일정을 복수일로 분할"],
           ["A-5", "게임물 Open API의 수록 범위가 특정 플랫폼에 치우치지 않는다.",
            "플랫폼·장르별 건수 분포 산출",
            "치우침 확인 시 5.5절 한계에 구체 수치를 명시하고 해석 범위를 조정"]],
          widths=[1.3, 4.6, 4.5, 5.6])

    # 5
    h(doc, "5. 분석 요구사항", 1)
    h(doc, "5.1 분석 단계", 2)
    table(doc,
          ["단계", "분석 내용"],
          [["1단계\n현황 분석",
            "전체/12세/15세/청소년이용불가 등급 구성 비교 / 게임·영상물 연령등급 분포 비교 / "
            "연도별 청소년 이용 제한 비율 변화 / 게임 장르 및 영상물 유형별 등급 차이"],
           ["2단계\n내용정보 분석",
            "청소년 이용 제한 등급에서 빈도가 높은 내용요소 탐색 / 등급별 내용정보 수준 차이 / "
            "동일 내용요소가 매체별로 등급에 미치는 영향 비교 / 복수 요소 동시 발생 콘텐츠의 등급 분포"],
           ["3단계\n부적합 특성 탐색",
            "5.4절 핵심 분석 2축을 통해 매체를 가로지르는 공통 요인과 매체별 차이를 규명"]],
          widths=[3.0, 13.0])

    h(doc, "5.2 핵심 분석 질문", 2)
    for i, q in enumerate([
        "청소년 이용 제한 등급에서 가장 많이 나타나는 내용요소는 무엇인가?",
        "게임과 영상물의 주요 유해요소에는 차이가 있는가?",
        "특정 내용요소 조합에서 청소년 이용 제한 비율이 크게 증가하는가?",
        "12세 → 15세 → 청소년이용불가로 올라갈수록 내용정보는 어떻게 변화하는가?",
        "매체가 달라도 청소년 이용 제한과 반복적으로 함께 나타나는 공통 요인이 존재하는가?",
    ], 1):
        bullet(doc, f"Q{i}. {q}")

    h(doc, "5.3 분석 설계상 유의사항", 2)
    para(doc, "본 주제는 두 가지 구조적 함정을 안고 있으며, 이를 통제하지 않으면 분석 결과가 자명한 결론에 그친다.", bold=True)
    callout(doc, "함정 1 — 순환 논리",
            "연령등급은 내용정보를 근거로 결정된다. 따라서 '폭력성이 높으면 청소년이용불가 비율이 높다'는 결과는 발견이 아니라 "
            "제도 설계의 재확인에 불과하다. 단일 내용요소와 등급의 관계를 기술하는 데 그치지 않고, 5.4절의 세 축을 통해 "
            "제도만으로 설명되지 않는 부분을 분리해야 한다.")
    callout(doc, "함정 2 — 구성 변화 효과",
            "연도별 추이는 실제 심의 경향 변화가 아니라 분모 구성 변화를 반영할 수 있다. 본 프로젝트는 자체등급분류를 "
            "제외하므로 분류 주체 변화에 따른 왜곡은 발생하지 않으나, 플랫폼·장르 구성 변화는 여전히 남는다. "
            "연도별 분석 시 분모의 플랫폼·장르 구성을 함께 제시하여 구성 변화와 경향 변화를 구분한다.")

    h(doc, "5.4 핵심 분석 2축", 2)
    para(doc, "5.3절의 순환 논리를 피하기 위해, 단일 내용요소와 등급의 관계를 기술하는 데 그치지 않고 "
              "아래 두 축을 분석의 중심에 둔다.")
    table(doc,
          ["축", "분석 내용", "기대 산출"],
          [["① 매체 간 판정 차이",
            "동일한 내용 프로필(예: 폭력성 높음, 나머지 보통)을 가진 콘텐츠의 매체별 등급 분포 비교",
            "같은 내용 수준이 매체에 따라 다른 등급으로 이어지는지에 대한 정량 근거"],
           ["② 내용요소 조합 효과",
            "단일 요소 최고값만으로 등급을 설명하는 기준선 대비, 요소 조합을 고려했을 때의 설명력 증분 측정",
            "특정 조합에서 청소년 이용 제한 비율이 비선형적으로 상승하는 구간 식별"]],
          widths=[3.2, 6.8, 6.0])

    h(doc, "5.5 분석 범위의 한계", 2)
    callout(doc, "필수 명시",
            "본 프로젝트는 Open API 제공 데이터로 한정하므로, 게임물 표본은 자체등급분류를 거친 물량을 포함하지 않는다. "
            "그 결과 게임물 표본은 국내 유통 게임물 전체가 아니라 그 부분집합이며, 플랫폼 구성이 실제 유통 구조와 다를 수 있다. "
            "따라서 5.4절 축 ①의 '게임물'은 전체 게임물이 아닌 Open API 수록 게임물로 읽어야 하며, "
            "이 조건을 대시보드와 리포트에 모두 명시한다.")
    bullet(doc, "게임물과 영상물의 모집단 정의가 서로 다르므로, 매체 간 비교 결과를 두 매체 전체의 차이로 일반화하지 않는다.")
    bullet(doc, "연도별 추이는 수록 범위 변화의 영향을 받을 수 있으므로, 절대 건수보다 등급 구성비 중심으로 해석한다.")
    bullet(doc, "4.5절 A-5 검증 결과(플랫폼·장르별 건수 분포)를 본 절에 구체 수치로 반영한다.")

    # 6
    h(doc, "6. 대시보드 기능 요구사항", 1)
    h(doc, "6.1 화면 구성", 2)
    table(doc,
          ["탭", "목적", "주요 구성 요소"],
          [["Overview", "전체 현황 파악",
            "전체 콘텐츠 수 / 게임·영상물 분포 / 연령등급 구성비 / 청소년 이용 제한 비율 / 기간별 등급 변화"],
           ["Rating\nComparison", "매체 간 등급 비교",
            "게임 vs 영상물 연령등급 비교 / 연도별 등급 분포 / 매체별 청소년 이용 제한 비율 / 장르·유형별 차이"],
           ["Content Factor", "내용요소 분포 확인",
            "내용요소별 분포 / 연령등급별 내용요소 비교 / 게임 vs 영상물 내용특성 비교"],
           ["Combination\nAnalysis", "조합 효과 확인",
            "조합별 콘텐츠 수 / 조합별 청소년 이용 제한 비율 / 주요 조합과 연령등급 관계 시각화"],
           ["Detail", "세부 데이터 탐색",
            "기간·매체·연령등급·내용요소 필터 / 조건별 원데이터 테이블 / 결과 다운로드"]],
          widths=[2.8, 3.4, 9.8])

    h(doc, "6.2 공통 필터", 2)
    bullet(doc, "기간 (연 단위 범위 선택)")
    bullet(doc, "매체 (게임물 / 영상물 / 전체)")
    bullet(doc, "연령등급 (다중 선택)")
    bullet(doc, "게임 장르 / 영상물 유형 (다중 선택)")
    bullet(doc, "내용요소 및 수준 (다중 선택)")

    h(doc, "6.3 비기능 요구사항", 2)
    table(doc,
          ["ID", "요구사항"],
          [["N-1", "필터 변경 후 화면 갱신은 3초 이내에 완료한다."],
           ["N-2", "데이터 로딩은 캐싱하여 재실행 시 재로딩이 발생하지 않도록 한다."],
           ["N-3", "모든 그래프는 Plotly 기반 인터랙티브 요소(확대, 툴팁, 범례 토글)를 제공한다."],
           ["N-4", "필터 조건에 해당하는 데이터가 없을 경우 빈 화면 대신 안내 문구를 표시한다."],
           ["N-5", "표본 수가 통계적으로 불충분한 구간은 화면상에 별도 표기한다."],
           ["N-6", "Streamlit Cloud에 배포하여 별도 설치 없이 URL로 접근 가능하도록 한다."]],
          widths=[1.6, 14.4])

    # 7
    h(doc, "7. 기술 스택 및 구조", 1)
    table(doc,
          ["구분", "기술", "용도"],
          [["데이터 수집", "Python, requests", "Open API 호출 및 원본 적재"],
           ["데이터 처리", "pandas, pyarrow", "정제·통합 및 parquet 저장"],
           ["시각화", "Plotly", "인터랙티브 그래프"],
           ["대시보드", "Streamlit", "화면 구성 및 배포"],
           ["형상 관리", "git", "코드 및 문서 이력 관리"]],
          widths=[3.2, 4.4, 8.4])
    para(doc, "데이터 흐름: Open API → raw(원본 보존) → interim(정제) → processed(통합 Dataset) → 대시보드")
    para(doc, "별도 데이터베이스는 사용하지 않는다. 정적 스냅샷 기준 분석이므로 파일 기반 저장으로 충분하며, "
              "클라우드 배포 시 접근성 측면에서도 유리하다.")

    # 8
    h(doc, "8. 산출물", 1)
    table(doc,
          ["ID", "산출물", "형태"],
          [["O-1", "게임·영상물 등급분류 통합 분석 Dataset", "parquet / csv"],
           ["O-2", "내용정보 매핑표 및 매핑 근거", "csv + 설명 문서"],
           ["O-3", "연령등급 및 내용정보 EDA 결과", "notebook / 이미지"],
           ["O-4", "청소년 이용 제한 콘텐츠 주요 특성 분석 결과", "notebook / 이미지"],
           ["O-5", "Streamlit 인터랙티브 대시보드", "공개 URL"],
           ["O-6", "주요 분석 인사이트 리포트", "문서"]],
          widths=[1.6, 8.4, 6.0])

    # 9
    h(doc, "9. 일정", 1)
    table(doc,
          ["단계", "기간", "주요 작업", "완료 기준"],
          [["0. 데이터 검증", "1일차", "API 응답 필드 확인, 4.5절 가정 검증", "가정 검증 결과 문서화"],
           ["1. 수집", "2~4일차", "수집 스크립트 개발, 전량 수집, 완결성 점검", "raw 데이터 확정"],
           ["2. 정제·통합", "5~9일차", "등급 표준화, 매핑표 작성, 중복·결측 처리", "통합 Dataset 확정"],
           ["3. 현황 EDA", "10~12일차", "등급 분포·추이·장르별 분석", "EDA 결과 정리"],
           ["4. 핵심 분석", "13~17일차", "5.4절 3축 분석", "분석 결과 정리"],
           ["5. 대시보드", "18~22일차", "5개 탭 구현 및 배포", "공개 URL 동작"],
           ["6. 리포트", "23~24일차", "인사이트 리포트 및 방법론 부록 작성", "리포트 완성"]],
          widths=[2.8, 2.0, 6.4, 4.8])
    para(doc, "2단계(정제·통합)가 전체 공수의 약 40%를 차지한다. 기관 간 항목 매핑과 중복 판정 기준 수립에 "
              "가장 많은 시간이 소요되며, 이 단계의 결과가 이후 모든 분석의 전제가 된다.")

    # 10
    h(doc, "10. 리스크 및 대응", 1)
    table(doc,
          ["ID", "리스크", "영향", "대응"],
          [["R-1", "API에 내용정보가 제공되지 않음", "높음",
            "0단계에서 최우선 확인. 미제공 시 게임물 단독 심화 분석으로 주제 조정"],
           ["R-2", "두 기관 내용정보 항목의 대응 관계가 불명확", "높음",
            "매핑표에 근거와 한계를 명시하고, 느슨한 매핑 항목은 해석 시 별도 표기"],
           ["R-3", "게임물 표본이 Open API 수록분에 한정되어 전체 유통 게임물을 대표하지 못함", "높음",
            "5.5절에 한계로 명시하고, 대시보드·리포트에 모집단 정의를 표기. 매체 간 비교 결과를 전체로 일반화하지 않음"],
           ["R-4", "API 호출 제한으로 수집 지연", "중간",
            "체크포인트 기반 분할 수집, 필요 시 대상 기간 축소"],
           ["R-5", "분석 결과가 제도 설계의 재확인에 그침", "높음",
            "5.4절 3축을 분석의 중심으로 설정 (5.3절 함정 1)"],
           ["R-6", "조합 분석 시 셀 표본 수 부족", "중간",
            "최소 표본 기준을 설정하고 미달 구간은 화면·리포트에 표기 (N-5)"]],
          widths=[1.3, 4.8, 1.6, 8.3])

    # 11
    h(doc, "11. 용어 정의", 1)
    table(doc,
          ["용어", "정의"],
          [["연령등급", "전체이용가, 12세이용가, 15세이용가, 청소년이용불가로 구분되는 이용 가능 연령 구분"],
           ["청소년 이용 제한 콘텐츠", "본 문서에서는 청소년이용불가 등급을 받은 콘텐츠를 의미"],
           ["내용정보", "등급 판정의 근거가 되는 콘텐츠 속성 항목 (선정성, 폭력성, 공포, 약물 등)"],
           ["내용 프로필", "하나의 콘텐츠가 가지는 내용정보 항목별 수준의 조합"],
           ["자체등급분류", "게임물관리위원회가 지정한 사업자가 직접 등급을 분류하는 제도. "
                          "Open API 제공 대상이 아니므로 본 프로젝트의 분석 범위에서 제외된다 (3장, 5.5절)"],
           ["통합 Dataset", "두 기관 데이터를 표준화·매핑하여 매체 간 비교가 가능하도록 구성한 최종 분석용 데이터"]],
          widths=[4.0, 12.0])

    doc.save(OUT_FILE)
    print(f"saved: {OUT_FILE}")


if __name__ == "__main__":
    build()
