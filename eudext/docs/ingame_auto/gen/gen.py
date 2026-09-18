"""classification.json / classification.md 생성 (dbg_plan 전용)."""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from common import CATS  # noqa: E402
import items_ab, items_cd1, items_d2, items_ef, items_port1, items_rv, items_mem  # noqa: E402

EUDEXT = items_ab.ITEMS + items_cd1.ITEMS + items_d2.ITEMS + items_ef.ITEMS
PORT = items_port1.ITEMS + items_rv.ITEMS + items_mem.ITEMS
ALL = EUDEXT + PORT

ids = [x["id"] for x in ALL]
dup = [k for k, v in collections.Counter(ids).items() if v > 1]
assert not dup, dup

import plan  # noqa: E402

_known = set(ids)
assert not (set(plan.PLAN) - _known), set(plan.PLAN) - _known
assert not (set(plan.SEPARATE) - _known), set(plan.SEPARATE) - _known
for _x in ALL:
    _x["phase"] = None
    if _x["id"] in plan.PLAN:
        _x["bundle"], _x["phase"] = plan.PLAN[_x["id"]]
        assert _x["category"] not in ("CRASH_RISK", "MULTI"), _x["id"]
        _pname = {p[0]: p[1].split(" ")[0] for p in plan.PHASES}[_x["phase"]]
        _x["done_marker"] = "통합 맵: aa.%s.end > 0 (phase %d 끝 프레임). 원래 맵 기준(프레임은 phase 시작부터 셈): %s" % (
            _pname, _x["phase"], _x["done_marker"])
    elif _x["id"] in plan.SEPARATE:
        _x["bundle"] = plan.SEPARATE[_x["id"]]
    assert "A_calc" not in _x["bundle"] and "B_shape" not in _x["bundle"], (_x["id"], _x["bundle"])


def group(it):
    return "eudext" if it in EUDEXT else "이식판"


def counts(items):
    c = collections.Counter(x["category"] for x in items)
    return [c.get(k, 0) for k in CATS]


def any_auto(x):
    return x["category"] in ("AUTO", "AUTO_ASSIST")


def auto_part(x):
    return x["category"] in ("AUTO", "AUTO_ASSIST") or "AUTO" in x["extra"] or "AUTO_ASSIST" in x["extra"]


def stats(items):
    n = len(items)
    a = sum(1 for x in items if x["category"] == "AUTO")
    aa = sum(1 for x in items if any_auto(x))
    ap = sum(1 for x in items if auto_part(x))
    risk = sum(1 for x in items if x["category"] == "CRASH_RISK" or "CRASH_RISK" in x["extra"])
    return n, a, aa, ap, risk


def pct(a, n):
    return "%d (%.0f%%)" % (a, 100.0 * a / n) if n else "0"


def esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def main():
    with open(os.path.join(OUT, "classification.json"), "w", encoding="utf-8") as f:
        json.dump(ALL, f, ensure_ascii=False, indent=1)

    lines = []
    lines.append("| 묶음 | 항목 수 | " + " | ".join(CATS) + " |")
    lines.append("|---|---|" + "---|" * len(CATS))
    req = [x for x in EUDEXT if x["required"]]
    for name, items in (("eudext 전체", EUDEXT), ("└ eudext 필수 47", req), ("이식판 전체", PORT),
                        ("└ UE_RE", items_port1.ITEMS[:19]), ("└ theSeed", items_port1.ITEMS[19:]),
                        ("└ Respect V", items_rv.ITEMS), ("└ Memory 2", items_mem.ITEMS[:17]),
                        ("└ Memory 1", items_mem.ITEMS[17:]), ("합계", ALL)):
        lines.append("| %s | %d | %s |" % (name, len(items), " | ".join(str(c) for c in counts(items))))
    lines.append("")
    lines.append("| 묶음 | 주 분류 AUTO | AUTO + AUTO_ASSIST | 자동 판정이 일부라도 있음(보조 포함) | 튕김 위험 표시(주·보조) |")
    lines.append("|---|---|---|---|---|")
    for name, items in (("eudext", EUDEXT), ("eudext 필수", req), ("이식판", PORT), ("합계", ALL)):
        n, a, aa, ap, risk = stats(items)
        lines.append("| %s (%d) | %s | %s | %s | %d |" % (name, n, pct(a, n), pct(aa, n), pct(ap, n), risk))
    count_table = "\n".join(lines)

    tabs = []
    for cat in CATS:
        rows = [x for x in ALL if x["category"] == cat]
        tabs.append("### %s (%d)\n" % (cat, len(rows)))
        tabs.append("| ID | 절 | 맵 | 보조 | 판정(기대) | 완료 표식 | bundle | phase |")
        tabs.append("|---|---|---|---|---|---|---|---|")
        for x in rows:
            idt = x["id"] + (" **[필수]**" if x["required"] else "")
            tabs.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                idt, esc(x["doc_section"]), esc(x["map"]), esc(", ".join(x["extra"])),
                esc(x["expect"]), esc(x["done_marker"]), esc(x["bundle"]),
                "" if x["phase"] is None else x["phase"]))
        tabs.append("")
    cat_tables = "\n".join(tabs)

    risk_rows = ["| ID | 주 분류 | 맵 | 왜 위험한가 |", "|---|---|---|---|"]
    for x in ALL:
        if x["category"] == "CRASH_RISK" or "CRASH_RISK" in x["extra"]:
            risk_rows.append("| %s | %s | %s | %s |" % (x["id"], x["category"], esc(x["map"]),
                                                       esc(x["risk"] or x["notes"])))
    risk_table = "\n".join(risk_rows)

    ph = ["| phase | 이름 | 프레임 창 | 원래 맵 | 항목 | 주 분류(수) | 비고 |", "|---|---|---|---|---|---|---|"]
    for num, name, frames, src, note in plan.PHASES:
        rows = [x for x in ALL if x["phase"] == num]
        cc = collections.Counter(x["category"] for x in rows)
        ph.append("| %d | `%s` | %s | %s | %s | %s | %s |" % (
            num, name, frames, src, ", ".join(x["id"] for x in rows),
            ", ".join("%s %d" % (k, cc[k]) for k in CATS if cc.get(k)), esc(note)))
    inside = [x for x in EUDEXT if x["phase"] is not None]
    core = [x for x in inside if x["phase"] <= 18]
    ph.append("")
    ph.append("통합 맵에 들어간 eudext 항목 %d개 (필수 %d) — 기다리기만 하는 구간(phase 1~18) %d개, 선택 구간(19 assist, 20 visual) %d개. "
              "주 분류: %s. 이 가운데 주 분류 VISUAL 인 %d개는 '값은 자동, 화면은 사람' 으로 나눈 것." % (
                  len(inside), sum(1 for x in inside if x["required"]), len(core), len(inside) - len(core),
                  ", ".join("%s %d" % (k, v) for k, v in zip(CATS, counts(inside)) if v),
                  sum(1 for x in inside if x["category"] == "VISUAL")))
    phase_table = "\n".join(ph)

    outside = collections.OrderedDict()
    for x in EUDEXT:
        if x["phase"] is None:
            outside.setdefault(x["bundle"], []).append(x)
    ot = ["| 넣지 않는 곳(bundle) | 항목 | 주 분류 |", "|---|---|---|"]
    for b, rows in outside.items():
        ot.append("| %s | %s | %s |" % (esc(b), ", ".join(x["id"] + ("*" if x["required"] else "") for x in rows),
                                         ", ".join(sorted({x["category"] for x in rows}))))
    ot.append("")
    ot.append("(* = 필수) 통합 맵 밖 eudext 항목 %d개." % sum(len(v) for v in outside.values()))
    outside_table = "\n".join(ot)

    with open(os.path.join(OUT, "gen", "body.md"), encoding="utf-8") as f:
        body = f.read()
    md = (body.replace("{{COUNTS}}", count_table)
              .replace("{{PHASETABLE}}", phase_table)
              .replace("{{OUTSIDE}}", outside_table)
              .replace("{{CATTABLES}}", cat_tables)
              .replace("{{RISKTABLE}}", risk_table))
    with open(os.path.join(OUT, "classification.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print(count_table)
    print("eudext", len(EUDEXT), "port", len(PORT), "all", len(ALL))


if __name__ == "__main__":
    main()
