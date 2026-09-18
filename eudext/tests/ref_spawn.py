"""`spawn` 참조 모델 (파이썬) — S1 6절 의미(theSeed G_CB + CAPlotIndexed)와 8.1 표의 eudext 규칙.

S1 이 말한 `gcb_ref.py` 는 저장소에 없어서 S1 9.1·9.2 기대값과 명세로 새로 짰다. 회전·길이 계산은 `ref_mathx`
(CtrigAsm Lua 원문을 옮긴 참조, spawn.py 의 파이썬 계산과 따로 짠 것)를 쓴다.

모델
- 레코드 = 층 하나. `recs` 는 살아 있는 레코드를 **넣은 순서**로 둔다(pool 순회 규칙).
- 넣기: 빈 칸(capacity − 살아 있는 수)이 층 수보다 적으면 통째로 버리고 overflow += 1.
- tick: 시작할 때 목록을 고정(tick 중에 넣은 작업은 다음 tick). 레코드마다
    바로 앞 레코드가 "다음 층 있음" 으로 끝났으면 w = 2
    w == 0 이면: L = 스케줄[ptr](ptr < 밴드 수면 ptr += 1) 또는 lm, k = min(L, 남은 점), k 번 변환·경계·소환,
               w = delay, 남은 점 0 이면 끝(목록에서 뺌)
    w = max(w − 1, 0)
- 변환: 크기(S ≠ 100 이면 CiDiv(x·S mod 2³², 100)) → 회전(rot ≠ 0 또는 전역: CA_Rotate, 전역각은 점마다 읽음)
        → + (dx + cx), + (dy + cy) (32비트) → X ≤ W−1 이고 Y ≤ H−1(부호 없음)이면 소환
"""

import ref_mathx as RM

M32 = 0xFFFFFFFF
INF = M32
LM_MAX = 255

u32, s32 = RM.u32, RM.s32


