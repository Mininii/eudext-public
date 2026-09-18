"""`chat` 시험 (에뮬레이터 + testing/chatmodel 채팅 버퍼 모델): 줄 주소·EPD·떠 있음·화면 위치, 타자기(원본 참조 모델과
프레임마다 버퍼 바이트 비교 — 기본·속도·차례·소리·규칙·표식·대상·enable·nul_cell), S6 5.1-3 개별 항목(변환 프레임, 드러내기 순서,
홀수 slot 정렬, 바이트 표식 비교, 줄 꺼짐·새 줄, 대상 밖, 소리 빈칸·공백, 사용자 채팅 밀어내기), CP 보존, 경고·빌드 오류,
채팅 모델 자체, epScript 예제·인게임 확인 맵 번역·에뮬레이터·euddraft 빌드.

python tests/t_chat.py
비용 표: python tools/cost.py tests/t_chat.py [--append --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402
import warnings  # noqa: E402

from eudplib import (  # noqa: E402
    CompressPayload,
    DisplayTextAll,
    DoActions,
    EUDEndIf,
    EUDIf,
    EUDVariable,
    Exactly,
    LoadMap,
    Memory,
    RawTrigger,
    SetMemory,
    SetTo,
    f_getcurpl,
    f_setcurpl,
)

from eudext import _compat, chat, local, players  # noqa: E402
from eudext import textfx as tfx  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import BASE_MAP, chatmodel, emu, scmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
EX = os.path.join(_common.PKG, "examples")
WAV = "sound\\glue\\bnetclick.wav"
MARK_BYTES = tfx.MARK_U200B.to_bytes(4, "little")

ck = Checker("t_chat (python)")


# =============================================================================================
# 1. 파이썬 쪽
# =============================================================================================


def python_checks():
    for k in range(11):
        ck.eq("line_ptr %d" % k, chat.line_ptr(k), 0x640B60 + 218 * k)
        ck.eq("f_line_ptr 상수 %d" % k, chat.f_line_ptr(k), 0x640B60 + 218 * k)
        # eudplib f_getnextchatdst 와 같은 식: EPD(0x640B60) + Σ ceil(2^i · 54.5)
        want = (0x640B60 - 0x58A364) // 4 + sum((109 * (1 << i) + 1) // 2 for i in range(4) if k & (1 << i))
        ck.eq("line_epd %d" % k, chat.f_line_epd(k), want)
        ck.eq("셀 주소 %d" % k, chat.line_cell_addr(k, 0), 0x640B60 + 218 * k + 2 * (k & 1))
        ck.eq("모델 셀 주소 %d" % k, chatmodel.line_cell_addr(k, 53), chat.line_cell_addr(k, 53))
    ck.eq("줄 끝: 짝수 셀 53 = 바이트 212", chat.line_cell_addr(0, 53) - 0x640B60, 212)
    ck.eq("줄 끝: 홀수 셀 53 = 바이트 214", chat.line_cell_addr(1, 53) - chat.line_ptr(1), 214)
    for bad in (11, -1, "3", True):
        ck.raises("slot 오류 %r" % (bad,), EudextError, chat.line_ptr, bad)
        ck.raises("line_active slot 오류 %r" % (bad,), EudextError, chat.line_active, bad)
    ck.raises("셀 번호 오류", EudextError, chat.line_cell_addr, 0, 54)

    tw = chat.Typewriter()
    ck.eq("mark str", tw.mark("\x13안녕"), "\r\r!H\x13안녕")
    ck.eq("mark 여러 줄", tw.mark("a\nb\nc"), "\r\r!Ha\n\r\r!Hb\n\r\r!Hc")
    ck.eq("mark 끝 줄바꿈", tw.mark("a\n"), "\r\r!Ha\n")
    ck.eq("mark 빈 가운데 줄", tw.mark("a\n\nb"), "\r\r!Ha\n\r\r!H\n\r\r!Hb")
    ck.eq("mark bytes", tw.mark(b"x\ny"), b"\r\r!Hx\n\r\r!Hy")
    ck.eq("mark 빈 문구", tw.mark(""), "\r\r!H")
    tw2 = chat.Typewriter(marker="##가")
    ck.eq("marker str", tw2.marker, "##가".encode())
    ck.eq("mark 한글 표식", tw2.mark("a"), "##가a")
    tw3 = chat.Typewriter(marker=b"\xff\xfe#")
    ck.raises("UTF-8 아닌 표식 + str 문구", EudextError, tw3.mark, "a")
    ck.eq("UTF-8 아닌 표식 + bytes 문구", tw3.mark(b"a"), b"\xff\xfe#a")
    ck.raises("mark 형 오류", EudextError, tw.mark, 5)
    for bad in (b"ab", b"a" * 17, b"a\0b", b"\r\xe2\x80\x8b", b"\r\xe2\x80", b"xx\r\xe2\x80\x8b", b"xy\r\xe2", 5):
        ck.raises("marker 오류 %r" % (bad,), EudextError, chat.Typewriter, marker=bad)
    for kw in ({"speed": 0}, {"speed": 53}, {"speed": 1.5}, {"erase": -1}, {"erase": 53}, {"sound": 3},
               {"rule": "x"}, {"every": 0}, {"every": True}):
        ck.raises("옵션 오류 %r" % (kw,), EudextError, chat.Typewriter, **kw)
    ck.true("repr", "Typewriter" in repr(tw))


def model_checks():
    """채팅 버퍼 모델 자체 (빈 빌드의 machine 위에서)."""
    cmk = Checker("t_chat (model)")
    LoadMap(BASE_MAP)
    CompressPayload(True)
    m = emu.Program(lambda: None).build()
    scmodel.install(m, text=True)
    cm = chatmodel.install(m, next_line=9, lines={2: b"hello"})
    cmk.true("chat_model", chatmodel.chat_model(m) is cm)
    cmk.eq("미리 쓴 줄", (cm.text(2), cm.active(2), cm.next_slot), (b"hello", True, 9))
    slots = [cm.push_line(b"L%d" % i) for i in range(4)]
    cmk.eq("push 칸이 돈다", slots, [9, 10, 0, 1])
    cmk.eq("포인터", cm.next_slot, 2)
    cmk.eq("row_slot", [cm.row_slot(r) for r in (0, 8, 9, 10)], [2, 10, 0, 1])
    cmk.eq("push_text 여러 줄", cm.push_text("가\nb"), [2, 3])
    cmk.eq("visible", (cm.visible(2), cm.visible(3)), ("가", "b"))
    # 홀수 줄 셀은 +2 바이트
    cm.write_raw(5, b"\r\r" + MARK_BYTES + b"xyz")
    cmk.eq("홀수 셀 0", cm.cell(5, 0), tfx.MARK_U200B)
    cm.write_raw(4, MARK_BYTES + b"q")
    cmk.eq("짝수 셀 0", cm.cell(4, 0), tfx.MARK_U200B)
    cmk.eq("visible 표식·0x0D 빼기", cm.visible(5), "xyz")
    cm.hide(5)
    cmk.eq("hide", (cm.active(5), cm.visible(5), cm.raw(5)[:3]), (False, "", b"\0\r" + MARK_BYTES[:1]))
    cm.unhide(5, 0x0D)
    cmk.true("unhide", cm.active(5))
    # NUL 뒤 바이트 (strcpy 가정)
    cm.write_raw(6, b"abcdefgh")
    cm.write_raw(6, b"xy")
    cmk.eq("NUL 뒤 그대로", cm.raw(6)[:9], b"xy\0defgh\0")
    cm.write_raw(6, b"z", clear_rest=True)
    cmk.eq("clear_rest", cm.raw(6), b"z" + bytes(217))
    cm.write_raw(7, b"q" * 300)
    cmk.eq("217 자르기", (len(cm.text(7)), cm.raw(7)[217]), (217, 0))
    cm.set_cells(8, [1, 2, 3], start=10)
    cmk.eq("set_cells", cm.cells(8)[10:13], [1, 2, 3])
    # 표시 시간 가정
    cm2 = chatmodel.install(m, expire=3)
    cm2.clear()
    cm2.push_line(b"a")
    cm2.advance(2)
    cmk.true("expire 전", cm2.active(0))
    cm2.advance(1)
    cmk.true("expire 뒤 꺼짐", not cm2.active(0))
    cm2.clear(next_line=4)
    cmk.true("clear", cm2.buffer() == bytes(218 * 11) and cm2.next_slot == 4)
    # DisplayText 처리기: CP == 이 PC 일 때만, 글 기록 모델도 계속 기록
    cmk.true("처리기 이어짐", m.chat_model is cm2 and m._chatmodel_prev is not None)
    ref = chatmodel.TypewriterRef()
    ref.frame(cm2, run=False)
    cmk.eq("ref run=False", ref.st, [0] * 11)
    return cmk


# =============================================================================================
# 2. 에뮬레이터
# =============================================================================================

TW = {
    "tw_default": dict(),
    "tw_speed2": dict(speed=2, erase=0, nul_cell=False),
    "tw_every3_sound": dict(every=3, sound=WAV),
    "tw_eudplib": dict(rule="eudplib", sound=WAV),
    "tw_marker": dict(marker=b"##TW", erase=1),
    "tw_obs": dict(targets=players.Observers),
}
TW_OBJ = {}
VAR_VALUES = {"tw_vars": dict(speed=3, every=2)}


def ref_for(case):
    """Typewriter 인스턴스와 같은 설정의 참조 모델 (변수 옵션은 시험 케이스가 넣는 값)."""
    tw = TW_OBJ[case]
    kw = dict(marker=tw.marker, speed=tw.speed, erase=tw.erase, sound=tw.sound is not None, nul_cell=tw.nul_cell,
              rule=tw.rule, every=tw.every)
    kw.update(VAR_VALUES.get(case, {}))
    return chatmodel.TypewriterRef(**kw)


SPEED_V = EUDVariable()
EVERY_V = EUDVariable()
EN_FLAG = EUDVariable()
EN_FLAG2 = EUDVariable()
build_msgs = []


def build_cases(s):
    for name, kw in TW.items():
        TW_OBJ[name] = chat.Typewriter(**kw)

        @s.case(name)
        def _(t, name=name):
            TW_OBJ[name].tick()
            for k in range(11):
                t.watch("rem%d" % k, TW_OBJ[name].rem_vars[k].getValueAddr())

    TW_OBJ["tw_vars"] = chat.Typewriter(speed=SPEED_V, every=EVERY_V)
    TW_OBJ["tw_enable"] = chat.Typewriter(enable=EN_FLAG)
    TW_OBJ["tw_enable_fn"] = chat.Typewriter(enable=lambda: [EN_FLAG.Exactly(1), EN_FLAG2.Exactly(1)])

    @s.case("tw_vars")
    def _(t):
        SPEED_V << 3
        EVERY_V << 2
        TW_OBJ["tw_vars"].tick()

    @s.case("tw_enable")
    def _(t):
        EN_FLAG << t.var("en")
        TW_OBJ["tw_enable"].tick()

    @s.case("tw_enable_fn")
    def _(t):
        EN_FLAG << t.var("en")
        EN_FLAG2 << t.var("en2")
        TW_OBJ["tw_enable_fn"].tick()
        TW_OBJ["tw_enable_fn"].tick()  # 함수 enable 은 여러 번 불러도 된다 (한 프레임에 두 번 = 두 칸씩)

    @s.case("tw_display")
    def _(t):
        # DisplayText(표식 문구) → 같은 프레임에 변환 (모델 처리기가 버퍼에 쓴다)
        if EUDIf()(t.var("go").Exactly(1)):
            DoActions(DisplayTextAll(TW_OBJ["tw_default"].mark("\x13\x04첫째 줄 가나\n\x07둘째 줄 ab")))
        EUDEndIf()
        TW_OBJ["tw_default"].tick()

    @s.case("tw_cp")
    def _(t):
        orig = f_getcurpl()
        f_setcurpl(7)
        TW_OBJ["tw_default"].tick()
        t.flag("cp_raw", Memory(0x6509B0, Exactly, 7))
        t.out("cp_cache", f_getcurpl())
        f_setcurpl(orig)

    @s.case("addr")
    def _(t):
        k = t.var("k")
        t.out("ptr", chat.f_line_ptr(k))
        t.out("epd", chat.f_line_epd(k))

    @s.case("active")
    def _(t):
        with local.allow():
            t.flag("av", chat.line_active(t.var("k")))
            for j in range(11):
                t.flag("a%d" % j, chat.line_active(j))

    @s.case("row")
    def _(t):
        with local.allow():
            t.out("slot", chat.f_slot_of_row(t.var("row")))
            t.out("top", chat.f_slot_of_row(0))

    # 경고
    @s.case("warn_row")
    def _(t):
        t.out("slot", chat.f_slot_of_row(3))

    @s.case("warn_active")
    def _(t):
        t.flag("f", chat.line_active(4))

    @s.case("no_warn")
    def _(t):
        local.begin()
        t.out("slot", chat.f_slot_of_row(3))
        t.flag("f", chat.line_active(4))
        local.end()
        TW_OBJ["tw_default"].tick()  # tick 은 어디서 불러도 경고가 없다

    # 빌드 오류
    @s.case("err_active", expect_build_error=EudextError, expect_message="slot")
    def _(t):
        chat.line_active(11)

    @s.case("err_row", expect_build_error=EudextError, expect_message="slot")
    def _(t):
        chat.f_slot_of_row(12)

    @s.case("err_enable_twice", expect_build_error=EudextError, expect_message="한 번만")
    def _(t):
        tw = chat.Typewriter(enable=EN_FLAG.Exactly(1))
        tw.tick()
        tw.tick()


class Env:
    def __init__(self, s):
        self.s = s
        self.m = s.machine

    @property
    def cm(self):
        return chatmodel.chat_model(self.m)

    def wavs(self):
        tm = scmodel.text_model(self.m)
        return [r for r in tm.records if r.kind == "wav"]


def fresh(env):
    env.s.reset()
    cm = chatmodel.install(env.m)
    cm.clear()
    tm = scmodel.text_model(env.m)
    tm.clear()
    return cm


def step_compare(env, case, ref, inputs=None, label="", run=True):
    """ref 로 한 프레임(원본) → 버퍼를 되돌리고 에뮬레이터 한 사이클 → 11줄 바이트 비교."""
    cm = env.cm
    before = cm.buffer()
    nxt = cm.next_slot
    ref.frame(cm, run=run)
    want = cm.buffer()
    env.m.write_bytes(chatmodel.CHAT_BUF, before)
    r = env.s.run(case, inputs or {})
    got = cm.buffer()
    ok = r.error is None and got == want and cm.next_slot == nxt
    if not ok:
        diff = [k for k in range(11) if got[218 * k:218 * (k + 1)] != want[218 * k:218 * (k + 1)]]
        msg = "err=%s 다른 줄 %s" % (r.error, diff)
        if diff:
            k = diff[0]
            msg += "\n   got  %s\n   want %s" % (got[218 * k:218 * k + 60].hex(), want[218 * k:218 * k + 60].hex())
        env.s.expect_true(case, False, label, msg)
        env.m.write_bytes(chatmodel.CHAT_BUF, want)  # 다음 비교가 앞 차이에 끌려가지 않게
    return ok, r


def text_pool(tw):
    return [
        tw.mark("\x13\x04가사 한 줄 abc é"),
        tw.mark("\x07Hello \x04World  \r\r\r\r끝\n두 번째 줄"),
        tw.mark("😀ab\r\r\r\rcd\x07\r\r\rx ß"),
        tw.mark("a" * 70),
        tw.mark("\x1f" + "가" * 30),
        tw.mark(""),
        "plain line 보통 줄",
        "Mininii: !Hhi",
        "\x04" * 150 + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        "xx\r\r!Hmisaligned",
    ]


def scenario(env, case, rng, frames, label, inputs=None, events=0.15, hide_rate=0.04):
    tw = TW_OBJ[case]
    ref = ref_for(case)
    cm = fresh(env)
    cm.next_slot = rng.randrange(11)
    pool = text_pool(tw)
    bad = 0
    ok_frames = 0
    for f in range(frames):
        r = rng.random()
        if r < events:
            cm.push_text(rng.choice(pool))
        elif r < events + hide_rate:
            cm.hide(rng.randrange(11))
        elif r < events + hide_rate + 0.01:
            k = rng.randrange(11)
            cm.unhide(k, 0x0D)
        ok, _r = step_compare(env, case, ref, inputs, "%s 프레임 %d" % (label, f))
        if ok:
            ok_frames += 1
        else:
            bad += 1
            if bad > 3:
                break
    env.s.expect_true(case, bad == 0, "%s %d 프레임" % (label, frames), "틀린 프레임 %d" % bad)
    return ref


def run_scenarios(env, rng):
    for case in ("tw_default", "tw_speed2", "tw_every3_sound", "tw_eudplib", "tw_marker", "tw_vars"):
        for rep in range(3):
            ref = scenario(env, case, rng, 160, "무작위 %d" % rep)
            if TW_OBJ[case].sound is not None:
                n = len(env.wavs())
                env.s.expect_true(case, n == ref.sounds and all(w.text == WAV for w in env.wavs()),
                                  "소리 수 %d" % rep, "에뮬 %d 참조 %d" % (n, ref.sounds))
                env.s.expect_true(case, all(w.cp == 0 for w in env.wavs()), "소리 CP = 이 PC", "")
    # enable: 섞어서
    ref = chatmodel.TypewriterRef()
    cm = fresh(env)
    pool = text_pool(TW_OBJ["tw_enable"])
    bad = 0
    for f in range(200):
        if rng.random() < 0.15:
            cm.push_text(rng.choice(pool))
        en = 1 if (f // 17) % 2 == 0 else 0
        ok, _ = step_compare(env, "tw_enable", ref, {"en": en}, "enable %d" % f, run=bool(en))
        bad += not ok
    env.s.expect_true("tw_enable", bad == 0, "enable 켜고 끄기 200 프레임", "틀린 %d" % bad)
    # 함수 enable: 조건 둘 다 참일 때만, 한 프레임에 tick 두 번
    ref = chatmodel.TypewriterRef()
    cm = fresh(env)
    bad = 0
    for f in range(160):
        if rng.random() < 0.15:
            cm.push_text(rng.choice(pool))
        en, en2 = rng.randrange(2), rng.randrange(2)
        before = cm.buffer()
        ref.frame(cm, run=bool(en and en2))
        ref.frame(cm, run=bool(en and en2))
        want = cm.buffer()
        env.m.write_bytes(chatmodel.CHAT_BUF, before)
        r = env.s.run("tw_enable_fn", {"en": en, "en2": en2})
        if r.error or cm.buffer() != want:
            bad += 1
            env.m.write_bytes(chatmodel.CHAT_BUF, want)
    env.s.expect_true("tw_enable_fn", bad == 0, "함수 enable 160 프레임", "틀린 %d" % bad)


def arch_cells(data, erase=2, rule="ctrig"):
    res = tfx.scan_const(data + bytes(20), 52, rule)
    arch = [tfx.BLANK] * 52
    arch[: len(res.cells)] = res.cells
    for idx, c in res.extra.items():
        arch[idx] = (arch[idx] & ~0xFF) | c
    for i in range(erase):
        arch[i] = tfx.BLANK
    return arch


def run_specific(env):
    s = env.s
    case = "tw_default"
    B = tfx.BLANK
    for slot in (4, 5):  # 짝수·홀수
        cm = fresh(env)
        cm.next_slot = slot
        text = "\r\r!H\x13\x04가나 a"
        cm.push_line(text)
        head = cm.raw(slot)[:2]
        r = s.run(case)
        cells = cm.cells(slot)
        s.expect_true(case, r.error is None and cells == [tfx.MARK_U200B] + [B] * 52 + [0],
                      "변환 프레임 slot %d = 표식 + 빈칸 52 + NUL" % slot, str([hex(x) for x in cells[:4]]))
        if slot % 2:
            s.expect_true(case, cm.raw(slot)[:6] == head + MARK_BYTES, "홀수 slot 머리 2바이트 그대로 + 표식 +2",
                          cm.raw(slot)[:6].hex())
        else:
            s.expect_true(case, cm.raw(slot)[:4] == MARK_BYTES, "짝수 slot 표식 +0", cm.raw(slot)[:4].hex())
        arch = arch_cells(text.encode())
        ok = True
        for f in range(1, 60):
            s.run(case)
            k = min(f - 1, 52)
            want = arch[:k] + [B] * (52 - k)
            if cm.cells(slot)[1:53] != want:
                ok = False
                s.expect_true(case, False, "slot %d 프레임 %d" % (slot, f), str([hex(x) for x in cm.cells(slot)[1:8]]))
                break
        s.expect_true(case, ok, "slot %d 드러내기: 프레임 f 에 셀 1..f−1 = 보관 0..f−2 (앞 2칸 빈칸)" % slot)
        s.expect_true(case, arch[:2] == [B, B] and arch[2] == tfx.cell_const("\x13"), "!H 지움 + 셋째 = \\x13")
        s.expect_true(case, cm.visible(slot) == "가나 a", "보이는 글 slot %d" % slot, repr(cm.visible(slot)))
    # 바이트 비교: 홀수 slot 에서 원문 +2 에 표식이 있으면 변환하지 않는다 (dword 경계로 비교하면 맞아 보인다)
    for slot, raw, conv in ((3, b"xx\r\r!Hq", False), (3, b"\r\r!Hq", True), (2, b"\r\r!Hq", True),
                            (2, b"\r\r!hq", False), (6, b"\r!Hq", False), (7, b"\r\r!", False)):
        cm = fresh(env)
        cm.write_raw(slot, raw)
        s.run(case)
        s.expect_true(case, (cm.cell(slot, 0) == tfx.MARK_U200B) == conv, "표식 바이트 비교 slot %d %r" % (slot, raw),
                      hex(cm.cell(slot, 0)))
    # 줄이 꺼지면 멈추고, 같은 slot 새 표식 줄은 처음부터
    cm = fresh(env)
    cm.push_line("\r\r!Habcdefghij")
    s.run(case)
    for _ in range(6):
        s.run(case)
    shown = cm.cells(0)[1:53]
    cm.hide(0)
    for _ in range(10):
        s.run(case)
    s.expect_true(case, cm.cells(0)[1:53] == shown, "꺼진 줄은 그대로", "")
    s.expect_true(case, env.m.var("%s.rem0" % case) >= 1, "꺼져도 진행 상태 유지(원본과 같음)")
    cm.unhide(0, 0x0D)
    s.run(case)
    after = cm.cells(0)[1:53]
    s.expect_true(case, shown[5] == B and after[:5] == shown[:5] and after[5] == tfx.cell_const("d"),
                  "다시 켜지면 이어서 (셀 6 = d)", str([hex(x) for x in after[:7]]))
    cm.next_slot = 0
    cm.push_line("\r\r!HZZ")
    s.run(case)
    s.run(case)
    s.run(case)
    s.run(case)
    s.expect_true(case, cm.cells(0)[1:4] == [B, B, tfx.BLANK] and cm.cells(0)[0] == tfx.MARK_U200B,
                  "새 표식 줄은 k=0 부터", str([hex(x) for x in cm.cells(0)[:4]]))
    s.run(case)
    s.expect_true(case, cm.cells(0)[3] == tfx.cell_const("Z"), "새 줄 셋째 칸", hex(cm.cells(0)[3]))
    # 사용자 채팅이 진행 중인 slot 을 덮으면 상태를 지우고 그 줄을 건드리지 않는다
    cm = fresh(env)
    cm.push_line("\r\r!H" + "q" * 40)
    s.run(case)
    for i in range(10):
        cm.push_line("user%d: hello" % i)
        s.run(case)
    cm.push_line("Mininii: overwritten")  # slot 0 을 덮음
    s.run(case)
    for _ in range(5):
        s.run(case)
    s.expect_true(case, cm.text(0) == b"Mininii: overwritten", "덮인 줄 그대로", repr(cm.text(0)))
    s.expect_true(case, env.m.var("%s.rem0" % case) == 0, "덮이면 진행 상태 0")
    # nul_cell: 보통 긴 줄이 짝수 212, 홀수 214 에서 잘린다 / nul_cell=False 는 그대로
    for name, nul in (("tw_default", True), ("tw_speed2", False)):
        cm = fresh(env)
        long_line = b"\x04" * 200 + b"0123456789ABCDEF"
        cm.push_line(long_line)
        cm.push_line(long_line)
        s.run(name)
        v0, v1 = cm.visible(0), cm.visible(1)
        want = ("0123456789AB", "0123456789ABCD") if nul else ("0123456789ABCDEF",) * 2
        s.expect_true(name, (v0, v1) == want, "nul_cell=%s 긴 줄" % nul, repr((v0, v1)))
    # 소리: 빈칸·공백 셀에서는 나지 않는다 (eudplib 배치 공백 0x0D0D200D)
    cm = fresh(env)
    cm.push_line("\r\r!Ha b\r\r\r\r\x07\r\r\r c")
    for _ in range(40):
        s.run("tw_eudplib")
    arch = arch_cells("\r\r!Ha b\r\r\r\r\x07\r\r\r c".encode(), erase=TW_OBJ["tw_eudplib"].erase, rule="eudplib")
    loud = [c for c in arch[:51] if (c & 0xFFFFFF00) != 0x0D0D0D00 and (c & 0xFF00) != 0x2000]
    s.expect_true("tw_eudplib", TW_OBJ["tw_eudplib"].erase == 4 and cm.visible(0) == "a b c",
                  "eudplib 규칙: 표식 4셀을 지워 !H 가 안 보인다", repr(cm.visible(0)))
    s.expect_true("tw_eudplib", len(env.wavs()) == len(loud), "소리 = 빈칸·공백 아닌 셀 수",
                  "%d vs %d" % (len(env.wavs()), len(loud)))
    cm = fresh(env)
    cm.push_line("\r\r!H a  \r\r\r\rb")
    for _ in range(50):
        s.run("tw_every3_sound")
    s.expect_true("tw_every3_sound", len(env.wavs()) == 2, "ctrig 규칙 소리 (a, b)", str(len(env.wavs())))
    # DisplayText 로 여러 줄 표식 → 둘 다 변환, 드러낸 뒤 보이는 글
    cm = fresh(env)
    s.run("tw_display", {"go": 1})
    s.expect_true("tw_display", [cm.cell(k, 0) for k in (0, 1)] == [tfx.MARK_U200B] * 2 and cm.next_slot == 2,
                  "DisplayText 두 줄 변환", str([hex(cm.cell(k, 0)) for k in (0, 1)]))
    for _ in range(60):
        s.run("tw_display", {"go": 0})
    s.expect_true("tw_display", (cm.visible(0), cm.visible(1)) == ("첫째 줄 가나", "둘째 줄 ab"), "DisplayText 결과",
                  repr((cm.visible(0), cm.visible(1))))
    # CP 보존
    cm = fresh(env)
    cm.push_line("\r\r!Hab")
    for i in range(4):
        r = s.run("tw_cp")
        s.expect_true("tw_cp", r.error is None and r["cp_raw"] == 1 and r["cp_cache"] == 7, "CP 7 유지 %d" % i, repr(r))
    # 대상 밖(관전자 대상, 이 PC 0) → 버퍼 그대로
    cm = fresh(env)
    cm.push_line("\r\r!Hobserver only")
    before = cm.buffer()
    for _ in range(5):
        s.run("tw_obs")
    s.expect_true("tw_obs", cm.buffer() == before, "대상 밖 PC 는 버퍼 그대로")


def run_addr(env):
    s = env.s
    for k in range(16):
        want_epd = (0x640B60 - 0x58A364) // 4 + sum((109 * (1 << i) + 1) // 2 for i in range(4) if k & (1 << i))
        s.check("addr", {"k": k}, {"ptr": 0x640B60 + 218 * k, "epd": want_epd}, label="slot %d" % k)
    cm = fresh(env)
    rng = random.Random(3)
    for rep in range(12):
        cm.clear()
        on = [rng.randrange(2) for _ in range(11)]
        for k in range(11):
            cm.write_raw(k, (b"\r" if rng.random() < 0.5 else b"x") + b"abc")
            if not on[k]:
                cm.hide(k)
        for k in (0, 1, 5, 10, 11):
            r = s.run("active", {"k": k})
            flags = [r["a%d" % j] for j in range(11)]
            s.expect_true("active", flags == on and r["av"] == (on[k] if k < 11 else 0), "무작위 %d k=%d" % (rep, k),
                          "%s vs %s av=%s" % (flags, on, r["av"]))
    # 홀수 줄의 떠 있음은 원문 첫 바이트(= 셀 −2 바이트)만 본다
    cm.clear()
    cm.write_raw(3, b"\0\r" + MARK_BYTES)
    r = s.run("active", {"k": 3})
    s.expect_true("active", r["a3"] == 0 and r["av"] == 0, "홀수 줄 첫 바이트 0 = 꺼짐")
    for nxt in range(11):
        cm.next_slot = nxt
        for row in range(22):
            s.check("row", {"row": row}, {"slot": (row + nxt) % 11, "top": nxt}, label="next %d row %d" % (nxt, row))


def run_warnings(env):
    s = env.s
    s.expect_true("warn_row", any("chat.slot_of_row" in x and "t_chat.py" in x for x in build_msgs), "구역 밖 경고",
                  "; ".join(build_msgs))
    s.expect_true("warn_active", any("로컬 조건(LocalCondition)" in x and "t_chat.py" in x for x in build_msgs),
                  "로컬 조건 경고", "; ".join(build_msgs))
    s.expect_true("no_warn", sum("slot_of_row" in x for x in build_msgs) == 1
                  and sum("LocalCondition" in x for x in build_msgs) == 1, "구역 안·tick 은 경고 없음", "; ".join(build_msgs))
    for name in ("warn_row", "warn_active", "no_warn"):
        r = s.run(name)
        s.expect_true(name, r.error is None, "실행", repr(r))


def run_observer(env, rng):
    s = env.s
    s.restart(local_player=128)
    cm = fresh(env)
    cm.push_line("\r\r!Hobserver")
    for _ in range(15):
        s.run("tw_obs")
    s.expect_true("tw_obs", cm.visible(0) == "observer", "관전자(128) PC 에서 동작", repr(cm.visible(0)))
    scenario(env, "tw_obs", rng, 120, "관전자 무작위")
    scenario(env, "tw_default", rng, 80, "관전자 PC 기본(Everyone)")
    s.restart(local_player=0)


def section_emu():
    rng = random.Random(29)
    s = Suite("t_chat", memory={"text": True}, prep=lambda m: chatmodel.install(m))
    build_cases(s)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s.build()
    build_msgs.extend(str(x.message) for x in w)
    env = Env(s)
    run_addr(env)
    run_specific(env)
    run_scenarios(env, rng)
    run_warnings(env)
    run_observer(env, rng)
    # 실행 수 보고
    cm = fresh(env)
    idle = s.run("tw_default").steps[0]
    cm.push_line("\r\r!H\x13\x04가사 한 줄 abc")
    conv = s.run("tw_default").steps[0]
    reveal = [s.run("tw_default").steps[0] for _ in range(5)]
    print("  타자기 실행: 빈 프레임 %d, 변환 프레임 %d, 드러내기 프레임 %r" % (idle, conv, reveal))
    ok = s.report()
    return ok


# =============================================================================================
# 3. epScript 예제·인게임 맵
# =============================================================================================


def eps_checks(cke):
    src = open(os.path.join(EX, "chat_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("chat_example.eps", src)
    cke.eq("eps errors", nerr, 0)
    for needle in ("chat.Typewriter(targets=pl.Everyone, speed=1, erase=2)", "tw.tick()", "tw.mark(",
                   "chat.f_slot_of_row(0)", "chat.f_line_active(0)", "local.f_begin()"):
        cke.true("eps: " + needle, out is not None and needle in out, "")
    src = open(os.path.join(EX, "chat_ingame.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("chat_ingame.eps", src)
    cke.eq("ingame eps errors", nerr, 0)
    for needle in ("chat.Typewriter(enable=phaseA)", "fast.tick()", "slow.tick()", "chat.f_line_ptr(s)",
                   "f_memcpy(p + 2, p + i, 216 - i)"):
        cke.true("ingame eps: " + needle, out is not None and needle in out, "")
    # 원문 바이트 배치 (D17-4, D17-5 안내문과 맞는가)
    even = "\x04[D17-4] even slot: expect 12 chars after colon: ".encode()
    odd = "\x04[D17-4] odd slot: expect 14 chars after colon: ".encode()
    cke.eq("D17-4 숫자 시작 바이트", (len(even) + 151, len(odd) + 152), (200, 200))
    r = tfx.scan_const(b"\r\r!H" + ("\x04[D17-5] 52칸 한도: " + "0123456789" * 6).encode(), 52)
    cke.eq("D17-5 마지막 칸", r.cells[-4:], [tfx.cell_const(c) for c in "0123"])


def _load(name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_chat_" + name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name + ".eps"), os.path.join(work, name + ".eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name + ".eps"), {})


def eps_emulate(cke):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        mod = _load("chat_example")
        prog = emu.Program(mod.afterTriggerExec)
        for n in ("frame", "activeTop", "topSlot"):
            prog.watch(n, getattr(mod, n))
        m = prog.build()
    cke.eq("example 경고 없음", [str(x.message) for x in w if "구역 밖" in str(x.message) or "LocalCondition" in str(x.message)], [])
    scmodel.install(m, text=True)
    cm = chatmodel.install(m)
    m.cycle(80)
    cke.eq("example 값", {n: m.var(n) for n in ("frame", "activeTop", "topSlot")},
           {"frame": 80, "activeTop": 1, "topSlot": 2})
    cke.eq("example 줄", (cm.visible(0), cm.visible(1)), ("첫 줄 — 한 글자씩", "둘째 줄 abc"))
    cm.next_slot = 0
    cm.hide(0)
    m.cycle(1)
    cke.eq("example 줄 0 꺼짐·맨 위 slot", (m.var("activeTop"), m.var("topSlot")), (0, 0))


def ingame_emulate(cke):
    mod = _load("chat_ingame")
    prog = emu.Program(mod.afterTriggerExec)
    for n in ("frame", "relayed", "lastNext"):
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, text=True)
    cm = chatmodel.install(m)
    seen = set()
    err = None
    try:
        for cyc in range(1250):
            if cyc == 500:
                cm.push_line("\x03Mininii:\x04 !H안녕 éè 가나다".encode())
            if cyc == 700:
                cm.push_line("P1: no marker here".encode())
            m.cycle()
            seen.update(cm.visible(k) for k in range(11))
    except emu.EmuError as e:
        err = str(e)
    cke.eq("ingame emu 오류", err, None)
    cke.eq("ingame 값", {n: m.var(n) for n in ("frame", "relayed")}, {"frame": 1250, "relayed": 1})
    want = [
        "[D17-0] eudext 채팅 확인 맵 — 줄머리 [D17-n] 을 보고 알려 주세요",
        "[D17-1] 가운데 정렬 — 한 글자씩: 가나다라마바사 ABC",
        "[D17-2] 첫째 줄 (짝·홀 slot)",
        "[D17-2] 둘째 줄",
        "[D17-2] 셋째 줄 — 모두 표식 없이",
        "[D17-3] 2바이트 UTF-8: é ñ ü ß ç ø Ω — 깨지지 않으면 정상",
        "[D17-5] 52칸 한도: 0123456789012345678901234567890123",
        "[D17-6] 채팅으로 !H안녕 éè 가나다 를 보내 보세요 — 한 글자씩 다시 나오면 정상",
        "안녕 éè 가나다",
        "P1: no marker here",
        "[D17-7] 소리 판: 2프레임에 한 글자, 글자마다 딸깍, 공백은 조용",
        "[D17-8] 끝난 줄도 시간이 지나면 보통 채팅처럼 사라지면 정상",
    ]
    for text in want:
        cke.true("ingame 줄 %s" % text[:12], text in seen, "")
    cke.true("ingame !H 가 보인 적 없음", not any(v.startswith("!H") or "\r\r!H" in v for v in seen), "")
    d4 = [v for v in seen if v.startswith("[D17-4]")]
    cke.eq("ingame D17-4 한 가지 모양", len(d4), 1)
    d4 = d4[0] if d4 else ""
    cke.true("ingame D17-4 잘림", d4.endswith(": 0123456789AB") or d4.endswith(": 0123456789ABCD"), repr(d4))
    cke.true("ingame D17-4 안내와 맞음", ("even" in d4) == d4.endswith(": 0123456789AB"), repr(d4))
    wavs = [r for r in m.text_model.records if r.kind == "wav"]
    cke.true("ingame 소리 판에서 소리", len(wavs) > 20 and all(r.cycle >= 960 for r in wavs), str(len(wavs)))
    cke.true("ingame 빈 프레임 실행 수", m.ends[-1][0] < 200, str(m.ends[-1]))
    print("  인게임 맵 에뮬레이션: 최대 한 프레임 실행 %d, 소리 %d" % (max(e[0] for e in m.ends), len(wavs)))


def eps_build(cke):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("chat_example", "chat_ingame"):
        work = os.path.join(_common.WORK, "t_chat_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        cke.true("euddraft " + name, r.ok, r.log[-2000:])
        cke.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

C_TW = chat.Typewriter()
C_TW_SOUND = chat.Typewriter(sound=WAV, every=2)
C_SLOT = EUDVariable()


def _raw_line(slot, data):
    """slot 에 원문을 쓰는 준비 트리거 (dword 단위 SetMemory, 줄 앞을 덮지 않게 원문 자리부터 정렬해 쓴다)."""
    p = chat.line_ptr(slot)
    raw = (data.encode() if isinstance(data, str) else data) + b"\0"
    base = p & ~3
    head = p - base
    buf = bytearray(4 + len(raw) + 4)
    buf[head:head + len(raw)] = raw
    buf = bytes(buf[: (head + len(raw) + 3) & ~3])
    return [SetMemory(base + i, SetTo, struct.unpack_from("<I", buf, i)[0]) for i in range(0, len(buf), 4)]


def _setup_line(slot, data, extra=0):
    def setup(t):
        RawTrigger(actions=_raw_line(slot, data))
        for _ in range(extra):
            C_TW.tick()

    return setup


def _allowed(fn):
    with local.allow():
        return fn()


def _setup_sound(t):
    RawTrigger(actions=_raw_line(3, "\r\r!Habcdef"))
    for _ in range(4):
        C_TW_SOUND.tick()


COST_CASES = [
    CostCase("Typewriter.tick 빈 버퍼 (11줄 판정)", lambda t: C_TW.tick(), funcs=[C_TW._get_body()],
             note="본문 = 이 인스턴스 1벌 (스캐너 제외)"),
    CostCase("tick 변환 프레임 (표식 줄 16글자)", lambda t: C_TW.tick(), setup=_setup_line(4, "\r\r!H\x13\x04가사 한 줄 \x07abc 끝"),
             funcs=[tfx._scanner("ctrig", False)], note="본문 = 스캐너 1벌 (f_scan_cells 와 공유)"),
    CostCase("tick 변환 프레임 (홀수 slot, ASCII 50)", lambda t: C_TW.tick(), setup=_setup_line(5, "\r\r!H" + "a" * 50)),
    CostCase("tick 드러내기 프레임 (한 줄, 셀 하나)", lambda t: C_TW.tick(), setup=_setup_line(4, "\r\r!Habcdef", extra=3)),
    CostCase("tick 다 드러낸 줄만 (한 줄)", lambda t: C_TW.tick(), setup=_setup_line(4, "\r\r!Hab", extra=60)),
    CostCase("tick 소리·every=2 드러내기 (차례 프레임)", lambda t: C_TW_SOUND.tick(), setup=_setup_sound,
             funcs=[C_TW_SOUND._get_body()], cycles=2, note="두 프레임 중 큰 값"),
    CostCase("f_line_ptr (변수)", lambda t: chat.f_line_ptr(C_SLOT), funcs=[chat._line_ptr_func()]),
    CostCase("f_line_epd (변수)", lambda t: chat.f_line_epd(C_SLOT), funcs=[chat._line_epd_func()]),
    CostCase("line_active (변수) + EUDIf", lambda t: _allowed(lambda: t.flag("f", chat.line_active(C_SLOT))),
             funcs=[chat._active_func()], note="EUDIf·깃발 대입 포함"),
    CostCase("line_active (상수) + EUDIf", lambda t: _allowed(lambda: t.flag("f", chat.line_active(3))),
             note="EUDIf·깃발 대입 포함"),
    CostCase("f_slot_of_row (상수 row)", lambda t: _allowed(lambda: chat.f_slot_of_row(0)),
             funcs=[chat._slot_of_row_func()]),
]


def main():
    python_checks()
    cmk = model_checks()
    ok1 = section_emu()
    cke = Checker("t_chat (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    ingame_emulate(cke)
    eps_build(cke)
    finish(ok1, ck.report(), cmk.report(), cke.report())


if __name__ == "__main__":
    main()
