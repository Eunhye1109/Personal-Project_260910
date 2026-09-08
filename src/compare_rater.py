# -*- coding: utf-8 -*-
"""
4단계 축④ — 누가 등급을 매기느냐에 따라 달라지는가 (위원회 vs 사업자 자체등급분류)

같은 게임물인데 등급을 매기는 주체가 둘이다.

    위원회 심의      게임물관리위원회·게임콘텐츠등급분류위원회가 직접 매긴다. Open API 로 공개된다
    자체등급분류      구글·애플 같은 사업자가 스스로 매긴다. 홈페이지 공표 목록에만 있다

이 프로젝트는 Open API 데이터로 분석하는데, 그것이 게임물 전체의 얼마만큼인지를
지금까지 숫자로 말하지 못했다. 이 문서가 그 자리를 채운다.

두 데이터를 합치지 않는다. 판정 주체가 다르고 기간도 다르다. 나란히 놓고 견주기만 한다.

비교할 때 지키는 것
    · 자체등급분류 데이터가 약 7주치뿐이므로, 위원회 쪽도 같은 기간으로 잘라서 본다
    · 위원회의 전 기간 수치도 함께 실어, 같은 기간 표본이 작아서 생기는 왜곡을 확인한다
    · 장르는 표기 체계가 달라(단일 19종 vs 복합 294종) 맞출 수 없으므로 통제하지 않는다

실행
    python src/compare_rater.py
    python src/compare_rater.py --no-sync
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

DESCRIPTORS = ["사행성", "폭력성", "선정성", "언어", "약물", "공포", "범죄"]
GRADE_ORDER = ["전체이용가", "12세이용가", "15세이용가", "청소년이용불가"]

_lines: list[str] = []
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, OSError):
    pass


def say(t: str = "") -> None:
    print(t)
    _lines.append(t)


def head(t: str) -> None:
    say("")
    say("=" * 78)
    say(t)
    say("=" * 78)


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def latest(pattern: str) -> Path:
    files = sorted(PROC.glob(pattern))
    if not files:
        sys.exit(f"[중단] {pattern} 정제본이 없습니다.")
    return files[-1]


def load():
    a = pd.read_parquet(latest("grac_game_clean_*.parquet"))     # 위원회
    s = pd.read_parquet(latest("grac_self_clean_*.parquet"))     # 자체등급분류
    a = a[~a["is_canceled"]].copy()                              # 등급취소 건 제외
    lo, hi = s["rated_date"].min(), s["rated_date"].max()
    same = a[(a["rated_date"] >= lo) & (a["rated_date"] <= hi)].copy()
    return a, s, same, lo, hi


# ───────────────────────────────── §1 규모
def s1(a, s, same, lo, hi, res) -> None:
    head("1. 같은 기간에 누가 얼마나 매기는가")
    say(f"자체등급분류 데이터가 있는 구간은 {lo:%Y-%m-%d} ~ {hi:%Y-%m-%d}, 약 {(hi - lo).days}일이다.")
    say("이 구간으로 위원회 데이터를 잘라 같은 기간끼리 견준다.")
    say("")
    say(f"  위원회 심의        {len(same):>8,}건")
    say(f"  사업자 자체등급분류 {len(s):>8,}건")
    ratio = len(s) / len(same) if len(same) else 0
    say("")
    say(f"  ▶ 같은 기간에 사업자가 매긴 것이 위원회가 매긴 것의 약 {ratio:.0f}배다.")
    say(f"    비율로 보면 전체 {len(same)+len(s):,}건 중 위원회 심의는 {pct(len(same)/(len(same)+len(s)), 2)}에 그친다.")
    say("")
    say(f"  참고 — 위원회 전 기간 수집분은 {len(a):,}건이고 구간이 "
        f"{a['rated_date'].min():%Y-%m}부터 {a['rated_date'].max():%Y-%m}까지 약 19년이다.")
    say(f"    19년치 위원회 물량({len(a):,}건)보다 7주치 자체등급분류({len(s):,}건)가 더 많다.")
    res["규모"] = {"기간": f"{lo:%Y-%m-%d}~{hi:%Y-%m-%d}", "위원회_같은기간": len(same),
                 "자체등급분류": len(s), "배수": round(ratio, 1), "위원회_전기간": len(a)}


# ───────────────────────────────── §2 등급
def s2(a, s, same, res) -> None:
    head("2. 등급 분포가 얼마나 다른가")
    say("같은 기간끼리 비교하되, 위원회 전 기간 수치도 함께 실어 표본이 작아서 생기는 흔들림을 확인한다.")
    say("")
    say(f"  {'등급':<14} {'위원회(같은 기간)':>18} {'위원회(전 기간)':>18} {'자체등급분류':>16}")
    rows = {}
    for g in GRADE_ORDER:
        p_same = float((same["givenrate"] == g).mean()) if len(same) else 0.0
        p_all = float((a["givenrate"] == g).mean())
        p_self = float((s["grade"] == g).mean())
        rows[g] = [round(p_same, 4), round(p_all, 4), round(p_self, 4)]
        say(f"  {g:<14} {pct(p_same):>18} {pct(p_all):>18} {pct(p_self, 2):>16}")

    ys, ya, yf = rows["청소년이용불가"]
    say("")
    say(f"  ▶ 청소년이용불가 비율이 위원회 {pct(ys)}(같은 기간) · {pct(ya)}(전 기간) 인데")
    say(f"    자체등급분류는 {pct(yf, 2)}다. 실제 건수로는 {int(s['is_youth_restricted'].sum()):,}건뿐이다.")
    say("")
    say("  ※ 이것을 '사업자가 느슨하게 매긴다'로 바로 읽으면 안 된다.")
    say("    자체등급분류는 앱마켓에 올라오는 모바일 게임이 대부분이라, 애초에 들어오는 게임이 다르다.")
    say("    위원회는 아케이드 기기처럼 사행성 심의가 필요한 물량을 맡는다.")
    say("    아래 3·4절에서 내용정보를 맞춘 뒤 다시 본다.")
    res["등급분포"] = rows


# ───────────────────────────────── §3 내용정보
def s3(a, s, same, res) -> None:
    head("3. 내용정보는 어떻게 다른가")
    say("두 데이터 모두 같은 이름의 항목 7종을 쓴다. 얼마나 붙어 있는지를 본다.")
    say("")
    say(f"  내용정보가 하나라도 있는 건")
    say(f"    위원회(같은 기간) {pct(float(same['has_descriptor'].mean())) if len(same) else '-':>8}")
    say(f"    위원회(전 기간)   {pct(float(a['has_descriptor'].mean())):>8}")
    say(f"    자체등급분류      {pct(float(s['has_descriptor'].mean())):>8}")
    say("")
    say(f"  {'항목':<8} {'위원회(같은 기간)':>18} {'위원회(전 기간)':>18} {'자체등급분류':>16}")
    hold = {}
    for name in DESCRIPTORS:
        col = f"내용_{name}"
        p_same = float(same[col].mean()) if len(same) else 0.0
        p_all = float(a[col].mean())
        p_self = float(s[col].mean())
        hold[name] = [round(p_same, 4), round(p_all, 4), round(p_self, 4)]
        say(f"  {name:<8} {pct(p_same):>18} {pct(p_all):>18} {pct(p_self, 2):>16}")

    say("")
    say(f"  ▶ 사행성이 갈린다. 위원회 쪽은 전 기간 {pct(hold['사행성'][1])}인데 "
        f"자체등급분류는 {pct(hold['사행성'][2], 2)}다.")
    say("    자체등급분류에는 사행성 게임물이 사실상 들어오지 않는다는 뜻이고,")
    say("    2절의 청소년이용불가 비율 차이도 상당 부분 여기서 온다(사행성 단독 보유 시 청불 97.1%).")
    res["내용정보"] = hold


# ───────────────────────────────── §4 같은 내용정보에서
def s4(a, s, same, res) -> None:
    head("4. 같은 내용정보를 가졌을 때 등급이 다른가")
    say("항목 하나만 가진 건끼리 비교한다. 위원회 쪽은 같은 기간 표본이 작아 전 기간 값을 쓴다.")
    say("표본이 30건 미만인 항목은 싣지 않는다.")
    say("")
    say(f"  {'내용정보 (단독)':<16} {'위원회(전 기간)':>20} {'자체등급분류':>20} {'차이':>10}")
    rows = {}
    for name in DESCRIPTORS:
        col = f"내용_{name}"
        sa = a[(a[col] == 1) & (a["n_descriptors"] == 1)]["is_youth_restricted"].dropna()
        ss = s[(s[col] == 1) & (s["n_descriptors"] == 1)]["is_youth_restricted"].dropna()
        if len(sa) < 30 or len(ss) < 30:
            say(f"  {name:<16} {'표본 부족':>20}  (위원회 {len(sa):,} / 자체 {len(ss):,})")
            continue
        d = float(ss.mean() - sa.mean())
        rows[name] = {"위원회": round(float(sa.mean()), 4), "자체": round(float(ss.mean()), 4),
                      "차이": round(d, 4), "위원회n": int(len(sa)), "자체n": int(len(ss))}
        say(f"  {name:<16} {pct(sa.mean()):>11}({len(sa):>6,}) "
            f"{pct(ss.mean(), 2):>11}({len(ss):>6,}) {d*100:>+9.1f}%p")

    if rows:
        say("")
        say("  ▶ 같은 항목 하나만 붙어 있어도 위원회 쪽이 훨씬 높은 등급을 매긴다.")
        say("    다만 이것 역시 '같은 게임에 다른 등급을 매겼다'는 증거는 아니다.")
        say("    항목 이름이 같아도 그 안의 내용은 다를 수 있고(자체등급분류에는 단계 정보도 없다),")
        say("    두 집단에 들어오는 게임물 자체가 다르다.")
    res["같은내용정보"] = rows


# ───────────────────────────────── §5 시사점
def s5(res) -> None:
    head("5. 이 비교가 말해 주는 것")
    r = res["규모"]
    say(f"  1) Open API 로 공개되는 것은 게임물 등급분류의 극히 일부다.")
    say(f"     같은 기간 기준으로 위원회 심의는 전체의 {pct(r['위원회_같은기간']/(r['위원회_같은기간']+r['자체등급분류']), 2)}에 그친다.")
    say(f"     19년치 위원회 물량보다 7주치 자체등급분류가 더 많다.")
    say("")
    say("  2) 그래서 이 프로젝트의 게임물 분석 결과는 '게임물 전체'가 아니라")
    say("     '위원회가 직접 심의한 게임물'의 이야기로 읽어야 한다. PRD 5.5절 한계가 이것이다.")
    say("")
    say("  3) 두 집단은 들어오는 게임물 자체가 다르다.")
    say("     자체등급분류에는 사행성 게임물이 사실상 없고, 위원회 쪽에는 아케이드 기기가 많다.")
    say("     따라서 등급 분포 차이를 심의 엄격도 차이로 읽으면 안 된다.")
    say("")
    say("  4) 그럼에도 이 비교는 필요하다. 공개 데이터만 보고 '게임물 청소년이용불가가 30%'라고")
    say("     말하면 실제와 크게 어긋난다. 두 경로를 합쳐 보면 그 값은 0.5% 아래로 내려간다.")
    say("")
    say("  ※ 비교군 데이터는 이 프로젝트가 수집한 것이 아니다. 별개 업무에서 확보돼 있던 파일을")
    say("    가져다 썼고, 출처와 한계는 data/external/README.md 에 적어 두었다.")


def write_html(res: dict) -> Path:
    body = "\n".join(_lines).replace("&", "&amp;").replace("<", "&lt;")
    r = res["규모"]
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>누가 등급을 매기는가</title>
<style>
 body {{ margin:0; padding:32px; background:#f7f7f5; color:#1f2328;
        font-family:"맑은 고딕","Malgun Gothic",system-ui,sans-serif; }}
 .wrap {{ max-width:1040px; margin:0 auto; background:#fff; padding:36px 40px;
          border:1px solid #e3e3e0; border-radius:8px; }}
 h1 {{ font-size:20px; margin:0 0 4px; color:#1f3864; }}
 .sub {{ color:#6b7280; font-size:13px; margin-bottom:20px; }}
 .key {{ background:#fff4e0; border:1px solid #f0d9a8; border-radius:6px;
         padding:14px 18px; font-size:14px; margin-bottom:24px; line-height:1.7; }}
 pre {{ font-family:"D2Coding",Consolas,monospace; font-size:12.5px; line-height:1.65;
        white-space:pre; overflow-x:auto; background:#fbfbfa; border:1px solid #ececea;
        border-radius:6px; padding:20px; }}
</style></head><body><div class="wrap">
<h1>누가 등급을 매기는가 — 위원회 심의 vs 사업자 자체등급분류</h1>
<div class="sub">비교 구간 {r['기간']} · 위원회 {r['위원회_같은기간']:,}건 · 자체등급분류 {r['자체등급분류']:,}건
 · 생성 {datetime.now():%Y-%m-%d %H:%M}</div>
<div class="key"><b>Open API 로 공개되는 것은 게임물 등급분류의 극히 일부다.</b>
같은 기간에 사업자가 스스로 매긴 것이 위원회가 심의한 것의 약 {r['배수']:.0f}배이고,
19년치 위원회 물량보다 7주치 자체등급분류가 더 많다. 두 데이터는 판정 주체도 기간도 달라
<b>합치지 않고 나란히 놓고 견주기만 한다.</b></div>
<pre>{body}</pre>
</div></body></html>"""
    p = OUT / "compare_rater_report.html"
    p.write_text(html, encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    a, s, same, lo, hi = load()
    res: dict = {"생성": datetime.now().isoformat(timespec="seconds")}
    say(f"위원회 정제본 {len(a):,}건(등급취소 제외) / 자체등급분류 정제본 {len(s):,}건")

    s1(a, s, same, lo, hi, res)
    s2(a, s, same, res)
    s3(a, s, same, res)
    s4(a, s, same, res)
    s5(res)

    (OUT / "compare_rater_summary.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "compare_rater_report.txt").write_text("\n".join(_lines), encoding="utf-8")
    html = write_html(res)
    print("")
    print(f"저장: {OUT / 'compare_rater_summary.json'}")
    print(f"저장: {OUT / 'compare_rater_report.txt'}")
    print(f"저장: {html}")

    if not args.no_sync:
        print("")
        sync_nas.sync()


if __name__ == "__main__":
    main()
