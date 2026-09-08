# -*- coding: utf-8 -*-
"""
영등위 현황 EDA 보고 페이지 생성

전에는 이 HTML을 손으로 고쳤다. 그러다 보니 수집이 늘어날 때마다 숫자가 어긋났고,
9월 2일자 99,000건 기준 문장이 전량 수집 뒤에도 그대로 남아 있었다.
이제 정제본에서 값을 다시 계산해 페이지를 통째로 만들어 낸다.

    src/templates/eda_head.html   제목·글꼴·CSS
    src/templates/eda_tail.html   그래프를 그리는 자바스크립트 ({{DATA}} 자리에 값이 들어간다)
    이 스크립트                    본문 글과 데이터

실행
    python src/make_eda_report.py
    python src/make_eda_report.py --no-sync
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_nas  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
TMPL = Path(__file__).resolve().parent / "templates"

NAMES = {1: "주제", 2: "선정성", 3: "폭력성", 4: "대사", 5: "공포", 6: "약물", 7: "모방위험"}
LV = [f"rtStdName{i}_lv" for i in range(1, 8)]
GRADES = ["전체관람가", "12세이상관람가", "15세이상관람가", "청소년관람불가", "제한관람가"]
GRADE_AGES = [0, 12, 15, 18, 19]
LEVEL_TO_AGE = {1: 0, 2: 12, 3: 15, 4: 18, 5: 19}


def latest_clean() -> Path:
    files = sorted(PROC.glob("kmrb_video_clean_*.parquet"))
    if not files:
        sys.exit("[중단] 정제본이 없습니다. 먼저 src/clean_kmrb.py 를 실행하세요.")
    return files[-1]


def js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


# ────────────────────────────────────────── 값 계산
def compute(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=LV).copy()
    d["cmax"] = d[LV].max(axis=1).astype(int)

    # 연도별 등급 구성
    year = []
    for y, sub in d.groupby(d["rt_date"].dt.year):
        if pd.isna(y) or len(sub) < 50:
            continue
        share = [round(float((sub["grade_age"] == a).mean() * 100), 1) for a in GRADE_AGES]
        year.append([int(y), int(len(sub)), share])

    grade_n = [int((d["grade_age"] == a).sum()) for a in GRADE_AGES]
    kind = [[str(k), int(v)] for k, v in d["kindName"].value_counts().head(6).items()]

    # 표기 체계별 항목 평균
    step = d[d["content_notation"] == "단계표기"]
    gradenota = d[d["content_notation"] == "등급표기"]
    nota = [[round(float(step[c].mean()), 2), round(float(gradenota[c].mean()), 2)] for c in LV]

    # 등급별 항목 평균
    prof = []
    for a in GRADE_AGES:
        sub = d[d["grade_age"] == a]
        prof.append([round(float(sub[c].mean()), 2) if len(sub) else 0.0 for c in LV])

    # 최고값 x 등급 (항등식 확인용)
    rule = []
    for lv in range(1, 6):
        sub = d[d["cmax"] == lv]
        rule.append([lv, int(len(sub))] + [int((sub["grade_age"] == a).sum()) for a in GRADE_AGES])
    ok = (d["cmax"].map(LEVEL_TO_AGE) == d["grade_age"])
    rule_rate = float(ok.mean())
    rule_by_nota = {str(k): [int(len(v)), round(float((v["cmax"].map(LEVEL_TO_AGE) == v["grade_age"]).mean()), 5)]
                    for k, v in d.groupby("content_notation") if len(v) > 100}

    # 신청 대비 조정
    adj_src = d.dropna(subset=["hope_grade_age"])
    diff = adj_src["grade_age"] - adj_src["hope_grade_age"]
    adj = [["신청대로", int((diff == 0).sum()), round(float((diff == 0).mean() * 100), 1)],
           ["상향 조정", int((diff > 0).sum()), round(float((diff > 0).mean() * 100), 1)],
           ["하향 조정", int((diff < 0).sum()), round(float((diff < 0).mean() * 100), 1)]]
    up = adj_src[diff > 0]["hopeGradeName"].value_counts().head(4)
    adjup = [[str(k), int(v)] for k, v in up.items()]

    # 항목 간 상관
    corr = [[round(float(v), 2) for v in row] for row in d[LV].corr().values]

    # 결정사유
    reason = d[d["rtCoreHarmRsnNm"].notna() & (d["rtCoreHarmRsnNm"].astype(str).str.strip() != "")]
    ex = reason.assign(r=reason["rtCoreHarmRsnNm"].astype(str).str.split(",")).explode("r")
    ex["r"] = ex["r"].str.strip()
    ex = ex[ex["r"] != ""]
    kinds = reason["kindName"].value_counts().head(5).index
    names = list(ex["r"].value_counts().index)
    heat = []
    for k in kinds:
        base = reason[reason["kindName"] == k]
        sub = ex[ex["kindName"] == k]
        heat.append([str(k)] + [round(float((sub["r"] == n).sum()) / len(base) * 100, 1) for n in names])

    return {
        "n": int(len(d)), "cols": int(len(df.columns)),
        "date_min": d["rt_date"].min(), "date_max": d["rt_date"].max(),
        "YEAR": year, "GRADE_N": grade_n, "KIND": kind, "NOTA": nota, "PROF": prof,
        "RULE": rule, "rule_rate": rule_rate, "rule_by_nota": rule_by_nota,
        "ADJ": adj, "ADJUP": adjup, "CORR": corr,
        "reason_n": int(len(reason)), "reason_names": names, "HEAT": heat,
        "reason_years": (int(reason["rt_date"].dt.year.min()), int(reason["rt_date"].dt.year.max())),
        "adult_share": float((d["kindName"] == "성인물").mean()),
        "youth_share": float(d["grade_age"].ge(18).mean()),
    }


# ────────────────────────────────────────── 본문 글
def body_html(v: dict) -> str:
    y0, y1 = v["YEAR"][0], v["YEAR"][-1]
    step_n, step_r = v["rule_by_nota"].get("단계표기", [0, 0])
    grade_n, grade_r = v["rule_by_nota"].get("등급표기", [0, 0])
    names = v["reason_names"]

    return f"""<div class="wrap">

