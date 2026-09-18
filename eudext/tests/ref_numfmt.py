"""numfmt 파이썬 참조 구현 (eudplib 없이, numfmt 와 따로 짠 모델) — tests/t_numfmt.py 가 쓴다.

- `dec(...)`: 파이썬 `format` 의미(너비·채움·부호·세 자리 묶음·0 채움과 구분자)를 글자 토큰 목록으로 만들고,
  eudext 확장(max_digits·cut_low·sign_space·전각·자리 색·글자표·셀 배치)을 토큰에 적용한 뒤 바이트로 바꾼다.
  확장을 쓰지 않는 경우는 `format(value, spec)` 과 같아야 한다(`py_spec` 로 스스로 확인).
- `per(...)`, `man18(...)`, `man_visible(...)`, `gauge(...)`, `dp_*`: S3 4.4·4.5·8.1 규칙.
- 기대값 표 `S3_EXPECT`: docs/spec/S3_display.md 8.1 을 그대로 옮긴 바이트.

python tests/ref_numfmt.py 로 자체 점검을 돌린다.
"""

D = 0x0D
M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1


def _fw(ch):
    if ch == "\r":
        return ch
    if ch == " ":
        return "　"
    if 0x21 <= ord(ch) <= 0x7E:
        return chr(ord(ch) + 0xFEE0)
    return ch


def _interpret(value, bits, signed):
    m = (1 << bits) - 1
    v = value & m
    if signed and v >> (bits - 1):
        return v - (1 << bits)
    return v


def tokens(value, bits=32, width=0, fill="\r", sign=None, sign_space=False, max_digits=None, cut_low=0, group=None,
           align=None, neg_fill=None, neg_align=None, base=10, lower=False):  # fmt: skip
    """→ (토큰 목록, 음수인가). 토큰 = ("d", 자리값, k) | ("s", 글자) | ("f", 글자) | ("x",)(가린 자리)."""
    x = _interpret(value, bits, sign is not None)
    neg = x < 0
    a = -x if neg else x
    if base == 16:
        ds = "%x" % a
    else:
        ds = str(a)
    if max_digits and len(ds) > max_digits:
        ds = ds[-max_digits:]
    n = len(ds)
    if neg:
        fill_, align_ = (neg_fill if neg_fill is not None else fill), neg_align
        if align_ is None:
            align_ = align if neg_fill is None else ("=" if fill_ == "0" else ">")
    else:
        fill_, align_ = fill, align
    if align_ is None:
        align_ = "=" if fill_ == "0" else ">"
    g = group[0] if group else None
    sep = group[1] if group else None

    def unit(k):  # 자리 k 앞에(왼쪽에서 오른쪽으로 쓸 때 자리 k 다음에) 구분자가 오는가
        return g is not None and k > 0 and k % g == 0

    body = []
    for i, ch in enumerate(ds):
        k = n - 1 - i
        body.append(("d", int(ch, 16), k))
        if unit(k):
            body.append(("s", sep))
    signs = []
    if sign is not None:
        if neg:
            signs = ["-"]
        elif sign in ("+-", "+"):
            signs = ["+"]
        elif sign in (" -", " "):
            signs = [" "]
    if signs and sign_space:
        signs.append(" ")
    sign_t = [("f", c) for c in signs]
    zero = fill_ == "0" and align_ == "="
    if align_ == "=":
        need = width - len(signs)
        k = n
        if zero:
            while len(body) < need:
                if unit(k):
                    body.insert(0, ("s", sep))
                    if len(body) >= need:
                        break
                body.insert(0, ("d", 0, k))
                k += 1
            if body[0][0] == "s":
                body.insert(0, ("d", 0, k))
        else:
            while len(body) < need:
                body.insert(0, ("f", fill_))
        out = sign_t + body
    else:
        out = sign_t + body
        while len(out) < width:
            out.insert(0, ("f", fill_))
    if cut_low:
        out = [("x",) if (t[0] == "d" and t[2] < cut_low) else t for t in out]
    return out, neg


