"""`shape` 시험: CX(lupa 로 CB Paint) 고정 시드 스냅숏·원본 TEP(tepc) 대조, 정확 반올림 수학(`_crmath` — 독립 고정밀 기준값·
특수값·원본 플러그인 측정값·Lua 연결), 좌표 자르기(D6)·Hollow·NaN, Shape·sweep·스케줄,
저장 인코딩 왕복, ShapeSet(db·varray, 중복 제거, 게으른 표) 에뮬레이터 읽기, epScript 예제 번역·에뮬레이션·euddraft 빌드
(번들 파이썬 3.14 에서 lupa 적재 — Preload / VenvSite / 폴더 찾기), 좌표 1,700점 scx 크기.

python tests/t_shape.py
비용 표: python tools/cost.py tests/t_shape.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import hashlib  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402

import ref_crmath  # noqa: E402

from eudplib import (  # noqa: E402
    CompressPayload,
    EUDDoEvents,
    EUDEndInfLoop,
    EUDInfLoop,
    EUDVariable,
    FlattenList,
    LoadMap,
    SaveMap,
    ShufflePayload,
)

from eudext import _compat, _crmath, shape  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.shape import CX, Shape, ShapeSet  # noqa: E402
from eudext.testing import BASE_MAP, emu, scmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402
from eudext.tools.lua_consts import lua_c_locale  # noqa: E402

M32 = 0xFFFFFFFF
EX = os.path.join(_common.PKG, "examples")
EXTRA = ["CSMakeSpiral.lua", "CS_Addon.lua"]
SEED = 1234
GRAPH_FN = "function __eudext_t(t) return {60*math.cos(t/10), 45*math.sin(t/10)} end"
TEPC = os.environ.get("EUDEXT_TEPC") or "/home/developer/TEP3.0_Headless_Compiler/build/tepc"

# 고정 시드(1234) 스냅숏: 이름 → (식, 점 수, NaN 좌표 수, 자르기≠반올림 점 수, 정수 점 sha1 앞 16자, 앞 6점)
# 값은 lupa(Lua 5.4) + CB Paint v2.5 + 정확 반올림 수학(_crmath)으로 만들었다 — 모든 OS 에서 같아야 한다.
# tep_compare() 가 헤드리스 TEP(tepc)로 다시 계산해 같은지 본다(수학 라이브러리 차이로 알려진 예외는 TEP_KNOWN).
# star 는 2026-09-17 에 고쳤다: Ubuntu(glibc 수학) 기록은 6번째 점 (34, 48)·sha efaed7f3d105fe89 였고, 정확 반올림과
# 원본 플러그인(TrigEditPlus3.0.sdp) 측정은 (34, 47) 이다(참값 48 을 double 연쇄 계산이 47.99999999999999 로 낸다).
SNAP = {
    "circle": ("CSMakeCircle(6,32,0,37,0)", 37, 0, 23, "8f5c66f9426235df",
               [(0, 0), (0, -32), (27, -15), (27, 15), (0, 32), (-27, 15)]),
    "circle_hollow": ("CSMakeCircle(6,32,0,37,7)", 30, 0, 19, "d96ef91354908931",
                      [(0, -64), (32, -55), (55, -31), (64, 0), (55, 31), (32, 55)]),
    "polygon_hollow": ("CSMakePolygon(6,32,0,37,5)", 32, 0, 19, "11c1510193eda17f",
                       [(-27, 15), (-27, -16), (0, -64), (27, -48), (55, -31), (55, 0)]),
    "star": ("CSMakeStar(5,144,96,0,CS_Level('Star',5,3),0)", 31, 0, 25, "a30a3dc0621c0001",
             [(0, 0), (0, -59), (56, -77), (56, -18), (91, 29), (34, 47)]),
    "star_rot": ("CS_Rotate(CSMakeStar(5,72,60,0,CS_Level('Star',5,4),0),15)", 61, 0, 42, "87473626ee093c47",
                 [(0, 0), (0, 0), (46, -37), (0, 0), (50, 32), (0, 0)]),
    "line": ("CSMakeLine(4,30,0,13,1)", 12, 0, 0, "2e440d42912e4a68",
             [(0, -30), (30, 0), (0, 30), (-30, 0), (0, -60), (60, 0)]),
    "ray": ("CSMakeLine(1,32,0,6,1)", 5, 0, 0, "5592bfe878db89e7",
            [(0, -32), (0, -64), (0, -96), (0, -128), (0, -160)]),
    "ratio": ("CS_RatioXY(CSMakeCircle(6,32,0,37,0),2,0.5)", 37, 0, 22, "bfb2a26a305f65c5",
              [(0, 0), (0, -16), (55, -7), (55, 7), (0, 16), (-55, 7)]),
    "move": ("CS_MoveXY(CSMakePolygon(4,40,0,25,0),100,-50)", 25, 0, 8, "83c90583f45b784f",
             [(100, -50), (100, -90), (140, -50), (100, -10), (60, -49), (100, -130)]),
    "fill": ("CS_FillXY(0,128,96,16,16)", 48, 0, 0, "077773c53f59177a",
             [(-56, -40), (-40, -40), (-24, -40), (-8, -40), (8, -40), (24, -40)]),
    "spiral": ("CSMakeSpiral(6,16,0.2,24,0,30,0)", 30, 0, 15, "832b4a27d7e1e7e5",
               [(0, 0), (-4, 0), (-1, -4), (2, -3), (4, 0), (1, 4)]),
    "movera": ("CS_MoveRA(CSMakeCircle(6,32,0,7,0),10,30)", 7, 2, 2, "2ee30637ed594870",
               [(0, 0), (21, -36), (42, 0), (21, 36), (-20, 36), (-42, 0)]),
    "shuffle": ("CS_Shuffle(CSMakeCircle(6,32,0,19,0))", 19, 0, 8, "68fdcd6bc0a030ac",
                [(-55, 31), (55, 31), (32, 55), (0, 64), (64, 0), (55, -31)]),
    "graph": ("CSMakeGraphT({1,1},'__eudext_t',0,0,8,nil,40)", 40, 0, 31, "f0605181e1b91a7b",
              [(60, 0), (59, 7), (56, 15), (52, 22), (46, 28), (40, 33)]),
    "connect": ("CS_ConnectPath(CSMakePath({0,0},{64,0},{64,64}),16)", 35, 0, 16, "fc0e079ac0d2fa92",
                [(0, 0), (60, 0), (56, 0), (52, 0), (48, 0), (45, 0)]),
    "slice": ("CS_Slice(CSMakePath({0,0},{8,0},{16,0},{200,0},{208,0}),3,1)[1]", 5, 0, 0, "438b67702a01721b",
              [(0, 0), (8, 0), (16, 0), (200, 0), (208, 0)]),
    "big": ("CSMakeCircle(12,16,0,1700,0)", 1700, 0, 1184, "89d12e2630fd823b",
            [(0, 0), (0, -16), (8, -13), (13, -7), (16, 0), (13, 7)]),
}
SNAP_ORDER = list(SNAP)  # 식을 이 순서로 계산한다(shuffle 이 난수를 쓰므로 순서가 결과를 바꾼다)

# 헤드리스 TEP(tepc) 대조의 알려진 예외: 이름 → {점 번호: tepc 가 내는 점}.
# 이유: tepc 는 C 수학 라이브러리를 그대로 쓴다 — Windows 판(build-win, mingw-w64)은 msvcrt/mingwex 의 tan(rad 72°) 가
# 정확 반올림보다 1ulp 커서 star 의 참값 48·96 점을 48·96 으로 낸다. Linux 판(glibc)도 같은 4점이다(Ubuntu 에서 tepc 와 일치했던
# 옛 스냅숏 sha efaed7f3d105fe89 = mingw 수학으로 계산한 star).
# 원본 플러그인(MSVC 정적 CRT)과 eudext(정확 반올림)는 47.99999999999999 → 47, 95.99999999999999 → 95.
TEP_KNOWN = {"star": {5: (34, 48), 7: (-34, 48), 19: (69, 96), 23: (-69, 96)}}

# 원본 플러그인 TrigEditPlus3.0.sdp(32비트 v143 /MT, Lua 5.4.4)의 CRT sin/cos/tan 을 기계어 그대로 불러 잰 값
# (2026-09-17 Windows 조사 스크립트 fpx/plugcalc.py — 32비트 파이썬(py -3.9-32)이 필요해 저장소에는 두지 않고 결과만 둔다).
# (함수, 인자 비트, 플러그인 결과 비트): 앞 12개는 플러그인 = 정확 반올림 ≠ Windows x64 ucrt 인 인자, 뒤 4개는 star 인자
# (cos·sin rad 36°, tan rad 72°, sin rad 54°). 표본 26,283호출 중 플러그인 ≠ 정확 반올림은 35개(0.13%)였고 좌표에는 영향이 없었다.
PLUGIN_MEASURED = [
    ("cos", 0x4024383A4964B720, 0xBFE8C7D31513120D),  # 10.109819692177155 → -0.7743926440821852
    ("cos", 0x4011F59DBA9D847E, 0xBFCC3FD044DD3D39),  # 4.489859500755413 → -0.22069743502150077
    ("cos", 0xC00EC80296265324, 0xBFE859721E46A4AA),  # -3.8476611833997527 → -0.7609186736418867
    ("cos", 0xC01D065AF61DAAD5, 0x3FE2027F7ACF4B7F),  # -7.256206365166425 → 0.562804927695069
    ("sin", 0x400238A3037E3A4B, 0x3FE8553EE43DEF14),  # 2.2776546738526 → 0.760405965600031
    ("sin", 0x3FE7DB1BB7C0E4C0, 0x3FE5B4EF5731C2CC),  # 0.7454966153083191 → 0.6783367827429969
    ("sin", 0xC01AE9B8DD6F67C1, 0xBFDB8D7E6A56D46F),  # -6.72824426643814 → -0.43051109680829475
    ("sin", 0x4024842F3596963C, 0xBFE7AFDDED2ECB30),  # 10.258172678596672 → -0.7402181274868322
    ("tan", 0xC0165168255B7BDC, 0x3FEB27CFDAAEB285),  # -5.579498847683649 → 0.848609854806981
    ("tan", 0x401C227C31880D81, 0x3FEDD729E0BF9CB9),  # 7.033676885537148 → 0.932515086137662
    ("tan", 0x40170E48DEE71353, 0xBFE24A1D1E0B7226),  # 5.7639498547112735 → -0.5715470873652222
    ("tan", 0xC027EFEBBAA86654, 0x3FE5C9BBF8DC3C71),  # -11.968595345551115 → 0.6808757648995095
    ("cos", 0x3FE41B2F769CF0E0, 0x3FE9E3779B97F4A8),  # rad 36° 0.6283185307179586 → 0.8090169943749475
    ("sin", 0x3FE41B2F769CF0E0, 0x3FE2CF2304755A5E),  # rad 36° → 0.5877852522924731
    ("tan", 0x3FF41B2F769CF0E0, 0x40089F188BDCD7AD),  # rad 72° 1.2566370614359172 → 3.0776835371752527
    ("sin", 0x3FEE28C731EB6950, 0x3FE9E3779B97F4A8),  # rad 54° 0.9424777960769379 → 0.8090169943749475
]
# 원본 플러그인 math_rad·math_deg 기계어가 곱하는 상수(역어셈블, fmul qword [0x1009D820]·[0x1009D838])
PLUGIN_RAD = 0x3F91DF46A2529D39
PLUGIN_DEG = 0x404CA5DC1A63C1F8


def sha(points):
    return hashlib.sha1(repr(tuple(points)).encode()).hexdigest()[:16]


def make_cx(seed=SEED):
    cx = CX(extra=EXTRA, seed=seed)
    cx.run(GRAPH_FN)
    return cx


def snapshot_shapes(cx):
    return {name: cx.eval(SNAP[name][0], name=name) for name in SNAP_ORDER}


def trunc_diff(s):
    return sum(1 for x, y in s.raw if x == x and y == y and (int(x), int(y)) != (round(x), round(y)))


# =============================================================================================
# 파이썬 쪽 (lupa · Shape · 인코딩)
# =============================================================================================


def check_snapshot(ck, shapes):
    for name in SNAP_ORDER:
        expr, n, nan, diff, h, first = SNAP[name]
        s = shapes[name]
        ck.eq("snap %s 점 수" % name, len(s), n)
        ck.eq("snap %s NaN" % name, s.nan_count, nan)
        ck.eq("snap %s 자르기≠반올림" % name, trunc_diff(s), diff)
        ck.eq("snap %s sha" % name, sha(s.points), h)
        ck.eq("snap %s 앞 6점" % name, list(s.points[:6]), first)
        ck.eq("snap %s 자르기 규칙" % name, list(s.points), [(shape.tep_int(x), shape.tep_int(y)) for x, y in s.raw])


def check_trunc_rule(ck, cx):
    cases = [(0, 0), (2.7, 2), (-2.7, -2), (0.5, 0), (-0.5, 0), (-1.5, -1), (-15.999999999999998, -15), (32767.9, 32767),
             (-32768.9, -32768), (float("nan"), 0), (float("inf"), 0), (float("-inf"), 0), (1e30, 0), (-1e30, 0),
             (2**31, -2**31), (2**32 + 5, 5), (-1, -1), (True, 1), (4294967295.0, -1), (2.0**62, 0), (-(2.0**63), 0)]
    for v, want in cases:
        ck.eq("tep_int(%r)" % (v,), shape.tep_int(v), want)
    ck.raises("tep_int 문자열", EudextError, shape.tep_int, "3")
    ring = cx.eval("CSMakeCircle(6,32,0,37,0)")
    # 원의 세 번째 점 (27.71…, -15.999…) → (27, -15): 반올림이면 (28, -16)
    ck.eq("원 3번 점 raw", (round(ring.raw[2][0], 3), ring.raw[2][1]), (27.713, -15.999999999999998))
    ck.eq("원 3번 점 자르기", ring.points[2], (27, -15))
    ck.eq("floor 가 아님 (-27.7 → -27)", ring.points[5], (-27, 15))


# =============================================================================================
# 정확 반올림 수학 (_crmath)
# =============================================================================================


def fbits(v):
    return struct.unpack("<Q", struct.pack("<d", v))[0]


def unbits(b):
    return struct.unpack("<d", struct.pack("<Q", b))[0]


NAN_NEG = "NaN-"  # 정의역 밖: 부호 비트 1 인 quiet NaN (x86 기본 NaN)
NAN_IN = "NaN="  # NaN 입력을 비트 그대로 돌려줌
QNAN = unbits(0x7FF8000000000123)  # 꼬리표 있는 NaN
INF = math.inf
KAHAN = 6381956970095103 * 2.0**797  # π/2 배수에 가장 가까운 double (Kahan·McDonald, 거리 약 4.7e-19)
THREE_Q = ref_crmath.atan2(1.0, -1.0)  # 3π/4 의 정확 반올림

# C99 부록 F.9 특수값 (함수, 인자, 기대값)
CR_SPECIALS = [
    ("sin", (0.0,), 0.0), ("sin", (-0.0,), -0.0), ("sin", (0,), 0.0), ("sin", (INF,), NAN_NEG), ("sin", (-INF,), NAN_NEG),
    ("sin", (QNAN,), NAN_IN), ("sin", (5e-324,), 5e-324), ("sin", (-5e-324,), -5e-324), ("sin", (1e-300,), 1e-300),
    ("cos", (0.0,), 1.0), ("cos", (-0.0,), 1.0), ("cos", (INF,), NAN_NEG), ("cos", (QNAN,), NAN_IN),
    ("cos", (KAHAN,), -4.687165924254628e-19), ("cos", (5e-324,), 1.0),
    ("tan", (-0.0,), -0.0), ("tan", (-INF,), NAN_NEG), ("tan", (QNAN,), NAN_IN), ("tan", (math.pi / 2,), 1.633123935319537e16),
    ("asin", (1.0,), math.pi / 2), ("asin", (-1,), -math.pi / 2), ("asin", (-0.0,), -0.0), ("asin", (1.0000000000000002,), NAN_NEG),
    ("asin", (-2.0,), NAN_NEG), ("asin", (INF,), NAN_NEG), ("asin", (QNAN,), NAN_IN),
    ("acos", (1.0,), 0.0), ("acos", (-1.0,), math.pi), ("acos", (0.0,), math.pi / 2), ("acos", (-0.0,), math.pi / 2),
    ("acos", (-1.0000000000000002,), NAN_NEG), ("acos", (-INF,), NAN_NEG), ("acos", (QNAN,), NAN_IN),
    ("atan2", (0.0, -0.0), math.pi), ("atan2", (-0.0, -0.0), -math.pi), ("atan2", (0.0, 0.0), 0.0), ("atan2", (-0.0, 0.0), -0.0),
    ("atan2", (0.0, -1.0), math.pi), ("atan2", (-0.0, -1.0), -math.pi), ("atan2", (0.0, 1.0), 0.0), ("atan2", (-0.0, 1.0), -0.0),
    ("atan2", (0.0, -INF), math.pi), ("atan2", (-0.0, INF), -0.0),
    ("atan2", (1.0, 0.0), math.pi / 2), ("atan2", (-1.0, -0.0), -math.pi / 2),
    ("atan2", (INF, INF), math.pi / 4), ("atan2", (INF, -INF), THREE_Q), ("atan2", (-INF, INF), -math.pi / 4),
    ("atan2", (-INF, -INF), -THREE_Q), ("atan2", (INF, 5.0), math.pi / 2), ("atan2", (-INF, -5.0), -math.pi / 2),
    ("atan2", (1.0, INF), 0.0), ("atan2", (-1.0, INF), -0.0), ("atan2", (1.0, -INF), math.pi), ("atan2", (-1.0, -INF), -math.pi),
    ("atan2", (QNAN, 1.0), NAN_IN), ("atan2", (1.0, QNAN), NAN_IN), ("atan2", (QNAN, INF), NAN_IN),
    ("atan2", (5e-324, 1e308), 0.0), ("atan2", (-5e-324, 1e308), -0.0), ("atan2", (-5e-324, -1e308), -math.pi),
    ("atan2", (1e308, 5e-324), math.pi / 2), ("atan2", (1, 1), math.pi / 4),
    ("exp", (0.0,), 1.0), ("exp", (-0.0,), 1.0), ("exp", (INF,), INF), ("exp", (-INF,), 0.0), ("exp", (QNAN,), NAN_IN),
    ("exp", (709.79,), INF), ("exp", (1000,), INF), ("exp", (-745.2,), 0.0), ("exp", (-745.1,), 5e-324), ("exp", (-1000,), 0.0),
    ("exp", (5e-324,), 1.0), ("exp", (-5e-324,), 1.0), ("exp", (1,), math.e),
    ("log", (0.0,), -INF), ("log", (-0.0,), -INF), ("log", (-1.0,), NAN_NEG), ("log", (-INF,), NAN_NEG),
    ("log", (-5e-324,), NAN_NEG), ("log", (INF,), INF), ("log", (1,), 0.0), ("log", (QNAN,), NAN_IN),
    ("log2", (8,), 3.0), ("log2", (2.0**-1074,), -1074.0), ("log2", (0.5,), -1.0), ("log2", (0.0,), -INF), ("log2", (-2.0,), NAN_NEG),
    ("log10", (1e22,), 22.0), ("log10", (1000,), 3.0), ("log10", (-0.0,), -INF), ("log10", (INF,), INF), ("log10", (QNAN,), NAN_IN),
]


def crmath_cases(rng):
    """(함수 이름, 인자) 목록 — 무작위 + 경계(큰 인자·비정규 수·±1 근처·넘침 경계·2 와 10 의 거듭제곱)."""
    out = []
    trig = [rng.uniform(-10, 10) for _ in range(50)]
    trig += [rng.choice((1, -1)) * math.ldexp(rng.random() + 0.5, rng.randint(-40, 40)) for _ in range(30)]
    trig += [math.pi, -math.pi, math.pi / 2, math.pi / 4, 1.2566370614359172, 0.6283185307179586, 0.9424777960769379, 100.0,
             710.0, 1e22, -1e22, 1e300, 1.7976931348623157e308, KAHAN, 2.0**1000, 1e-8, -1e-300, 2.2250738585072014e-308]
    for f in ("sin", "cos", "tan"):
        out += [(f, (a,)) for a in trig]
    unit = [rng.uniform(-1, 1) for _ in range(40)]
    unit += [sg * (1 - 2.0**-k) for k in (1, 3, 10, 26, 40, 52, 53) for sg in (1, -1)]
    unit += [sg * 2.0**-k for k in (1, 20, 60, 300, 1074) for sg in (1, -1)]
    for f in ("asin", "acos"):
        out += [(f, (v,)) for v in unit]
    ex = [rng.uniform(-745, 709.7) for _ in range(30)] + [rng.uniform(-3, 3) for _ in range(20)]
    ex += [709.782712893384, 709.7827128933841, 709.78, -745.1332191019411, -745.1332191019412, -744.44, -708.39, 1e-10, -1e-300]
    out += [("exp", (a,)) for a in ex]
    lg = [math.ldexp(rng.random() + 0.5, rng.randint(-1073, 1023)) for _ in range(30)] + [rng.uniform(0.1, 10) for _ in range(20)]
    lg += [1 + 2.0**-k for k in (1, 20, 52)] + [1 - 2.0**-k for k in (1, 20, 53)]
    lg += [2.0**k for k in (-1074, -1022, -1, 1, 3, 1023)] + [10.0**k for k in (-5, -1, 1, 2, 15, 22, 23, 300)]
    lg += [5e-324, 1.7976931348623157e308, 3.0, math.e]
    for f in ("log", "log2", "log10"):
        out += [(f, (a,)) for a in lg]
    pairs = [(rng.uniform(-10, 10) * 10.0 ** rng.randint(-6, 6), rng.uniform(-10, 10) * 10.0 ** rng.randint(-6, 6))
             for _ in range(50)]
    pairs += [(1.0, 1.0), (-1.0, -1.0), (1.0, -1.0), (1e-300, -1e300), (1e300, 1e-300), (3.0, 1.0), (-2.5, 1.0), (1e-20, 1.0)]
    out += [("atan2", p) for p in pairs]
    return out


def _special_ok(got, want, args):
    if want == NAN_NEG:
        return got != got and fbits(got) >> 63 == 1
    if want == NAN_IN:
        nan = next(a for a in args if a != a)
        return fbits(got) == fbits(nan)
    return isinstance(got, float) and fbits(got) == fbits(want)


def check_crmath(ck):
    import decimal

    rng = random.Random(17)
    cases = crmath_cases(rng)
    bad = []
    for fname, args in cases:
        got = getattr(_crmath, fname)(*args)
        want = ref_crmath.atan2(*args) if fname == "atan2" else ref_crmath.FUNCS[fname](*args)
        if fbits(got) != fbits(want):
            bad.append((fname, args, got, want))
    ck.eq("정확 반올림 = 고정밀 기준값(ref_crmath, 다른 알고리즘) %d 호출" % len(cases), bad, [])
    bad = [(f, a, getattr(_crmath, f)(*a), w) for f, a, w in CR_SPECIALS if not _special_ok(getattr(_crmath, f)(*a), w, a)]
    ck.eq("C99 특수값 %d개 (±0 부호·inf·NaN·넘침)" % len(CR_SPECIALS), bad, [])
    ck.eq("atan(y) = atan2(y, 1)", [fbits(_crmath.atan(v)) for v in (0.5, -3.0, 1e300)],
          [fbits(_crmath.atan2(v, 1.0)) for v in (0.5, -3.0, 1e300)])
    # 원본 플러그인 측정값
    bad = [(f, hex(a), hex(fbits(getattr(_crmath, f)(unbits(a)))), hex(w)) for f, a, w in PLUGIN_MEASURED
           if fbits(getattr(_crmath, f)(unbits(a))) != w]
    ck.eq("원본 플러그인 측정값 %d개 = 정확 반올림" % len(PLUGIN_MEASURED), bad, [])
    ck.eq("tan(rad 72°) = 3.0776835371752527 (원본 플러그인)", _crmath.tan(72 * (math.pi / 180.0)), 3.0776835371752527)
    # 사용자 decimal 전역 문맥(정밀도·반올림 방식)에 흔들리지 않는다
    # acos·atan2 를 먼저: π 를 decimal 문맥 밖에서 처음 계산하는 길 (clear_cache 가 π 캐시도 비운다)
    probe = [(_crmath.acos, 0.3), (_crmath.atan2, (3.0, 1.0)), (_crmath.sin, 0.6283185307179586), (_crmath.tan, 1.2566370614359172),
             (_crmath.exp, 1.5), (_crmath.log, 7.0), (_crmath.log2, 3.0), (_crmath.cos, 1e300)]
    want = [fbits(f(*a) if isinstance(a, tuple) else f(a)) for f, a in probe]
    old = decimal.getcontext()
    try:
        c = decimal.Context(prec=6, rounding=decimal.ROUND_FLOOR, Emax=99, Emin=-99)
        decimal.setcontext(c)
        _crmath.clear_cache()
        got = [fbits(f(*a) if isinstance(a, tuple) else f(a)) for f, a in probe]
        got += [fbits(_crmath.exp(-700.0)), fbits(_crmath.atan2(1e-300, 1e300))]
    finally:
        decimal.setcontext(old)
    _crmath.clear_cache()
    ck.eq("decimal 전역 문맥과 무관", got, want + [fbits(ref_crmath.exp(-700.0)), fbits(0.0)])


def check_lua_math(ck, cx):
    import re

    lua54 = shape.import_lupa()
    L = cx.lua
    with lua_c_locale():
        caller = L.eval("function(n, ...) return math[n](...) end")

    def lua(n, *a):
        with lua_c_locale():
            return caller(n, *a)

    # math.rad·deg 는 바꾸지 않는다: 원본 플러그인과 같은 상수 곱 한 번
    ck.eq("math.rad 상수 = 원본 플러그인 기계어", hex(fbits(lua("rad", 1))), hex(PLUGIN_RAD))
    ck.eq("math.deg 상수 = 원본 플러그인 기계어", hex(fbits(lua("deg", 1.0))), hex(PLUGIN_DEG))
    degs = (36, 72, 54, 144 / 2, 0.1, -123.456, 1e10)
    ck.eq("math.rad(x) = x · 상수", [fbits(lua("rad", d)) for d in degs], [fbits(d * unbits(PLUGIN_RAD)) for d in degs])
    # Lua 에서 부른 값 = _crmath (math.atan 두 꼴, math.log 밑 셋)
    rng = random.Random(23)
    bad = []
    for _ in range(40):
        a = rng.uniform(-10, 10)
        v = rng.uniform(-1, 1)
        p = abs(a) + 0.01
        pairs = [(lua("sin", a), _crmath.sin(a)), (lua("cos", a), _crmath.cos(a)), (lua("tan", a), _crmath.tan(a)),
                 (lua("asin", v), _crmath.asin(v)), (lua("acos", v), _crmath.acos(v)), (lua("exp", a), _crmath.exp(a)),
                 (lua("atan", a), _crmath.atan2(a, 1.0)), (lua("atan", a, v), _crmath.atan2(a, v)),
                 (lua("log", p), _crmath.log(p)), (lua("log", p, 2), _crmath.log2(p)), (lua("log", p, 10.0), _crmath.log10(p)),
                 (lua("log", p, 3), _crmath.log(p) / _crmath.log(3.0))]
        bad += [(a, v, k, g, w) for k, (g, w) in enumerate(pairs) if fbits(g) != fbits(w)]
    ck.eq("Lua math.* = _crmath (480 호출)", bad, [])
    bad = [(f, hex(a)) for f, a, w in PLUGIN_MEASURED if fbits(lua(f, unbits(a))) != w]
    ck.eq("Lua math.* = 원본 플러그인 측정값", bad, [])
    ck.eq("정수·문자열 인자 (luaL_checknumber)", [lua("sin", 1), lua("sin", "1"), lua("sin", " 0x10 "), lua("cos", 0), lua("log", 8, "2")],
          [_crmath.sin(1.0), _crmath.sin(1.0), _crmath.sin(16.0), 1.0, 3.0])
    ck.eq("math.atan(y, nil) = math.atan(y)", lua("atan", 2.5, None), _crmath.atan2(2.5, 1.0))
    ck.eq("결과는 늘 float", cx.value("{math.type(math.sin(0)), math.type(math.cos(0)), math.type(math.exp(0)), "
                                   "math.type(math.log(1)), math.type(math.atan(0)), math.type(math.log(8, 2))}"), ["float"] * 6)
    ck.eq("±0·NaN 은 Lua 캐시를 거치지 않는다 (부호·NaN 유지)",
          cx.value("{math.sin(0.0), 1/math.sin(-0.0), 1/math.tan(-0.0), 1/math.asin(-0.0), 1/math.atan(-0.0), "
                   "math.atan(0.0, -1), math.atan(-0.0, -1), (function(n) return math.cos(n) ~= math.cos(n) end)(0/0)}"),
          [0.0, -INF, -INF, -INF, -INF, math.pi, -math.pi, True])
    # Lua 쪽 캐시: 같은 인자는 파이썬을 한 번만 부른다 (±0·NaN 은 매번)
    calls = []
    names = ("sin", "cos", "tan", "asin", "acos", "atan2", "exp", "log", "log2", "log10")

    def counting(n):
        f = getattr(_crmath, n)

        def g(*a):
            calls.append(n)
            return f(*a)

        return g

    rt = lua54.LuaRuntime(unpack_returned_tuples=True, register_eval=False, encoding="latin-1")
    with lua_c_locale():
        rt.execute(_crmath.LUA_GLUE.encode("utf-8"), *[counting(n) for n in names])
        r = rt.execute("""
            local a = math.sin(0.5) + math.sin(0.5) + math.sin(0.5)
            local b = math.sin(1) + math.sin(1.0)
            local c = 1 / math.sin(-0.0) + 1 / math.sin(-0.0)
            local n = 0 / 0
            local d = math.cos(n) ~= math.cos(n)
            local e = math.atan(1, 2) + math.atan(1, 2)
            local f = math.atan(0, -1) + math.atan(0, -1)
            local g = math.log(8, 2) + math.log(8, 2)
            local h = math.log(100, 3) + math.log(100, 3)
            local i = math.log(100) + math.exp(2) + math.exp(2)
            return c, d
        """)
    ck.eq("Lua 캐시: 파이썬 호출 순서", calls, ["sin", "sin", "sin", "sin", "cos", "cos", "atan2", "atan2", "atan2", "log2", "log", "log",
                                           "exp"])
    ck.eq("Lua 캐시: 결과", r, (-INF, True))
    # 인자 오류 문구 = 원본 Lua (luaL_checknumber·luaL_typeerror)
    plain = lua54.LuaRuntime()
    pat = re.compile(r"bad argument #\d+ to '\w+' \([^)]*\)")
    diff = []
    for expr in ("math.sin()", "math.sin(nil)", "math.cos({})", "math.tan('x')", "math.asin(true)", "math.acos()", "math.atan()",
                 "math.atan(1, {})", "math.log(1, 'q')", "math.log()", "math.exp(print)"):
        want = got = None
        try:
            with lua_c_locale():
                plain.execute("local v = " + expr)
        except lua54.LuaError as e:
            want = pat.search(str(e)).group(0)
        try:
            cx.run("local v = " + expr, "=probe")
        except EudextError as e:
            m = pat.search(str(e))
            got = m.group(0) if m and "probe:1: " + m.group(0) in str(e) else str(e)
        if want is None or got != want:
            diff.append((expr, got, want))
    ck.eq("인자 오류 문구·위치 = 원본 Lua", diff, [])
    # `^`: 바꿀 수 없다 — CB Paint 는 ^2(곱셈)와 CS_Round 의 10^Digit 만 쓴다 (이 플랫폼 pow 로 정확한지)
    ck.eq("10^k (k = 0~22) 정확 (CS_Round·CXRound)", [cx.value("10^%d" % k) for k in range(23)], [float(10**k) for k in range(23)])
    ck.eq("x^2 = x·x (luai_numpow)", [fbits(cx.value("(%r)^2" % x)) for x in (0.1, 1.7, -3.3)], [fbits(x * x) for x in (0.1, 1.7, -3.3)])
    # star: 원본 플러그인 47·95 (INGAME_CHECKLIST D7-6 스크립트와 같은 식)
    star = SNAP["star"][0]
    ck.eq("star S[7]·S[21] raw y (참값 48·96)", (cx.value(star + "[7][2]"), cx.value(star + "[21][2]")),
          (47.99999999999999, 95.99999999999999))
    ck.eq("star D7-6 bit32.band = 47·95", (cx.value("bit32.band(%s[7][2], 0xFFFFFFFF)" % star),
                                          cx.value("bit32.band(%s[21][2], 0xFFFFFFFF)" % star)), (47, 95))


def check_hollow_nan(ck, cx):
    full = cx.eval("CSMakePolygon(6,32,0,37,0)")
    hol = cx.eval("CSMakePolygon(6,32,0,37,5)")
    ck.eq("Hollow 표 길이 (선언 32 + 뒤에 남은 5)", cx.value("#CSMakePolygon(6,32,0,37,5)"), 38)
    ck.eq("Hollow 선언 개수", cx.value("CSMakePolygon(6,32,0,37,5)[1]"), 32)
    ck.eq("Hollow 는 [1] 개까지만", len(hol), 32)
    ck.eq("Hollow = 앞 5점을 건너뛴 도형", hol.points, full.points[5:37])
    extra = cx.value("CSMakePolygon(6,32,0,37,5)[34]")
    ck.true("Hollow 뒤에 남은 점이 표에 있다", isinstance(extra, list) and len(extra) == 2, repr(extra))
    ra = cx.eval("CS_MoveRA(CSMakeCircle(6,32,0,7,0),10,30)")
    fix = cx.eval("CS_FixShape(CS_MoveRA(CSMakeCircle(6,32,0,7,0),10,30))")
    ck.true("원점 극좌표 → NaN", all(math.isnan(v) for v in ra.raw[0]), repr(ra.raw[0]))
    ck.eq("NaN → 0 (CS_FixShape 와 같다)", ra.points, fix.points)
    ck.eq("NaN 개수", (ra.nan_count, fix.nan_count), (2, 0))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s = Shape([(float("inf"), 1), (2, float("-inf"))], name="inf")
    ck.eq("무한대 → 0", s.points, ((0, 1), (2, 0)))
    ck.true("무한대 경고", any("무한대" in str(x.message) for x in w), [str(x.message) for x in w])
    ck.raises("sweep NaN 은 오류", EudextError, ra.sweep, "right")


def check_cx_api(ck, cx):
    # 결정성: 같은 시드 → 같은 난수 도형, 다른 시드 → 다름
    a = make_cx().eval("CS_Shuffle(CSMakeCircle(6,32,0,19,0))")
    b = make_cx().eval("CS_Shuffle(CSMakeCircle(6,32,0,19,0))")
    c = make_cx(seed=0).eval("CS_Shuffle(CSMakeCircle(6,32,0,19,0))")
    ck.eq("같은 시드 같은 결과", a.points, b.points)
    ck.true("다른 시드 다른 결과", a.points != c.points)
    cx2 = make_cx(seed=0)
    cx2.reseed(SEED)
    ck.eq("reseed", cx2.eval("CS_Shuffle(CSMakeCircle(6,32,0,19,0))").points, a.points)
    ck.eq("seed None 은 시각 시드 (만들어짐)", CX(seed=None).seed, None)
    # call / 인자 변환
    ring = cx.call("CSMakeCircle", 6, 32, 0, 37, 0)
    ck.eq("call = eval", ring.points, cx.eval("CSMakeCircle(6,32,0,37,0)").points)
    ck.eq("call 이름", ring.name, "CSMakeCircle")
    rot = cx.call("CS_Rotate", ring, 90)  # Shape → Lua 표 (raw)
    ck.eq("Shape → Lua 는 raw (Lua 안에서 이어 계산한 것과 같다)", cx.call("CS_Rotate", cx.eval("CSMakeStar(5,72,60,0,CS_Level('Star',5,4),0)"), 15).points,
          cx.eval("CS_Rotate(CSMakeStar(5,72,60,0,CS_Level('Star',5,4),0),15)").points)
    ck.eq("CS_Rotate 90 = 시계 방향 (12시 → 3시)", rot.points[1], (32, 0))
    ck.eq("CS_Rotate 45", cx.call("CS_Rotate", ring, 45).points[1], (22, -22))
    path = cx.call("CSMakePath", [[0, 0], [64, 0], [64, 64]])  # 파이썬 목록 → 표
    ck.eq("list → 표", path.points, ((0, 0), (64, 0), (64, 64)))
    ck.eq("dict → 표", cx.lua.eval("function(t) return t.a + t.b end")(cx.to_lua({"a": 2, "b": 5})), 7)
    ck.eq("value 표 → list", cx.value("{1, {2, 3}}"), [1, [2, 3]])
    ck.eq("value 표 → dict", cx.value("{a = 1}"), {"a": 1})
    ck.eq("lua_to_py 수", shape.lua_to_py(3), 3)
    ck.eq("CS_Level", cx.value("CS_Level('Star', 5, 3)"), 31)
    ck.eq("식에 한글 주석", cx.value("1 -- 한글"), 1)
    # run / run_file / get
    work = os.path.join(_common.WORK, "t_shape_lua")
    os.makedirs(work, exist_ok=True)
    lf = os.path.join(work, "map_shapes.lua")
    with open(lf, "wb") as f:
        f.write(b"\xef\xbb\xbf-- \xed\x95\x9c\xea\xb8\x80 \xec\xa3\xbc\xec\x84\x9d\nSH_T = CSMakePolygon(3, 48, 0, 10, 0)\n"
                b"SH_P = CSMakePath({0,0},{1.5,-2.5},{-0.5,0.5})\nreturn 42\n")
    ck.eq("run_file 반환 (BOM 뗌)", cx.run_file(lf), 42)
    ck.eq("get", len(cx.get("SH_T")), 10)
    ck.eq("get 자르기", cx.get("SH_P").points, ((0, 0), (1, -2), (0, 0)))
    ck.eq("run", cx.run("SH_Q = CSMakeLine(1, 10, 90, 3, 1) return SH_Q[1]"), 2)
    ck.eq("run 뒤 get (90° = 3시)", cx.get("SH_Q").points, ((10, 0), (20, 0)))
    ck.true("files", len(cx.files) == 4 and cx.files[-1].endswith("map_shapes.lua"), cx.files)
    ck.true("FileDirectory", cx.lua.globals().FileDirectory.endswith("/"), cx.lua.globals().FileDirectory)
    # CSSave 가 FileDirectory 에 쓴다 (exists/isdir 흉내)
    ck.eq("invoke (도형이 아닌 반환)", cx.invoke("CSSaveWithName", "t_shape_save", 0, ring, "Ring"), None)
    ck.eq("invoke 값", cx.invoke("CS_Level", "Polygon", 6, 3), 19)
    ck.raises("invoke 없는 함수", EudextError, cx.invoke, "NoSuch")
    ck.true("CSSave 파일", os.path.isfile(os.path.join(cx.file_dir, "CS", "t_shape_save.txt")))
    # math.atan2 흉내 (CS_ShapeInShape)
    sis = cx.eval("CS_ShapeInShape(CSMakeCircle(6,32,0,19,0), CSMakePolygon(3,24,0,4,0), 1, 0, nil)")
    ck.eq("CS_ShapeInShape (math.atan2)", len(sis), 76)
    ck.eq("bit32.band 흉내", cx.value("bit32.band(-1.5, 0xFFFFFFFF)"), 0xFFFFFFFF)
    # 오류
    ck.raises("없는 함수", EudextError, cx.call, "CSMakeNothing", 1)
    ck.raises("Lua 오류 (CS_InputError 미정의)", EudextError, cx.eval, "CS_FillXY(0,{128,128},16,16)")
    ck.raises("도형이 아닌 값", EudextError, cx.eval, "42")
    ck.raises("점 수 음수", EudextError, cx.eval, "{-1}")
    ck.raises("점 수 소수", EudextError, cx.eval, "{1.5, {0,0}}")
    ck.raises("선언보다 짧은 표", EudextError, cx.eval, "{3, {0,0}, {1,1}}")
    ck.raises("점 모양", EudextError, cx.eval, "{1, {0}}")
    ck.raises("없는 전역", EudextError, cx.get, "SH_NONE")
    ck.raises("없는 파일", EudextError, cx.run_file, "no_such_file.lua")
    ck.raises("run 오류", EudextError, cx.run, "error('x')")
    ck.raises("lib_dir 없음", EudextError, CX, lib_dir=work)
    ck.raises("extra 없음", EudextError, CX, extra=["nope.lua"])
    ck.raises("reseed 실수", EudextError, cx.reseed, 1.5)
    ck.raises("to_lua 객체", EudextError, cx.to_lua, object())
    try:
        cx.eval("CS_FillXY(0,{128,128},16,16)")
    except EudextError as e:
        ck.true("Lua 오류 메시지에 줄 번호", "CB Paint v2.5.lua:4690" in str(e), str(e))


def lua_gunfade():
    """theSeed MapConfig/Shape.lua 의 GunFadeShape 원문을 잘라 돌릴 코드 (PushErrorMsg·G_CB_LoopSchedule 만 채움)."""
    path = os.path.join(_common.ROOT, "reference", "theSeed", "MapConfig", "Shape.lua")
    with open(path, "rb") as f:
        src = f.read().decode("utf-8")
    m = re.search(r"\nfunction GunFadeShape\(.*?\nend\n", src, re.S)
    return "GunFadeEnable = true\nG_CB_LoopSchedule = {}\n" + m.group(0)


def check_shape_api(ck, cx):
    s = Shape.from_points([(0, 0), (1.9, -1.9), (-3, 4)], name="t")
    ck.eq("from_points", s.points, ((0, 0), (1, -1), (-3, 4)))
    ck.eq("raw", s.raw, ((0, 0), (1.9, -1.9), (-3, 4)))
    ck.eq("from_flat", Shape.from_flat([0, 0, 1.9, -1.9, -3, 4]).points, s.points)
    ck.raises("from_flat 홀수", EudextError, Shape.from_flat, [1, 2, 3])
    ck.eq("len/iter/getitem", (len(s), list(s), s[2]), (3, [(0, 0), (1, -1), (-3, 4)], (-3, 4)))
    ck.eq("bounds", s.bounds(), (-3, -1, 1, 4))
    ck.eq("빈 bounds", Shape([]).bounds(), None)
    ck.true("eq/hash (내용)", s == Shape([(0, 0), (1, -1), (-3, 4)]) and hash(s) == hash(Shape([(0, 0), (1, -1), (-3, 4)])))
    ck.true("스케줄이 다르면 다름", s != s.with_schedule([1, 2]))
    ck.true("repr", "점 3" in repr(s) and "스케줄" in repr(s.with_schedule([3])), repr(s))
    ck.eq("FlattenList 가 Shape 를 풀지 않음", FlattenList([s, s]), [s, s])
    ck.raises("점 모양", EudextError, Shape, [(1,)])
    ck.raises("좌표 문자열", EudextError, Shape, [("a", 1)])
    ck.raises("좌표 None", EudextError, Shape, [(None, 1)])
    # 스케줄
    w = s.with_schedule([1, 0, 2])
    ck.eq("with_schedule", (w.points, w.schedule), (s.points, (1, 0, 2)))
    ck.eq("with_schedule 는 원본을 바꾸지 않음", s.schedule, None)
    ck.raises("빈 스케줄", EudextError, s.with_schedule, [])
    ck.raises("음수 스케줄", EudextError, s.with_schedule, [1, -1])
    ck.raises("끝나지 않는 스케줄", EudextError, s.with_schedule, [1, 0])
    ck.eq("합이 모자라도 마지막이 0 아니면 됨", s.with_schedule([1]).schedule, (1,))
    ck.raises("스케줄 문자열", EudextError, s.with_schedule, "12")
    # sweep: theSeed GunFadeShape(Lua 원문)와 같은 순서·스케줄
    L = cx.lua
    cx.run(lua_gunfade(), "=GunFadeShape")
    gf = L.globals().GunFadeShape
    sched_of = L.eval("function(s) local t = G_CB_LoopSchedule[s] local o = {} for i = 1, t[1] do o[i] = t[i+1] end return o end")
    srcs = {
        "circle": cx.eval("CSMakeCircle(6,32,0,37,0)"),
        "star": cx.eval("CSMakeStar(5,144,96,0,CS_Level('Star',5,3),0)"),
        "fill": cx.eval("CS_FillXY(0,128,96,16,16)"),
        "big": cx.eval("CSMakeCircle(12,16,0,300,0)"),
    }
    L.execute("""function __diamond(HalfW, HalfH, Step)
        local Pts = {}
        for x = -HalfW, HalfW, Step do
            local Limit = math.floor(HalfH * (1 - math.abs(x) / HalfW))
            for y = -math.floor(Limit / Step) * Step, Limit, Step do table.insert(Pts, {x, y}) end
        end
        local Shape = {#Pts}
        for i, P in ipairs(Pts) do Shape[i + 1] = P end
        return Shape
    end""")
    srcs["diamond"] = cx.eval("__diamond(320, 128, 32)")
    for name, src in srcs.items():
        for mode in ("right", "left", "in"):
            for ppc in (32, 16, 7.5):
                lt = gf(cx.to_lua(src), ppc, mode)
                want = cx.shape(lt)
                got = src.sweep(mode, px_per_cycle=ppc)
                ck.eq("sweep %s %s %s 순서" % (name, mode, ppc), got.points, want.points)
                ck.eq("sweep %s %s %s 스케줄" % (name, mode, ppc), list(got.schedule), shape.lua_to_py(sched_of(lt)))
    # theSeed 페이드 다이아몬드(640×256, 32px) — 원본 주석대로 밴드 21개
    fd = srcs["diamond"].sweep("right", 32)
    ck.eq("다이아몬드 밴드 수", len(fd.schedule), 21)
    # 새 모드(out/down/up)는 같은 규칙을 파이썬으로
    def ref_sweep(src, key, ppc):
        order = sorted(range(len(src.raw)), key=lambda i: key(src.raw[i]))
        pts = [src.raw[i] for i in order]
        lo = key(pts[0])
        counts = []
        for p in pts:
            b = int(math.floor((key(p) - lo) / ppc)) + 1
            counts += [0] * (b - len(counts))
            counts[b - 1] += 1
        return Shape(pts).points, counts
    for mode, key in (("out", lambda p: abs(p[0])), ("down", lambda p: p[1]), ("up", lambda p: -p[1])):
        for name, src in srcs.items():
            got = src.sweep(mode, 24)
            pts, counts = ref_sweep(src, key, 24)
            ck.eq("sweep %s %s" % (name, mode), (got.points, list(got.schedule)), (pts, counts))
    e = Shape([]).sweep("right")
    ck.eq("빈 도형 sweep", (len(e), e.schedule), (0, (0,)))
    ck.true("sweep 이름", srcs["circle"].sweep("left", 32).name.endswith("~left32"), srcs["circle"].sweep("left", 32).name)
    ck.eq("sweep 이름 (이름 없는 도형)", Shape([(1, 1)]).sweep("up", 8).name, "shape~up8")
    ck.raises("sweep 모드", EudextError, s.sweep, "diag")
    ck.raises("sweep 폭 0", EudextError, s.sweep, "right", 0)
    ck.raises("sweep 폭 문자열", EudextError, s.sweep, "right", "32")
    ck.true("sweep 은 새 객체", srcs["circle"].sweep("right") is not srcs["circle"].sweep("right"))


def check_encoding(ck):
    rng = random.Random(7)
    edges = [-32768, -32767, -1, 0, 1, 32766, 32767]
    pairs = [(x, y) for x in edges for y in edges] + [(rng.randint(-32768, 32767), rng.randint(-32768, 32767)) for _ in range(2000)]
    bad = [(x, y) for x, y in pairs if shape.decode_point(shape.encode_point(x, y)) != (x, y)]
    ck.eq("인코딩 왕복 %d쌍" % len(pairs), bad, [])
    ck.eq("인코딩 값", [shape.encode_point(0, 0), shape.encode_point(-32768, -32768), shape.encode_point(32767, 32767),
                      shape.encode_point(-3, 5)], [0x80008000, 0, M32, 0x80057FFD])
    ck.eq("f_ 별칭", (shape.f_encode_point(1, 2), shape.f_decode_point(0x80028001)), (0x80028001, (1, 2)))
    for x, y in ((32768, 0), (0, -32769), (1.5, 0), (True, 0), ("1", 0)):
        ck.raises("인코딩 범위 %r" % ((x, y),), EudextError, shape.encode_point, x, y)


def check_shapeset_compile(ck, cx):
    ring = cx.eval("CSMakeCircle(6,32,0,37,0)")
    ring2 = Shape(ring.raw)
    star = cx.eval("CSMakeStar(5,144,96,0,CS_Level('Star',5,3),0)")
    fade = ring.sweep("right")
    ss = ShapeSet([ring, star])
    ck.eq("add 번호", (ss.add(ring), ss.add(ring2), ss.add(fade), ss.add(fade.with_schedule(fade.schedule))), (0, 0, 2, 2))
    ck.eq("sid_of", (ss.sid_of(ring), ss.sid_of(ring2), ss.sid_of(star)), (0, 0, 1))
    ck.eq("중복 제거: 좌표 한 번 (fade 는 순서가 달라 따로)", ss.stored_points, 37 + 31 + 37)
    ck.eq("len/getitem/shapes", (len(ss), ss[1] is star, len(ss.shapes)), (3, True, 3))
    ck.eq("max_count / data_bytes", (ss.max_count, ss.data_bytes), (37, 4 * 105))
    same = ShapeSet([ring, ring.with_schedule([37])])
    ck.eq("같은 좌표 다른 스케줄: sid 둘, 좌표 한 번", (len(same), same.stored_points), (2, 37))
    nd = ShapeSet([ring, ring2], dedupe=False)
    ck.eq("dedupe=False", (len(nd), nd.stored_points, nd.add(ring)), (2, 74, 0))
    ck.eq("점 목록 add", ss.add([(1, 2), (3, 4)]), 3)
    va = ShapeSet([ring], storage="varray")
    ck.eq("varray 크기·간격", (va.data_bytes, va.step), (37 * 144, 144))
    ck.raises("storage 이름", EudextError, ShapeSet, [], storage="array")
    ck.raises("dedupe 형식", EudextError, ShapeSet, [], dedupe=1)
    ck.raises("Shape 하나를 목록 대신", EudextError, ShapeSet, ring)
    ck.raises("Shape 아님", EudextError, ss.add, 5)
    ck.raises("넣지 않은 도형", EudextError, ss.sid_of, cx.eval("CSMakeCircle(6,32,0,7,0)"))
    ck.raises("db 좌표 범위", EudextError, ShapeSet, [Shape([(40000, 0)])])
    ck.eq("varray 는 32비트 좌표", ShapeSet([Shape([(40000, -70000)])], storage="varray").stored_points, 1)
    ck.true("repr", "도형 4" in repr(ss), repr(ss))


def check_lupa_loader(ck):
    ck.eq("lupa 기본 경로 (venv)", shape.LUPA_SOURCE, "기본 경로")
    cands = shape.lupa_site_candidates()
    ck.true("후보에 저장소 .tools", any(c.endswith(os.path.join(".tools", "euddraft_site")) for c in cands), cands)
    ck.true("후보에 ~/.venvs/euddraft011_site", any(c.endswith(os.path.join(".venvs", "euddraft011_site")) for c in cands), cands)
    old = os.environ.get(shape.LUPA_SITE_ENV)
    os.environ[shape.LUPA_SITE_ENV] = os.pathsep.join(["/a", "/b"])
    try:
        ck.eq("환경 변수 후보가 앞", shape.lupa_site_candidates()[:2], ["/a", "/b"])
    finally:
        if old is None:
            del os.environ[shape.LUPA_SITE_ENV]
        else:
            os.environ[shape.LUPA_SITE_ENV] = old
    # 폴더 찾기: 기본 경로에서 lupa 를 못 찾는 프로세스를 만들고 EUDEXT_LUPA_SITE 로 venv 의 lupa 를 알려 준다
    import lupa

    site = os.path.dirname(os.path.dirname(lupa.__file__))
    fake = os.path.join(_common.WORK, "t_shape_fake_site")
    os.makedirs(fake, exist_ok=True)
    link = os.path.join(fake, "lupa")
    if not os.path.exists(link):
        try:
            os.symlink(os.path.dirname(lupa.__file__), link)
        except OSError:
            shutil.copytree(os.path.dirname(lupa.__file__), link)
    code = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "import eudplib\n"
        "sys.path[:] = [p for p in sys.path if p != %r]\n"
        "import eudext.shape as s\n"
    ) % (_common.ROOT, site)
    ok_code = code + "print('SRC', s.LUPA_SOURCE)\nprint('N', len(s.CX().eval('CSMakeCircle(6,32,0,37,0)')))\n"
    env = dict(os.environ, EUDEXT_LUPA_SITE=fake, EUDEXT_WORK=_common.WORK, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-c", ok_code], capture_output=True, env=env, timeout=120)
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    ck.true("폴더 찾기 적재 (EUDEXT_LUPA_SITE)", "SRC " + fake in out and "N 37" in out, out[-1500:])
    ck.true("폴더 찾기 알림 줄", "[eudext.shape] lupa" in out, out[-1500:])
    # 못 찾으면: import 는 되고(Shape/ShapeSet 은 쓸 수 있음) CX 에서 EudextError. 저장소 .tools 폴더(cp314)는 3.13 에서 실패해야 한다
    bad_code = code + (
        "print('SS', len(s.ShapeSet([s.Shape([(1, 2)])])))\n"
        "s._ROOT = '/nonexistent'\n"
        "try:\n    s.CX()\n    print('NOERR')\nexcept s.EudextError as e:\n    print('ERR', 'lupa' in str(e))\n"
        "print('TRIED', len(s._lupa_errors))\n"
    )
    env2 = dict(env, EUDEXT_LUPA_SITE=os.path.join(fake, "none"), HOME=os.path.join(fake, "home"))
    p = subprocess.run([sys.executable, "-c", bad_code], capture_output=True, env=env2, timeout=120)
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    ck.true("lupa 없음 → Shape 는 됨, CX 는 EudextError", "SS 1" in out and "ERR True" in out, out[-1500:])
    ck.true("cp314 폴더는 3.13 에서 거절", re.search(r"TRIED [3-9]", out) is not None, out[-1500:])


def python_checks(ck):
    cx = make_cx()
    shapes = snapshot_shapes(cx)
    check_snapshot(ck, shapes)
    check_trunc_rule(ck, cx)
    t0 = time.time()
    check_crmath(ck)
    check_lua_math(ck, make_cx())
    print("  정확 반올림 수학 시험 %.2fs, 캐시 %r" % (time.time() - t0, _crmath.cache_info()))
    check_hollow_nan(ck, cx)
    check_cx_api(ck, make_cx())
    check_shape_api(ck, make_cx())
    check_encoding(ck)
    check_shapeset_compile(ck, make_cx())
    check_lupa_loader(ck)
    return shapes


# =============================================================================================
# 원본 TEP(헤드리스 tepc) 대조
# =============================================================================================


def tep_script():
    lib = shape.DEFAULT_LIB_DIR.replace("\\", "/") + "/"
    lines = [
        "-- eudext t_shape: CB Paint 도형을 TEP 안에서 계산해 좌표를 bit32.band(파일 배열 규칙)로 트리거 값에 싣는다",
        'local LIB = "%s"' % lib,
        'dofile(LIB .. "CB Paint v2.5.lua")',
    ]
    lines += ['dofile(LIB .. "%s")' % e for e in EXTRA]
    lines += [
        "math.randomseed(%d)" % SEED,
        GRAPH_FN,
        "local function emit(k, s)",
        "  local acts = {}",
        "  local function flush()",
        "    if #acts > 0 then Trigger { players = {P1}, conditions = { Always() }, actions = acts, flag = {preserved} } end",
        "    acts = {}",
        "  end",
        "  for i = 1, s[1] do",
        "    acts[#acts+1] = SetDeathsX(P1, SetTo, bit32.band(s[i+1][1], 0xFFFFFFFF), k, 0xFFFFFFFF)",
        "    acts[#acts+1] = SetDeathsX(P1, SetTo, bit32.band(s[i+1][2], 0xFFFFFFFF), k, 0xFFFFFFFF)",
        "    if #acts >= 64 then flush() end",
        "  end",
        "  flush()",
        "end",
    ]
    for k, name in enumerate(SNAP_ORDER):
        lines.append("emit(%d, %s)" % (k + 1, SNAP[name][0]))
    # 직접 캐스트(luaL_checkint_Fix — 정적 CSPlot 경로)와 bit32 경로의 NaN·소수 차이 기록
    lines += [
        "local r = CS_MoveRA(CSMakeCircle(6,32,0,7,0),10,30)",
        "Trigger { players = {P1}, conditions = { Always() }, actions = {",
        "  SetDeathsX(P1, SetTo, bit32.band(r[2][1], 0xFFFFFFFF), 100, 0xFFFFFFFF),",
        "  SetDeathsX(P1, SetTo, r[2][1], 100, 0xFFFFFFFF),",
        "  SetDeathsX(P1, SetTo, -15.999999999999998, 100, 0xFFFFFFFF),",
        "  SetDeathsX(P1, SetTo, bit32.band(-49.999, 0xFFFFFFFF), 100, 0xFFFFFFFF) }, flag = {preserved} }",
    ]
    return "\n".join(lines) + "\n"


def tep_compare(ck, shapes):
    """헤드리스 TEP(tepc, TrigEditPlus v3.0 인코더 그대로)에서 같은 식을 계산한 좌표 = lupa + tep_int 결과."""
    if not os.path.isfile(TEPC):
        print("  tepc 없음: %s — 원본 TEP 대조 건너뜀 (EUDEXT_TEPC 로 지정)" % TEPC)
        return
    sys.path.insert(0, EX)
    try:
        import mathx_tep_check as tc
    finally:
        sys.path.remove(EX)
    work = os.path.join(_common.WORK, "t_shape_tepc")
    os.makedirs(work, exist_ok=True)
    lua = os.path.join(work, "shapes.lua")
    with open(lua, "w", encoding="utf-8") as f:
        f.write(tep_script())
    base = os.path.join(work, "in.scx")
    shutil.copy2(BASE_MAP, base)
    out = os.path.join(work, "out.scx")
    p = subprocess.run([TEPC, base, lua, out, "--quiet"], capture_output=True, stdin=subprocess.DEVNULL, timeout=300)
    ck.eq("tepc 실행", p.returncode, 0)
    if p.returncode != 0:
        print(p.stdout.decode("utf-8", "replace")[-2000:], p.stderr.decode("utf-8", "replace")[-2000:])
        return
    got = {}
    for _conds, acts in tc.triggers(tc.read_chk(out)):
        for unit, atype, val in acts:
            if atype == 45:
                got.setdefault(unit, []).append(val - (1 << 32) if val & 0x80000000 else val)
    for k, name in enumerate(SNAP_ORDER):
        vals = got.get(k + 1, [])
        tep_pts = list(zip(vals[0::2], vals[1::2]))
        ours = list(shapes[name].points)
        known = TEP_KNOWN.get(name, {})
        if known and len(tep_pts) == len(ours):
            # 알려진 예외(TEP_KNOWN 주석): tepc 의 C 수학 라이브러리가 정확 반올림이 아니라 다른 점. 그 점은 tepc 값이
            # 우리 값(수학 라이브러리가 바뀐 tepc) 또는 알려진 값이어야 하고, 나머지 점은 모두 같아야 한다.
            odd = {i: tep_pts[i] for i in known if tep_pts[i] not in (ours[i], known[i])}
            ck.eq("TEP 대조 %s 알려진 예외 점 %s (tepc 수학 = 비정확 반올림)" % (name, sorted(known)), odd, {})
            seen = sorted(i for i in known if tep_pts[i] == known[i] != ours[i])
            print("  TEP 대조 %s: 알려진 예외 %d/%d점이 tepc 에서 다름 %s (원본 플러그인·eudext = %s)" % (
                name, len(seen), len(known), [tep_pts[i] for i in seen], [ours[i] for i in seen]))
            tep_pts = [ours[i] if i in known else p for i, p in enumerate(tep_pts)]
        ck.eq("TEP 대조 %s (%d점)" % (name, len(ours)), tep_pts, ours)
    ck.eq("TEP NaN: bit32 경로 0, 직접 캐스트 0x80000000, 소수 0 방향", got.get(100), [0, -(1 << 31), -15, -49])


# =============================================================================================
# 에뮬레이터 (ShapeSet 읽기)
# =============================================================================================

CXE = make_cx()
E_SHAPES = {name: CXE.eval(SNAP[name][0], name=name) for name in SNAP_ORDER}
E_LIST = [E_SHAPES["circle"], E_SHAPES["star"], E_SHAPES["circle"].sweep("right"), E_SHAPES["movera"],
          Shape([(-32768, 32767), (32767, -32768), (0, 0), (-1, -1)], name="edge"), Shape([], name="empty"),
          E_SHAPES["circle"].with_schedule([1, 6, 12, 18]), E_SHAPES["big"]]
SS_DB = ShapeSet(E_LIST, name="t_db")
SS_VA = ShapeSet(E_LIST, storage="varray", name="t_va")
SS_ND = ShapeSet(E_LIST[:3] + [Shape(E_LIST[0].raw)], dedupe=False, name="t_nd")
LAZY = ShapeSet([E_LIST[0]], name="t_lazy")


def build_cases(s):
    for tag, ss in (("db", SS_DB), ("va", SS_VA), ("nd", SS_ND)):
        def pa(t, ss=ss):
            x, y = ss.point_at(t.var("sid"), t.var("i"))
            t.out("x", x)
            t.out("y", y)

        def cnt(t, ss=ss):
            st, n, sc = ss.lookup(t.var("sid"))
            t.out("st", st)
            t.out("n", n)
            t.out("sc", sc)
            t.out("n2", ss.count(t.var("sid")))
            t.out("st2", ss.start(t.var("sid")))
            t.out("sc2", ss.schedule(t.var("sid")))

        def const_sid(t, ss=ss):
            x, y = ss.point_at(1, t.var("i"))
            t.out("x", x)
            t.out("y", y)

        def seq(t, ss=ss):
            # 커서를 직접 진행하며 읽는다 (Plotter 와 같은 방식)
            st = ss.start(t.var("sid"))
            cur = EUDVariable()
            cur << st
            k = t.var("k")
            from eudplib import EUDEndWhile, EUDWhile

            if EUDWhile()(k.AtLeast(1)):
                cur += ss.step
                k -= 1
            EUDEndWhile()
            x, y = ss.read_at(cur)
            t.out("x", x)
            t.out("y", y)

        def pf(t, ss=ss):
            st = ss.start(t.var("sid"))
            ss.point_from(st, t.var("i"), ret=[t.var("x"), t.var("y")])

        s.case(tag + "_pa")(pa)
        s.case(tag + "_cnt")(cnt)
        s.case(tag + "_const")(const_sid)
        s.case(tag + "_seq")(seq)
        s.case(tag + "_pf")(pf)

    @s.case("fold")
    def _(t):
        x, y = SS_DB.point_at(1, 3)
        t.out("py", x * 1000 + y)
        n = SS_DB.count(2)
        st, n2, sc = SS_DB.lookup(6)
        t.out("n", n + n2)
        t.out("sc", sc)
        t.out("st", SS_DB.start(0))
        SS_DB.point_at(1, 3, ret=[t.var("rx"), t.var("ry")])
        SS_VA.lookup(6, ret=[t.var("vst"), t.var("vn"), t.var("vsc")])

    @s.case("tables")
    def _(t):
        for k in range(len(SS_DB)):
            t.out("st%d" % k, SS_DB.start(k))
            t.out("sc%d" % k, SS_DB.schedule(k))

    @s.case("lazy")
    def _(t):
        x, y = LAZY.point_at(t.var("sid"), t.var("i"))
        t.out("x", x)
        t.out("y", y)
        t.out("n", LAZY.count(t.var("sid")))

    @s.case("err_const_sid", expect_build_error=EudextError, expect_message="범위 밖")
    def _(t):
        SS_DB.point_at(len(SS_DB), 0)

    @s.case("err_const_i", expect_build_error=EudextError, expect_message="점 번호")
    def _(t):
        SS_DB.point_at(0, 37)

    @s.case("err_empty", expect_build_error=EudextError, expect_message="점이 없습니다")
    def _(t):
        SS_VA.point_at(5, t.var("i"))

    @s.case("err_sid_type", expect_build_error=EudextError)
    def _(t):
        SS_DB.count("a")

    @s.case("err_i_float", expect_build_error=EudextError)
    def _(t):
        SS_DB.point_at(0, 1.5)


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def run_emu(s, rng):
    m = s.machine
    for tag, ss in (("db", SS_DB), ("va", SS_VA), ("nd", SS_ND)):
        shapes = ss.shapes
        for sid, shp in enumerate(shapes):
            n = len(shp)
            idx = list(range(n)) if n <= 64 else sorted({0, 1, n - 1} | set(rng.sample(range(n), 40)))
            for i in idx:
                x, y = shp.points[i]
                s.check(tag + "_pa", {"sid": sid, "i": i}, {"x": x, "y": y}, label="%s pa %d/%d" % (tag, sid, i))
                s.check(tag + "_pf", {"sid": sid, "i": i}, {"x": x, "y": y}, label="%s pf %d/%d" % (tag, sid, i))
            for i in idx[:12]:
                x, y = shp.points[i]
                s.check(tag + "_seq", {"sid": sid, "k": i}, {"x": x, "y": y}, label="%s seq %d/%d" % (tag, sid, i))
            r = s.run(tag + "_cnt", {"sid": sid})
            s.expect_true(tag + "_cnt", r.values["n"] == n and r.values["n2"] == n, "%s count %d" % (tag, sid), repr(r.values))
            s.expect_true(tag + "_cnt", r.values["st"] == r.values["st2"] and r.values["sc"] == r.values["sc2"],
                          "%s lookup = start/schedule %d" % (tag, sid), repr(r.values))
            if shp.schedule is not None:
                sc = r.values["sc"]
                mem = [m.dw(0x58A364 + 4 * (sc + k)) for k in range(len(shp.schedule) + 1)]
                s.expect_true(tag + "_cnt", mem == [len(shp.schedule)] + list(shp.schedule),
                              "%s 스케줄 표 %d" % (tag, sid), repr(mem))
            else:
                s.expect_true(tag + "_cnt", r.values["sc"] == 0, "%s 스케줄 없음 %d" % (tag, sid), repr(r.values))
            if tag != "va" and n:
                st = r.values["st"]
                mem = [shape.decode_point(m.dw(0x58A364 + 4 * (st + k))) for k in range(n)]
                s.expect_true(tag + "_cnt", mem == list(shp.points), "%s 좌표표 메모리 %d" % (tag, sid))
        for sid in (len(shapes), len(shapes) + 1, 0x7FFFFFFF, M32):
            s.check(tag + "_cnt", {"sid": sid}, {"n": 0, "st": 0, "sc": 0, "n2": 0, "st2": 0, "sc2": 0},
                    label="%s 범위 밖 sid %d" % (tag, sid))
        star = shapes[1]
        for i in range(len(star)):
            x, y = star.points[i]
            s.check(tag + "_const", {"i": i}, {"x": x, "y": y}, label="%s const %d" % (tag, i))
    # 중복 제거: 같은 좌표는 같은 시작 주소
    r = s.run("db_cnt", {"sid": 0})
    r6 = s.run("db_cnt", {"sid": 6})
    s.expect_true("db_cnt", r.values["st"] == r6.values["st"], "db 같은 좌표 같은 시작", repr((r.values, r6.values)))
    r = s.run("nd_cnt", {"sid": 0})
    r3 = s.run("nd_cnt", {"sid": 3})
    s.expect_true("nd_cnt", r.values["st"] != r3.values["st"], "dedupe=False 따로 싣기", repr((r.values, r3.values)))
    # 상수 접기
    x, y = SS_DB[1].points[3]
    sched6 = SS_DB.schedule(6)
    r = s.run("fold")
    s.expect_true("fold", s32(r.values["py"]) == x * 1000 + y and r.values["n"] == 37 + 37, "상수 점·개수", repr(r.values))
    s.expect_true("fold", (r.values["rx"], r.values["ry"]) == (x & M32, y & M32), "상수 점 ret", repr(r.values))
    s.expect_true("fold", r.values["vn"] == 37 and r.values["vsc"] != 0, "varray lookup ret", repr(r.values))
    rt = s.run("tables")
    s.expect_true("tables", rt.values["sc6"] == r.values["sc"] != 0 and rt.values["st0"] == r.values["st"],
                  "상수 표 값 = 변수 읽기", repr((rt.values, r.values, sched6)))
    # 게으른 표: 페이로드를 쓰는 동안에는 더할 수 없고, 다 쓴 뒤에 더한 도형은 다음 빌드에 실린다
    w = LAZY._tstart

    class _Buf:
        def WriteBytes(self, b):
            pass

        def WriteDword(self, v):
            pass

    s.expect_true("lazy", not w.frozen, "빌드가 끝나면 풀림")
    w.CollectDependency(_Buf())
    s.expect_true("lazy", _raises(lambda: LAZY.add(Shape([(1, 1)]))), "페이로드를 모으는 중 add 는 오류")
    w.WritePayload(_Buf())
    s.expect_true("lazy", _raises(lambda: LAZY.add(Shape([(1, 1)]))), "할당 단계 쓰기 뒤에도 굳어 있음")
    w.WritePayload(_Buf())
    w.GetDataSize()
    s.expect_true("lazy", LAZY.add(Shape([(5, -7), (9, 11)], name="later")) == 1, "다 쓴 뒤 add 는 다음 빌드용")
    s.check("lazy", {"sid": 0, "i": 1}, {"x": 0, "y": -32, "n": 37})
    s.check("lazy", {"sid": 1, "i": 0}, {"n": 0, "x": 0, "y": 0}, label="lazy 두 번째 도형은 이 빌드에 없음 (0, 0)")


def _raises(fn):
    try:
        fn()
    except EudextError:
        return True
    return False


def lazy_second_build(ck):
    """다음 빌드에서는 LAZY 에 도형을 더할 수 있고, 변수 sid 의 범위도 늘어난다(_compat.register_build_reset)."""
    ck.eq("두 번째 빌드: 이미 더한 도형", LAZY.sid_of(LAZY[1]), 1)
    ck.eq("두 번째 빌드 add", LAZY.add(Shape([(1, 2)], name="later2")), 2)
    s = Suite("t_shape_lazy2", verbose=False)

    @s.case("lazy")
    def _(t):
        x, y = LAZY.point_at(t.var("sid"), t.var("i"))
        t.out("x", x)
        t.out("y", y)
        t.out("n", LAZY.count(t.var("sid")))

    s.build()
    s.check("lazy", {"sid": 1, "i": 1}, {"x": 9, "y": 11, "n": 2})
    s.check("lazy", {"sid": 2, "i": 0}, {"x": 1, "y": 2, "n": 1})
    s.check("lazy", {"sid": 3, "i": 0}, {"n": 0})
    ok = s.report()
    ck.true("두 번째 빌드 결과", ok)


# =============================================================================================
# epScript 예제 · euddraft
# =============================================================================================


def eps_checks(ck):
    src = open(os.path.join(EX, "shape_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("shape_example.eps", src)
    ck.eq("shape_example 번역 오류", nerr, 0)
    for needle in ("shape.CX(seed=1234)", 'cx.call("CSMakeCircle", 6, 32, 0, 37, 0)', 'ring.sweep("right", px_per_cycle=32)',
                   "shape.Shape.from_flat(FlattenList([0, 0, 16, -16, -3, 5]))",
                   "shape.ShapeSet(FlattenList([ring, star, fade, dots]))", 'storage="varray"',
                   "shapes.point_at(sid, idx)", "shapes.lookup(2)"):
        ck.true("eps: " + needle, out is not None and needle in out, "")


def eps_emulate(ck):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_shape_eps")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "shape_example.eps"), os.path.join(work, "shape_example.eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "shape_example.eps"), {})
    prog = emu.Program(mod.afterTriggerExec)
    names = ("sid", "idx", "px", "py", "n", "vx", "vy", "band0", "bands", "cnt2", "frame", "star3")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m)
    ring, star = mod.ring, mod.star
    dots = [(0, 0), (16, -16), (-3, 5)]
    rows = []
    for sid, idx in ((0, 2), (1, 4), (2, 0), (3, 2), (4, 0), (0, 36)):
        m.set_var("sid", sid)
        m.set_var("idx", idx)
        m.cycle()
        got = {k: m.var(k) for k in names}
        rows.append(got)
        shp = mod.shapes[sid] if sid < 4 else None
        want_xy = shp.points[idx] if shp is not None else (0, 0)
        want = {"n": len(shp) if shp is not None else 0, "vx": dots[idx % 3][0] & M32, "vy": dots[idx % 3][1] & M32,
                "band0": 5, "bands": 6, "cnt2": 37, "star3": 56 * 1000 - 18,
                "px": want_xy[0] & M32, "py": want_xy[1] & M32}
        ck.eq("eps emu sid=%d idx=%d" % (sid, idx), {k: got[k] for k in want}, want)
    ck.eq("eps emu ring·star", (len(ring), len(star)), (37, 31))
    texts = [x for x in m.log if x[0] == "act" and x[1] == 9]
    ck.eq("eps 출력 한 줄", len(texts), 1)
    print("  shape epScript 에뮬레이션: 페이로드 %d B, 마지막 %r" % (prog.payload_size, rows[-1]))


def euddraft_builds(ck):
    """번들 파이썬(3.14)에서 lupa 적재: ① 예제 eds(Preload, VenvSite 없음 → 폴더 찾기) ② VenvSite 절대 경로 ③ Preload 없음."""
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    site = os.path.join(_common.ROOT, ".tools", "euddraft_site")
    # 확장 파일 이름: Linux `lua54.cpython-314-….so`, Windows `lua54.cp314-win_amd64.pyd`
    ck.true("euddraft 용 lupa 폴더 (cp314)", os.path.isdir(os.path.join(site, "lupa")) and any(
        f.startswith(("lua54.cpython-314", "lua54.cp314-")) for f in os.listdir(os.path.join(site, "lupa"))), site)
    src = os.path.join(EX, "shape_example.eds")
    base = os.path.join(_common.WORK, "t_shape_eds")
    os.makedirs(base, exist_ok=True)
    text = open(src, encoding="utf-8").read()
    variants = {"shape_example": src}
    v2 = os.path.join(base, "venv", "shape_example.eds")
    v3 = os.path.join(base, "nopre", "shape_example.eds")
    pre = re.compile(r"(?m)^Preload : shape$")
    for path, body in ((v2, pre.sub("Preload : shape\nVenvSite : %s" % site.replace("\\", "/"), text)),
                       (v3, pre.sub("", text))):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        body = body.replace("input : ../testing/base.scx", "input : %s" % BASE_MAP)
        body = body.replace("[../boot.py]", "[%s]" % os.path.join(_common.PKG, "boot.py"))
        body = body.replace("EudextRoot : ../..", "EudextRoot : %s" % _common.ROOT)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        shutil.copy2(os.path.join(EX, "shape_example.eps"), os.path.join(os.path.dirname(path), "shape_example.eps"))
    variants["venvsite"] = v2
    variants["no_preload"] = v3
    for tag, eds in variants.items():
        work = os.path.join(_common.WORK, "t_shape_build_" + tag)
        new_eds, out_map = build.prepare_eds(eds, work)
        r = build.run_euddraft(new_eds, out_map=out_map, log_path=os.path.join(work, tag + ".log"))
        print("  %s: %s" % (tag, r.summary()))
        ck.true("euddraft " + tag, r.ok, r.log[-2000:])
        ck.true("eps compiled " + tag, '[epScript] Compiling "shape_example.eps"' in r.log, "")
        if tag == "shape_example":
            ck.true("boot preload shape", "preload=shape venv=-" in r.log, r.log[:800])
        if tag == "venvsite":
            ck.true("boot VenvSite", "preload=shape venv=yes" in r.log, r.log[:800])
            ck.true("VenvSite 면 폴더 찾기를 안 씀", "[eudext.shape] lupa" not in r.log, r.log[:800])
        if tag == "no_preload":
            ck.true("Preload 없이도 폴더 찾기로 적재", "[eudext.shape] lupa 2.8 를 불러왔습니다: " + site in r.log, r.log[:800])


def measure_scx():
    """scx 증가(압축 뒤): 1,700점 원 하나("db"·"varray")와 도형 50개(각 37점) — 빈 빌드와 파일 크기 차이."""
    rows = []

    def build(tag, fn):
        _compat.reset_build_state()
        LoadMap(BASE_MAP)
        CompressPayload(True)
        ShufflePayload(False)
        v = EUDVariable()

        def main():
            if EUDInfLoop()():
                _compat.set_game_loop_start()
                fn(v)
                EUDDoEvents()
            EUDEndInfLoop()

        out = os.path.join(_common.WORK, "t_shape_scx_%s.scx" % tag)
        SaveMap(out, main)
        ShufflePayload(True)
        return os.path.getsize(out)

    def use(ss):
        return lambda v: ss.point_at(v, v)

    big = E_SHAPES["big"]
    empty = build("empty", lambda v: v.AddNumber(1))
    one = build("db1", use(ShapeSet([Shape([(0, 0)])])))
    rows.append(("도형 1개 1점 (\"db\", 읽기 코드 포함)", one - empty))
    rows.append(("1,700점 원 (\"db\")", build("db1700", use(ShapeSet([big]))) - empty))
    rows.append(("1,700점 원 (\"varray\")", build("va1700", use(ShapeSet([big], storage="varray"))) - empty))
    rng = random.Random(3)
    many = [Shape([(rng.randint(-500, 500), rng.randint(-500, 500)) for _ in range(37)]) for _ in range(50)]
    rows.append(("도형 50개 × 37점 (\"db\")", build("db50", use(ShapeSet(many))) - empty))
    for name, d in rows:
        print("  scx 증가 %-36s %+d B" % (name, d))
    return dict(rows)


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

C_DB = ShapeSet([E_SHAPES["circle"], E_SHAPES["star"], E_SHAPES["circle"].sweep("right")], name="cost_db")
C_VA = ShapeSet([E_SHAPES["circle"], E_SHAPES["star"]], storage="varray", name="cost_va")
C_BIG = ShapeSet([E_SHAPES["big"]] + [E_SHAPES[n] for n in SNAP_ORDER], name="cost_big")


_CUR = {}


def _cost_seq(ss):
    def build(t):
        ss.read_at(_CUR[ss.name])

    return build


def _cost_seq_setup(ss):
    _CUR[ss.name] = EUDVariable()  # 준비 케이스와 잴 케이스가 같은 커서를 쓴다 (케이스 입력 칸은 케이스마다 따로)

    def setup(t):
        _CUR[ss.name] << ss.start(1)

    return setup


COST_CASES = [
    CostCase("point_at(변수 sid, 변수 i) db", lambda t: C_DB.point_at(t.var("s"), t.var("i")), [{"s": 0, "i": 3}, {"s": 1, "i": 30}],
             funcs=[shape._db_reader()], note="주소표 읽기 + 점 읽기"),
    CostCase("point_at(상수 sid, 변수 i) db", lambda t: C_DB.point_at(1, t.var("i")), {"i": 5}),
    CostCase("point_at(변수 sid, 변수 i) db, 도형 18개·점 3,900", lambda t: C_BIG.point_at(t.var("s"), t.var("i")),
             [{"s": 0, "i": 1600}, {"s": 17, "i": 3}], note="도형 수·점 수와 무관"),
    CostCase("read_at(변수 커서) db", _cost_seq(C_DB), setup=_cost_seq_setup(C_DB), funcs=[shape._db_reader()],
             note="Plotter 의 점 읽기 몫"),
    CostCase("point_at(변수 sid, 변수 i) varray", lambda t: C_VA.point_at(t.var("s"), t.var("i")), [{"s": 0, "i": 3}, {"s": 1, "i": 30}],
             funcs=[shape._varray_index_fn()], note="144·i 곱 포함"),
    CostCase("read_at(변수 커서) varray", _cost_seq(C_VA), setup=_cost_seq_setup(C_VA), note="원소 사슬 점프 + 복사"),
    CostCase("count(변수 sid)", lambda t: C_DB.count(t.var("s")), [{"s": 1}, {"s": 99}], note="범위 밖 sid 포함"),
    CostCase("lookup(변수 sid)", lambda t: C_DB.lookup(t.var("s")), [{"s": 2}, {"s": 99}]),
    CostCase("point_at(상수, 상수) (접기)", lambda t: t.out("x", C_DB.point_at(1, 2)[0])),
]


def main():
    rng = random.Random(11)
    ck = Checker("t_shape (python)")
    shapes = python_checks(ck)
    ckt = Checker("t_shape (TEP 대조)")
    tep_compare(ckt, shapes)

    s = Suite("t_shape")
    build_cases(s)
    s.build()
    run_emu(s, rng)
    ok1 = s.report()
    ckl = Checker("t_shape (다음 빌드)")
    lazy_second_build(ckl)

    cke = Checker("t_shape (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    euddraft_builds(cke)
    rows = measure_scx()
    cke.true("scx 1,700점 db ≤ 8KB (좌표 6.8KB)", rows["1,700점 원 (\"db\")"] <= 8000, repr(rows))
    finish(ok1, ck.report(), ckt.report(), ckl.report(), cke.report())


if __name__ == "__main__":
    main()