<header>
  <div class="eyebrow">현황 EDA · {datetime.now():%Y-%m-%d} 산출</div>
  <h1>비디오물 등급분류 현황</h1>
  <p class="lede">영상물등급위원회가 공개하는 비디오물 등급분류 결과를 전량 받아 정리한 1차 분석이다.
  관람등급이 어떻게 분포하는지, 등급을 정하는 내용정보가 어떤 모양인지를 본다.</p>

  <dl class="facts">
    <div class="fact"><dt>분석 대상</dt><dd>{v['n']:,}<small> 건</small></dd></div>
    <div class="fact"><dt>기간</dt><dd>{v['date_min']:%Y}<small>-{v['date_min']:%m} ~ </small>{v['date_max']:%Y}<small>-{v['date_max']:%m}</small></dd></div>
    <div class="fact"><dt>수집 진행</dt><dd>100<small>% 완료</small></dd></div>
    <div class="fact"><dt>내용정보 항목</dt><dd>7<small> 종 · 1~5 단계</small></dd></div>
  </dl>

  <p class="notice"><strong>수집이 끝났다.</strong> 한때 약 99,000건에서 조회가 막혔으나,
  기간을 나눠 받는 방식으로 바꿔 {v['n']:,}건 전량을 받았다. 이 페이지의 모든 수치는 전량 기준이다.</p>
</header>

