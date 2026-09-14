# -*- coding: utf-8 -*-
"""
발표자료(PPTX) 생성

특강 발표용 슬라이드를 만든다. 수치는 손으로 적지 않고 outputs 의 요약 JSON 에서
읽어 온다. 원자료가 갱신되면 이 스크립트를 다시 돌리는 것으로 발표자료도 따라간다.

슬라이드마다 발표자 노트를 넣는다. 노트에는 그 장에서 무엇을 말할지, 숫자가 무엇을
뜻하는지, 질문이 나오면 어떻게 답할지를 적어 둔다. 발표자가 분석 과정을 다시 뒤지지
않고도 설명할 수 있도록 하기 위한 것이다.

같은 내용을 인쇄해서 볼 수 있도록 발표 노트를 Word 문서로도 함께 낸다.

실행
    python docs/make_ppt.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from pptx import Presentation                                      # noqa: E402
from pptx.dml.color import RGBColor                                # noqa: E402
from pptx.enum.text import PP_ALIGN                                # noqa: E402
from pptx.util import Emu, Inches, Pt                              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG = ROOT / "docs" / "figs_ppt"
# ⚠ 손으로 다듬은 발표본은 "[BI 분석가 과정] 발표자료_260914_최은혜.pptx" 이며 이 스크립트가
#   덮어쓰지 않도록 출력 파일명을 분리해 둔다. 글꼴·배색·배치를 손본 결과가 들어 있어
#   다시 만들면 그 작업이 사라진다.
DEST = ROOT / "docs" / "[BI 분석가 과정] 발표자료_260914_최은혜_자동생성본.pptx"
URL = "https://rating-analysis-260910.streamlit.app/"

# 화면·리포트와 같은 색 규칙
BLUE = "#2a78d6"      # 영상물·위원회
ORANGE = "#eb6834"    # 게임물
PURPLE = "#4a3aa7"    # 자체등급분류
INK = RGBColor(0x1F, 0x23, 0x28)
MUTED = RGBColor(0x6B, 0x72, 0x80)
ACCENT = RGBColor(0x1F, 0x38, 0x64)
LINE = RGBColor(0xE3, 0xE3, 0xE0)
FONT = "맑은 고딕"

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def load(name: str) -> dict:
    p = OUT / name
    if not p.exists():
        sys.exit(f"[중단] {p.name} 이 없습니다. 분석 스크립트를 먼저 실행하세요.")
    return json.loads(p.read_text(encoding="utf-8"))


# ───────────────────────────────────────── 그림
def fig_compose(g: dict) -> Path:
    items = list(g["결론"]["청불_항목구성"].items())
    names = [n for n, _ in items][::-1]
    vals = [v[1] * 100 for _, v in items][::-1]
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=200)
    colors = [ORANGE if n == "사행성" else "#f3c3ab" for n in names]
    ax.barh(names, vals, color=colors, height=0.62)
    for y, v in enumerate(vals):
        ax.text(v + 1.5, y, f"{v:.1f}%", va="center", fontsize=10, color="#4a423a")
    ax.set_xlim(0, 90)
    ax.set_xlabel("청소년이용불가 게임물 중 해당 항목을 보유한 비율", fontsize=9, color="#6e655b")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=10)
    ax.tick_params(axis="x", labelsize=9, colors="#6e655b")
    fig.tight_layout()
    p = FIG / "compose.png"
    fig.savefig(p, transparent=False, facecolor="white")
    plt.close(fig)
    return p


def fig_solo(y: dict) -> Path:
    d = y["항목별"]["게임물(위원회)"]
    order = ["사행성", "선정성", "약물", "언어", "폭력성", "범죄", "공포", "(없음)"]
    names = [n for n in order if n in d]
    vals = [d[n]["청불률"] * 100 for n in names]
    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=200)
    colors = [ORANGE if n == "사행성" else "#f3c3ab" for n in names]
    bars = ax.bar(names, vals, color=colors, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.1f}%",
                ha="center", fontsize=9.5, color="#4a423a")
    ax.set_ylim(0, 110)
    ax.set_ylabel("청소년이용불가 비율", fontsize=9, color="#6e655b")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=10)
    fig.tight_layout()
    p = FIG / "solo.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    return p


def fig_combo(y: dict) -> Path:
    rows = [(k, v["게임물"] * 100, v["영상물"] * 100) for k, v in y["조합"].items()]
    rows.sort(key=lambda r: -r[1])
    names = [r[0] for r in rows][::-1]
    game = [r[1] for r in rows][::-1]
    video = [r[2] for r in rows][::-1]
    ypos = range(len(names))
    fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
    h = 0.38
    ax.barh([y0 + h / 2 for y0 in ypos], game, height=h, color=ORANGE, label="게임물")
    ax.barh([y0 - h / 2 for y0 in ypos], video, height=h, color=BLUE, label="영상물")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(names, fontsize=9.5)
    ax.set_xlabel("청소년 이용 제한 비율", fontsize=9, color="#6e655b")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=9, colors="#6e655b")
    ax.legend(fontsize=9, frameon=False, loc="lower right")
    fig.tight_layout()
    p = FIG / "combo.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    return p


def fig_share(r: dict) -> Path:
    a, s = r["규모"]["위원회_같은기간"], r["규모"]["자체등급분류"]
    total = a + s
    fig, ax = plt.subplots(figsize=(7.6, 1.05), dpi=200)
    ax.barh([0], [s / total * 100], color=PURPLE, height=0.42)
    ax.barh([0], [a / total * 100], left=[s / total * 100], color=ORANGE, height=0.42)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, 0.8)
    ax.axis("off")
    ax.text(50, 0, f"사업자 자체등급분류 {s:,}건 ({s / total * 100:.2f}%)",
            ha="center", va="center", color="white", fontsize=11)
    ax.text(100, 0.4, f"위원회 심의 {a:,}건 ({a / total * 100:.2f}%)",
            ha="right", va="bottom", color=ORANGE, fontsize=10.5)
    fig.tight_layout()
    p = FIG / "share.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    return p


# ───────────────────────────────────────── 슬라이드 부품
BLANK = 6


def txbox(slide, x, y, w, h, text, size=16, bold=False, color=INK,
          align=PP_ALIGN.LEFT, space=6, line=1.25):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    for i, part in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        p.line_spacing = line
        run = p.add_run()
        run.text = part
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = FONT
    return box


def bar(slide, y=1.12, w=12.33, x=0.5, color=ACCENT, h=0.035):
    shp = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def new(prs, title=None, eyebrow=None):
    s = prs.slides.add_slide(prs.slide_layouts[BLANK])
    if eyebrow:
        txbox(s, 0.5, 0.34, 6, 0.3, eyebrow, size=11, color=MUTED)
    if title:
        txbox(s, 0.5, 0.58, 12.3, 0.55, title, size=26, bold=True, color=ACCENT)
        bar(s)
    return s


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def table(slide, x, y, w, rows, col_w=None, size=11, head=True, row_h=0.32):
    nr, nc = len(rows), len(rows[0])
    shp = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w),
                                 Inches(row_h * nr)).table
    if col_w:
        total = sum(col_w)
        for i, cw in enumerate(col_w):
            shp.columns[i].width = Emu(int(Inches(w) * cw / total))
    shp.first_row = False
    shp.horz_banding = False
    for i, row in enumerate(rows):
        shp.rows[i].height = Inches(0.42 if (head and i == 0) else row_h)
        for j, val in enumerate(row):
            cell = shp.cell(i, j)
            cell.text = str(val)
            cell.margin_left, cell.margin_right = Inches(0.1), Inches(0.1)
            cell.margin_top, cell.margin_bottom = Inches(0.05), Inches(0.05)
            cell.fill.solid()
            cell.fill.fore_color.rgb = (RGBColor(0xEE, 0xF1, 0xF6) if (head and i == 0)
                                        else RGBColor(0xFF, 0xFF, 0xFF) if i % 2
                                        else RGBColor(0xFA, 0xFA, 0xF8))
            for para in cell.text_frame.paragraphs:
                para.alignment = PP_ALIGN.LEFT
                para.line_spacing = 1.2
                for run in para.runs:
                    run.font.size = Pt(size)
                    run.font.name = FONT
                    run.font.bold = bool(head and i == 0)
                    run.font.color.rgb = ACCENT if (head and i == 0) else INK
    return shp


def big(slide, x, y, value, label, color=ACCENT, size=54):
    txbox(slide, x, y, 4.4, 1.0, value, size=size, bold=True, color=color)
    txbox(slide, x, y + 1.08, 4.4, 0.9, label, size=12, color=MUTED, line=1.35)


def pic(slide, path, x, y, w):
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w))


def write_notes_doc(prs) -> Path:
    """슬라이드 제목과 발표자 노트를 인쇄용 문서로 옮긴다."""
    import docx
    from docx.shared import Pt as DocPt, RGBColor as DocColor

    doc = docx.Document()
    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = DocPt(10.5)

    head = doc.add_paragraph()
    run = head.add_run("발표 노트")
    run.font.size = DocPt(20)
    run.font.bold = True
    run.font.color.rgb = DocColor(0x1F, 0x38, 0x64)
    sub = doc.add_paragraph()
    run = sub.add_run("게임·영상물 등급분류 공공데이터 분석 · BI 분석가 과정 개인 프로젝트 · 최은혜")
    run.font.size = DocPt(10)
    run.font.color.rgb = DocColor(0x6B, 0x72, 0x80)
    note = doc.add_paragraph()
    run = note.add_run("슬라이드별로 무엇을 말할지, 숫자가 무엇을 뜻하는지, 질문이 나오면 "
                       "어떻게 답할지를 적었다. 같은 내용이 PPT 의 발표자 노트에도 들어 있다.")
    run.font.size = DocPt(10)

    for i, slide in enumerate(prs.slides, 1):
        title = ""
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                for para in shape.text_frame.paragraphs:
                    for r in para.runs:
                        if r.font.size and r.font.size >= DocPt(24) and not title:
                            title = r.text.strip()
                if title:
                    break
        p = doc.add_paragraph()
        p.paragraph_format.space_before = DocPt(16)
        run = p.add_run(f"{i}. {title or '(제목 없음)'}")
        run.font.size = DocPt(13)
        run.font.bold = True
        run.font.color.rgb = DocColor(0x1F, 0x38, 0x64)
        body = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
        for line in (body or "(노트 없음)").split("\n"):
            q = doc.add_paragraph()
            q.paragraph_format.space_after = DocPt(3)
            q.add_run(line)

    p = ROOT / "docs" / "[BI 분석가 과정] 발표노트_260914_최은혜.docx"
    doc.save(p)
    return p


# ───────────────────────────────────────── 본문
def build() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    g = load("eda_grac_summary.json")
    y = load("youth_summary.json")
    r = load("compare_rater_summary.json")
    it = load("integrated_dataset_summary.json")

    f_compose, f_solo, f_combo, f_share = (
        fig_compose(g), fig_solo(y), fig_combo(y), fig_share(r))

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    # 1 표지
    s = prs.slides.add_slide(prs.slide_layouts[BLANK])
    bar(s, y=2.55, x=0.9, w=1.6, h=0.06)
    txbox(s, 0.9, 1.55, 11, 0.5, "BI 분석가 과정 개인 프로젝트", size=13, color=MUTED)
    txbox(s, 0.9, 2.85, 11.5, 1.6,
          "청소년 이용 제한 등급은\n무엇을 기준으로 결정되는가", size=40, bold=True, color=ACCENT)
    txbox(s, 0.9, 4.75, 11.5, 0.9,
          "게임물·영상물 등급분류 공공데이터 240,290건 전량 분석", size=17, color=INK)
    txbox(s, 0.9, 6.2, 11.5, 0.5, "2026. 09. 14.   최은혜", size=13, color=MUTED)
    notes(s, "인사와 주제 한 줄 소개.\n\n"
             "말할 것: 게임물과 영상물의 등급분류 결과를 각 기관 공개 API 로 전량 받아, "
             "청소년 이용을 제한하는 등급이 무엇으로 결정되는지 확인한 프로젝트다. "
             "두 매체를 같은 표에 놓고 비교한 자료가 드물어서 이 주제를 골랐다.\n\n"
             "발표 시간은 10~15분, 마지막에 대시보드를 직접 열어 보여 주는 순서로 진행한다고 예고하면 좋다.")

    # 2 목차
    s = new(prs, "발표 순서")
    table(s, 0.6, 1.6, 12.1, [
        ["순서", "내용", "핵심 숫자"],
        ["1. 주제와 데이터", "왜 이 주제인가 · 무엇을 얼마나 모았는가", "240,290건"],
        ["2. 결론 1 · 게임물", "청소년이용불가를 만드는 것은 사행성이다", "76.3%"],
        ["3. 결론 2 · 공개 범위", "위원회 심의는 전체의 일부다", "0.27%"],
        ["4. 결론 3 · 영상물", "등급은 내용정보의 최고값과 같다", "99.93%"],
        ["5. 매체 비교", "같은 조건에서 게임물이 더 엄격하다", "+15.1%p"],
        ["6. 산출물", "데이터셋·EDA·특성 분석·대시보드·리포트", "5종"],
        ["7. 한계와 배운 것", "무엇을 못 했고 어떤 결론을 폐기했는가", "2건 폐기"],
    ], col_w=[2.4, 6.4, 2.2], row_h=0.46, size=13)
    notes(s, "순서만 짧게 읽고 넘어간다. 30초를 넘기지 않는다.\n\n"
             "강조할 점: 결론이 세 가지이고, 각 결론마다 근거 수치를 하나씩 들고 왔다는 것.")

    # 3 주제
    s = new(prs, "왜 이 주제인가", "1. 주제와 데이터")
    txbox(s, 0.6, 1.55, 12.1, 1.2,
          "게임물과 영상물은 각각 다른 기관이 등급을 매기고, 그 결과를 공개한다.\n"
          "그런데 두 자료를 한 표에 놓고 비교한 분석은 찾기 어렵다.", size=16)
    table(s, 0.6, 3.0, 12.1, [
        ["분석 질문", "확인 방법"],
        ["청소년 이용을 제한하는 등급은 무엇을 근거로 결정되는가",
         "등급과 내용정보 7개 항목의 대응 관계를 전량 교차 확인"],
        ["매체에 따라 판정이 달라지는가",
         "명칭이 같은 4개 항목만 남겨 동일 조건에서 비교"],
        ["공개된 데이터로 '게임물 전체'를 말할 수 있는가",
         "위원회 심의분과 사업자 자체등급분류 물량을 같은 기간으로 비교"],
    ], col_w=[5.5, 6.6], row_h=0.55, size=13)
    txbox(s, 0.6, 5.6, 12.1, 0.8,
          "통상 게임물 규제의 이유로는 폭력성과 선정성이 언급된다. 데이터의 답은 달랐다.",
          size=15, bold=True, color=ACCENT)
    notes(s, "말할 것: 세 가지 질문으로 시작했다. 특히 두 번째 질문(매체 비교)은 강사 피드백에서 "
             "나온 요구였다.\n\n"
             "마지막 줄이 이 발표의 예고편이다. 여기서 한 박자 쉬고 다음 장으로 넘어가면 좋다.\n\n"
             "질문 대비: '왜 이 주제냐'고 물으면, 등급분류 데이터는 공개돼 있는데 매체를 가로지르는 "
             "비교가 없었고, 두 기관이 항목 이름을 비슷하게 쓰고 있어 비교 가능성이 있어 보였다고 답한다.")

    # 4 데이터
    s = new(prs, "무엇을 얼마나 모았는가", "1. 주제와 데이터")
    table(s, 0.6, 1.6, 12.1, [
        ["구분", "출처", "건수", "기간", "역할"],
        ["영상물", "영상물등급위원회 Open API", f"{it['영상물']:,}건", "2009~2026", "분석 대상"],
        ["게임물(위원회)", "게임물관리위원회 Open API", f"{it['게임물_위원회']:,}건", "2007~2026", "분석 대상"],
        ["게임물(자체등급분류)", "별도 업무에서 확보한 파일", f"{it['게임물_자체']:,}건", "2026-07~08", "비교군"],
        ["통합 분석 Dataset", "위 셋을 한 표로 통합", f"{it['행']:,}행 × {it['열']}열", it["기간"], "산출물 ①"],
    ], col_w=[2.6, 4.0, 1.9, 1.9, 1.7], row_h=0.5, size=12.5)
    txbox(s, 0.6, 4.4, 12.1, 0.4, "수집 과정에서 막혔던 두 가지", size=15, bold=True, color=ACCENT)
    txbox(s, 0.6, 4.9, 12.1, 1.6,
          "· 영상물: 약 99,000건 지점부터 조회가 거부되었다. 페이지 대신 기간을 나눠 요청하는 "
          "방식으로 바꿔 전량을 받았다.\n"
          "· 게임물: 사무실 회선에서 기관 서버에 접속되지 않아 집에서 수집하였다. "
          "순차 호출·요청 상한 등 안전장치를 걸고 월 단위로 나눠 받았다.\n"
          "· 두 매체 모두 기관이 제공하는 총 건수와 수집 건수가 정확히 일치한다.", size=14)
    notes(s, "말할 것: 표본이 아니라 전량이다. 기관이 알려주는 총 건수와 정확히 맞는 것을 확인했다.\n\n"
             "자체등급분류 76,409건은 이 프로젝트에서 수집한 것이 아니라 다른 일을 하다 확보해 둔 "
             "파일이고, 약 7주치가 전부여서 추세 분석에는 쓰지 않고 규모 비교에만 썼다.\n\n"
             "질문 대비: '왜 집에서 수집했나' → 사무실 회선에서 해당 기관 서버로 접속이 되지 않았다. "
             "인증키 문제가 아니라 회선 문제였고, 집에서는 정상 수집되었다.")

    # 5 통합 규칙
    s = new(prs, "두 기관의 자료를 어떻게 한 표로 합쳤는가", "1. 주제와 데이터")
    table(s, 0.6, 1.6, 12.1, [
        ["", "영상물", "게임물"],
        ["내용정보 제공 형태", "항목마다 1~5단계 수준", "해당 항목의 이름만 나열"],
        ["항목 구성", "주제·선정성·폭력성·대사·공포·약물·모방위험",
         "선정성·폭력성·공포·약물·언어·범죄·사행성"],
        ["통합한 항목", "선정성·폭력성·공포·약물 4개만 (명칭이 동일)", "좌동"],
        ["통합하지 않은 항목", "주제·대사·모방위험", "언어·범죄·사행성"],
    ], col_w=[2.8, 4.8, 4.5], row_h=0.55, size=12.5)
    txbox(s, 0.6, 4.7, 12.1, 1.8,
          "· 명칭이 같은 4개만 같은 칸에 넣었다. 대사와 언어처럼 비슷해 보이는 항목도 재는 대상이 "
          "달라 합치지 않았다. 합치면 없는 값을 만들어 내는 셈이 된다.\n"
          "· 영상물의 1~5단계는 3단계 이상을 '보유'로 보아 게임물의 보유·미보유 체계에 맞췄다. "
          "원래 단계값도 함께 보관해 두었다.\n"
          f"· 비교에 쓸 수 있는 건은 {it['비교표본']:,}건이다. 제외 대상은 지우지 않고 표시만 해 두었다.",
          size=13.5)
    notes(s, "이 장이 분석의 전제다. 천천히 설명한다.\n\n"
             "말할 것: 두 기관이 내용정보를 주는 방식이 아예 다르다. 영상물은 항목마다 점수가 있고, "
             "게임물은 해당하는 항목 이름만 나열한다. 그래서 그대로는 비교가 안 된다.\n\n"
             "핵심은 '이름이 같은 4개만 합쳤다'는 것. 대사와 언어는 이름이 비슷하지만 재는 대상이 "
             "달라서 합치지 않았다. 이건 강사 피드백에서 지적받은 부분이기도 하다.\n\n"
             "질문 대비: '왜 3단계에서 잘랐나' → 4단계로 자르면 영상물은 4단계가 곧 청소년관람불가라 "
             "정의상 100%가 나와 비교가 성립하지 않는다. 3단계라는 선택 자체에 근거가 있는 것은 "
             "아니며, 이 한계는 뒤에서 다시 말한다.")

    # 6 결론 요약
    s = new(prs, "결론 세 가지")
    rows = [
        ("결론 1", "게임물의 청소년이용불가를 결정하는 것은\n폭력성이나 선정성이 아니라 사행성이다",
         f"{g['결론']['청불_항목구성']['사행성'][1] * 100:.1f}%", "청소년이용불가 게임물 중\n사행성 보유 비율"),
        ("결론 2", "그런데 위원회 심의 대상은\n게임물 등급분류 전체의 일부에 불과하다",
         f"{r['규모']['위원회_같은기간'] / (r['규모']['위원회_같은기간'] + r['규모']['자체등급분류']) * 100:.2f}%",
         "같은 기간 위원회 심의가\n차지하는 비중"),
        ("결론 3", "영상물의 등급은 내용정보 7개 항목의\n최고값과 사실상 동일하다",
         "99.93%", "최고값과 결정등급이\n일치하는 비율"),
    ]
    for i, (tag, text, num, cap) in enumerate(rows):
        top = 1.6 + i * 1.85
        txbox(s, 0.6, top, 1.1, 0.4, tag, size=12, bold=True, color=ACCENT)
        txbox(s, 1.8, top - 0.06, 6.6, 1.2, text, size=15.5, bold=True)
        txbox(s, 8.7, top - 0.18, 2.2, 0.8, num, size=30, bold=True, color=ACCENT)
        txbox(s, 11.0, top - 0.02, 2.0, 1.0, cap, size=10.5, color=MUTED)
    notes(s, "발표의 뼈대. 이 장에서 세 문장을 또박또박 말하고, 뒤 장에서 하나씩 근거를 댄다.\n\n"
             "세 결론이 이어지는 순서가 중요하다. 1번은 '게임 규제의 실체가 무엇이냐', "
             "2번은 '그런데 그 이야기가 게임물 전체에 해당하느냐', 3번은 '영상물은 아예 구조가 "
             "다르다' 로 이어진다.\n\n"
             "청중이 한 문장만 기억한다면 결론 1이다.")

    # 7 결론 1
    s = new(prs, "청소년이용불가 게임물은 무엇을 갖고 있었는가", "2. 결론 1 · 게임물")
    pic(s, f_compose, 0.7, 1.55, 7.4)
    yr = g["결론"]
    txbox(s, 8.5, 1.7, 4.4, 3.4,
          f"청소년이용불가 게임물 {yr['청불건수']:,}건 중\n"
          f"{yr['청불_항목구성']['사행성'][1] * 100:.1f}%가 사행성을 보유한다.\n\n"
          f"폭력성 {yr['청불_항목구성']['폭력성'][1] * 100:.1f}%,\n"
          f"선정성 {yr['청불_항목구성']['선정성'][1] * 100:.1f}%와\n"
          "차이가 크다.\n\n"
          "한 건이 여러 항목을 보유할 수 있어\n합계는 100%를 넘는다.", size=14)
    txbox(s, 0.7, 5.6, 12.0, 0.9,
          f"사행성 보유 게임물의 청소년이용불가 비율 {yr['사행성있음'][1] * 100:.1f}%   ·   "
          f"미보유 시 {yr['사행성없음'][1] * 100:.1f}%", size=16, bold=True, color=ACCENT)
    notes(s, "말할 것: 청소년이용불가를 받은 게임물이 실제로 어떤 항목을 갖고 있었는지 센 것이다. "
             "약 4분의 3이 사행성을 갖고 있다.\n\n"
             "아래 줄이 더 중요하다. 사행성이 붙으면 95.3%가 청소년이용불가이고, 없으면 8.9%다. "
             "다른 어떤 항목에서도 이만한 차이가 나지 않는다.\n\n"
             "용어 설명이 필요하면: 사행성은 도박성, 즉 베팅 요소를 말한다. 웹보드 게임(고스톱·포커류)이 "
             "여기 해당한다.")

    # 8 결론 1 보조
    s = new(prs, "항목을 하나만 가진 건으로 좁혀도 같다", "2. 결론 1 · 게임물")
    pic(s, f_solo, 0.7, 1.5, 7.6)
    d = y["항목별"]["게임물(위원회)"]
    txbox(s, 8.6, 1.7, 4.3, 3.6,
          "다른 항목이 섞이지 않은 건만\n모아 비교한 것이다.\n\n"
          f"사행성 단독 {d['사행성']['청불률'] * 100:.1f}%\n"
          f"선정성 단독 {d['선정성']['청불률'] * 100:.1f}%\n"
          f"폭력성 단독 {d['폭력성']['청불률'] * 100:.1f}%\n\n"
          "같은 '항목 하나'인데 결과가\n전혀 다르다.", size=14)
    txbox(s, 0.7, 5.5, 12.0, 1.1,
          "게임물은 수준이라는 개념 없이 어떤 항목이 붙었는지로 등급이 갈린다.\n"
          f"내용정보가 비어 있는 {d['(없음)']['건수']:,}건의 청소년이용불가 비율은 "
          f"{d['(없음)']['청불률'] * 100:.2f}%로, 미기재가 아니라 '해당 요소 없음'으로 볼 수 있다.",
          size=13.5)
    notes(s, "말할 것: 앞 장은 '청불 게임이 무엇을 갖고 있었나'였고, 이 장은 반대 방향이다. "
             "'그 항목 하나만 가진 게임은 어떤 등급을 받았나'를 본 것이다.\n\n"
             "사행성만 붙으면 97.1%가 청소년이용불가인데, 폭력성만 붙은 게임은 11.1%뿐이다. "
             "열 개 중 아홉은 청소년도 이용할 수 있다는 뜻이다.\n\n"
             "아래 문장은 데이터 품질 이야기다. 내용정보 칸이 빈 게 절반 가까이 되는데, 그 건들의 "
             "청불률이 0.06%라서 '기록을 안 한 것'이 아니라 '해당 요소가 없는 것'으로 판단했다.")

    # 9 결론 2
    s = new(prs, "그런데 이 이야기는 게임물 전체가 아니다", "3. 결론 2 · 공개 범위")
    share = r["규모"]["위원회_같은기간"] / (r["규모"]["위원회_같은기간"] + r["규모"]["자체등급분류"]) * 100
    big(s, 0.7, 1.55, f"{share:.2f}%", "같은 기간 전체 등급분류 중\n위원회 심의가 차지하는 비중", size=60)
    table(s, 5.4, 1.7, 7.3, [
        ["구분", "건수", "청소년이용불가"],
        [f"위원회 심의 ({r['규모']['기간']})", f"{r['규모']['위원회_같은기간']:,}건",
         f"{y['규모']['게임물 · 위원회분류']['비율'] * 100:.1f}% (전 기간)"],
        ["사업자 자체등급분류 (같은 기간)", f"{r['규모']['자체등급분류']:,}건",
         f"{y['규모']['게임물 · 자체등급분류']['비율'] * 100:.2f}%"],
        ["차이", f"약 {r['규모']['배수']:.0f}배", ""],
    ], col_w=[3.6, 1.9, 1.8], row_h=0.55, size=12.5)
    pic(s, f_share, 0.7, 4.6, 11.6)
    txbox(s, 0.7, 6.3, 12.0, 0.9,
          "19년간의 위원회 분류 건수보다 7주간의 자체등급분류 건수가 더 많다. "
          "다만 두 경로에 들어오는 게임물의 성격이 달라 심의 엄격도의 차이로 해석해서는 안 된다.",
          size=13.5)
    notes(s, "말할 것: 결론 1은 위원회가 직접 심의한 게임물 이야기다. 그런데 게임물 등급분류는 "
             "두 경로로 이뤄진다. 위원회 심의와, 구글·애플 같은 사업자의 자체등급분류다.\n\n"
             "같은 기간으로 맞춰 보니 위원회 207건 대 자체등급분류 76,409건, 약 369배 차이였다. "
             "공개 API 로 볼 수 있는 건 전체의 0.27%뿐이다.\n\n"
             "중요: 이 차이를 '사업자가 느슨하다'로 읽으면 안 된다. 자체등급분류에는 사행성 게임이 "
             "거의 없다(0.05% 대 23.2%). 애초에 들어오는 게임이 다르다.\n\n"
             "질문 대비: '그럼 결론 1은 의미가 없나' → 아니다. 다만 '위원회가 직접 심의한 게임물'이라는 "
             "조건을 반드시 붙여야 한다는 뜻이고, 그 조건을 대시보드와 리포트에 모두 적어 두었다.")

    # 10 결론 3
    s = new(prs, "영상물은 등급 결정 구조가 아예 다르다", "4. 결론 3 · 영상물")
    txbox(s, 0.6, 1.55, 12.1, 0.9,
          "영상물은 내용정보 7개 항목에 각각 1~5단계를 부여한다. "
          "그 최고값을 그대로 등급에 대응시켜 보았다.", size=15)
    table(s, 0.6, 2.6, 7.6, [
        ["내용정보 최고값", "대응하는 관람등급"],
        ["1단계", "전체관람가"],
        ["2단계", "12세이상관람가"],
        ["3단계", "15세이상관람가"],
        ["4단계", "청소년관람불가"],
        ["5단계", "제한관람가"],
    ], col_w=[3.4, 4.2], row_h=0.42, size=12.5)
    big(s, 8.6, 2.5, "99.93%", "134,462건 중 134,364건이\n이 규칙에 부합한다", size=44)
    txbox(s, 8.6, 4.5, 4.3, 1.2,
          "표기 체계가 바뀐 2017년 5월 이후\n94,516건에서는 예외가 0건이다.", size=13, color=INK)
    txbox(s, 0.6, 5.9, 12.1, 1.0,
          "등급은 산정된 값이 아니라 최고값을 옮겨 적은 값이다. "
          "따라서 내용정보로 등급을 설명하는 분석은 성립하지 않는다. 같은 값을 두 번 쓰는 것이기 때문이다.",
          size=14.5, bold=True, color=ACCENT)
    notes(s, "말할 것: 영상물은 항목마다 점수가 있으니, 그 점수와 등급의 관계를 보는 게 자연스러운 "
             "분석이다. 그런데 해 보니 관계가 아니라 항등식이었다.\n\n"
             "가장 높은 점수가 1단계면 전부 전체관람가, 2단계면 전부 12세다. 99.93%가 그렇고, "
             "표기 방식이 바뀐 2017년 5월 이후로는 예외가 하나도 없다.\n\n"
             "이 발견의 의미: 원래 하려던 분석(내용정보로 등급 설명)이 무의미해졌다. 실제로 회귀분석을 "
             "돌렸더니 AUC 가 1.000 이 나왔는데, 모형이 좋아서가 아니라 정답을 미리 알려준 것이었다. "
             "이걸 확인하고 분석 방향을 바꿨다.\n\n"
             "AUC 설명이 필요하면: 1에 가까울수록 완벽히 맞힌다는 뜻이고, 1.000 은 현실 데이터에서 "
             "나올 수 없는 값이라 의심해야 한다고 말한다.")

    # 11 결론 3 보조
    s = new(prs, "판단이 개입하는 유일한 영역", "4. 결론 3 · 영상물")
    big(s, 0.7, 1.7, "12.2%", "신청등급과 결정등급이\n달라진 비율", size=52)
    txbox(s, 5.2, 1.7, 7.5, 2.6,
          "· 상향 8.6% · 하향 3.6%\n"
          "· 신청등급은 신청인이 스스로 판단해 적어 낸 값이므로 결정등급과 같은 값이 아니다.\n"
          "· 12세로 신청한 건의 28.2%가 상향 조정되었다. 신청인이 등급을 가장 낮게 예측하는 구간이다.\n"
          "· 반대로 청소년관람불가로 신청하면 더 올라갈 여지가 없어 조정이 드물다.", size=14)
    txbox(s, 0.7, 4.8, 12.0, 1.3,
          "내용정보와 결정등급은 같은 값이라 서로를 설명하지 못한다.\n"
          "이 12.2% 구간이 자료에서 심의 판단을 확인할 수 있는 유일한 영역이다.",
          size=15, bold=True, color=ACCENT)
    notes(s, "말할 것: 앞 장에서 등급은 옮겨 적은 값이라고 했다. 그러면 이 자료에서 사람의 판단은 "
             "어디에 남아 있나. 신청등급이다.\n\n"
             "신청인이 스스로 매긴 등급과 위원회가 결정한 등급이 갈리는 지점, 그게 12.2%다. "
             "여기만 내용정보로 설명되지 않는다.\n\n"
             "질문 대비: '상향률을 모형으로 설명해 봤나' → 내용정보와 종별·연도로 상향 여부를 "
             "예측하면 AUC 0.825 가 나온다. 신청등급 자체는 변수로 넣지 않았다. 넣으면 다시 "
             "항등식이 되기 때문이다.")

    # 12 매체 비교
    s = new(prs, "같은 조건에서 비교하면 게임물이 더 엄격하다", "5. 매체 비교")
    pic(s, f_combo, 0.6, 1.45, 7.3)
    txbox(s, 8.7, 1.6, 4.2, 3.8,
          "명칭이 같은 4개 항목의 보유 조합이\n완전히 같은 건끼리 비교하였다.\n\n"
          f"비교 가능한 {len(y['조합'])}개 조합 전부에서\n게임물의 제한 비율이 높다.\n\n"
          f"평균 차이 +{y['조합_평균차이'] * 100:.1f}%p", size=14)
    txbox(s, 0.6, 5.8, 12.2, 1.5,
          "한계: 영상물의 5단계를 게임물의 보유·미보유에 맞추려면 어딘가에서 잘라야 하는데, "
          "그 지점은 데이터로 정해지지 않는다. 3단계로 자르면 위와 같고, 4단계로 자르면 영상물이 "
          "정의상 100%가 되어 비교 자체가 성립하지 않는다.\n"
          "따라서 '게임물이 더 엄격하다'는 문장은 절단 기준을 함께 적어야만 쓸 수 있다.",
          size=13.5)
    notes(s, "말할 것: 강사 피드백의 핵심 요구가 '같은 내용 수준에서 매체 간 차이를 보라'는 것이었다. "
             "이 장이 그 답이다.\n\n"
             "보유 조합이 완전히 같은 건끼리만 비교했다. 예를 들어 '선정성만 있는 건'끼리, "
             "'폭력성과 공포가 있는 건'끼리 비교한 것이다. 비교 가능한 10개 조합 전부에서 게임물이 "
             "더 높았고 평균 15.1%p 차이였다.\n\n"
             "한계를 반드시 같이 말한다. 이 결론은 '3단계 이상을 보유로 본다'는 기준 위에서만 "
             "성립한다. 발표에서 이 단서를 빼면 과장이 된다.\n\n"
             "질문 대비: '왜 사행성은 비교에서 뺐나' → 영상물에 대응 항목이 없어서다. 넣으면 "
             "사행성 때문에 청불이 된 게임이 '항목 없음' 칸에 섞여 결과가 뒤집힌다. 영상물 쪽도 "
             "대칭으로 주제·대사·모방위험을 뺐다.")

    # 13 청소년 이용 제한 특성
    s = new(prs, "청소년 이용 제한 콘텐츠의 특성", "5. 매체 비교")
    reg = y["규모"]
    table(s, 0.6, 1.6, 12.1, [
        ["구분", "건수", "제한 건수", "비율"],
        ["게임물 · 위원회 심의", f"{reg['게임물 · 위원회분류']['건수']:,}",
         f"{reg['게임물 · 위원회분류']['제한']:,}", f"{reg['게임물 · 위원회분류']['비율'] * 100:.1f}%"],
        ["게임물 · 자체등급분류", f"{reg['게임물 · 자체등급분류']['건수']:,}",
         f"{reg['게임물 · 자체등급분류']['제한']:,}", f"{reg['게임물 · 자체등급분류']['비율'] * 100:.2f}%"],
        ["영상물 · 전체", f"{reg['영상물 · 전체']['건수']:,}",
         f"{reg['영상물 · 전체']['제한']:,}", f"{reg['영상물 · 전체']['비율'] * 100:.1f}%"],
        ["영상물 · 성인물 제외", f"{reg['영상물 · 성인물 제외']['건수']:,}",
         f"{reg['영상물 · 성인물 제외']['제한']:,}", f"{reg['영상물 · 성인물 제외']['비율'] * 100:.1f}%"],
    ], col_w=[4.6, 2.6, 2.6, 2.3], row_h=0.5, size=13)
    txbox(s, 0.6, 4.5, 12.1, 2.0,
          "· 영상물의 43.7%는 성인물에 기인한다. 성인물은 내용정보와 무관하게 사실상 전건이 "
          "청소년관람불가여서, 제외하면 10.7%로 낮아진다. 종별을 통제하지 않으면 결론이 뒤집힌다.\n"
          "· 게임물에서 청소년 이용 제한이 가장 많은 장르는 보드게임(베팅성)으로 99.7%이며, "
          "플랫폼에서는 온라인 게임이 74.9%로 가장 높다. 둘 다 웹보드 게임이 몰려 있는 영역이다.\n"
          "· 자체등급분류의 청소년이용불가 83건은 제도상 사업자가 부여할 수 없는 등급이므로, "
          "사후에 등급이 조정된 결과로 해석하였다.", size=13.5)
    notes(s, "말할 것: 세 결론 밖에서 따로 정리한 분석이다. 청소년 이용 제한 콘텐츠만 떼어 규모·추이·"
             "분포·항목·조합을 본 것이고, 산출물 ③번에 해당한다.\n\n"
             "가장 조심해야 할 숫자가 영상물 43.7%다. 이건 성인물이 만든 숫자여서 그대로 인용하면 "
             "오해를 부른다. 성인물을 빼면 10.7%다.\n\n"
             "질문 대비: '자체등급분류 83건은 뭐냐' → 사업자는 청소년이용불가 게임물을 자체분류할 수 "
             "없다. 그런데 83건이 남아 있다는 건 이 데이터가 '분류 시점의 등급'이 아니라 '현재 등급'을 "
             "보여준다는 뜻이다. 사후 조정의 흔적으로 읽었다.")

    # 14 산출물
    s = new(prs, "산출물 5종", "6. 산출물")
    table(s, 0.6, 1.55, 12.1, [
        ["산출물", "형태", "내용"],
        ["① 통합 분석 Dataset", "parquet · csv", f"게임물·영상물 {it['행']:,}행 × {it['열']}열, 데이터 사전 포함"],
        ["② 연령등급·내용정보 EDA", "HTML 2종", "영상물·게임물 각각의 현황 분석"],
        ["③ 청소년 이용 제한 특성 분석", "HTML", "규모·추이·분포·항목·조합·자체등급분류 6개 절"],
        ["④ 인터랙티브 대시보드", "공개 URL", "Streamlit · Plotly 6개 화면, 조건 변경 조회"],
        ["⑤ 주요 분석 인사이트 리포트", "HTML", "결론 3가지를 한 편으로 정리"],
    ], col_w=[3.6, 2.0, 6.5], row_h=0.52, size=12.5)
    txbox(s, 0.6, 4.9, 12.1, 0.5, URL, size=15, bold=True, color=ACCENT)
    txbox(s, 0.6, 5.5, 12.1, 1.2,
          "모든 산출물은 스크립트로 재생성된다. 원자료가 갱신되면 수치가 자동으로 따라가며, "
          "리포트와 대시보드가 서로 다른 숫자를 말하지 않도록 계산부를 한 곳에 두었다.\n"
          "이 발표자료도 같은 요약 파일에서 수치를 읽어 만든다.", size=13.5)
    notes(s, "말할 것: 산출물은 다섯 가지다. 화면에 URL 이 있으니 다음 장에서 직접 열어 보여 준다.\n\n"
             "강조할 점: 손으로 옮겨 적은 숫자가 없다는 것. 리포트든 대시보드든 발표자료든 모두 같은 "
             "계산 결과를 읽어 오게 만들었다. 수집이 늘어나도 숫자가 어긋나지 않는다.\n\n"
             "질문 대비: '데이터는 어디서 볼 수 있나' → 통합 Dataset 은 parquet 과 csv 로 있고, "
             "열 정의를 적은 데이터 사전을 HTML 로 함께 만들어 두었다.")

    # 15 대시보드
    s = new(prs, "대시보드: 화면 하나가 질문 하나에 답한다", "6. 산출물")
    pic(s, FIG / "dashboard.jpg", 0.6, 1.5, 8.3)
    txbox(s, 9.2, 1.6, 3.7, 4.2,
          "① 등급 결정 기준\n② 등급 상향 요인\n③ 신청등급 대비 조정\n"
          "④ 매체 간 판정 차이\n⑤ 공개 데이터 포괄 범위\n⑥ 개별 건 조회\n\n"
          "공통 필터: 기간 · 영상물 종별 ·\n게임물 플랫폼 · 성인물 제외\n\n"
          "필터를 바꾸면 화면의 해석 문장도\n다시 계산된다.", size=13.5)
    txbox(s, 0.6, 6.45, 12.1, 0.5, URL, size=14, bold=True, color=ACCENT)
    notes(s, "여기서 실제로 브라우저를 열어 보여 주는 것이 가장 효과적이다.\n\n"
             "시연 순서 추천: ① 화면에서 대각선만 채워진 교차표를 보여 주고(결론 3), "
             "④ 화면으로 넘어가 이진화 기준을 4단계로 바꿔 경고 문구가 뜨는 것을 보여 준다. "
             "'이 기준으로는 비교가 성립하지 않는다'는 것을 화면이 스스로 경고하도록 만들어 두었다.\n\n"
             "주의: 무료 요금제라 한동안 접속이 없으면 앱이 대기 상태로 들어간다. "
             "발표 시작 전에 미리 한 번 열어 두어야 한다. 첫 접속은 십여 초 걸린다.\n\n"
             "질문 대비: '어떻게 배포했나' → GitHub 비공개 저장소에 올리고 Streamlit Cloud 에 "
             "연결했다. 화면이 쓰는 열만 남긴 사본을 따로 만들어 저장소에 넣었다.")

    # 16 한계
    s = new(prs, "한계와 후속 과제", "7. 한계와 배운 것")
    table(s, 0.6, 1.55, 12.1, [
        ["구분", "내용"],
        ["표본의 범위",
         "게임물 결과는 위원회가 직접 심의한 분류분에 한정된다. 공개 API 로 확인되는 범위는 전체의 0.27%다."],
        ["표본 구성 편중",
         "영상물은 성인물이 37%를 차지하며, 성인물은 내용정보와 무관하게 대부분 청소년관람불가다."],
        ["이진화 기준",
         "매체 비교는 영상물을 3단계에서 자른 기준 위에서만 성립한다. 절단 지점은 데이터로 정해지지 않는다."],
        ["비교군 자료",
         "자체등급분류 비교군은 약 7주치가 전부이고 재수집이 불가능하여 추세 분석에 쓸 수 없다."],
        ["후속 과제",
         "두 자료 모두 서술형 설명 필드를 갖고 있다. 게임물 개요는 97.4%, 영상물 작품 내용은 2018년 이후 100% 기록되어 있어 다음 분석의 재료가 된다."],
    ], col_w=[2.4, 9.7], row_h=0.62, size=12.5)
    notes(s, "말할 것: 한계를 숨기지 않는 게 이 발표의 신뢰도를 만든다. 네 가지를 짚는다.\n\n"
             "특히 첫 번째(0.27%)와 세 번째(3단계 절단)는 결론을 인용할 때 반드시 따라붙어야 하는 "
             "단서다.\n\n"
             "후속 과제는 '다음에 뭘 할 거냐'는 질문에 대한 답으로 준비해 둔 것이다. 두 자료 모두 "
             "사람이 쓴 설명문 칸이 있어서 텍스트 분석으로 이어갈 수 있다.")

    # 17 배운 것
    s = new(prs, "폐기한 결론 두 가지", "7. 한계와 배운 것")
    txbox(s, 0.6, 1.5, 12.1, 0.5,
          "분석 도중 결과가 뒤집혀 폐기한 것이 둘 있다. 과정에서 가장 많이 배운 부분이다.",
          size=14.5)
    table(s, 0.6, 2.2, 12.1, [
        ["폐기한 결론", "왜 틀렸는가"],
        ["내용정보로 등급을 설명할 수 있다\n(회귀분석 AUC 1.000)",
         "모형이 좋았던 것이 아니라 등급이 곧 내용정보의 최고값이어서 같은 값을 두 번 쓴 것이었다. "
         "교차표를 찍어 보고 나서야 항등식임을 확인했다."],
        ["항목이 여러 개 겹칠수록 등급이 올라간다\n(개수 4개 93.4% → 5개 71.5%로 꺾임)",
         "성인물이 특정 구간에 몰려 생긴 착시였다. 성인물을 제외하니 꺾임이 사라지고 단조 증가로 "
         "바뀌었다. 종별을 통제하지 않은 것이 원인이다."],
    ], col_w=[4.6, 7.5], row_h=1.15, size=12.5)
    txbox(s, 0.6, 5.5, 12.1, 1.2,
          "배운 것: 결과가 지나치게 깨끗하면 모형이 아니라 데이터 구조를 먼저 의심해야 한다. "
          "그리고 비율을 비교하기 전에 그 비율을 만든 집단의 구성을 먼저 맞춰야 한다.",
          size=14.5, bold=True, color=ACCENT)
    notes(s, "이 장이 발표의 인상을 결정한다. 실패를 숨기지 않고 원인을 설명하는 장이다.\n\n"
             "첫 번째: 처음에는 내용정보로 등급을 예측하는 모형을 만들려고 했다. AUC 가 1.000 이 "
             "나왔고, 좋아하기 전에 이상하다고 생각해서 교차표를 찍어 봤더니 두 값이 같은 값이었다.\n\n"
             "두 번째: 항목이 여러 개 겹칠수록 등급이 올라가는데 5개에서 꺾이는 결과가 나왔다. "
             "성인물이 4개 구간에 89% 몰려 있어 생긴 착시였다. 심슨의 역설 사례다.\n\n"
             "질문 대비: '심슨의 역설이 뭐냐' → 전체를 합쳐서 보면 한 방향인데 집단을 나눠 보면 "
             "반대 방향이 나오는 현상이라고 짧게 답한다.")

    # 18 마무리
    s = new(prs, "정리")
    txbox(s, 0.7, 1.6, 12.0, 2.6,
          "1.  게임물의 청소년이용불가를 결정하는 것은 폭력성이나 선정성이 아니라 사행성이다.\n"
          "2.  다만 공개 데이터로 확인할 수 있는 범위는 게임물 등급분류 전체의 0.27%다.\n"
          "3.  영상물의 등급은 내용정보의 최고값과 동일하며, 판단이 개입하는 영역은 12.2%뿐이다.\n"
          "4.  같은 조건에서 비교하면 게임물의 판정이 더 엄격하다. 단 절단 기준을 전제로 한다.",
          size=17, line=1.6)
    txbox(s, 0.7, 4.6, 12.0, 0.5, "산출물", size=13, bold=True, color=ACCENT)
    txbox(s, 0.7, 5.1, 12.0, 1.2,
          f"대시보드 {URL}\n"
          "통합 Dataset · EDA 2종 · 청소년 이용 제한 특성 분석 · 인사이트 리포트", size=13.5)
    txbox(s, 0.7, 6.4, 12.0, 0.5, "감사합니다.", size=16, bold=True, color=ACCENT)
    notes(s, "네 문장으로 정리하고 마친다.\n\n"
             "질의응답에서 자주 나올 만한 것 정리:\n"
             "· 데이터는 어떻게 받았나 → 두 기관 공개 API, 전량, 기관 총 건수와 일치.\n"
             "· 왜 두 매체를 비교했나 → 강사 피드백에서 나온 요구이자, 두 기관이 같은 이름의 항목을 "
             "쓰고 있어 비교 가능성이 있었다.\n"
             "· 실무에 어떻게 쓰나 → 등급분류 결과를 인용할 때 '어느 경로의 분류분인지'를 함께 "
             "밝혀야 한다는 점, 그리고 공개 데이터만으로 게임물 전체를 말할 수 없다는 점.\n"
             "· 가장 어려웠던 점 → 수집 자체보다, 결과가 너무 깨끗해서 의심해야 했던 지점들.")

    prs.save(DEST)
    print(f"저장: {DEST}")
    print(f"저장: {write_notes_doc(prs)}")
    print(f"슬라이드 {len(prs.slides.__iter__.__self__._sldIdLst)}장")


if __name__ == "__main__":
    build()