def tdiv(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def size_py(x, y, size):
    """S1 6.3-1: x·S/100 (곱 32비트, 0 방향)."""
    if size == 100:
        return x, y
    return tdiv(s32(x * size), 100), tdiv(s32(y * size), 100)


def rotate_py(x, y, a, cycle=360):
    """S1 6.3-2: CtrigAsm CA_Rotate (ref_mathx) → 부호 있는 값."""
    X, Y = RM.rotate(x, y, a, cycle)
    return s32(X), s32(Y)


def lengthdir_py(r, a, cycle=360):
    c, s = RM.lengthdir(r, a, cycle)
    return s32(c), s32(s)


def transform(x, y, size=100, rot=0, glob=False, rotation=0, dx=0, dy=0, cx=0, cy=0, cycle=360, W=4096, H=4096):
    """점 하나 → (X, Y, 소환하나). X·Y 는 부호 없는 32비트."""
    x, y = size_py(x, y, size)
    if glob:
        x, y = rotate_py(x, y, rotation, cycle)
    elif u32(rot):
        x, y = rotate_py(x, y, rot, cycle)
    X = u32(x + dx + cx)
    Y = u32(y + dy + cy)
    return X, Y, (X <= W - 1 and Y <= H - 1)


class Layer:
    """넣을 층 하나의 값 (파이썬 참조용)."""

    def __init__(self, unit, points, owner=7, lm=LM_MAX, delay=0, size=100, rot=0, glob=False, rtype=0,
                 schedule=None, tag=None):
        self.unit = unit
        self.points = list(points)
        self.owner = owner
        self.lm = (len(self.points) // 50 + 1) if lm == 0 else lm
        self.delay = delay
        self.size = size
        self.rot = u32(rot)
        self.glob = glob
        self.rtype = rtype
        self.schedule = None if schedule is None else tuple(schedule)
        self.tag = tag


class Rec:
    __slots__ = ("layer", "job", "index", "pc", "left", "sp", "w", "has_next", "cx", "cy", "dx", "dy", "order")

    def __init__(self, layer, job, index, has_next, cx, cy, dx, dy, order):
        self.layer = layer
        self.job = job
        self.index = index
        self.pc = 0
        self.left = len(layer.points)
        self.sp = 1 if layer.schedule is not None else 0
        self.w = 0 if index == 0 else INF
        self.has_next = has_next
        self.cx, self.cy, self.dx, self.dy = cx, cy, dx, dy
        self.order = order


class Spawn:
    """소환 한 기의 기록: frame, X, Y, unit, owner, job, layer, point(점 번호), rtype, order."""

    __slots__ = ("frame", "X", "Y", "unit", "owner", "job", "layer", "point", "rtype", "order", "cx", "cy")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def key(self):
        return (self.frame, self.X, self.Y, self.unit, self.owner)

    def __repr__(self):
        return "Spawn(f%d %d,%d u%d p%d job%s/%d)" % (self.frame, s32(self.X), s32(self.Y), self.unit, self.owner,
                                                      self.job, self.layer)


class RefSpawner:
    """spawn.Spawner 의 파이썬 참조.

    인자: capacity, map_size((W, H)), cycle
    상태: recs, overflow, rotation(전역각), anchor((x, y)), frame(지금까지 tick 수)
    메서드: push(layers, center=None, offset=(0, 0), order=None) → 넣었나, tick(on_spawn=None) → [Spawn], clear(), live
    on_spawn(sp, spawn) 는 소환 뒤(성공 기준 없이) 부른다 — 핸들러 안의 push·전역각 바꾸기 흉내.
    """

    def __init__(self, capacity, map_size=(4096, 4096), cycle=360):
        self.capacity = capacity
        self.W, self.H = map_size
        self.cycle = cycle
        self.recs = []
        self.overflow = 0
        self.rotation = 0
        self.anchor = (0, 0)
        self.frame = 0
        self.jobs = 0

    @property
    def live(self):
        return len(self.recs)

    def push(self, layers, center=None, offset=(0, 0), order=None):
        if not layers:
            raise ValueError("층이 없다")
        if self.capacity - len(self.recs) < len(layers):
            self.overflow += 1
            return False
        cx, cy = self.anchor if center is None else center
        job = self.jobs
        self.jobs += 1
        for i, ly in enumerate(layers):
            self.recs.append(Rec(ly, job, i, i + 1 < len(layers), u32(cx), u32(cy), u32(offset[0]), u32(offset[1]),
                                 order))
        return True

    def clear(self):
        self.recs = []

    def tick(self, on_spawn=None):
        out = []
        carry = False
        for rec in list(self.recs):
            if rec not in self.recs:
                continue
            ly = rec.layer
            if carry:
                carry = False
                rec.w = 2
            if rec.w == 0:
                if ly.schedule is not None:
                    L = ly.schedule[rec.sp - 1]
                    if len(ly.schedule) > rec.sp:
                        rec.sp += 1
                else:
                    L = ly.lm
                k = min(L, rec.left)
                for _ in range(k):
                    x, y = ly.points[rec.pc]
                    X, Y, ok = transform(x, y, ly.size, ly.rot, ly.glob, self.rotation, rec.dx, rec.dy, rec.cx,
                                         rec.cy, self.cycle, self.W, self.H)
                    if ok:
                        sp = Spawn(frame=self.frame, X=X, Y=Y, unit=ly.unit, owner=ly.owner, job=rec.job,
                                   layer=rec.index, point=rec.pc, rtype=ly.rtype, order=rec.order, cx=rec.cx,
                                   cy=rec.cy)
                        out.append(sp)
                        if on_spawn is not None:
                            on_spawn(self, sp)
                    rec.pc += 1
                    rec.left -= 1
                rec.w = ly.delay
                if rec.left == 0:
                    if rec.has_next:
                        carry = True
                    self.recs.remove(rec)
            rec.w = max(rec.w - 1, 0)
        self.frame += 1
        return out

    def counts(self, frames, **kw):
        """frames 프레임 동안 프레임마다 소환 수 목록 (계획표 확인용)."""
        return [len(self.tick(**kw)) for _ in range(frames)]


# --- S1 9.1 표 (프레임별 점 수) — 명세 그대로 적은 기대값 ---

TABLE_91 = {
    # 이름: (층 [(점 수, lm, delay, 스케줄)], 프레임별 기대 점 수, 끝난 프레임(마지막 층을 반납한 프레임))
    "A": ([(41, LM_MAX, 0, None)], [41], 0),
    "B": ([(300, LM_MAX, 0, None)], [255, 45], 1),
    "C": ([(41, 10, 0, None)], [10, 10, 10, 10, 1], 4),
    "C'": ([(41, 10, 1, None)], [10, 10, 10, 10, 1], 4),
    "D": ([(41, 10, 3, None)], [10, 0, 0, 10, 0, 0, 10, 0, 0, 10, 0, 0, 1], 12),
    "E": ([(41, LM_MAX, 0, None), (41, LM_MAX, 0, None)], [41, 0, 41], 2),
    "F": ([(41, 0, 0, None)], [1] * 41, 40),
    "G": ([(255, LM_MAX, 0, None)], [255], 0),
    "H": ([(256, LM_MAX, 2, None)], [255, 0, 1], 2),
    "I": ([(12, LM_MAX, 0, (5, 0, 7))], [5, 0, 7], 2),
}


def table_91_check():
    """참조 모델이 S1 9.1 표(A~I)의 기대값과 같은지. 반환: [(이름, 맞나, 받은 값)]"""
    out = []
    for name, (layers, want, end) in TABLE_91.items():
        sp = RefSpawner(8)
        lys = [Layer(1, [(0, 0)] * n, lm=lm, delay=d, schedule=sc) for n, lm, d, sc in layers]
        sp.push(lys, center=(100, 100))
        got = []
        ended = None
        for f in range(len(want) + 3):
            got.append(len(sp.tick()))
            if ended is None and sp.live == 0:
                ended = f
        ok = got[:len(want)] == want and all(v == 0 for v in got[len(want):]) and ended == end
        out.append((name, ok, (got, ended)))
    return out


# --- S1 9.2 좌표 기대값 ---

LENGTHDIR_92 = [
    ((32, 0), (32, 0)),
    ((32, 45), (22, 22)),
    ((-32, 90), (0, -32)),
    ((100, -90), (0, -100)),
    ((100, 450), (0, 100)),
    ((100, 359), (99, -1)),
    ((100, 360), (100, 0)),
    ((-100, 30), (-86, -49)),
    ((32767, 45), (23169, 23169)),
]

ROTATE_92 = [
    ((0, -32, 90), (32, 0)),
    ((32, 0, 45), (22, 22)),
    ((27, -16, 30), (30, 0)),
    ((27, -16, -30), (16, -26)),
    ((0, -32, 180), (0, 32)),
    ((64, 64, 45), (0, 90)),
    ((-48, 20, 135), (19, -47)),
    ((100, 0, 1), (99, 1)),
]

SIZE_92 = [
    ((27, -16, 150), (40, -24)),
    ((-33, 33, 50), (-16, 16)),
    ((7, -7, 0), (0, 0)),
    ((100, -100, 255), (255, -255)),
    ((1, -1, 99), (0, 0)),
]

# (점, 설정, 기대 (X, Y, 소환)) — W = 6144, H = 3072
FULL_92 = [
    ((27, -16), dict(size=150, rot=30, dx=10, dy=0, cx=3072, cy=1536), (3127, 1535, True)),
    ((64, 0), dict(cx=6100, cy=100), (6164, 100, False)),
    ((-32, 0), dict(cx=10, cy=10), (0xFFFFFFEA, 10, False)),
    ((0, 0), dict(cx=6143, cy=3071), (6143, 3071, True)),
    ((1, 0), dict(cx=6143, cy=3071), (6144, 3071, False)),
    ((0, -32), dict(glob=True, rotation=90, cx=100, cy=100), (132, 100, True)),
    ((0, -32), dict(rot=-90, cx=100, cy=100), (68, 100, True)),
]

W92, H92 = 6144, 3072


def vectors_92_check():
    """참조 계산이 S1 9.2 표의 기대값과 같은지. 반환: [(이름, 맞나, 받은 값, 기대)]"""
    out = []
    for (r, a), want in LENGTHDIR_92:
        got = lengthdir_py(r, a)
        out.append(("lengthdir(%d, %d)" % (r, a), got == want, got, want))
    for (x, y, a), want in ROTATE_92:
        got = rotate_py(x, y, a)
        out.append(("rotate(%d, %d, %d)" % (x, y, a), got == want, got, want))
    for (x, y, s), want in SIZE_92:
        got = size_py(x, y, s)
        out.append(("size(%d, %d)·%d" % (x, y, s), got == want, got, want))
    for (x, y), kw, want in FULL_92:
        got = transform(x, y, W=W92, H=H92, **kw)
        out.append(("full %r %r" % ((x, y), kw), got == want, got, want))
    return out