<section>
  <div class="shead"><span class="snum">요약</span><h2>먼저 볼 것 세 가지</h2></div>
  <div class="finds">
    <div class="find">
      <span class="tag">결론</span>
      <h3>등급에 사람의 판단이 거의 없다</h3>
      <p>내용정보 7개 항목 중 가장 높은 단계를 그대로 옮기면 관람등급이 된다.
      {v['n']:,}건 가운데 {v['rule_rate']*100:.2f}%가 그렇고, 표기가 바뀐 2017년 5월 이후
      {grade_n:,}건은 어긋난 건이 하나도 없다. 계산이 아니라 옮겨 적기다.</p>
    </div>
    <div class="find">
      <span class="tag">판단이 드는 곳</span>
      <h3>신청 등급을 조정하는 {(v['ADJ'][1][2] + v['ADJ'][2][2]):.1f}%뿐</h3>
      <p>내용정보와 결정 등급은 같은 값이라 서로를 설명하지 못한다. 신청 등급은 다르다.
      신청사가 스스로 적어 낸 값이기 때문이다. 이 자료에서 위원회의 판단이 드러나는 곳은
      여기뿐이다(위로 {v['ADJ'][1][2]}% · 아래로 {v['ADJ'][2][2]}%).</p>
    </div>
    <div class="find">
      <span class="tag">읽을 때 주의</span>
      <h3>성인물이 {v['adult_share']*100:.0f}%를 차지한다</h3>
      <p>성인물은 내용정보와 상관없이 거의 전부 청소년관람불가다. 종류를 맞추지 않고 낸 결론은
      뒤집힐 수 있다. 실제로 1차 분석에서 한 번 뒤집혔다.</p>
    </div>
  </div>
</section>

