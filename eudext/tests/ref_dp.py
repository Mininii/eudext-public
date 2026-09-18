"""DisplayPrint 참조 모델 (eudplib 없이) — tests/t_display.py 가 쓴다. docs/spec/S3_display.md 4.1~4.5·8.1 을 옮겼다.

S3 의 참조 모델 `s3_ref.py`(Windows 스크래치패드)는 이 저장소에 없어 명세와 8.1 기대값으로 새로 짰다.
원소 서식(dec16·decfw48·hex12·dec20·name20·man18·per8·dig2·gauge40)은 `ref_numfmt`(WP5, S3 8.1 과 바이트 일치)를 쓴다.

- DPL 모델: `El` 원소 목록 → `dpl_display`(4.1 틀 + 런타임 채움), `dpl_er`(4.2 13번째 줄), `dpl_tbl`(4.3 TBL).
  원소 종류: "s"(문자열) "v"(V, fwc/hex) "w"(W) "name"(PName) "byte"(숫자 원소) "vlist"(V 목록) "setnum"(SetNumX)
  "eper"(SetEPer) "dig2"(dpletter2) "gauge"(GaugeBar — STR 판의 틀 이중 삽입까지).
- eudext 모델: `ex_out(part)` 원소 하나의 출력 바이트, `ex_concat`(TBL 과 보이는 글), `ex_fill_slot`(틀 자리 맞춤),
  `ex_template`(틀 규칙 — 상수는 그대로, 실행 원소는 4 배수 자리).
- `visible(bytes)`: NUL 앞까지, 0x01~0x1F(줄바꿈 제외) 빼고 UTF-8.
- `ER_LAYOUT`, `TBL_LAYOUT`: S3 4.2·4.3 끝의 예.

python tests/ref_dp.py 로 자체 점검(8.1 예·DPL 규칙)을 돌린다.
"""

import ref_numfmt as R

D = 0x0D
M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
DPL_COLORS = (0x08, 0x0E, 0x0F, 0x10, 0x11, 0x15, 0x16, 0x17)
TAIL = "\u2009".encode("utf-8")


def s32(v):
    v &= M32
    return v - (1 << 32) if v >> 31 else v


def s64(v):
    v &= M64
    return v - (1 << 64) if v >> 63 else v


