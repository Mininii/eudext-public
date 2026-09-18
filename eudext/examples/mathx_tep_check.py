"""C9-1 확인 도구: 원본 TEP(Windows SCMDraft 2 플러그인)가 만드는 CtrigAsm 수학 표 값이 eudext.mathx 표와 같은가.

CtrigAsm 은 `0x10000*math.sin(math.rad(i*90/Range))` 같은 실수를 트리거 값으로 넣고, TEP 가 C `(int)` 캐스트로 자른다.
sin 30° 와 tan 45° 는 자르기 경계(32767.999… / 65535.999…)에 붙어 있어서 C 라이브러리(`sin`/`tan`)가 1ulp 만 달라도
값이 바뀐다(T[30] = 32767 → 32768, atan2(1, 1) = 46 → 45). eudext 는 정확 반올림 값을 쓴다(`mathx_tables`).
Linux 헤드리스 TEP(`tepc`, glibc)는 같은 값을 낸다(tests/t_mathx.py). 실제 맵을 빌드하는 Windows TEP 에서도 같은지 본다.

쓰는 법 (Windows):
    1) python eudext\\examples\\mathx_tep_check.py lua mathx_tables.lua
       → CtrigAsm 표 식을 그대로 쓴 TEP 스크립트(라이브러리 불러오기 없음)를 만든다.
    2) SCMDraft 2 로 아무 빈 맵(예: eudext\\testing\\base.scx 사본)을 열고 TrigEditPlus 에 그 스크립트를 붙여 넣어
       컴파일한 뒤 맵을 저장한다 (트리거 약 260개가 생긴다).
    3) python eudext\\examples\\mathx_tep_check.py check <저장한 맵.scx>
       → "C9-1 일치" 가 나오면 끝. 아니면 다른 칸 목록을 알려 준다.

(`check` 는 날 scenario.chk 도 받는다. scx 를 읽으려면 eudplib 0.81 이 있는 파이썬으로 실행한다.)
"""

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eudext import mathx_tables as mt  # noqa: E402

# 트리거 무리 번호 = 조건·액션의 유닛 칸
G_SIN360, G_TAN360, G_COARSE, G_TAN256, G_PRECISE = 1, 2, 3, 4, 5
PRECISE_SAMPLES = ((30, 32767), (30, 1), (45, 12345), (60, 20000), (89, 32767), (90, 32767), (1, 7), (15, 30000), (75, 9999))

LUA = """-- eudext mathx C9-1: CtrigAsm v5.5 Include_MatheMatics 표 식 (CA:84385~84410, 84672~84800, 84481~84497) 그대로
-- 라이브러리를 불러오지 않는다. 컴파일해서 맵을 저장한 뒤 mathx_tep_check.py check 로 대조한다.
local function tbl(AngleCycle, sinGroup, tanGroup)
	local Range = AngleCycle/4
	if sinGroup then
		for i = 0, Range do
			Trigger { players = {P1}, conditions = { Always() },
				actions = { SetDeathsX(P1,SetTo,0x10000*math.sin(math.rad(i*90/Range)),%(sinunit)s,0xFFFFFFFF) }, flag = {preserved} }
		end
	end
	for i = 0, Range-1 do
		Trigger { players = {P1}, conditions = { Deaths(P1, AtMost, 0x10000*math.tan(math.rad(i*90/Range)), tanGroup) }, flag = {preserved} }
	end
end
tbl(360, true, %(tan360)d)
for k = 1, 7 do
	Trigger { players = {P1}, conditions = { Deaths(P1, AtMost, 0x10000*math.tan(math.rad(k*90/8)), %(coarse)d) }, flag = {preserved} }
end
tbl(256, false, %(tan256)d)
local Range = 360/4
for _, lk in ipairs({%(samples)s}) do
	local l, k = lk[1], lk[2]
	local Ret = k*math.sin(math.rad(l*90/Range))
	Trigger { players = {P1}, conditions = { Always() },
		actions = { SetDeathsX(P1,SetTo,bit32.band(Ret,0xFFFFFFFF),%(precise)d,0xFFFFFFFF), SetDeathsX(P1,SetTo,l*65536+k,%(precise)d,0xFFFFFFFF) },
		flag = {preserved} }
end
""" % {
    "sinunit": G_SIN360,
    "tan360": G_TAN360,
    "coarse": G_COARSE,
    "tan256": G_TAN256,
    "precise": G_PRECISE,
    "samples": ", ".join("{%d,%d}" % lk for lk in PRECISE_SAMPLES),
}