def render(toks, U=1, mode="plain", fullwidth=False, colors=None, glyphs=None, base=10, lower=False):
    """토큰 → 바이트. U = 슬롯 폭, mode = plain | eudplib | ctrig."""
    prefix = colors is not None or mode != "plain"
    out = b""
    for t in toks:
        if t[0] == "x":
            out += bytes([D]) * U
            continue
        if t[0] == "d":
            d, k = t[1], t[2]
            if glyphs is not None:
                g = glyphs[d]
                g = g if isinstance(g, bytes) else g.encode()
            else:
                ch = "0123456789abcdef"[d] if lower else "0123456789ABCDEF"[d]
                g = (_fw(ch) if fullwidth else ch).encode()
            c = D
            if colors is not None:
                if isinstance(colors, int):
                    c = colors or D
                elif k < len(colors):
                    c = colors[k] or D
        else:
            ch = t[1]
            g = (_fw(ch) if fullwidth else ch).encode()
            c = D
        if g == b"\r":
            out += bytes([D]) * U
        elif len(g) == 4 and U == 4 and not (mode == "plain" and prefix):
            out += g
        elif mode == "plain":
            out += ((bytes([c]) if prefix else b"") + g).ljust(U, bytes([D]))
        else:
            pad = bytes([D]) * (3 - len(g))
            out += bytes([c]) + (g + pad if mode == "eudplib" else pad + g)
    return out


def slot_width(fullwidth=False, colors=None, glyphs=None, mode="plain", chars=()):
    if glyphs is not None:
        cw = max(len(g if isinstance(g, bytes) else g.encode()) for g in glyphs)
    else:
        cw = 3 if fullwidth else 1
    for ch in chars:
        if ch != "\r":
            cw = max(cw, len((_fw(ch) if fullwidth else ch).encode()))
    if mode != "plain" or fullwidth:
        return 4
    return cw + (1 if colors is not None else 0)


def dec(value, bits=32, width=0, fill="\r", sign=None, sign_space=False, max_digits=None, cut_low=0, fullwidth=False,
        colors=None, group=None, glyphs=None, align=None, mode="plain", neg_fill=None, neg_align=None):  # fmt: skip
    toks, _neg = tokens(value, bits, width, fill, sign, sign_space, max_digits, cut_low, group, align, neg_fill, neg_align)
    chars = [fill] + ([neg_fill] if neg_fill else []) + ["-", "+", " "] + ([group[1]] if group else [])
    if mode == "plain" and fullwidth:
        mode = "eudplib"
    U = slot_width(fullwidth, colors, glyphs, mode, chars)
    return render(toks, U, mode, fullwidth, colors, glyphs)


def hexf(value, width=8, lower=False, fill="0", align=None):
    toks, _ = tokens(value, 32, width, fill, None, False, None, 0, None, align, base=16)
    return render(toks, 1, base=16, lower=lower)


def py_spec(width=0, fill="\r", sign=None, group=None, align=None, typ="d"):
    """확장 없는 옵션 → 파이썬 format 지정자 (같은 결과여야 함)."""
    if align is None:
        align = "=" if fill == "0" else ">"
    sg = {None: "", "-": "-", "+-": "+", " -": " "}[sign]
    gp = group[1] if group else ""
    if fill == "0" and align == "=":
        return "%s0%s%s%s" % (sg, width or "", gp, typ)
    return "%s%s%s%s%s%s" % (fill, align, sg, width or "", gp, typ)


# ---------------------------------------------------------------------------------------------
# Per · Man · Gauge · dp 프리셋 (S3 4.4·4.5)
# ---------------------------------------------------------------------------------------------


def per(v, scale=1000, frac=3, max_=None, trim=True, int_min=1, width=0, fill="\r"):
    s = len(str(scale)) - 1
    if max_ is not None:
        v = min(v, max_)
    ip, fp = divmod(v, scale)
    ints = str(ip).rjust(int_min, "0")
    fs = str(fp).rjust(s, "0")[:frac]
    out = ints
    if frac:
        if trim:
            t = fs.rstrip("0")
            fs2 = t + "\r" * (frac - len(t))
            dot = "." if t else "\r"
        else:
            fs2, dot = fs, "."
        out += dot + fs2
    out = out.rjust(width, fill)
    return out.encode()