<section>
  <div class="shead"><span class="snum">1</span><h2>등급은 무엇으로 정해지는가</h2></div>
  <p class="sdesc">내용정보 7개 항목 중 가장 높은 단계를 관람등급으로 옮겨 보았다.
  1단계는 전체관람가, 2단계는 12세, 3단계는 15세, 4단계는 청소년관람불가, 5단계는 제한관람가에 해당한다.</p>

  <figure>
    <div class="scroll"><svg id="c-rule" width="900" height="300" role="img" aria-label="내용정보 최고값과 관람등급의 대응"></svg></div>
    <figcaption>대각선만 채워져 있다. 두 값이 사실상 같은 것이라는 뜻이다.
    전체 일치율 {v['rule_rate']*100:.2f}%, 단계표기 시기({step_n:,}건) {step_r*100:.3f}%,
    등급표기 시기({grade_n:,}건) {grade_r*100:.3f}%.
    어긋난 건은 모두 2017년 5월 이전이고 대부분 최고값이 5단계인데 제한관람가가 아니라
    청소년관람불가로 결정된 경우다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">2</span><h2>연도별 등급 구성</h2></div>
  <p class="sdesc">해마다 어떤 등급이 얼마나 나왔는지를 비율로 쌓았다. 막대 왼쪽 숫자는 그해 등급분류 건수다.</p>

  <figure>
    <div class="legend" id="lg-grade"></div>
    <div class="scroll"><svg id="c-year" width="900" height="{60 + len(v['YEAR']) * 31}" role="img" aria-label="연도별 관람등급 구성 비율"></svg></div>
    <figcaption>2016년을 기점으로 구성이 크게 움직인다. 건수가 특정 해에 튀는 것은
    그해 신청이 몰린 결과이며, 비율 변화와 건수 변화를 따로 보아야 한다.</figcaption>
    <details><summary>표로 보기</summary><div class="scroll"><table id="t-year"></table></div></details>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">3</span><h2>관람등급과 종별 분포</h2></div>
  <p class="sdesc">전체 기간을 합쳤을 때의 분포다. 종별에서 성인물이 차지하는 비중이
  이후 해석에 계속 영향을 준다.</p>

  <figure>
    <div class="scroll"><svg id="c-grade" width="900" height="200" role="img" aria-label="관람등급 분포"></svg></div>
    <div class="scroll"><svg id="c-kind" width="900" height="235" role="img" aria-label="종별 분포"></svg></div>
    <figcaption>비디오물은 성인물 비중이 높다. 게임물과 비교할 때 이 구성 차이가
    매체 차이로 오해되지 않도록 종별을 맞춘 뒤 비교해야 한다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">4</span><h2>두 가지 표기 체계</h2></div>
  <p class="sdesc">내용정보 표기는 2017년 5월에 한 번 바뀐다. 그 전에는 <span class="mono">1단계-낮음</span>처럼
  단계로, 그 뒤에는 <span class="mono">전체관람가</span>처럼 등급 이름으로 쓴다.
  둘 다 5단계라 하나로 합칠 수 있는지 확인한 것이다.</p>

  <figure>
    <div class="legend">
      <span><i class="sw" style="background:var(--catA)"></i>단계표기 · 2017년 4월까지</span>
      <span><i class="sw" style="background:var(--catB)"></i>등급표기 · 2017년 5월부터</span>
    </div>
    <div class="scroll"><svg id="c-nota" width="900" height="300" role="img" aria-label="표기 체계별 내용정보 항목 평균"></svg></div>
    <figcaption>등급표기 쪽이 전반적으로 낮은 것은 체계가 달라서가 아니라
    그 시기에 전체관람가 비중이 커졌기 때문이다. 항목 사이의 상대적 순서는 두 체계에서 그대로 유지된다.</figcaption>
    <details><summary>표로 보기</summary><div class="scroll"><table id="t-nota"></table></div></details>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">5</span><h2>등급별 내용정보 프로파일</h2></div>
  <p class="sdesc">관람등급마다 7개 항목이 평균 몇 단계인지를 격자로 표시했다. 색이 진할수록 높은 값이다.</p>

  <figure>
    <div class="scroll"><svg id="c-prof" width="900" height="290" role="img" aria-label="관람등급별 내용정보 항목 평균"></svg></div>
    <figcaption>전체관람가는 7개 항목이 모두 정확히 1.00이다. 하나라도 2단계가 되면
    전체관람가가 나오지 않는다는 뜻이고, 이는 1절의 최고값 규칙과 같은 이야기다.
    청소년관람불가에서 주제·선정성·대사·모방위험만 높은 것은 성인물 비중이 높은 표본의 성격이다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">6</span><h2>무엇이 등급을 끌어올렸나</h2></div>
  <p class="sdesc">등급이 최고값이라면, 남는 질문은 그 최고값을 무엇이 차지하느냐다.
  응답에 들어 있는 결정사유 항목이 이것을 이름으로 알려준다.
  기록된 건은 {v['reason_n']:,}건이고 구간은 {v['reason_years'][0]}년부터 {v['reason_years'][1]}년까지다.</p>

  <figure>
    <div class="scroll"><svg id="c-heat" width="900" height="260" role="img" aria-label="종별로 등급을 결정한 내용정보 항목"></svg></div>
    <figcaption>종별에 따라 등급을 끌어올린 항목이 뚜렷하게 갈린다.
    이것은 최고값 규칙에서 자동으로 따라 나오는 결과가 아니라 콘텐츠 성격의 차이다.
    다만 결정사유는 최근 구간에만 기록돼 있어 전 기간으로 넓혀 읽을 수는 없다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">7</span><h2>신청등급과 결정등급</h2></div>
  <p class="sdesc">신청사가 희망한 등급과 위원회가 결정한 등급이 다른 사례다.
  내용정보와 결정등급은 사실상 같은 값이라 서로를 설명하지 못하지만, 신청등급은 다르다.
  이 데이터에서 판단이 개입하는 영역은 여기뿐이다.</p>

  <figure>
    <div class="scroll"><svg id="c-adj" width="900" height="120" role="img" aria-label="신청등급 대비 결정등급 조정 비율"></svg></div>
    <div class="scroll"><svg id="c-adjup" width="900" height="200" role="img" aria-label="상향 조정된 건의 신청등급 분포"></svg></div>
    <figcaption>상향 조정이 하향보다 많다. 상향된 건 가운데 상당수가 낮은 등급으로 신청했던 건이다.
    이 조정 사례는 매체 간 판정 차이를 볼 때 그대로 쓸 수 있는 재료다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">8</span><h2>항목끼리 얼마나 같이 움직이나</h2></div>
  <p class="sdesc">내용정보 7개 항목 사이의 상관계수다. 파란색은 음의 상관, 주황색은 양의 상관이다.</p>

  <figure>
    <div class="scroll"><svg id="c-corr" width="900" height="700" role="img" aria-label="내용정보 항목 간 상관계수 행렬"></svg></div>
    <figcaption><strong>항목이 두 덩어리로 갈린다.</strong>
    주제·선정성·대사·모방위험이 서로 강하게 붙어 다니고, 폭력성·공포·약물이 또 다른 덩어리를 이룬다.
    두 덩어리 사이의 상관은 0에 가깝거나 음수다. 앞 덩어리는 성인물, 뒤 덩어리는 극영화·애니메이션 쪽에서
    주로 나타난다.</figcaption>
  </figure>
