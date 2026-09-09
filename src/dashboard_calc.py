# -*- coding: utf-8 -*-
"""
대시보드 계산부 — 화면(app.py)이 부르는 집계 함수만 모아 둔다.

Streamlit 없이도 부를 수 있도록 순수 pandas 로만 짰다. 화면을 띄우지 않고
`python src/dashboard_calc.py` 로 숫자가 리포트와 맞는지 확인할 수 있다.

**여기서 새 규칙을 만들지 않는다.** 분석 스크립트(analyze_stage4·compare_media·
compare_rater)가 이미 정한 판단을 그대로 옮긴다. 규칙이 갈리면 화면과 리포트가
서로 다른 숫자를 말하게 된다.

옮겨 온 판단
  · 매체 비교는 이름이 같은 4개(선정성·폭력성·공포·약물)로만 한다
  · 비교 대상 밖 항목이 붙은 건은 양쪽 대칭으로 뺀다
    (안 빼면 사행성 단독 게임 97.1% 가 '(없음)' 칸에 들어가 결과가 뒤집힌다)
  · 영상물은 성인물 제외, 게임물은 등급취소 제외
  · 영상물 이진화 기준은 3단계. 4단계는 정의상 100% 가 되어 비교가 아니다
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "dashboard"

KMRB_ITEMS = ["주제", "선정성", "폭력성", "대사", "공포", "약물", "모방위험"]
GRAC_ITEMS = ["선정성", "폭력성", "공포", "언어", "약물", "범죄", "사행성"]

# 이름이 같아 매체 비교에 쓸 수 있는 4개 (PRD 4.4)
COMPARABLE = ["선정성", "폭력성", "공포", "약물"]
KMRB_OTHER = ["주제", "대사", "모방위험"]      # 영상물에만 있는 항목
GRAC_OTHER = ["언어", "범죄", "사행성"]        # 게임물에만 있는 항목

GRADE_ORDER = ["전체관람가", "12세이상관람가", "15세이상관람가", "청소년관람불가", "제한관람가"]
GAME_ORDER = ["전체이용가", "12세이용가", "15세이용가", "청소년이용불가"]
LEVEL_NAME = {1: "1단계", 2: "2단계", 3: "3단계", 4: "4단계", 5: "5단계"}

# 최고값 규칙이 말하는 대응 (4.7절)
EXPECT_AGE = {1: 0, 2: 12, 3: 15, 4: 18, 5: 19}


def load(name: str) -> pd.DataFrame:
    path = DATA / f"{name}.parquet"
    if not path.exists():
        sys.exit(f"[중단] {path} 가 없습니다. 먼저 make_dashboard_data.py 를 실행하세요.")
    return pd.read_parquet(path)


# ───────────────────────────────────────── 공통 필터
def filter_kmrb(df, years=None, kinds=None, grades=None, drop_adult=False) -> pd.DataFrame:
    d = df
    if years:
        d = d[d["rt_year"].between(years[0], years[1])]
    if kinds:
        d = d[d["kindName"].astype(str).isin(kinds)]
    if grades:
        d = d[d["gradeName"].astype(str).isin(grades)]
    if drop_adult:
        d = d[d["kindName"].astype(str) != "성인물"]
    return d


def filter_grac(df, years=None, platforms=None, grades=None, drop_canceled=False) -> pd.DataFrame:
    d = df
    if years:
        d = d[d["rated_year"].between(years[0], years[1])]
    if platforms:
        d = d[d["platform"].astype(str).isin(platforms)]
    if grades:
        d = d[d["givenrate"].astype(str).isin(grades)]
    if drop_canceled:
        d = d[~d["is_canceled"]]
    return d


# ───────────────────────────────────────── 화면1 등급 결정 규칙
def rule_crosstab(df: pd.DataFrame) -> pd.DataFrame:
    """내용정보 최고값 × 관람등급. 최고값 규칙이 맞다면 대각선만 찬다."""
    d = df.dropna(subset=["content_max", "gradeName"])
    if d.empty:
        return pd.DataFrame()
    ct = pd.crosstab(d["content_max"].astype(int).map(LEVEL_NAME), d["gradeName"].astype(str))
    rows = [LEVEL_NAME[i] for i in range(1, 6) if LEVEL_NAME[i] in ct.index]
    cols = [g for g in GRADE_ORDER if g in ct.columns]
    return ct.reindex(index=rows, columns=cols, fill_value=0)


def _match_flag(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["content_max", "grade_age"]).copy()
    d["일치"] = d["content_max"].astype(int).map(EXPECT_AGE).eq(d["grade_age"].astype(int))
    return d


def rule_match(df: pd.DataFrame) -> pd.DataFrame:
    """최고값이 등급과 맞아떨어지는 비율. 표기 체계별로 나눠 본다."""
    d = _match_flag(df)
    if d.empty:
        return pd.DataFrame(columns=["표기 체계", "건수", "일치율"])
    out = (d.groupby(d["content_notation"].astype(str), observed=True)["일치"]
             .agg(건수="size", 일치율="mean"))
    out.loc["전체"] = [len(d), float(d["일치"].mean())]
    return out.reset_index(names="표기 체계")


def rule_by_year(df: pd.DataFrame) -> pd.DataFrame:
    d = _match_flag(df)
    if d.empty:
        return pd.DataFrame(columns=["rt_year", "건수", "일치율"])
    return (d.groupby("rt_year")["일치"].agg(건수="size", 일치율="mean").reset_index())


def rule_exceptions(df: pd.DataFrame) -> pd.DataFrame:
    """규칙에서 어긋난 건. 어디서 어긋나는지 보이면 규칙의 성격이 드러난다."""
    d = _match_flag(df)
    bad = d[~d["일치"]]
    if bad.empty:
        return pd.DataFrame()
    return (bad.groupby([bad["content_max"].astype(int).map(LEVEL_NAME),
                         bad["gradeName"].astype(str)], observed=True)
               .size().rename("건수").reset_index()
               .rename(columns={"content_max": "내용정보 최고값", "gradeName": "결정 등급"})
               .sort_values("건수", ascending=False))


# ───────────────────────────────────────── 화면2 무엇이 등급을 올렸나
def reason_long(df: pd.DataFrame) -> pd.DataFrame:
    """결정사유를 항목 하나씩 풀어 놓는다. `선정성,폭력성` 처럼 여러 개가 한 칸에 온다."""
    s = df["rtCoreHarmRsnNm"].astype(str).str.strip()
    has = df[s.notna() & ~s.isin(["", "nan", "None"])].copy()
    if has.empty:
        return has.assign(항목=pd.Series(dtype=object))
    long = (has.assign(항목=has["rtCoreHarmRsnNm"].astype(str).str.split(","))
               .explode("항목"))
    long["항목"] = long["항목"].str.strip()
    return long[long["항목"] != ""]


def reason_freq(df: pd.DataFrame) -> pd.DataFrame:
    long = reason_long(df)
    if long.empty:
        return pd.DataFrame(columns=["항목", "건수", "비율"])
    base = long["rtNo"].nunique()
    vc = long.groupby("항목", observed=True)["rtNo"].nunique().sort_values(ascending=False)
    return pd.DataFrame({"항목": vc.index, "건수": vc.values, "비율": vc.values / base})


def reason_by_kind(df: pd.DataFrame, min_n: int = 100) -> pd.DataFrame:
    """종별로 어떤 항목이 등급을 결정했는지. 분모는 그 종별의 '사유가 기록된 건'."""
    long = reason_long(df)
    if long.empty:
        return pd.DataFrame()
    long = long.assign(종별=long["kindName"].astype(str))
    base = long.groupby("종별")["rtNo"].nunique()
    keep = base[base >= min_n].index
    if not len(keep):
        return pd.DataFrame()
    tab = (long[long["종별"].isin(keep)]
           .groupby(["종별", "항목"], observed=True)["rtNo"].nunique().unstack(fill_value=0))
    tab = tab.div(base[keep], axis=0)
    order = reason_freq(df)["항목"].tolist()
    return tab.reindex(columns=[c for c in order if c in tab.columns])


def reason_by_year(df: pd.DataFrame, min_n: int = 100) -> pd.DataFrame:
    long = reason_long(df)
    if long.empty:
        return pd.DataFrame()
    base = long.groupby("rt_year")["rtNo"].nunique()
    keep = base[base >= min_n].index
    if not len(keep):
        return pd.DataFrame()
    tab = (long[long["rt_year"].isin(keep)]
           .groupby(["rt_year", "항목"], observed=True)["rtNo"].nunique().unstack(fill_value=0))
    return tab.div(base[keep], axis=0)


def reason_coverage(df: pd.DataFrame) -> dict:
    long = reason_long(df)
    n = long["rtNo"].nunique() if len(long) else 0
    years = long["rt_year"] if len(long) else pd.Series(dtype=int)
    return {"기록건수": int(n), "전체": int(len(df)),
            "기록률": float(n / len(df)) if len(df) else 0.0,
            "시작": int(years.min()) if len(years) else None,
            "끝": int(years.max()) if len(years) else None}


# ───────────────────────────────────────── 화면3 신청 대비 조정
def _adjust_frame(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=["hope_grade_age", "grade_age"]).copy()
    d["diff"] = d["grade_age"].astype(int) - d["hope_grade_age"].astype(int)
    return d


def adjust_summary(df: pd.DataFrame) -> pd.DataFrame:
    d = _adjust_frame(df)
    if d.empty:
        return pd.DataFrame(columns=["구분", "건수", "비율"])
    diff = d["diff"]
    return pd.DataFrame({
        "구분": ["신청대로", "상향 조정", "하향 조정"],
        "건수": [int((diff == 0).sum()), int((diff > 0).sum()), int((diff < 0).sum())],
        "비율": [float((diff == 0).mean()), float((diff > 0).mean()), float((diff < 0).mean())],
    })


def adjust_by_kind(df: pd.DataFrame, min_n: int = 200) -> pd.DataFrame:
    d = _adjust_frame(df)
    if d.empty:
        return pd.DataFrame()
    out = (d.assign(종별=d["kindName"].astype(str)).groupby("종별")
            .agg(건수=("diff", "size"),
                 상향=("diff", lambda s: float((s > 0).mean())),
                 하향=("diff", lambda s: float((s < 0).mean()))))
    return out[out["건수"] >= min_n].sort_values("상향", ascending=False).reset_index()


def adjust_by_hope(df: pd.DataFrame, min_n: int = 200) -> pd.DataFrame:
    d = _adjust_frame(df)
    if d.empty:
        return pd.DataFrame()
    out = (d.assign(신청등급=d["hopeGradeName"].astype(str)).groupby("신청등급")
            .agg(건수=("diff", "size"),
                 상향=("diff", lambda s: float((s > 0).mean())),
                 하향=("diff", lambda s: float((s < 0).mean()))))
    out = out[out["건수"] >= min_n]
    order = [g for g in GRADE_ORDER if g in out.index]
    return out.reindex(order + [i for i in out.index if i not in order]).reset_index()


def adjust_profile(df: pd.DataFrame) -> pd.DataFrame:
    """상향/하향/신청대로 세 무리의 내용정보 평균 단계. 어디서 어긋나는지 본다."""
    d = _adjust_frame(df)
    if d.empty:
        return pd.DataFrame()
    d["조정"] = np.where(d["diff"] > 0, "상향", np.where(d["diff"] < 0, "하향", "신청대로"))
    cols = [f"내용_{n}" for n in KMRB_ITEMS]
    out = d.groupby("조정")[cols].mean().T
    out.index = KMRB_ITEMS
    return out.reindex(columns=[c for c in ["신청대로", "상향", "하향"] if c in out.columns])


# ───────────────────────────────────────── 화면4 매체 비교
def media_frame(k: pd.DataFrame, g: pd.DataFrame, threshold: int = 3):
    """두 매체를 같은 모양으로 맞춘다. compare_media.py 의 load() 와 같은 규칙."""
    k = k[k["kindName"].astype(str) != "성인물"].dropna(subset=["grade_age"])
    kk = pd.DataFrame({"media": "영상물",
                       "is_youth_restricted": k["grade_age"].astype(int).ge(18).astype(int).values,
                       "sub": k["kindName"].astype(str).values})
    for name in COMPARABLE:
        kk[name] = (k[f"내용_{name}"] >= threshold).astype("Int64").values
    other_k = (k[[f"내용_{n}" for n in KMRB_OTHER]] >= threshold).any(axis=1).values
    kk = kk[~other_k].dropna(subset=COMPARABLE)

    g = g[~g["is_canceled"]].dropna(subset=["grade_age"])
    gg = pd.DataFrame({"media": "게임물",
                       "is_youth_restricted": g["grade_age"].astype(int).ge(18).astype(int).values,
                       "sub": g["platform"].astype(str).values})
    for name in COMPARABLE:
        gg[name] = g[f"내용_{name}"].astype("Int64").values
    other_g = g[[f"내용_{n}" for n in GRAC_OTHER]].sum(axis=1).gt(0).values
    gg = gg[~other_g].dropna(subset=COMPARABLE)

    both = pd.concat([kk, gg], ignore_index=True)
    both["n"] = both[COMPARABLE].sum(axis=1)
    both["combo"] = both[COMPARABLE].apply(
        lambda r: "+".join(n for n in COMPARABLE if r[n] == 1) or "(없음)", axis=1)
    info = {"영상물_비교표본": int(len(kk)), "게임물_비교표본": int(len(gg)),
            "영상물_제외": int(other_k.sum()), "게임물_제외": int(other_g.sum()),
            "기준": threshold}
    return both, info


def hold_rate(both: pd.DataFrame) -> pd.DataFrame:
    """항목별 보유율. 이 값 자체가 다른 것은 매체의 성격 차이다."""
    rows = []
    for name in COMPARABLE:
        rows.append({"항목": name,
                     "영상물": float(both.loc[both["media"] == "영상물", name].mean()),
                     "게임물": float(both.loc[both["media"] == "게임물", name].mean())})
    out = pd.DataFrame(rows)
    out["차이"] = out["게임물"] - out["영상물"]
    return out


def combo_compare(both: pd.DataFrame, min_n: int = 50) -> pd.DataFrame:
    """보유 조합이 완전히 같은 건끼리만 비교한다."""
    rows = []
    for combo, sub in both.groupby("combo"):
        st = sub.groupby("media")["is_youth_restricted"].agg(["size", "mean"])
        if len(st) < 2 or st["size"].min() < min_n:
            continue
        a, b = st.loc["영상물"], st.loc["게임물"]
        rows.append({"조합": combo, "영상물 n": int(a["size"]), "영상물": float(a["mean"]),
                     "게임물 n": int(b["size"]), "게임물": float(b["mean"]),
                     "차이": float(b["mean"] - a["mean"])})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("차이", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def solo_compare(both: pd.DataFrame, min_n: int = 30) -> pd.DataFrame:
    """항목 하나만 가진 건으로 비교한다. 다른 항목이 섞이지 않아 그 항목의 무게가 그대로 보인다."""
    solo, rows = both[both["n"] == 1], []
    for name in COMPARABLE:
        st = solo[solo[name] == 1].groupby("media")["is_youth_restricted"].agg(["size", "mean"])
        if len(st) < 2 or st["size"].min() < min_n:
            continue
        a, b = st.loc["영상물"], st.loc["게임물"]
        rows.append({"항목": name, "영상물 n": int(a["size"]), "영상물": float(a["mean"]),
                     "게임물 n": int(b["size"]), "게임물": float(b["mean"]),
                     "차이": float(b["mean"] - a["mean"])})
    return pd.DataFrame(rows)


# ───────────────────────────────────────── 화면5 누가 매기는가
def rater_period(g: pd.DataFrame, s: pd.DataFrame):
    """비교군은 약 7주치 스냅숏뿐이다. 위원회 쪽을 같은 기간으로 잘라야 물량이 비교된다."""
    lo, hi = s["rated_date"].min(), s["rated_date"].max()
    return g[g["rated_date"].between(lo, hi)], lo, hi


def rater_volume(g: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    same, _, _ = rater_period(g, s)
    n_a, n_s = len(same), len(s)
    tot = n_a + n_s
    return pd.DataFrame({
        "구분": ["위원회 심의", "자체등급분류"],
        "건수": [n_a, n_s],
        "비중": [n_a / tot if tot else 0.0, n_s / tot if tot else 0.0],
    })


def rater_grade(g: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    same, _, _ = rater_period(g, s)
    a = same["givenrate"].astype(str).value_counts(normalize=True)
    b = s["grade"].astype(str).value_counts(normalize=True)
    out = pd.DataFrame({"위원회": a, "자체등급분류": b}).fillna(0.0)
    order = [x for x in GAME_ORDER if x in out.index]
    return out.reindex(order + [i for i in out.index if i not in order])


def rater_content(g: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """항목별 보유율. 사행성이 어디에 몰려 있는지가 이 화면의 핵심이다."""
    same, _, _ = rater_period(g, s)
    rows = {n: [float(same[f"내용_{n}"].mean()), float(s[f"내용_{n}"].mean())] for n in GRAC_ITEMS}
    out = pd.DataFrame(rows, index=["위원회", "자체등급분류"]).T
    out.loc["(내용정보 없음)"] = [float((~same["has_descriptor"].astype(bool)).mean()),
                            float((~s["has_descriptor"].astype(bool)).mean())]
    return out


# ───────────────────────────────────────── 자가 점검
def main() -> None:
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError):
        pass
    k, g, s = load("kmrb"), load("grac"), load("self")
    print(f"영상물 {len(k):,} / 게임물 {len(g):,} / 비교군 {len(s):,}")

    print("\n[화면1] 최고값 규칙 일치율")
    print(rule_match(k).to_string(index=False))

    cov = reason_coverage(k)
    print(f"\n[화면2] 결정사유 기록 {cov['기록건수']:,}건 ({cov['기록률']:.1%}), "
          f"{cov['시작']}~{cov['끝']}")
    print(reason_by_kind(k).round(3).to_string())

    print("\n[화면3] 신청 대비 조정")
    print(adjust_summary(k).to_string(index=False))

    both, info = media_frame(k, g, 3)
    print(f"\n[화면4] 비교표본 영상물 {info['영상물_비교표본']:,} / 게임물 {info['게임물_비교표본']:,}")
    cc = combo_compare(both)
    print(cc.round(3).to_string(index=False))
    if len(cc):
        print(f"  조합 {len(cc)}개 평균 차이 {cc['차이'].mean() * 100:+.1f}%p, "
              f"게임물이 더 엄한 조합 {(cc['차이'] > 0).sum()}개")
    print(solo_compare(both).round(3).to_string(index=False))

    print("\n[화면5] 같은 기간 물량")
    print(rater_volume(g, s).to_string(index=False))


if __name__ == "__main__":
    main()