def per_visible(v, scale=1000, frac=3, max_=None, int_min=1):
    s = len(str(scale)) - 1
    if max_ is not None:
        v = min(v, max_)
    ip, fp = divmod(v, scale)
    txt = str(ip).rjust(int_min, "0")
    fs = str(fp).rjust(s, "0")[:frac].rstrip("0")
    if fs:
        txt += "." + fs
    return txt


DPS_COL = [0x03, 0x1C, 0x1D, 0x19, 0x1B, 0x15, 0x11, 0x18, 0x1E, 0x1F, 0x10, 0x11, 0x08, 0x06, 0x07, 0x04, 0x02, 0x01]
UNITS = "만억조경해자양구간정재극항아나불무"


def _L(n):
    return bytes(D if c == " " else ord(c) for c in "%4d" % n)


def man18(V, color):
    """CONV:223~428 을 옮긴 18B (S3 4.5 의 1~5 단계를 그대로)."""
    out = bytearray([D]) * 18
    t = 0
    if V >= 10**4:
        t = 1
        while V >= 10 ** (4 * t + 4):
            t += 1
    if t == 0:
        A, B = 0, V
    else:
        A = V // 10 ** (4 * t)
        B = (V // 10 ** (4 * t - 4)) % 10**4
    c1 = DPS_COL[t]
    c2 = DPS_COL[t - 1] if t >= 1 else DPS_COL[0]
    if t == 0:
        if A == 0 and B == 0:
            if color:
                out[0] = c1
            out[4] = 0x30
    else:
        if color:
            out[0] = c1
        out[1:5] = _L(A)
        if color:
            out[5] = 0x04
        out[6:9] = UNITS[t - 1].encode()
    if B != 0:
        if color:
            out[9] = c2
        out[10:14] = _L(B)
        if color:
            out[14] = 0x04
        if t >= 2:
            out[15:18] = UNITS[t - 2].encode()
    return bytes(out)


def man_visible(V, colors=None, after=None, top=2):
    """보이는 글(0x0D 없음): 위 두 덩이, B 가 0 이면 숨김, 덩이 안 앞 0 없음."""
    t = 0
    while V >= 10 ** (4 * (t + 1)):
        t += 1
    chunks = []
    if t == 0:
        chunks.append((V, 0, DPS_COL[0] if colors else None))
    else:
        A = V // 10 ** (4 * t)
        B = (V // 10 ** (4 * t - 4)) % 10**4
        chunks.append((A, t, DPS_COL[t] if colors else None))
        if B and top == 2:
            chunks.append((B, t - 1, DPS_COL[t - 1] if colors else None))
    out = b""
    for n, u, c in chunks:
        if c is not None:
            out += bytes([c])
        out += str(n).encode()
        if after is not None:
            out += bytes([after])
        if u >= 1:
            out += UNITS[u - 1].encode()
    return out


def _man_pair(colors, t):
    if colors is None:
        return D, D
    if colors == "dps":
        return DPS_COL[t], DPS_COL[t - 1] if t else DPS_COL[0]
    if all(isinstance(x, (tuple, list)) for x in colors):
        c = colors[t] if t < len(colors) else (D, D)
        return c[0] or D, c[1] or D
    per_ = [(x or D) for x in colors]
    get = lambda u: per_[u] if u < len(per_) else D  # noqa: E731
    return get(t), get(t - 1) if t else get(0)


def man(V, bits=32, top=2, colors=None, after=None, units=UNITS, fixed=False):
    """Man 의 바이트 (numfmt 문서의 규칙: 덩이 = [색][4자리][after][단위], 18B 틀에서 시작 위치까지 건너뜀)."""
    tmax = 2 if bits == 32 else 4
    uw = max(len(u.encode()) for u in units[:tmax])
    t = 0
    while t < tmax and V >= 10 ** (4 * (t + 1)):
        t += 1
    if t == 0:
        A, B = 0, V
    else:
        A = V // 10 ** (4 * t)
        B = (V // 10 ** (4 * t - 4)) % 10**4
    c1, c2 = _man_pair(colors, t)
    af = D if after is None else (after or D)

    def unit(u):
        return (units[u - 1].encode() if u >= 1 else b"").ljust(uw, bytes([D]))

    ca = 6 + uw
    blank = bytes([D]) * ca
    a_shown = t >= 1 or V == 0
    b_shown = (t >= 1 and top == 2 and B != 0) or (t == 0 and V != 0)
    if a_shown:
        a_after = D if (t == 0 and fixed) else af
        a_area = bytes([c1]) + _L(A) + bytes([a_after]) + unit(t)
    else:
        a_area = blank
    if b_shown:
        b_area = bytes([c2]) + _L(B) + bytes([af]) + (unit(t - 1) if t >= 2 else unit(0))
    else:
        b_area = blank
    img = a_area + b_area
    if fixed:
        return img
    first, n = (0, A) if a_shown else (ca, B)
    if colors is None:
        return img[first + 1 + (4 - len(str(n))) :]
    return img[first:]


def gauge(n, cells=20, glyph="l", on=0x07, off=0x04):
    g = glyph.encode()
    return b"".join(bytes([on if n > i else off]) + g for i in range(cells))


def dp_dec16(v):
    """Call_IToDec (DPL:627~969): [D D D D][D][부호][10 자리], 앞 0 → D, 음수 절댓값."""
    v &= M32
    out = bytearray([D]) * 6 + bytearray(b"0" * 10)
    a = v
    if v >= 0x80000000:
        out[5] = 0x2D
        a = (1 << 32) - v
    s = str(a)
    for i in range(10 - len(s)):
        out[6 + i] = D
    out[16 - len(s) :] = s.encode()
    return bytes(out)


def dp_decfw48(v):
    v &= M32
    s = "%010d" % v
    out = bytearray([D]) * 8
    lead = 10 - len(str(v))
    for i, ch in enumerate(s):
        out += bytes([D]) * 4 if i < lead else bytes([D, 0xEF, 0xBC, 0x90 + int(ch)])
    return bytes(out)


def dp_hex12(v):
    return bytes([D]) * 4 + ("%08X" % (v & M32)).encode()


def dp_dec20(x):
    x &= M64
    if x >> 63:
        return b"-" + ("%019d" % ((1 << 64) - x)).encode()
    s = str(x)
    return bytes([D]) * (20 - len(s)) + s.encode()


def dp_dig2(v):
    s = "%d" % (v & M32)
    if len(s) == 1:
        return bytes([D]) + s.encode()
    return s[-2:].encode()


def dp_name20(name_bytes, p):
    cols = (0x08, 0x0E, 0x0F, 0x10, 0x11, 0x15, 0x16, 0x17)
    nb = name_bytes[:16].ljust(16, b"\0")
    return bytes([D, D, D, cols[p]]) + bytes(D if b == 0 else b for b in nb)


def dp_per8(v, permil=False, tbl=False):
    """CONV:59~95 을 옮긴 8B."""
    mx = (1000000 if tbl else 5000000) if permil else 100000
    x = min(v, mx)
    dg = [(x // 10**i) % 10 for i in range(7)]  # dg[i] = 10^i 자리
    out = bytearray(8)
    out[0] = 0x30 + dg[6]
    out[1] = 0x30 + dg[5]
    out[2] = 0x30 + dg[4]
    out[3] = 0x30 + dg[3]
    out[4] = 0x2E
    out[5] = 0x30 + dg[2]
    out[6] = 0x30 + dg[1]
    out[7] = 0x30 + dg[0]
    if out[0] <= 0x30:
        out[0] = D
        if out[1] <= 0x30:
            out[1] = D
            if out[2] <= 0x30:
                out[2] = D
    if out[7] <= 0x30:
        out[7] = D
        if out[6] <= 0x30:
            out[6] = D
            if out[5] <= 0x30:
                out[5] = D
                out[4] = D
    return bytes(out)


def _h(s):
    """'0D×15 30' 모양의 기대값 표기를 바이트로."""
    out = bytearray()
    for part in s.replace("(", " ( ").replace(")", " ) ").split():
        if "×" in part:
            b, n = part.split("×")
            out += bytes([int(b, 16)]) * int(n)
        else:
            out.append(int(part, 16))
    return bytes(out)


# S3 8.1 기대값 (docs/spec/S3_display.md 에서 옮김)
S3_EXPECT = {
    "dec16": [
        (0, "0D×15 30"), (5, "0D×15 35"), (10, "0D×14 31 30"), (12345, "0D×11 31 32 33 34 35"),
        (999999999, "0D×7 39×9"), (1000000000, "0D×6 31 30×9"),
        (2147483647, "0D×6 32 31 34 37 34 38 33 36 34 37"),
        (0x80000000, "0D×5 2D 32 31 34 37 34 38 33 36 34 38"),
        (0xFFFFFFFF, "0D×5 2D 0D×9 31"), (0xFFFFFFF6, "0D×5 2D 0D×8 31 30"),
    ],
    "decfw48": [
        (0, "0D×45 EF BC 90"),
        (1234, "0D×33 EF BC 91 0D EF BC 92 0D EF BC 93 0D EF BC 94"),
        (4294967295, "0D×9 EF BC 94 0D EF BC 92 0D EF BC 99 0D EF BC 94 0D EF BC 99 0D EF BC 96 0D EF BC 97 0D EF BC 92 "
                     "0D EF BC 99 0D EF BC 95"),
    ],
    "hex12": [
        (0, "0D×4 30×8"), (0xABCDEF, "0D×4 30 30 41 42 43 44 45 46"), (0xFFFFFFFF, "0D×4 46×8"),
    ],
    "dec20": [
        (0, "0D×19 30"), (12800000000, "0D×9 31 32 38 30×8"), (10**18, "0D 31 30×18"),
        ((1 << 63) - 1, "0D 39 32 32 33 33 37 32 30 33 36 38 35 34 37 37 35 38 30 37"),
        (M64 - 4, "2D 30×18 35"),
        (1 << 63, "2D 39 32 32 33 33 37 32 30 33 36 38 35 34 37 37 35 38 30 38"),
    ],
    "man18_on": [
        (0, "03 0D 0D 0D 30 0D×13"), (7, "0D×9 03 0D 0D 0D 37 04 0D 0D 0D"),
        (10000, "1C 0D 0D 0D 31 04 EB A7 8C 0D×9"),
        (12345678, "1C 31 32 33 34 04 EB A7 8C 03 35 36 37 38 04 0D 0D 0D"),
        (100050000, "1D 0D 0D 0D 31 04 EC 96 B5 1C 0D 0D 0D 35 04 EB A7 8C"),
        (123456789012, "1D 31 32 33 34 04 EC 96 B5 1C 35 36 37 38 04 EB A7 8C"),
        (M64, "1B 31 38 34 34 04 EA B2 BD 19 36 37 34 34 04 EC A1 B0"),
    ],
    "man18_off": [
        (0, "0D 0D 0D 0D 30 0D×13"),
        (12345678, "0D 31 32 33 34 0D EB A7 8C 0D 35 36 37 38 0D 0D 0D 0D"),
    ],
    "per8": [
        (0, "0D 0D 0D 30 0D 0D 0D 0D"), (1, "0D 0D 0D 30 2E 30 30 31"), (500, "0D 0D 0D 30 2E 35 0D 0D"),
        (12500, "0D 0D 31 32 2E 35 0D 0D"), (12050, "0D 0D 31 32 2E 30 35 0D"), (150000, "0D 31 30 30 0D 0D 0D 0D"),
    ],
    "per8_permil": [
        (5000000, "35 30 30 30 0D 0D 0D 0D"), (1234567, "31 32 33 34 2E 35 36 37"),
    ],
    "dig2": [(0, "0D 30"), (5, "0D 35"), (42, "34 32"), (100, "30 30"), (105, "30 35")],
    "gauge40": [(0, "(04 6C)×20"), (3, "(07 6C)×3 (04 6C)×17"), (25, "(07 6C)×20")],
    "name20": [(("GALAXY_BURST", 0), "0D 0D 0D 08 47 41 4C 41 58 59 5F 42 55 52 53 54 0D 0D 0D 0D")],
}  # fmt: skip


def expect_bytes(s):
    """괄호 반복 `(04 6C)×20` 까지 푼다."""
    import re

    def rep(m):
        return " ".join([m.group(1)] * int(m.group(2)))

    s = re.sub(r"\(([^)]*)\)×(\d+)", rep, s)
    return _h(s)


def _selfcheck():
    import itertools
    import random

    bad = 0
    rng = random.Random(3)
    vals = [0, 1, 5, 9, 10, 99, 100, 999, 1000, 1234, 12345, 999999, 10**6, 2**31 - 1, 2**31, 2**32 - 1, 4294967291]
    vals += [rng.getrandbits(32) for _ in range(200)]
    for v, width, fill, sign, group, align in itertools.product(
        vals[:40], (0, 1, 3, 5, 8, 11, 14), ("\r", "0", " ", "*"), (None, "-", "+-", " -"), (None, (3, ",")), (None, ">", "=")
    ):  # fmt: skip
        if fill == "0" and align == ">" and group:
            continue
        ours = dec(v, 32, width, fill, sign, group=group, align=align)
        x = _interpret(v, 32, sign is not None)
        spec = py_spec(width, fill, sign, group, align)
        want = format(x, spec).encode()
        if ours != want:
            bad += 1
            if bad < 10:
                print("불일치", v, repr(spec), ours, want)
    for v in vals:
        for width in (0, 4, 8, 12):
            for fill in ("0", "\r"):
                if hexf(v, width, False, fill) != format(v, py_spec(width, fill, typ="X")).encode():
                    bad += 1
    for name, rows in S3_EXPECT.items():
        fn = {
            "dec16": dp_dec16, "decfw48": dp_decfw48, "hex12": dp_hex12, "dec20": dp_dec20,
            "man18_on": lambda v: man18(v, True), "man18_off": lambda v: man18(v, False),
            "per8": dp_per8, "per8_permil": lambda v: dp_per8(v, permil=True), "dig2": dp_dig2,
            "gauge40": lambda n: gauge(n), "name20": lambda a: dp_name20(a[0].encode(), a[1]),
        }[name]  # fmt: skip
        for v, e in rows:
            if fn(v) != expect_bytes(e):
                bad += 1
                print("S3 8.1 불일치", name, v, fn(v).hex(" "), expect_bytes(e).hex(" "))
    for v in [0, 7, 10000, 12345678, 100050000, 123456789012, M64, 99999999] + [rng.getrandbits(64) >> rng.randrange(64)
                                                                                   for _ in range(300)]:  # fmt: skip
        bits = 32 if v <= M32 else 64
        if man(v, bits, colors="dps", after=4, fixed=True) != man18(v, True) or man(v, bits, fixed=True) != man18(v, False):
            bad += 1
            print("man ≠ man18", v)
        if man(v, bits).replace(b"\r", b"") != man_visible(v):
            bad += 1
            print("man 보이는 글", v, man(v, bits), man_visible(v))
        if man(v, bits, colors="dps", after=4).replace(b"\r", b"") != man_visible(v, True, 4):
            bad += 1
            print("man 보이는 글 색", v)
    for v in (0, 1, 500, 12500, 12050, 150000, 1234567, 5000000):
        mx = 5000000 if v in (1234567, 5000000) else 100000
        if per(v, max_=mx, width=8) != dp_per8(v, permil=(mx == 5000000)):
            bad += 1
            print("per ≠ per8", v)
    print("ref_numfmt 자체 점검:", "통과" if bad == 0 else "실패 %d" % bad)
    return bad == 0


if __name__ == "__main__":
    _selfcheck()