</section>

<section>
  <div class="shead"><span class="snum">다음</span><h2>남은 일</h2></div>
  <ul class="items">
    <li><span class="pill done">해결</span><div><strong>내용정보 항목명 확정.</strong>
      응답이 항목을 번호로만 주고 이름을 주지 않았다. 같은 응답의 결정사유 항목이
      등급을 결정한 항목을 이름으로 담고 있어 그것으로 대응을 밝혔다.
      <strong>1 주제 · 2 선정성 · 3 폭력성 · 4 대사 · 5 공포 · 6 약물 · 7 모방위험</strong>이다.
      공공데이터포털 설명의 순서는 4·5·6번이 실제와 다르다.</div></li>
    <li><span class="pill done">해결</span><div><strong>전량 수집.</strong>
      약 99,000건에서 조회가 막혔으나 기간을 나눠 받는 방식으로 바꿔 {v['n']:,}건을 모두 받았다.</div></li>
    <li><span class="pill open">진행</span><div><strong>게임물과의 비교.</strong>
      게임물 등급분류 결과도 전량 받았다. 다만 게임물은 항목에 단계가 없고 해당 항목의 이름만
      나열되는 방식이라 같은 척도로 견줄 수 없다. 별도 문서에서 다룬다.</div></li>
    <li><span class="pill hold">유의</span><div><strong>이 표본으로 비디오물 전체를 말할 수 없다.</strong>
      성인물이 {v['adult_share']*100:.0f}%를 차지하고, 성인물은 내용정보와 무관하게 사실상 전건이
      청소년관람불가다. 종별을 맞추지 않고 낸 결론은 뒤집힐 수 있다.</div></li>
  </ul>
</section>

<footer>
  영상물등급위원회 비디오물 등급분류정보 조회 서비스(공공데이터포털) 전량 수집분 {v['n']:,}건 기준 ·
  {datetime.now():%Y-%m-%d} 산출 · <span class="mono">src/make_eda_report.py</span> 로 다시 만들 수 있다
</footer>
</div>

"""


def data_block(v: dict) -> str:
    return f"""const GRADES={js(GRADES)};
const RAMP=["--s1","--s2","--s3","--s4","--s5"];
const ITEMS={js([NAMES[i] for i in range(1, 8)])};
const YEAR={js(v['YEAR'])};
const GRADE_N={js(v['GRADE_N'])};
const KIND={js(v['KIND'])};
const NOTA={js(v['NOTA'])};
const PROF={js(v['PROF'])};
const RULE={js(v['RULE'])};
const ADJ={js(v['ADJ'])};
const ADJUP={js(v['ADJUP'])};
const CORR={js(v['CORR'])};
const REASONS={js(v['reason_names'])};
const HEAT={js(v['HEAT'])};
const TOTAL={v['n']};"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()

    src = latest_clean()
    print(f"정제본: {src.name}")
    df = pd.read_parquet(src)
    v = compute(df)
    print(f"  {v['n']:,}건 / {v['date_min']:%Y-%m-%d} ~ {v['date_max']:%Y-%m-%d}")
    print(f"  최고값 규칙 일치율 {v['rule_rate']*100:.2f}%")

    head = (TMPL / "eda_head.html").read_text(encoding="utf-8")
    tail = (TMPL / "eda_tail.html").read_text(encoding="utf-8")
    html = head + body_html(v) + tail.replace("{{DATA}}", data_block(v))

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "eda_report.html"
    dest.write_text(html, encoding="utf-8")
    print(f"\n저장: {dest}  ({dest.stat().st_size/1024:.0f} KB)")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
