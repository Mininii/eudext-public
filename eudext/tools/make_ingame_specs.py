"""인게임 자동 판정 명세를 만든다 — `examples/auto_all_spec.json` 과 `examples/ingame_specs/*.json` (DESIGN 5.5).

    python eudext/tools/make_ingame_specs.py [--out-dir <폴더>] [--check]

- 항목 **id 는 확인 문서 번호와 같다**(A-1, B10-2, D17-4 …) — 사용자 확인 문서(`EUDPLIB_PORT_CHECKLIST.md`)의 결과 칸에
  그대로 쓸 수 있고 `ingame_auto.py --write-checklist` 가 그 행을 찾는다.
- 기대값·읽을 값 설명은 `docs/ingame_auto/classification.json`(분류 286항목)에서 그대로 옮긴다(`info`).
- 10진 출력(fmt) 기대 글은 원래 확인 맵 `show()` 소스에서 뽑는다(`examples/auto_all/aa_fmt.py` — 맵 쪽과 같은 함수).
- `--check` 는 파일을 쓰지 않고 `tools/ingame_auto.py` 의 명세 검사만 돌린다.

맵 이름(`map`)은 `dbg.setup(map_name=…)` 과 같아야 한다. auto_all 은 `00_auto_all`, 계측판은 `tools/ingame_maps.py` 의
번호·이름(`<번호>_<이름>`)이다(eds 의 `[main] output` 파일 이름 = 기본 맵 이름).
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
EX = os.path.join(PKG, "examples")
PHASE_DIR = os.path.join(EX, "auto_all")
SPEC_DIR = os.path.join(EX, "ingame_specs")
CLASSIFICATION = os.path.join(PKG, "docs", "ingame_auto", "classification.json")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if PHASE_DIR not in sys.path:
    sys.path.insert(0, PHASE_DIR)

import aa_fmt  # noqa: E402 — examples/auto_all/aa_fmt.py (eudplib 없이 도는 순수 파이썬)

AUTO_ALL_MAP = "00_auto_all"
M32 = 0xFFFFFFFF

# 단계(phase 번호, 이름, 제목, 제한 시간 초, 선택 여부, 제한 사이클) — auto_all.eps·aa_common.PHASES 와 같다
# 시간은 터보([eudTurbo]) 기준이다: 한 사이클 = 한 프레임, 초당 약 24사이클. 제한 사이클은 "프레임 창 + 여유",
# 제한 시간은 그것을 24로 나눈 뒤 넘게 잡았다(터보가 붙지 않은 판은 시간 초과로 끝나며 이유가 설명에 붙는다)
SUITES = [
    (1, "units", "유닛 생성·칸 번호·새 유닛 순회·죽음 (B10)", 60, False, 200),
    (2, "pool", "오브젝트 풀 사슬 적재·넘침·순회 (C11)", 60, False, 200),
    (3, "switch", "스위치 표 주소 0x58DC40 (A-2)", 60, False, 300),
    (4, "s8", "SC 마스크 Subtract·Add 식 (A-1·B15-5)", 60, False, 100),
    (5, "datpatch", "dat 패치·피해 배율 표 (B15-1·3·10)", 60, False, 150),
    (6, "i64", "64비트 포화 뺄셈·비교·10진 (C3)", 60, False, 100),
    (7, "i64_ops", "64비트 곱셈·나눗셈·비트 (D4-1)", 60, False, 100),
    (8, "i128", "128비트 사칙·10진 (F20-1)", 60, False, 100),
    (9, "numfmt", "숫자 서식·이름 표 (D5-1·9·10)", 60, False, 100),
    (10, "cmp_cell", "안전 비교·Ccode (B1-1·C2-1)", 60, False, 100),
    (11, "mathx", "삼각·정수 수학 = CtrigAsm (C9-2)", 60, False, 150),
    (12, "players", "run_as·each 뒤 CP (B8-4)", 60, False, 100),
    (13, "plot", "도형 찍기 모양·속도·스케줄 (D7)", 120, False, 900),
    (14, "spawn", "G_CB 식 소환 패턴·로케이션 (A-3·E12)", 180, False, 1400),
    (15, "bullet", "총알 방향·칸·종류 교체 (D14)", 180, False, 1200),
    (16, "display", "DisplayPrint 대체 (E6)", 120, False, 900),
    (17, "chat", "타자기·채팅 줄 (D17)", 180, False, 2000),
    (18, "final", "몇 분 뒤 값 유지·CP (B15-4·C11-1)", 60, False, 100),
    (19, "assist", "사람 조작 — 채팅 한 줄 (D17-6·E6-2)", 120, True, 1800),
]


def _mark(name, **kw):
    return dict(kind="mark", name=name, **kw)


def _check(name, **kw):
    return dict(kind="check", name=name, **kw)


def _rec(name):
    """값만 기록하는 표식 (0 도 정상 — "사실 기록" 항목)."""
    return _mark(name, min=0)


def _group(ident, items, **kw):
    return dict(kind="group", id=ident, items=items, **kw)


def _fmt_expect(name):
    return aa_fmt.expect_text_of(os.path.join(EX, name))


# 프레임별 생성 수·좌표 배열의 기대값 (에뮬레이터 실측 = 트리거 계산 결과라 인게임도 같아야 한다)
PLOT_PF = [6, 6, 6, 1]
PLOT_PG = [6, 6, 6, 1]
PLOT_PS = [1, 1, 1, 3, 3, 3, 5, 5, 7, 5, 5, 3, 3, 3, 1, 1, 1]
SPAWN_HYDRA = [11, 6, 8, 4, 4, 8, 9, 4, 3, 4, 9, 3]
SPAWN_OBS = SPAWN_HYDRA * 3
SPAWN_SPIRAL = [6, -31, 47, -42, 95, -10, 110, 63, 65, 146, -39, 187, -166, 149, -254, 26, -249, -143, -130, -292]
D14_1_FACE = [128, 160, 192, 224, 0, 32, 64, 96]
D14_2_FACE = [128, 159, 192, 224, 0, 31, 64, 96]
RATIO_A, RATIO_B = 0x515BA0, 0x515B9C


def auto_all_items():
    """{항목 id: (phase 또는 None, [명세 항목])} — auto_all 에 들어가는 eudext 항목 91개."""
    it = {}

    # ---------------- phase 1 units (B10, B15-3)
    it["B10-1"] = (1, [_group("B10-1", [_mark("units.T4.ok1", equals=1), _mark("units.T4.ok2", equals=0),
                                        _check("units.B10-1.head")], checklist=True)])
    it["B10-2"] = (1, [_group("B10-2", [_mark("units.T1.ok", equals=1), _mark("units.T1.type", equals=0),
                                        _mark("units.T1.owner", equals=0), _mark("units.T1.order", min=1),
                                        _check("units.B10-2.idx"), _rec("units.T1.head0"), _rec("units.T1.head1"),
                                        _rec("units.T1.uniq"), _rec("units.T1.headdown")], checklist=True)])
    # 2026-09-18 인게임: 빈 칸 목록은 번호가 줄어드는 쪽(머리 1635 → 1634)이라 칸 걸음은 절대값으로 적는다(맵 stepAbs).
    it["B10-3"] = (1, [_group("B10-3", [_mark("units.T2.ok", equals=1), _mark("units.T2.type", equals=3),
                                        _mark("units.T2.subtype", equals=4), _mark("units.T2.headstep", equals=2),
                                        _mark("units.T2.subnext", equals=1), _rec("units.T2.subidx")],
                              checklist=True)])
    it["B10-4"] = (1, [_group("B10-4", [_mark("units.T3.ok", equals=1), _mark("units.T3.headstep", equals=3)],
                              checklist=True)])
    # F1 = 첫 프레임에 보이는 새 유닛. 2026-09-18 인게임은 2(파이어뱃 + T1 마린) — 미리 놓인 맵 리빌러 64기는 칸을 차지하지만
    # (머리 1635 = 1700 − 65) `EUDLoopNewUnit` 순회에 나오지 않는다. 에뮬레이터 모델은 66. 두 값을 다 받는다.
    it["B10-5"] = (1, [_group("B10-5", [_mark("units.B10-5.F1", min=2, max=68), _mark("units.B10-5.F2", min=1, max=2),
                                        _mark("units.B10-5.F3", equals=3), _mark("units.B10-5.F4", equals=1),
                                        _mark("units.B10-5.F5", equals=0), _mark("units.B10-5.F6", equals=1),
                                        _mark("units.B10-5.F7", equals=1), _mark("units.B10-5.F8", equals=0),
                                        _mark("units.B10-5.F9", equals=0), _mark("units.B10-5.F10", equals=0),
                                        _mark("units.B10-5.F11", equals=0), _mark("units.B10-5.F12", equals=0)],
                              checklist=True)])
    it["B10-6"] = (1, [_group("B10-6", [_mark("units.T6.order0", min=1), _rec("units.T6.hp0"),
                                        _rec("units.T6.sprite0"), _mark("units.T8.slot", min=1),
                                        _mark("units.T8.killslot", min=1), _rec("units.T8.front"),
                                        _mark("units.T10.ccdeaths", equals=1)], checklist=True)])
    it["B10-7"] = (1, [_group("B10-7", [_rec("units.T8.uniq0"), _rec("units.T8.uniq1"), _rec("units.T8.front")],
                              checklist=True)])
    it["B10-8"] = (1, [_group("B10-8", [_mark("units.T7.deadF8", equals=6), _mark("units.T10.ccdeaths", equals=1),
                                        _mark("units.T10.mark", equals=0), _mark("units.T10.tag", equals=0),
                                        _mark("units.T10.dead", min=7)], checklist=True)])
    it["B10-10"] = (1, [_group("B10-10", [_mark("units.T11.ok", equals=1), _mark("units.T11.timer", equals=0)],
                               checklist=True)])
    it["B15-3"] = (1, [_group("B15-3", [_mark("units.B15-3.found", equals=1), _mark("units.B15-3.hp1", min=1),
                                        _mark("units.B15-3.hp30", min=1),
                                        _mark("units.B15-3.max1", equals=100 * 256)], checklist=True)])

    # ---------------- phase 2 pool (C11-1~7)
    pool = {"C11-1": ["pool.C11-1.visits", "pool.C11-1.frame", "pool.C11-1.bad"],
            "C11-2": ["pool.C11-2.count", "pool.C11-2.dropped"],
            "C11-3": ["pool.C11-3.F3", "pool.C11-3.F4", "pool.C11-3.F5", "pool.C11-3.F6", "pool.C11-3.bad"],
            "C11-4": ["pool.C11-4.g1", "pool.C11-4.g0", "pool.C11-4.al1", "pool.C11-4.al2", "pool.C11-4.ix",
                      "pool.C11-4.sum"],
            "C11-5": ["pool.C11-5.count"],
            "C11-6": ["pool.C11-6.visits", "pool.C11-6.bad"],
            "C11-7": ["pool.C11-7.visits", "pool.C11-7.count"]}
    expect = {"pool.C11-2.count": 36, "pool.C11-2.dropped": 1, "pool.C11-3.F3": 1234, "pool.C11-3.F4": 1234,
              "pool.C11-3.F5": 1345, "pool.C11-3.F6": 345, "pool.C11-3.bad": 0, "pool.C11-4.g1": 99,
              "pool.C11-4.g0": 11, "pool.C11-4.al1": 1, "pool.C11-4.al2": 0, "pool.C11-4.ix": 1,
              "pool.C11-4.sum": 132, "pool.C11-5.count": 10, "pool.C11-6.bad": 0, "pool.C11-7.visits": 1,
              "pool.C11-7.count": 0, "pool.C11-1.bad": 0}
    for cid, names in pool.items():
        subs = [_check("pool.%s.ok" % cid)]
        for n in names:
            subs.append(_mark(n, equals=expect[n]) if n in expect else _mark(n, min=1))
        it[cid] = (2, [_group(cid, subs, checklist=True)])
    # C11-1 은 "여러 프레임 동안 유지" 라 phase 18(final)에서 한 번 더 본다 (같은 확인 문서 행 — 둘 다 통과해야 통과).
    # 키의 "#단계" 는 같은 항목을 다른 단계에도 두기 위한 표시다(id 는 앞부분만 쓴다)
    it["C11-1#final"] = (18, [_group("C11-1", [_check("final.C11-1.ok"), _mark("final.C11-1.visits", min=1),
                                               _mark("final.C11-1.bad", equals=0)], checklist=True)])

    # ---------------- phase 3 switch (A-2)
    it["A-2"] = (3, [_group("A-2", [_check("switch.A-2.w0"), _check("switch.A-2.w1"), _check("switch.A-2.cond1"),
                                    _check("switch.A-2.cond2"), _mark("switch.A-2.w0", equals=0x80000005),
                                    _mark("switch.A-2.w1", equals=0x81), _mark("switch.A-2.cond1", equals=1),
                                    _mark("switch.A-2.cond2", equals=1)], checklist=True)])

    # ---------------- phase 4 s8 (A-1, B15-5)
    got = ["S1", "S2", "S3", "S4", "S5", "X1", "X2", "X3", "P1", "P2", "P3", "F1", "E1", "E2", "E3", "E4", "E5"]
    subx = ["A", "A2", "Av", "C", "B", "Bw", "D"]
    addx = ["M", "Mu", "Mn"]
    it["A-1"] = (4, [_group("A-1", [_mark("s8.SUBX.match", min=1), _mark("s8.ADDX.match", min=1)]
                            + [_rec("s8." + n) for n in got]
                            + [_rec("s8.SUBX." + k) for k in subx] + [_rec("s8.ADDX." + k) for k in addx],
                            checklist=True)])
    it["B15-5"] = (4, [_group("B15-5", [_mark("s8.SUBX.match", mask=2, equals=2),
                                        _mark("s8.ADDX.match", mask=1, equals=1)], checklist=True)])

    # ---------------- phase 5 datpatch (B15-1·10) + 18 final (B15-4)
    it["B15-1"] = (5, [_group("B15-1", [_check("datpatch.B15-1.found"),
                                        _mark("datpatch.B15-1.start", in_=[RATIO_A, RATIO_B]),
                                        dict(kind="dwords", name="datpatch.B15-1.dump")], checklist=True)])
    it["B15-10"] = (5, [_group("B15-10", [_check("datpatch.B15-10.req"), _mark("datpatch.B15-10.req0", equals=0),
                                          _mark("datpatch.B15-10.req1", equals=0)], checklist=True)])
    it["B15-4"] = (18, [_group("B15-4", [_check("final.B15-4.keep"), _mark("final.B15-4.time", equals=777),
                                         _mark("final.B15-4.supply", equals=7),
                                         _mark("final.B15-3.max", equals=100 * 256),
                                         _mark("datpatch.B15-4.time", equals=777, suite="datpatch"),
                                         _mark("datpatch.B15-4.supply", equals=7, suite="datpatch")],
                                checklist=True)])

    # ---------------- phase 6~11 값 모듈
    it["C3-1"] = (6, [_group("C3-1", [_check("i64.C3-1.sub"), _mark("i64.C3-1.raw1", equals=0),
                                      _mark("i64.C3-1.raw2", equals=0),
                                      _mark("i64.C3-1.raw3", equals=0x7FFFFFFF)], checklist=True)])
    it["C3-2"] = (6, [dict(kind="check", id="C3-2", name="i64.C3-2.res", total=13, checklist=True)])
    it["C3-3"] = (6, [_group("C3-3", [dict(kind="result", name="i64.C3-3.all", total=23),
                                      dict(kind="text", name="i64.C3-3.fmt",
                                           equals=_fmt_expect("i64_ingame.eps"))], checklist=True)])
    it["D4-1"] = (7, [_group("D4-1", [dict(kind="result", name="i64_ops.D4-1.all", total=56),
                                      dict(kind="text", name="i64_ops.D4-1.fmt",
                                           equals=_fmt_expect("i64_ops_ingame.eps"))], checklist=True)])
    it["F20-1"] = (8, [_group("F20-1", [dict(kind="result", name="i128.F20-1.all", total=46),
                                        dict(kind="text", name="i128.F20-1.fmt",
                                             equals=_fmt_expect("i128_ingame.eps"))], checklist=True)])
    it["D5-1"] = (9, [_group("D5-1", [dict(kind="result", name="numfmt.D5-1.all", total=23),
                                      _check("numfmt.D5-1.ok"), _mark("numfmt.D5-1.lastbad", equals=0),
                                      _mark("numfmt.D5-1.cells", equals=1)], checklist=True)])
    it["D5-9"] = (9, [_group("D5-9", [_check("numfmt.D5-9.same"), dict(kind="text", name="numfmt.D5-9.name20"),
                                      dict(kind="text", name="numfmt.D5-9.eudplib", offset=3),
                                      _rec("numfmt.D5-9.color")], checklist=True)])
    # D5-10(약 31,000 트리거 프레임의 시간)은 단계 창이 3프레임이라 벽시계로 잴 수 없다 → 맵 전체 프레임/초 + 사람
    it["D5-10"] = (None, [_group("D5-10", [dict(kind="wall", metric="fps", min=1),
                                           dict(kind="manual",
                                                expect="numfmt 프레임(약 31,000 트리거)에서 눈에 띄는 멈춤이 있는지 — "
                                                       "단독 수치가 필요하면 16 맵을 따로 연다")], checklist=True)])
    it["B1-1"] = (10, [dict(kind="result", id="B1-1", name="cmp_cell.B1-1", total=15, checklist=True)])
    it["C2-1"] = (10, [dict(kind="result", id="C2-1", name="cmp_cell.C2-1", total=18, checklist=True)])
    mathx_groups = (("lengthdir", 19), ("rotate", 12), ("atan2", 37), ("div", 18), ("int", 24))
    it["C9-2"] = (11, [_group("C9-2", [dict(kind="result", name="mathx.C9-2.all", total=110)]
                              + [dict(kind="result", name="mathx.C9-2." + n, total=t) for n, t in mathx_groups]
                              + [_mark("mathx.C9-2.sample_c", equals=70), _mark("mathx.C9-2.sample_s", equals=70),
                                 _mark("mathx.C9-2.sample_a", equals=46), _mark("mathx.C9-2.sample_q", equals=9),
                                 _mark("mathx.C9-2.sample_nc", equals=0xFFFFFFAA),
                                 _mark("mathx.C9-2.sample_ns", equals=0xFFFFFFCF)], checklist=True)])

    # ---------------- phase 12 players (B8-4) + F19-1b 참고 기록
    it["B8-4"] = (12, [_group("B8-4", [_check("players.B8-4.cp"), _mark("players.B8-4.delta", equals=2),
                                       _mark("players.B8-4.loops", min=1)], checklist=True)])
    it["F19-1b"] = (12, [_group("F19-1b", [_rec("players.F19-1b.host"), _rec("players.human_mask"),
                                           _rec("players.is_human1")])])

    # ---------------- phase 13 plot (D7)
    # 2026-09-18 인게임: 몸집이 큰 공중 유닛(뮤탈·레이스·스카웃·커세어)은 만든 자리가 서로 겹치면 게임이 **밀어낸다**
    # (공중 충돌 끄기 NoAirCollision 을 쓰지 않으므로). 그래서 자리 판정은 점 간격(32px)보다 작은 스커지 플로터만 하고,
    # 밀린 수는 기록만 한다(posbad 102 → nudged). 생성 실패는 따로 센다(madebad).
    it["D7-1"] = (13, [_group("D7-1", [_check("plot.D7-1.pos"), _mark("plot.D7-1.posbad", equals=0),
                                       _mark("plot.D7-1.madebad", equals=0), _rec("plot.D7-1.nudged"),
                                       _mark("plot.D7-1.orderbad", equals=0), _mark("plot.D7-1.p2dx", equals=0),
                                       _mark("plot.D7-1.p2dy", equals=(-32) & M32)], checklist=True)])
    it["D7-2"] = (13, [_group("D7-2", [dict(kind="dwords", name="plot.D7-2.pF.seq", equals=PLOT_PF),
                                       dict(kind="dwords", name="plot.D7-2.pG.seq", equals=PLOT_PG),
                                       _mark("plot.D7-2.pF.span", equals=3), _mark("plot.D7-2.pG.span", equals=24),
                                       _mark("plot.D7-2.pF.n", equals=4),
                                       _mark("plot.D7-2.pG.n", equals=4)], checklist=True)])
    it["D7-3"] = (13, [_group("D7-3", [dict(kind="dwords", name="plot.D7-3.pS.seq", equals=PLOT_PS),
                                       _mark("plot.D7-3.pS.span", equals=64),
                                       _mark("plot.D7-3.pS.n", equals=17)], checklist=True)])
    it["D7-4"] = (13, [_group("D7-4", [_check("plot.D7-4.made"), _mark("plot.D7-4.rounds", equals=3),
                                       _mark("plot.D7-4.made", equals=211)], checklist=True)])
    it["D7-5"] = (13, [dict(kind="result", id="D7-5", name="plot.D7-5.all", total=15, checklist=True)])

    # ---------------- phase 14 spawn (A-3, E12, C11-9)
    it["A-3"] = (14, [_group("A-3", [_check("spawn.A-3.warp"), _mark("spawn.A-3.warp_x", equals=2731),
                                     _mark("spawn.A-3.warp_y", equals=2048),
                                     _mark("spawn.A-3.boss_pos_x", min=2699, max=2763),
                                     _mark("spawn.A-3.boss_pos_y", min=2016, max=2080),
                                     _mark("spawn.E12-4.mark_x", min=3381, max=3445),
                                     _mark("spawn.E12-4.mark_y", min=2016, max=2080)], checklist=True)])
    it["E12-1"] = (14, [_group("E12-1", [_check("spawn.E12-1.count"), _check("spawn.E12-1.overflow"),
                                         _check("spawn.E12-1.order"), _check("spawn.E12-1.pos"),
                                         _mark("spawn.E12-1.homes", equals=64), _mark("spawn.E12-1.expect", equals=64),
                                         _mark("spawn.E12-1.overflow", equals=0),
                                         _mark("spawn.E12-1.order_x", equals=2048),
                                         _mark("spawn.E12-1.order_y", equals=3413),
                                         _mark("spawn.E12-1.posbad", equals=0)], checklist=True)])
    it["C11-9"] = (14, [_group("C11-9", [_check("spawn.E12-1.count"), _check("spawn.E12-1.pos")], checklist=True)])
    it["E12-2"] = (14, [_group("E12-2", [_check("spawn.E12-2.count"), _check("spawn.E12-2.inv"),
                                         _check("spawn.E12-2.inv_off"), _mark("spawn.E12-2.parked", equals=73),
                                         _mark("spawn.E12-2.vis", equals=219),
                                         _mark("spawn.E12-2.live_at_gap", min=2),
                                         dict(kind="dwords", name="spawn.E12-2.hydra", equals=SPAWN_HYDRA),
                                         dict(kind="dwords", name="spawn.E12-2.obs", equals=SPAWN_OBS),
                                         _mark("spawn.E12-2.hydra_n", equals=12),
                                         _mark("spawn.E12-2.obs_n", equals=36)], checklist=True)])
    it["E12-3"] = (14, [_group("E12-3", [_check("spawn.E12-3.layers"), _check("spawn.E12-3.boss"),
                                         _check("spawn.E12-3.warp_pos"), _mark("spawn.E12-3.step12", equals=2),
                                         _mark("spawn.E12-3.step2", equals=2), _mark("spawn.E12-3.step3", equals=2),
                                         _mark("spawn.E12-3.boss", equals=1), _mark("spawn.E12-3.marks", equals=5),
                                         _mark("spawn.E12-3.warp_posbad", equals=0)], checklist=True)])
    it["E12-4"] = (14, [_group("E12-4", [_mark("spawn.E12-4.mark_x", min=3381, max=3445),
                                         _mark("spawn.E12-4.mark_y", min=2016, max=2080)], checklist=True)])
    it["E12-5"] = (14, [_group("E12-5", [dict(kind="dwords", name="spawn.E12-5.spiral",
                                              equals=[v & M32 for v in SPAWN_SPIRAL]),
                                         _mark("spawn.E12-5.n", equals=10)], checklist=True)])
    it["E12-6"] = (14, [_group("E12-6", [_check("spawn.E12-6.order"), _check("spawn.E12-6.gone"),
                                         _mark("spawn.E12-6.brood", equals=19),
                                         _mark("spawn.E12-6.order_x", equals=2048),
                                         _mark("spawn.E12-6.order_y", equals=2731)], checklist=True)])
    it["E12-7"] = (14, [_group("E12-7", [_check("spawn.E12-7.image"), _check("spawn.E12-7.gone"),
                                         _mark("spawn.E12-7.image", equals=546)], checklist=True)])
    it["E12-8"] = (14, [_group("E12-8", [dict(kind="result", name="spawn.E12-8.all", total=11),
                                         _mark("spawn.E12-8.live", equals=0)], checklist=True)])
    it["E12-9"] = (14, [_group("E12-9", [dict(kind="wall", metric="fps", min=1),
                                         dict(kind="wall", metric="max_gap_s", min=0)], checklist=True)])

    # ---------------- phase 15 bullet (D14)
    # 2026-09-18 인게임: 탄이 하나도 안 만들어졌다(19발 전부 실패). 원인 = 탄막 유닛 208·210·204 가 문·함정 = Building
    # 플래그라 CreateUnit 이 배치 상자(buildingDimensions)로 자리를 검사해 거절했다. BulletDat 이 bounds·placement 를
    # 쓰고 Building 을 끄도록 고쳤다. D14-0 은 그 dat 값과 대조 유닛(마린)을 기록해 다음 번에 원인을 바로 가른다.
    # 2026-09-18 1차: dat 는 다 들어갔는데도 탄 0발 → 배치 상자 가설은 아니다. 2차부터 [noAirCollision] 을 켜고
    # 공중 대조(ctlair = 같은 자리에 레이스)를 함께 기록한다 — 공중 쪽 자원 문제인지 208 종류 문제인지 가른다.
    it["D14-0"] = (15, [_group("D14-0", [_check("bullet.D14-0.made"), _mark("bullet.D14-0.ctl", equals=1),
                                         _rec("bullet.D14-0.ctlair"), _rec("bullet.D14-0.ctl208"),
                                         _rec("bullet.D14-0.b1"), _rec("bullet.D14-0.b2"), _rec("bullet.D14-0.b3"), _rec("bullet.D14-0.b4"), _rec("bullet.D14-0.b5"), _rec("bullet.D14-0.b6"), _rec("bullet.D14-0.b7"),
                                         _rec("bullet.D14-0.b8"), _rec("bullet.D14-0.b9"), _rec("bullet.D14-0.b10"), _rec("bullet.D14-0.se208"), _rec("bullet.D14-0.se0"), _rec("bullet.D14-0.gf208"), _rec("bullet.D14-0.gf0"), _rec("bullet.D14-0.av208"), _rec("bullet.D14-0.av0"),
                                         _mark("bullet.D14-0.fl208", equals=88),
                                         _mark("bullet.D14-0.spr106", equals=344),
                                         _mark("bullet.D14-0.wg127", equals=106),
                                         _mark("bullet.D14-0.elev", equals=20),
                                         _mark("bullet.D14-0.bdim", equals=1),   # 가로1 세로0 (CtrigAsm·UE_RE 값, 2026-09-18)
                                         _rec("bullet.D14-0.prop"), _rec("bullet.D14-0.bLT"),
                                         _rec("bullet.D14-0.bRB"), _rec("bullet.D14-0.head"),
                                         _rec("bullet.D14-0.head2"), _rec("bullet.D14-0.first")])])
    it["D14-1"] = (15, [_group("D14-1", [dict(kind="check", name="bullet.D14-1.facing", total=8),
                                         dict(kind="check", name="bullet.D14-1.dead", total=8),
                                         dict(kind="dwords", name="bullet.D14-1.face", equals=D14_1_FACE),
                                         dict(kind="dwords", name="bullet.D14-1.dead", equals=[1] * 8),
                                         _mark("bullet.D14-1.facingbad", equals=0),
                                         _mark("bullet.D14-1.hits", equals=8)], checklist=True)])
    it["D14-2"] = (15, [_group("D14-2", [dict(kind="check", name="bullet.D14-2.facing", total=8),
                                         dict(kind="check", name="bullet.D14-2.dead", total=8),
                                         _check("bullet.D14-2.near"), _check("bullet.D14-2.far"),
                                         _check("bullet.D14-2.near_hit"),
                                         dict(kind="dwords", name="bullet.D14-2.face", equals=D14_2_FACE),
                                         _mark("bullet.D14-2.near_facing", equals=109),
                                         _mark("bullet.D14-2.far_facing", equals=192),
                                         _rec("bullet.D14-2.far_dead"),
                                         _mark("bullet.D14-2.facingbad", equals=0)], checklist=True)])
    it["D14-4"] = (15, [_group("D14-4", [_check("bullet.D14-4.made"), _mark("bullet.D14-4.a", min=1),
                                         _mark("bullet.D14-4.b", min=1),
                                         _rec("bullet.D14-4.speed")], checklist=True)])
    it["D14-5"] = (15, [_group("D14-5", [_check("bullet.D14-5.pos"), _mark("bullet.D14-5.ax", equals=1000),
                                         _mark("bullet.D14-5.ay", equals=3400), _mark("bullet.D14-5.bx", equals=1200),
                                         _mark("bullet.D14-5.by", equals=3410)], checklist=True)])
    it["D14-6"] = (15, [_group("D14-6", [_check("bullet.D14-6.ue_re"), _mark("bullet.D14-6.count", equals=5),
                                         _mark("bullet.D14-6.a_a3", equals=0), _mark("bullet.D14-6.a_e4", equals=0),
                                         _rec("bullet.D14-6.a_dc"), _rec("bullet.D14-6.b_a3"),
                                         _rec("bullet.D14-6.b_dc"), _rec("bullet.D14-6.b_e4"),
                                         _rec("bullet.D14-6.selcount"),
                                         dict(kind="dwords", name="bullet.D14-6.pos"),
                                         dict(kind="dwords", name="bullet.D14-6.sel")], checklist=True)])
    it["D14-7"] = (15, [_group("D14-7", [_rec("bullet.D14-7.order1"), _rec("bullet.D14-7.type1"),
                                         _rec("bullet.D14-7.sprite1"), _rec("bullet.D14-7.order2"),
                                         _rec("bullet.D14-7.type2"), _rec("bullet.D14-7.sprite2")], checklist=True)])
    it["D14-8"] = (15, [_group("D14-8", [_check("bullet.D14-8.shell"),
                                         _mark("bullet.D14-8.shell", equals=210)], checklist=True)])
    it["D14-9"] = (15, [_group("D14-9", [_rec("bullet.D14-9.elev"), _rec("bullet.D14-9.dat")], checklist=True)])
    it["D14-13"] = (15, [dict(kind="manual", id="D14-13", checklist=True, expect="208 탄 모양이 UE_RE 와 같은가 (dat 값은 시험이 대조함)")])

    # ---------------- phase 16 display (E6)
    # 2026-09-18 인게임: E6-3(13번째 줄)·E6-4·E6-4b(TBL 쓰기)에서 EUD ERROR 로 멈췄다 → 통합 맵에서 뺐다.
    # 그 세 항목은 25_display_check 명세(other_specs)와 25b_display_bisect 에서만 판정한다. 자체 점검은 7 → 5.
    it["E6-8"] = (16, [_group("E6-8", [dict(kind="result", name="display.E6-8.all", total=5),
                                       _check("display.E6-8.ok"),
                                       _mark("display.E6-8.lastbad", equals=0)], checklist=True)])
    it["E6-5"] = (16, [_group("E6-5", [_check("display.E6-5.same"),
                                       dict(kind="text", name="display.E6-5.line",
                                            regex=r"같아야: (.+?) / \1 / \1 / \1")], checklist=True)])
    it["E6-9"] = (16, [_group("E6-9", [dict(kind="text", name="display.E6-9.line", contains="[E6-9] 긴 줄"),
                                       _mark("display.E6-9.len", min=219)], checklist=True)])
    it["E6-10"] = (16, [_group("E6-10", [_check("display.E6-10.pin"), _mark("display.E6-10.calls", min=60),
                                         _mark("display.E6-10.changes", min=3),
                                         _mark("display.E6-10.pinbad", equals=0),
                                         _mark("display.E6-10.slotchg", equals=0)], checklist=True)])

    # ---------------- phase 17 chat (D17)
    it["D17-1"] = (17, [_group("D17-1", [_check("chat.D17-1.reveal"),
                                         dict(kind="text", name="chat.D17-1.line",
                                              regex=r"^(?!.*!H).*가운데 정렬 — 한 글자씩: 가나다라마바사 ABC"),
                                         _mark("chat.D17-1.front10", min=5, max=11),
                                         _mark("chat.D17-1.front70", min=30)], checklist=True)])
    it["D17-2"] = (17, [_group("D17-2", [_check("chat.D17-2.same"),
                                         dict(kind="text", name="chat.D17-2.line1", contains="[D17-2] 첫째 줄"),
                                         dict(kind="text", name="chat.D17-2.line2", contains="[D17-2] 둘째 줄"),
                                         dict(kind="text", name="chat.D17-2.line3", contains="[D17-2] 셋째 줄"),
                                         _mark("chat.D17-2.front1", min=5)], checklist=True)])
    it["D17-3"] = (17, [_group("D17-3", [dict(kind="text", name="chat.D17-3.line",
                                              # 줄 끝이 잘려 마지막 글자가 깨지는 것은 봐준다(2026-09-18)
                                              regex=r"^[^�]*é ñ ü ß ç ø Ω")], checklist=True)])
    it["D17-4"] = (17, [_group("D17-4", [_check("chat.D17-4.nul"),
                                         dict(kind="text", name="chat.D17-4.line",
                                              regex=r": 0123456789AB(CD)?$"),
                                         _rec("chat.D17-4.slot"),
                                         _mark("chat.D17-4.nul", equals=1)], checklist=True)])
    it["D17-5"] = (17, [_group("D17-5", [_check("chat.D17-5.limit"), _mark("chat.D17-5.front", equals=52),
                                         dict(kind="text", name="chat.D17-5.line",
                                              regex=r"890123$")], checklist=True)])
    it["D17-7"] = (17, [_group("D17-7", [_check("chat.D17-7.pace"), _mark("chat.D17-7.front20", min=6, max=12),
                                         dict(kind="text", name="chat.D17-7.line",
                                              contains="[D17-7] 소리 판")], checklist=True)])
    it["D17-8"] = (17, [_group("D17-8", [_rec("chat.D17-8.gone")], checklist=True)])
    it["D17-9"] = (17, [_group("D17-9", [_check("chat.D17-9.speed"),
                                         _mark("chat.D17-9.delta", equals=20)], checklist=True)])

    # ---------------- phase 19 assist (선택)
    it["D17-6"] = (19, [_group("D17-6", [_check("assist.D17-6.relayed"),
                                         dict(kind="text", name="assist.D17-6.line"),   # 2026-09-18: 자판에 없는 글자를 못 치는 경우가 있다 — "무엇을 쳤는가" 대신 "중계된 글이 있는가"만 본다
                                         _rec("assist.D17-6.raw0"), _rec("assist.D17-6.raw4"),
                                         _rec("assist.D17-6.raw8"), _rec("assist.D17-6.marker"),
                                         _rec("assist.D17-6.lines")], checklist=True)])
    it["E6-2"] = (19, [_group("E6-2", [_check("assist.E6-2.pin"),
                                       _mark("assist.E6-2.pinbad", equals=0)], checklist=True)])

    # ---------------- phase 20 visual (사람 눈 — 판정 없음)
    visual = {
        "D5-2": "반각 [00042] [-1,234,567] [+0,001,234]",
        "D5-3": "전각 숫자 사이 빈틈 없음, 앞 0x0D 가 자리를 차지하지 않음",
        "D5-4": "자리마다 색 P6 갈색 … P1 빨강",
        "D5-5": "만 단위 색이 옛 DPS 화면과 같음",
        "D5-6": "[12.5] [1234.567] [막대 앞 3개 초록] [05]",
        "D5-7": "한자 글자·16진 표시",
        "D5-8": "0x0D 채움 고정 폭이 옛 DisplayPrint 와 같은 간격",
        "D6-1": "mcf 판 장식이 DPS강화하기·UE_RE 화면과 같음",
        "D6-2": "seed 판 장식이 theSeed·Stella_II 와 같음",
        "D6-3": "respect 판, \\x13 줄 가운데 정렬",
        "D6-4": "memory 판, \\r\\r 뒤 \\x13 가운데 정렬",
        "D6-5": "\\x13 두 번·오른쪽 정렬·줄바꿈 장식",
        "E6-7": "'|-10|1234만5678|12.5|42|42|' 대괄호 사이에 빈틈 없음",
        "E6-6": "임무 목표 창을 연 채로 카운터가 바뀌는지 (F10 → 임무 목표)",
    }
    for vid, text in visual.items():
        it[vid] = (None, [dict(kind="manual", id=vid, expect=text, checklist=True)])
    return it


def _fix_in(items):
    """`in_` 키를 명세의 `in` 으로 바꾼다(파이썬 예약어 회피)."""
    for x in items:
        if "in_" in x:
            x["in"] = x.pop("in_")
        if x.get("kind") == "group":
            _fix_in(x["items"])
    return items


def _info(cls, ident):
    e = cls.get(ident)
    if not e:
        return {}
    return {k: e[k] for k in ("read", "expect", "done_marker", "category", "doc_section", "required", "map", "bundle",
                              "notes", "risk", "extra", "instrument") if e.get(k) not in (None, [], "")}


def load_classification():
    with open(CLASSIFICATION, encoding="utf-8") as f:
        return {e["id"]: e for e in json.load(f)}


def auto_all_spec():
    cls = load_classification()
    items = auto_all_items()
    suites = {no: {"name": name, "phase": no, "title": title, "timeout_s": t, "timeout_cycles": c, "items": []}
              for no, name, title, t, _opt, c in SUITES}
    for no, _name, _title, _t, opt, _cycles in SUITES:
        if opt:
            suites[no]["optional"] = True
    map_items = []
    for key, (phase, specs) in items.items():
        ident = key.split("#")[0]
        specs = _fix_in([dict(x) for x in specs])
        for x in specs:
            x.setdefault("id", ident)
            x["info"] = _info(cls, ident)
        if phase is None:
            map_items.extend(specs)
        else:
            suites[phase]["items"].extend(specs)
    # 맵 전체 항목: 터보·정리·머리·벽시계
    map_items = [
        dict(kind="check", id="G-5", name="aa.turbo", checklist="G-5",
             info={"expect": "터보([eudTurbo])가 켜져 있어 24 사이클이 게임 프레임 24~40 안에 지난다 (인게임 G-1)"}),
        _mark("aa.turbo.frames", id="G-5.frames", min=1, max=40),
        dict(kind="check", id="clean.units", name="aa.clean.units"),
        dict(kind="check", id="clean.switch", name="aa.clean.switch"),
        dict(kind="check", id="clean.plot", name="aa.clean.plot"),
        dict(kind="check", id="clean.spawn", name="aa.clean.spawn"),
        dict(kind="check", id="clean.bullet", name="aa.clean.bullet"),
        # 남은 유닛 기록(판정 없음). n204 는 늘 1 이다 — shell 종류가 유닛 수 표에 남기는 자국(위 주석·aa_bullet.eps)
        dict(kind="mark", id="clean.n208", name="aa.clean.n208", min=0),
        dict(kind="mark", id="clean.n210", name="aa.clean.n210", min=0),
        dict(kind="mark", id="clean.n204", name="aa.clean.n204", min=0),
        dict(kind="mark", id="clean.nmar", name="aa.clean.nmar", min=0),
        dict(kind="check", id="clean.display", name="aa.clean.display"),
        dict(kind="check", id="cp", name="final.cp", suite="final"),
        _mark("aa.done", id="done", min=1),
        _rec("aa.assist.skipped"),
        dict(kind="hdr", id="local_player", field="local_player", max=131),
        dict(kind="wall", id="fps", metric="fps", min=1),
    ] + map_items
    return {
        "format": "eudext-ingame-spec",
        "version": 1,
        "map": AUTO_ALL_MAP,
        "title": "eudext 자동 점검 통합 맵 (안전한 항목 전부 — 약 4분 30초)",
        "done": ["aa.done"],
        # 터보 기준: 마지막 단계(assist)가 프레임 6400 에 끝난다 → 약 267초. 사이클 8000·벽시계 600초로 잡았다
        # (터보가 없으면 벽시계 쪽이 먼저 걸리고 "초당 사이클 …" 안내가 붙는다).
        "timeout_s": 600,
        "timeout_cycles": 8000,
        "stall_s": 20,
        "settle_cycles": 2,
        "checklist": [{"row": "00", "section": "확인 순서"}],
        "suites": [suites[no] for no, _n, _t, _s, _o, _c in SUITES],
        "items": map_items,
    }


# ---------------------------------------------------------------------------------------------
# 계측판(통합 맵 밖) 맵별 명세
# ---------------------------------------------------------------------------------------------


def other_specs():
    """{맵 이름: 명세} — 위험·소리·런처·키 조작·멀티 맵의 브리지 판정 부분."""
    cls = load_classification()

    def spec(map_name, title, items, done=None, timeout_s=300, suites=None, stall_s=None):
        doc = {"format": "eudext-ingame-spec", "version": 1, "map": map_name, "title": title,
               "timeout_s": timeout_s, "items": []}
        if done is not None:
            doc["done"] = done
        if stall_s:
            doc["stall_s"] = stall_s
        if suites:
            doc["suites"] = suites
        for ident, specs in items:
            for x in specs:
                x = dict(x)
                x.setdefault("id", ident)
                x["info"] = _info(cls, ident)
                doc["items"].append(x)
        return doc

    out = {}
    # 01 S8 (A-1·B15-5 — 통합 맵과 같은 시험을 단독 맵으로)
    got = ["S1", "S2", "S3", "S4", "S5", "X1", "X2", "X3", "P1", "P2", "P3", "F1", "E1", "E2", "E3", "E4", "E5"]
    out["01_S8_SubtractTest"] = spec(
        "01_S8_SubtractTest", "S8 마스크 Subtract·Add 식 (A-1)", [
            ("A-1", [_group("A-1", [_mark("m01.SUBX.match", min=1), _mark("m01.ADDX.match", min=1)]
                            + [_rec("m01." + n) for n in got], checklist=True)]),
            ("B15-5", [_group("B15-5", [_mark("m01.SUBX.match", mask=2, equals=2),
                                        _mark("m01.ADDX.match", mask=1, equals=1)], checklist=True)]),
        ], done=["done"], timeout_s=120)
    # 04 datpatch (B15-1·3·4·10 — 04 맵은 화면 줄이 없었다: 발견 ①)
    out["04_datpatch_check"] = spec(
        "04_datpatch_check", "dat 패치·피해 배율 표 (B15-1·3·4·10)", [
            ("B15-1", [_group("B15-1", [_check("m04.B15-1.found"), _mark("m04.B15-1.start", in_=[RATIO_A, RATIO_B]),
                                        dict(kind="dwords", name="m04.B15-1.dump")], checklist=True)]),
            ("B15-3", [_group("B15-3", [_mark("m04.B15-3.found", equals=1), _mark("m04.B15-3.hp", min=1),
                                        _mark("m04.B15-3.max", equals=100 * 256)], checklist=True)]),
            ("B15-4", [_group("B15-4", [_check("m04.B15-4.keep"), _mark("m04.B15-4.time", equals=777),
                                        _mark("m04.B15-4.supply", equals=7)], checklist=True)]),
            ("B15-10", [_group("B15-10", [_check("m04.B15-10.req"), _mark("m04.B15-10.req0", equals=0)],
                               checklist=True)]),
        ], done=["done"], timeout_s=300)
    # 27 X_limit (유닛 한도 — 튕길 위험 세션)
    out["27_X_limit"] = spec(
        "27_X_limit", "유닛 한도 채우기·칸 가득 총알 (B10-1(b)·B10-8·B10-9·D14-3·D14-2 출발=목표)", [
            ("B10-1", [_group("B10-1", [_mark("xl.t9.fill", min=1), _mark("xl.t9.ok", equals=0),
                                        _mark("xl.t9.ptr", equals=0), _mark("xl.t9.idx", min=1),
                                        _mark("xl.t9.head", min=1)], checklist=True)]),
            ("B10-8", [_group("B10-8", [_mark("xl.dying.limit", min=1),
                                        _rec("xl.dying.total")], checklist=True)]),
            ("B10-9", [_group("B10-9", [dict(kind="wall", metric="max_gap_s", min=0),
                                        dict(kind="wall", metric="fps", min=0.2)], checklist=True)]),
            ("D14-3", [_group("D14-3", [_check("xl.D14-3.zero"), _mark("xl.D14-3.e1", equals=0),
                                        _mark("xl.D14-3.e2", equals=0), _mark("xl.D14-3.e3", equals=0),
                                        _mark("xl.D14-3.fill", min=1)], checklist=True)]),
            ("D14-2", [_group("D14-2", [_mark("xl.D14-2.same", equals=128)], checklist=False)]),
        ], done=["done"], timeout_s=300, stall_s=30)
    # 08·22 pool (C11-8 멀티 — 같은 값들을 각 PC 에서)
    pool_items = [("C11-8", [_group("C11-8", [_check("m08.C11-%d.ok" % k) for k in range(1, 8)]
                                    + [_mark("m08.C11-1.bad", equals=0)], checklist=True)])]
    out["22_pool_multi"] = spec("22_pool_multi", "pool 멀티 (C11-8 — 모든 PC 에서 같은 판정)", pool_items,
                                done=["done"], timeout_s=300)
    out["08_pool_check"] = spec("08_pool_check", "pool 사슬 적재·넘침·순회 (C11-1~7 — 단독 판)", pool_items,
                                done=["done"], timeout_s=300)
    # 11 bgm (소리 — 값만 자동)
    out["11_bgm_check"] = spec(
        "11_bgm_check", "배경음악 (D16 — 값만 자동, 소리는 귀)", [
            ("D16-1", [_group("D16-1", [_rec("m11.step"), dict(kind="text", name="m11.patch")], checklist=True)]),
            ("D16-3", [_group("D16-3", [_rec("m11.pd_chunk"), _rec("m11.pe_chunk"), _rec("m11.pd_dt"),
                                        dict(kind="wall", metric="fps", min=0.2)], checklist=True)]),
            ("D16-4", [_group("D16-4", [_rec("m11.mute")], checklist=True)]),
            ("D16-5", [_group("D16-5", [_rec("m11.step"), dict(kind="wall", metric="fps", min=0.2)],
                              checklist=True)]),
            ("D16-7", [_group("D16-7", [_rec("m11.pd_chunk"), _rec("m11.player_s")], checklist=True)]),
        ], done=["done"], timeout_s=300)
    # 14 scrdb (런처)
    out["14_scrdb_check"] = spec(
        "14_scrdb_check", "SCR_DB 런처 연동 (D18 — loaded·saves 만 자동)", [
            ("D18-2", [_group("D18-2", [_mark("m14.loaded", equals=1)], checklist=True)]),
            ("D18-3", [_group("D18-3", [_mark("m14.saves", min=1)], checklist=True)]),
        ], done=["done"], timeout_s=600)
    # 17 exit_trap (위험)
    out["17_exit_trap_check"] = spec(
        "17_exit_trap_check", "나가면 멈춤 — 실험 기능 (F19-4, 위험)", [
            ("F19-4", [_group("F19-4", [_rec("m17.stage"), dict(kind="wall", metric="fps", min=0.2),
                                        dict(kind="hdr", field="local_player", max=131)], checklist=True)]),
        ], timeout_s=300, stall_s=30)
    # 18 sprite (위험)
    out["18_sprite_check"] = spec(
        "18_sprite_check", "28장 스프라이트·CGRP (F21, 위험 — 언리미터)", [
            ("F21-1", [_group("F21-1", [_mark("m18.dotMade", equals=16), _mark("m18.dotZero", equals=0),
                                        _mark("m18.bounceE", min=1)], checklist=True)]),
            ("F21-2", [_group("F21-2", [_mark("m18.stormE", min=1), _mark("m18.stormE2", min=1)], checklist=True)]),
            ("F21-3", [_group("F21-3", [_mark("m18.usE", min=1), _rec("m18.usDC"), _rec("m18.usE4"),
                                        _rec("m18.usMoving"), dict(kind="dwords", name="m18.sel")], checklist=True)]),
            ("F21-4", [_group("F21-4", [_rec("m18.scanLeft")], checklist=True)]),
            ("F21-5", [_group("F21-5", [_mark("m18.recE", min=1), _mark("m18.recE2", min=1),
                                        _rec("m18.marineX"), _rec("m18.marineY")], checklist=True)]),
            ("F21-6", [_group("F21-6", [_mark("m18.paintDone", equals=1), _mark("m18.drawn", equals=120),
                                        _mark("m18.dropped", equals=0)], checklist=True)]),
            ("F21-7", [_group("F21-7", [_rec("m18.userDone"), _rec("m18.userDrawn"), _rec("m18.userTotal"),
                                        _rec("m18.hdrW"), _rec("m18.hdrH")], checklist=True)]),
            ("F21-9", [_group("F21-9", [_mark("m18.fullZero", equals=1), _rec("m18.fillMade"),
                                        dict(kind="wall", metric="fps", min=0.2)], checklist=True)]),
        ], done=["done"], timeout_s=600, stall_s=30)
    # 20 players (멀티 — 각 PC 에서 리더 실행)
    out["20_players_check"] = spec(
        "20_players_check", "관전자·CP·사람 판정 (B8 — 각 PC 에서 리더 실행)", [
            ("B8-1", [_group("B8-1", [dict(kind="hdr", field="local_player", max=131),
                                      _rec("m20.contains_obs")], checklist=True)]),
            ("B8-5", [_group("B8-5", [_rec("m20.is_human1"), _rec("m20.human_mask")], checklist=True)]),
            ("B8-8", [_group("B8-8", [_mark("m20.contains_all", equals=1)], checklist=True)]),
        ], done=["done"], timeout_s=300)
    # 21 sync (키 조작)
    out["21_sync_check"] = spec(
        "21_sync_check", "동기화 입력 (B13 — 사람이 키를 누르고 브리지가 값을 기록)", [
            ("B13-1", [_group("B13-1", [dict(kind="wall", metric="fps", min=0.2),
                                        dict(kind="dwords", name="m21.score")], checklist=True)]),
            ("B13-2", [_group("B13-2", [dict(kind="dwords", name="m21.score"),
                                        _rec("m21.pulses")], checklist=True)]),
            ("B13-3", [_group("B13-3", [dict(kind="dwords", name="m21.held"),
                                        _rec("m21.level"), _rec("m21.typing")], checklist=True)]),
            ("B13-4", [_group("B13-4", [_rec("m21.mx"), _rec("m21.my"), _rec("m21.mouse_local")],
                              checklist=True)]),
            ("B13-5", [_group("B13-5", [_rec("m21.panel"), _rec("m21.f5_prints")], checklist=True)]),
            ("B13-6", [_group("B13-6", [_rec("m21.f5_prints"), _rec("m21.rclick_prints")], checklist=True)]),
            ("B13-8", [_group("B13-8", [dict(kind="dwords", name="m21.sel"), _rec("m21.sel_count")],
                              checklist=True)]),
            ("B13-9", [_group("B13-9", [dict(kind="wall", metric="seconds", min=1)], checklist=True)]),
        ], timeout_s=900, stall_s=30)
    # 23 misc (관전자 채팅·방장·와이드)
    out["23_misc_obs_check"] = spec(
        "23_misc_obs_check", "관전자 채팅·방장·와이드 (F19-1·1b·3·6)", [
            ("F19-1", [_group("F19-1", [dict(kind="hdr", field="local_player", max=131), _rec("m23.chat_mode"),
                                        _rec("m23.mode_changes")], checklist=True)]),
            ("F19-1b", [_group("F19-1b", [_rec("m23.host")], checklist=True)]),
            ("F19-3", [_group("F19-3", [_rec("m23.wide"), _rec("m23.screen")], checklist=True)]),
            ("F19-6", [_group("F19-6", [_rec("m23.chat_mode")], checklist=True)]),
        ], timeout_s=600, stall_s=30)
    # 25 display 관전자 (E6-1)
    # 2026-09-18 인게임: 통합 맵이 13번째 줄·TBL 쓰기에서 EUD ERROR 로 멈췄다 → E6-3·4·4b 는 이 맵에서만 판정한다.
    # 쪽마다 m25.stage(시작)·m25.stage_ok(끝)를 남기므로 멈추면 어느 쪽인지 알 수 있다. 완료 표식은 쪽 3 뒤(프레임 288).
    out["25_display_check"] = spec(
        "25_display_check", "DisplayPrint 13번째 줄·TBL·관전자 (E6-1·3·4·4b·8 — 튕길 위험)", [
            ("E6-1", [_group("E6-1", [_check("m25.E6-1.shown"), _rec("m25.E6-1.obs"), _rec("m25.E6-1.local"),
                                      dict(kind="hdr", field="local_player", max=131)], checklist=True)]),
            ("E6-8", [_group("E6-8", [dict(kind="result", name="m25.E6-8.all", total=7),
                                      _mark("m25.E6-8.lastbad", equals=0)], checklist=True)]),
            ("E6-3", [_group("E6-3", [_check("m25.E6-3.head"),
                                      dict(kind="text", name="m25.E6-3.line13", contains="[E6-3] 13번째 줄"),
                                      _mark("m25.E6-3.head_before", min=1)], checklist=True)]),
            ("E6-4", [_group("E6-4", [dict(kind="text", name="m25.E6-4.tbl", regex=r"^\[E6-4\] 마린 \d+"),
                                      _mark("m25.E6-4.frame", min=1)], checklist=True)]),
            ("E6-4b", [_group("E6-4b", [dict(kind="text", name="m25.E6-4b.tbl", regex=r"^\[E6-4b\]")],
                              checklist=True)]),
            ("E6-8#stage", [_group("E6-8#stage", [_rec("m25.stage"), _rec("m25.stage_ok")])]),
        ], done=["done"], timeout_s=300, stall_s=20)

    # 25b 좁히기 맵: 단계 18개(examples/display_bisect.py 머리말의 표)를 1초에 하나씩. 멈추면 bx.stage 가 범인.
    bisect_suites = [{"name": n, "phase": i + 1, "title": t, "timeout_s": 30, "timeout_cycles": 120, "items": []}
                     for i, (n, t) in enumerate([
                         ("noop", "쓰기 없음"), ("read13", "13번째 줄 읽기"), ("readhead", "0x628438 읽기"),
                         ("ccmu", "CreateUnit 실패 트릭만"), ("line13_4", "13번째 줄 4바이트"),
                         ("line13_16", "13번째 줄 16바이트"), ("line13_32", "13번째 줄 32바이트(변수 자리)"),
                         ("line13_93", "13번째 줄 93바이트 — 멈춘 틀"), ("line13_212", "13번째 줄 212바이트"),
                         ("line13_216", "13번째 줄 216바이트(줄 끝 마스크 dword)"),
                         ("cp13_93", "13번째 줄 93바이트 CP 방식(f_repmovsd_epd)"),
                         ("line10_93", "11번째 줄 93바이트"), ("line14_93", "15번째 줄 93바이트"),
                         ("tbl_read", "TBL 읽기"), ("tbl_const", "TBL 상수 쓰기"),
                         ("tbl_var", "TBL 변수 + tail + NUL (E6-4)"), ("tbl_raw", "TBL eos·tail 없이 (E6-4b)"),
                         ("done", "끝 표식")])]
    out["25b_display_bisect"] = spec(
        "25b_display_bisect", "13번째 줄·TBL 쓰기 좁히기 18단계 (E6-3·4·4b EUD ERROR — 튕길 위험)", [
            ("E6-3#bisect", [_group("E6-3#bisect", [_mark("bx.done", equals=1), _mark("bx.ok", equals=18),
                                                    _rec("bx.stage"), _rec("bx.head"), _rec("bx.local"),
                                                    dict(kind="text", name="bx.line13"),
                                                    dict(kind="text", name="bx.tbl")])]),
        ], done=["bx.done"], timeout_s=120, suites=bisect_suites, stall_s=20)
    return out


def write_all(out_dir=None, spec_dir=None, check=True):
    """명세 파일을 쓴다. 반환: [(경로, 맵 이름)]"""
    out_dir = out_dir or EX
    spec_dir = spec_dir or SPEC_DIR
    os.makedirs(spec_dir, exist_ok=True)
    written = []
    docs = [(os.path.join(out_dir, "auto_all_spec.json"), auto_all_spec())]
    for name, doc in sorted(other_specs().items()):
        docs.append((os.path.join(spec_dir, "%s.json" % name), doc))
    for path, doc in docs:
        text = json.dumps(doc, ensure_ascii=False, indent=1)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        written.append((path, doc["map"]))
    if check:
        from eudext.tools import ingame_auto as A

        specs = A.load_specs([p for p, _m in written])
        n = sum(len(s["items"]) + sum(len(x["items"]) for x in s["suites"]) for s in specs.values())
        print("명세 %d개, 항목 %d개 — 검사 통과" % (len(specs), n))
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description="인게임 자동 판정 명세 생성")
    ap.add_argument("--out-dir", default=None, help="auto_all_spec.json 을 쓸 폴더 (기본 examples/)")
    ap.add_argument("--spec-dir", default=None, help="맵별 명세 폴더 (기본 examples/ingame_specs/)")
    ap.add_argument("--check", action="store_true", help="검사만 (파일은 그대로 쓴다)")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    written = write_all(args.out_dir, args.spec_dir, check=True)
    for path, name in written:
        print("%-26s %s" % (name, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