def visible(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    i = data.find(b"\0")
    if i >= 0:
        data = data[:i]
    return bytes(b for b in data if b >= 0x20 or b == 0x0A).decode("utf-8", "replace")


class El:
    """DPL 원소 하나. kind 와 인자(값은 env 에서 읽을 이름 또는 상수)."""

    def __init__(self, kind, value=None, **opt):
        self.kind = kind
        self.value = value
        self.opt = opt

    def __repr__(self):
        return "El(%s, %r%s)" % (self.kind, self.value, "".join(", %s=%r" % kv for kv in sorted(self.opt.items())))

    def val(self, env):
        if isinstance(self.value, str) and self.kind != "s":
            return env[self.value]
        if isinstance(self.value, (list, tuple)) and self.kind == "vlist":
            return [env[x] if isinstance(x, str) else x for x in self.value]
        return self.value


# ---------------------------------------------------------------------------------------------
# 원소 서식 (4.4·4.5)
# ---------------------------------------------------------------------------------------------


def name20(names, p):
    """DPL 이름 칸(0x6D0FDC 캐시) 20B — p 0~6 만(7 이상은 None = 쓰지 않음)."""
    if not 0 <= p <= 6:
        return None
    return R.dp_name20(names.get(p, b""), p)


def dyn_bytes(el, env, names, ctx="dp"):
    """원소의 런타임 바이트(DPL 서브루틴이 쓰는 것). None = 아무것도 안 씀."""
    k = el.kind
    v = el.val(env)
    if k == "v":
        if el.opt.get("fwc"):
            return R.dp_decfw48(v)
        if el.opt.get("hex") and ctx != "er":
            return R.dp_hex12(v)
        return R.dp_dec16(v)
    if k == "w":
        return R.dp_dec20(v)
    if k == "name":
        return name20(names, v)
    if k == "byte":
        return bytes([v & 0xFF])
    if k == "vlist":
        return bytes(x & 0xFF for x in v)
    if k == "setnum":
        return R.man18(v, bool(el.opt.get("color")))
    if k == "eper":
        return R.dp_per8(v, permil=bool(el.opt.get("permil")), tbl=(ctx == "tbl"))
    if k == "dig2":
        return R.dp_dig2(v)
    if k == "gauge":
        return R.gauge(v, 20)
    raise ValueError(k)


def dp_width(el, ctx="dp"):
    k = el.kind
    if k == "v":
        if el.opt.get("fwc"):
            return 48
        if el.opt.get("hex") and ctx != "er":
            return 12
        return 16
    return {"w": 20, "name": 20, "byte": 1, "setnum": 18, "eper": 8, "dig2": 2, "gauge": 40}.get(k) or (
        len(el.value) if k == "vlist" else None
    )


# ---------------------------------------------------------------------------------------------
# DPL 틀 (4.1)
# ---------------------------------------------------------------------------------------------


def dpl_display(els, env, names=None, prev=None):
    """DisplayPrint 한 번 뒤의 틀 바이트(끝 \\r\\r\\r\\r 포함, NUL 제외). prev = 이전 틀(이름 원소가 안 쓸 때 남는 내용)."""
    names = names or {}
    tmpl = bytearray()
    dev = 0
    writes = []
    for el in els:
        if el.kind == "s":
            b = el.value.encode("utf-8") if isinstance(el.value, str) else el.value
            tmpl += b
            dev += len(b)
            continue
        w = dp_width(el)
        if el.kind == "gauge" and not el.opt.get("reset"):
            # GaugeBar(STR, ResetFlag=nil): 막대 40B 를 틀에 넣고 BSize +40 → 틀에 D 40 이 더 붙고 Dev 는 40 만 는다 (DF:2378)
            tmpl += R.gauge(0, 20)
        tmpl += bytes([D]) * w
        writes.append((dev, dyn_bytes(el, env, names)))
        dev += w
    tmpl += b"\r\r\r\r"
    out = bytearray(prev) if prev is not None and len(prev) == len(tmpl) else bytearray(tmpl)
    if prev is not None and len(prev) == len(tmpl):
        # 상수 부분은 늘 틀 그대로 (틀 문자열은 바뀌지 않는다 — 동적 칸만 덮인다)
        pass
    for off, b in writes:
        if b is not None:
            out[off : off + len(b)] = b
    return bytes(out)


# ---------------------------------------------------------------------------------------------
# DPL 13번째 줄 (4.2)
# ---------------------------------------------------------------------------------------------


def _print_utf8_2(buf, off, s):
    r = off % 4
    start = off - r
    data = bytes([D]) * r + s
    data += bytes(-len(data) % 4)
    buf[start : start + len(data)] = data


def dpl_er(els, env, names=None, before=None):
    """DisplayPrintEr 의 로컬 부분 뒤 0x641598 부터의 바이트(220). before = 쓰기 전 줄 내용(기본 0)."""
    names = names or {}
    buf = bytearray(before if before is not None else bytes(220))
    _print_utf8_2(buf, 0, bytes([D]) * 210)
    dev = 0
    later = []
    for el in els:
        k = el.kind
        if k == "s":
            b = el.value.encode("utf-8") if isinstance(el.value, str) else el.value
            if len(b) % 4:
                b = bytes([D]) * (4 - len(b) % 4) + b
            _print_utf8_2(buf, dev, b)
            dev += len(b)
        elif k == "v":
            _print_utf8_2(buf, dev, bytes([D]) * 16)
            later.append((dev, el))
            dev += 48 if el.opt.get("fwc") else 16
        elif k == "w":
            _print_utf8_2(buf, dev, bytes([D]) * 20)
            later.append((dev, el))
            dev += 20
        elif k == "name":
            later.append((dev, el))
            dev += 20
        elif k == "byte":
            _print_utf8_2(buf, dev, bytes([D]))
            later.append((dev, el))
            dev += 1
        elif k == "setnum":
            # SetNumErX: 지연 함수 — 호출 전 Dev 에 18B (호출 뒤 Dev 에 D×18 자리표시자, 원본 버그: 호출 전후 Dev 가 같아 결과 같음)
            _print_utf8_2(buf, dev, bytes([D]) * 18)
            later.append((dev, el))
            dev += 18
        else:
            raise ValueError("Er 에서 쓰지 않는 원소 %s" % k)
    for off, el in later:
        b = dyn_bytes(el, env, names, ctx="er")
        if b is not None:
            buf[off : off + len(b)] = b
    return bytes(buf), dev


# ---------------------------------------------------------------------------------------------
# DPL TBL (4.3)
# ---------------------------------------------------------------------------------------------


def dpl_tbl(els, env, original, names=None, utf8off=False):
    """DisplayPrintTbl 뒤의 TBL 자리 바이트. original = 원래 자리 내용(쓰지 않은 뒤쪽이 남는다)."""
    names = names or {}
    out = bytearray(original)
    pos = 0

    def put(b):
        nonlocal pos
        need = pos + len(b)
        if need > len(out):
            out.extend(bytes(need - len(out)))
        out[pos:need] = b
        pos = need

    for el in els:
        k = el.kind
        if k == "s":
            put(el.value.encode("utf-8") if isinstance(el.value, str) else el.value)
        elif k in ("vlist",) or el.opt.get("array"):
            continue  # VA·WA·V 목록은 TBL 에서 무시 (DPL:63~112)
        elif k == "gauge":
            put(R.gauge(el.val(env), 20))
        else:
            b = dyn_bytes(el, env, names, ctx="tbl")
            if b is None:
                pos += dp_width(el, "tbl")
            else:
                put(b)
    if not utf8off:
        put(TAIL)
    return bytes(out)


# ---------------------------------------------------------------------------------------------
# eudext 모델
# ---------------------------------------------------------------------------------------------


class XP:
    """eudext 원소 명세 (시험이 이것으로 실제 part 를 만들고, 모델이 출력 바이트를 낸다).

    kind: "s"(상수) "var"(맨 변수) "i64"(Int64) "dec"(numfmt.Dec 옵션) "hex" "man" "per" "gauge" "dp"(numfmt.dp.<name>)
          "pname"(PName) "local"(LocalName) "byte" "bytes" "pick"
    """

    def __init__(self, kind, value=None, **opt):
        self.kind = kind
        self.value = value
        self.opt = opt

    def __repr__(self):
        return "XP(%s, %r%s)" % (self.kind, self.value, "".join(", %s=%r" % kv for kv in sorted(self.opt.items())))


def ex_out(xp, env, names=None, local=0, ctx="show"):
    """eudext 원소의 출력 바이트(이어 붙이는 뜻 — 틀 자리 채움 전)."""
    names = names or {}
    k = xp.kind
    v = env.get(xp.value) if isinstance(xp.value, str) and k not in ("s", "pick") else xp.value
    if k == "s":
        return xp.value.encode("utf-8") if isinstance(xp.value, str) else xp.value
    if k == "var":
        return str(s32(v)).encode()
    if k == "i64":
        return str(s64(v)).encode()
    if k == "dec":
        return R.dec(v, xp.opt.get("bits", 32), **{a: b for a, b in xp.opt.items() if a != "bits"})
    if k == "hex":
        return R.hexf(v, **xp.opt)
    if k == "man":
        return R.man(v, xp.opt.get("bits", 32), **{a: b for a, b in xp.opt.items() if a != "bits"})
    if k == "per":
        o = dict(xp.opt)
        if "max" in o:
            o["max_"] = o.pop("max")
        return R.per(v, **o)
    if k == "gauge":
        return R.gauge(v, **xp.opt)
    if k == "dp":
        name = xp.opt["name"]
        if name == "name20":
            r = name20(names, v)
            return None if r is None else r
        fn = {"dec16": R.dp_dec16, "decfw48": R.dp_decfw48, "hex12": R.dp_hex12, "dec20": R.dp_dec20,
              "dig2": R.dp_dig2, "gauge40": lambda x: R.gauge(x, 20)}.get(name)  # fmt: skip
        if fn is not None:
            return fn(v)
        if name == "man18":
            return R.man18(v, bool(xp.opt.get("color")))
        if name == "per8":
            return R.dp_per8(v, permil=bool(xp.opt.get("permil")), tbl=bool(xp.opt.get("tbl")))
        raise ValueError(name)
    if k in ("pname", "local"):
        p = local if k == "local" else v
        if not 0 <= p <= 7:
            return b""
        nm = names.get(p, b"")
        nm = nm.split(b"\0")[0]
        color = xp.opt.get("color", "player")
        head = b"" if color is None else bytes([DPL_COLORS[p] if color == "player" else color])
        return head + nm
    if k == "byte":
        b = v & 0xFF
        return bytes([b if b else D])
    if k == "bytes":
        vals = [env.get(x) if isinstance(x, str) else x for x in xp.value]
        return bytes((x & 0xFF) or D for x in vals)
    if k == "pick":
        table = xp.opt["table"]
        idx = env.get(xp.value) if isinstance(xp.value, str) else xp.value
        s = table.get(idx) if isinstance(table, dict) else (table[idx] if 0 <= idx < len(table) else None)
        if s is None:
            s = xp.opt.get("default", "")
        return s.encode("utf-8") if isinstance(s, str) else s
    raise ValueError(k)


def ex_max_len(xp):
    k = xp.kind
    return {"var": 11, "i64": 20}.get(k)


def ex_concat(xps, env, names=None, local=0, tail=b"", eos=False):
    out = b""
    for xp in xps:
        b = ex_out(xp, env, names, local, ctx="tbl")
        if b:
            out += b
    out += tail
    if eos:
        out += b"\0"
    return out


def ex_fill_slot(out, size, align):
    """틀 자리 크기 size 에 출력 out 을 맞춘다 (right = 직접 쓰기, left = 복사)."""
    if out is None:
        return None
    if len(out) > size:
        raise ValueError("출력 %d > 자리 %d" % (len(out), size))
    pad = bytes([D]) * (size - len(out))
    return pad + out if align == "right" else out + pad


def ex_template(xps, slots, env, names=None, local=0, prev=None):
    """eudext 틀(상수 그대로 + 4 배수 자리)을 모델로 만들고 자리에 출력을 채운다.

    slots: 구현이 보고한 [(오프셋, 크기, 종류, 맞춤)] — 모델은 오프셋이 규칙(앞 글 끝을 4 배수로 올린 곳)과 같은지도 확인한다.
    반환: (바이트, 오류 목록)
    """
    errs = []
    buf = bytearray()
    it = iter(slots)
    placed = []
    for xp in xps:
        if xp.kind == "s":
            buf += ex_out(xp, env)
            continue
        try:
            off, size, kind, align = next(it)
        except StopIteration:
            errs.append("자리가 모자람")
            break
        want_off = len(buf) + (-len(buf) % 4)
        if off != want_off:
            errs.append("자리 오프셋 %d != %d (%r)" % (off, want_off, xp))
        if size % 4:
            errs.append("자리 크기 %d 가 4 배수가 아님" % size)
        buf += bytes([D]) * (want_off - len(buf)) + bytes([D]) * size
        placed.append((off, size, kind, align, xp))
    out = bytearray(prev) if prev is not None else buf
    for off, size, kind, align, xp in placed:
        b = ex_out(xp, env, names, local)
        if kind == "direct" and xp.kind == "dp" and xp.opt.get("name") == "name20" and b is None:
            continue  # name20 p ≥ 7: 이전 내용 그대로 (DPL 과 같음)
        if kind == "namecache":
            b = ex_namecache(xp, env, names, local)
            out[off : off + size] = b
            continue
        filled = ex_fill_slot(b if b is not None else b"", size, align)
        out[off : off + size] = filled
    return bytes(out), errs


def ex_namecache(xp, env, names, local):
    """PName(cache=True) 자리 28B: [색|D][이름 25B — NUL 뒤는 D][D D] (변수 p ≥ 8 이면 D 28)."""
    p = local if xp.kind == "local" else (env.get(xp.value) if isinstance(xp.value, str) else xp.value)
    color = xp.opt.get("color", "player")
    if not 0 <= p <= 7:
        return bytes([D]) * 28
    nm = names.get(p, b"").split(b"\0")[0][:25]
    if color is None:
        body = nm
    else:
        body = bytes([DPL_COLORS[p] if color == "player" else color]) + nm
    return body.ljust(28, bytes([D]))


# ---------------------------------------------------------------------------------------------
# S3 끝의 예
# ---------------------------------------------------------------------------------------------

ER_LAYOUT = (
    [El("s", "\x07HP "), El("v", "v"), El("s", " / "), El("byte", "c"), El("s", "MAX")],
    {"v": 123, "c": 0x1F},
    "07 48 50 20 0D0D0D0D0D0D0D0D0D0D0D0D0D 31 32 33 0D 20 2F 20 1F 0D 4D 41 58 00 00 00",
    29,
    "<07>HP 123 / <1F>MAX",
)
TBL_LAYOUT = (
    [El("s", "\x04Lv "), El("v", "v")],
    {"v": 42},
    b"?" * 32,
    "04 4C 76 20 0D0D0D0D0D0D0D0D0D0D0D0D0D0D 34 32 E2 80 89 3F3F3F3F3F3F3F3F3F",
)


def hexb(s):
    return bytes.fromhex(s.replace(" ", ""))


def _selfcheck():
    ok = fail = 0

    def eq(label, got, want):
        nonlocal ok, fail
        if got == want:
            ok += 1
        else:
            fail += 1
            print("  [실패] %s: %r != %r" % (label, got, want))

    els, env, hx, dev, _vis = ER_LAYOUT
    buf, d = dpl_er(els, env)
    eq("er_layout 32B", buf[:32], hexb(hx))
    eq("er_layout Dev", d, dev)
    eq("er_layout 210 D", buf[32:210], bytes([D]) * 178)
    eq("er_layout 210·211 NUL", buf[210:212], b"\0\0")
    eq("er_layout 보이는 글", visible(buf), "HP 123 / MAX")
    els, env, orig, hx = TBL_LAYOUT
    eq("tbl_layout", dpl_tbl(els, env, orig), hexb(hx))
    # 틀: GaugeBar 이중 삽입으로 뒤 원소가 앞으로 당겨진다
    t = dpl_display([El("gauge", "g"), El("s", " HP "), El("v", "v")], {"g": 3, "v": 7})
    eq("gauge 이중 삽입 길이", len(t), 40 + 40 + 4 + 16 + 4)
    eq("gauge 당겨짐", visible(t), "l" * 20 + "7" + " HP ")
    t = dpl_display([El("s", "\x07HP "), El("v", "v"), El("s", " / "), El("w", "w")], {"v": M32, "w": M64 - 4})
    eq("틀 보이는 글", visible(t), "HP -1 / -0000000000000000005")
    eq("틀 끝", t[-4:], b"\r\r\r\r")
    # eudext 출력
    eq("ex var", ex_out(XP("var", "x"), {"x": M32}), b"-1")
    eq("ex i64", ex_out(XP("i64", "x"), {"x": M64 - 4}), b"-5")
    eq("ex byte 0", ex_out(XP("byte", "x"), {"x": 0x100}), b"\r")
    eq("ex pname", ex_out(XP("pname", 1), {}, {1: b"Bob"}), b"\x0eBob")
    eq("ex pname 8", ex_out(XP("pname", "p"), {"p": 8}, {1: b"Bob"}), b"")
    eq("ex pick", ex_out(XP("pick", "i", table=["a", "bb"], default="?"), {"i": 5}), b"?")
    eq("ex fill right", ex_fill_slot(b"12", 4, "right"), b"\r\r12")
    eq("ex fill left", ex_fill_slot(b"12", 4, "left"), b"12\r\r")
    print("[ref_dp 자체 점검] 통과 %d, 실패 %d" % (ok, fail))
    return fail == 0


if __name__ == "__main__":
    import sys

    sys.exit(0 if _selfcheck() else 1)