def expected():
    """무리 번호 → 기대값 목록."""
    exp = {
        G_SIN360: list(mt.sin_table(360)),
        G_TAN360: list(mt.atan_thresholds(360)),
        G_COARSE: list(mt.coarse_thresholds()[1:]),
        G_TAN256: list(mt.atan_thresholds(256)),
        G_PRECISE: [],
    }
    for l, k in PRECISE_SAMPLES:
        exp[G_PRECISE].append((l * 65536 + k, int(k * mt.cr_sin(l * 90, 90))))
    return exp


def read_chk(path):
    with open(path, "rb") as f:
        head = f.read(4)
    if head == b"MPQ\x1a":
        from eudplib.bindings._rust import mpqapi

        return mpqapi.MPQ.open(path).extract_file("staredit\\scenario.chk")
    with open(path, "rb") as f:
        return f.read()


def triggers(chk):
    """TRIG 섹션(마지막 것)의 트리거 목록: [(조건 [(유닛, 종류, 값)], 액션 [(유닛, 종류, 값)])]."""
    trig = None
    i = 0
    while i + 8 <= len(chk):
        name = chk[i:i + 4]
        size = struct.unpack_from("<i", chk, i + 4)[0]
        if name == b"TRIG":
            trig = chk[i + 8:i + 8 + size]
        i += 8 + max(size, 0)
    if trig is None:
        raise ValueError("TRIG 섹션이 없습니다")
    out = []
    for t in range(len(trig) // 2400):
        b = trig[t * 2400:(t + 1) * 2400]
        conds, acts = [], []
        for c in range(16):
            o = c * 20
            ctype = b[o + 15]
            if ctype == 0:
                break
            conds.append((struct.unpack_from("<H", b, o + 12)[0], ctype, struct.unpack_from("<I", b, o + 8)[0]))
        for a in range(64):
            o = 320 + a * 32
            atype = b[o + 26]
            if atype == 0:
                break
            acts.append((struct.unpack_from("<H", b, o + 24)[0], atype, struct.unpack_from("<I", b, o + 20)[0]))
        out.append((conds, acts))
    return out


def check(path):
    """맵의 표를 대조한다. 반환: (일치 여부, 메시지 목록)."""
    got = {G_SIN360: [], G_TAN360: [], G_COARSE: [], G_TAN256: [], G_PRECISE: []}
    for conds, acts in triggers(read_chk(path)):
        for unit, ctype, val in conds:
            if ctype == 15 and unit in (G_TAN360, G_COARSE, G_TAN256):
                got[unit].append(val)
        pa = [val for unit, atype, val in acts if atype == 45 and unit == G_PRECISE]
        if len(pa) == 2:
            got[G_PRECISE].append((pa[1], pa[0]))
        for unit, atype, val in acts:
            if atype == 45 and unit == G_SIN360:
                got[unit].append(val)
    exp = expected()
    names = {G_SIN360: "sin 표(360)", G_TAN360: "atan2 문턱(360)", G_COARSE: "atan2 거친 문턱", G_TAN256: "atan2X 문턱(256)",
             G_PRECISE: "LengthdirX 표 표본"}
    msgs = []
    ok = True
    for g, want in exp.items():
        have = got[g]
        if len(have) != len(want):
            ok = False
            msgs.append("%s: 개수 %d (기대 %d)" % (names[g], len(have), len(want)))
            continue
        bad = [(i, h, w) for i, (h, w) in enumerate(zip(have, want)) if h != w]
        if bad:
            ok = False
            msgs.append("%s: 다른 칸 %s" % (names[g], ", ".join("[%d] %r (기대 %r)" % x for x in bad[:12])))
        else:
            msgs.append("%s: %d칸 일치" % (names[g], len(want)))
    return ok, msgs


def main(argv):
    if len(argv) != 2 or argv[0] not in ("lua", "check"):
        print(__doc__)
        return 2
    if argv[0] == "lua":
        with open(argv[1], "w", encoding="utf-8", newline="\r\n") as f:
            f.write(LUA)
        print("썼습니다: %s" % argv[1])
        return 0
    ok, msgs = check(argv[1])
    for m in msgs:
        print("  " + m)
    print("C9-1 일치" if ok else "C9-1 다름 — 위 줄을 알려 주세요")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
