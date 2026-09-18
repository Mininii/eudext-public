#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [eudext hybrid] euddraft 0.11 / eudplib 0.81 사본 — 원본 NSQC.py (md5 35ce5e53173aca18e20593f9f9c0704e, 줄 끝 LF 기준).
# hybrid/make_plugins.py 가 만든다. 손으로 고치지 말 것 (규칙은 그 파일의 머리 주석).
import re
import sys
from math import ceil
from math import floor
from eudplib import *

# Default: Valkyrie, Location 1, P11
# fmt: off
Check, ASM = EUDVariable(), EUDVariable()
QCUnit, QCLoc, QCPlayer = 58, 0, 10
QCX, QCY = 128, 128  # (4, 4)
QCDebug, UseVal = True, False
qc_cons, qc_rets, xy_cons, xy_rets, deathsUnits = [], [], [], [], set()
QCDummy, QCDummyk = '227', -1
# [eudext hybrid, eudplib 0.81] 눌림 기억 칸을 바이트 배열로 (MapSource SNQC 1.3 과 같은 수정).
# 0.9 판의 EUDArray(8) + 키 // 8 은 0.81 에서 (키 // 8) 번째 dword = 배열 밖이 된다. 0.76 과 같은 비트필드:
# 키 k 의 칸 = KeyArray 의 (k // 32) 번째 dword, (k % 32) 번째 비트.
KeyArray, KeyOffset = Db(32), set()
MouseArray, MouseOffset = Db(4), set()


def _keybit(offset):
    return KeyArray + 4 * (offset // 32), 2 ** (offset % 32)
cmpScreenX, cmpMouseX, cmpScreenY, cmpMouseY = [Forward() for i in range(4)]
cmpScreenX2, cmpScreenY2 = [Forward() for i in range(2)]
isMouseMoved, useMouseLocation = EUDVariable(), False
isScreenMoved, useScreenLocation = EUDVariable(), False
useMouseMoved, useScreenMoved, useWidescreen, isWideScreen = False, False, False, EUDVariable()
addMouseCoord, addScreenCoord = Forward(), Forward()
sX, sY, mX, mY, _csY, _cmY = EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable()
screenloc, PrevCp, ScreenX, ScreenY, _ScreenY = 0, EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable()
MouseButtonDict = {"L": 2, "LEFT": 2, "R": 8, "RIGHT": 8, "M": 32, "MIDDLE": 32}
KeyCodeDict = {
    'LBUTTON': 0x01, 'RBUTTON': 0x02, 'CANCEL': 0x03, 'MBUTTON': 0x04,
    'XBUTTON1': 0x05, 'XBUTTON2': 0x06, 'BACK': 0x08, 'TAB': 0x09,
    'CLEAR': 0x0C, 'ENTER': 0x0D, 'NX5': 0x0E, 'SHIFT': 0x10,
    'LCTRL': 0x11, 'LALT': 0x12, 'PAUSE': 0x13, 'CAPSLOCK': 0x14,
    'RALT': 0x15, 'JUNJA': 0x17, 'FINAL': 0x18, 'RCTRL': 0x19, 'ESC': 0x1B,
    'CONVERT': 0x1C, 'NONCONVERT': 0x1D, 'ACCEPT': 0x1E, 'MODECHANGE': 0x1F,
    'SPACE': 0x20, 'PGUP': 0x21, 'PGDN': 0x22, 'END': 0x23, 'HOME': 0x24,
    'LEFT': 0x25, 'UP': 0x26, 'RIGHT': 0x27, 'DOWN': 0x28,  # ARROW keys
    'SELECT': 0x29, 'PRINTSCREEN': 0x2A, 'EXECUTE': 0x2B, 'SNAPSHOT': 0x2C,
    'INSERT': 0x2D, 'DELETE': 0x2E, 'HELP': 0x2F,
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    'A': 0x41, 'B': 0x42, 'C': 0x43, 'D': 0x44, 'E': 0x45, 'F': 0x46,
    'G': 0x47, 'H': 0x48, 'I': 0x49, 'J': 0x4A, 'K': 0x4B, 'L': 0x4C,
    'M': 0x4D, 'N': 0x4E, 'O': 0x4F, 'P': 0x50, 'Q': 0x51, 'R': 0x52,
    'S': 0x53, 'T': 0x54, 'U': 0x55, 'V': 0x56, 'W': 0x57, 'X': 0x58,
    'Y': 0x59, 'Z': 0x5A,
    'LWIN': 0x5B, 'RWIN': 0x5C, 'APPS': 0x5D, 'SLEEP': 0x5F,
    'NUMPAD0': 0x60, 'NUMPAD1': 0x61, 'NUMPAD2': 0x62, 'NUMPAD3': 0x63,
    'NUMPAD4': 0x64, 'NUMPAD5': 0x65, 'NUMPAD6': 0x66, 'NUMPAD7': 0x67,
    'NUMPAD8': 0x68, 'NUMPAD9': 0x69,
    'NUMPAD*': 0x6A, 'NUMPAD+': 0x6B, 'SEPARATOR': 0x6C, 'NUMPAD-': 0x6D,
    'NUMPAD.': 0x6E, 'NUMPAD/': 0x6F,
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74,
    'F6': 0x75, 'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79,
    'F11': 0x7A, 'F12': 0x7B, 'F13': 0x7C, 'F14': 0x7D, 'F15': 0x7E,
    'F16': 0x7F, 'F17': 0x80, 'F18': 0x81, 'F19': 0x82, 'F20': 0x83,
    'F21': 0x84, 'F22': 0x85, 'F23': 0x86, 'F24': 0x87,
    'NUMLOCK': 0x90, 'SCROLL': 0x91, 'OEM_FJ_JISHO': 0x92,
    'OEM_FJ_MASSHOU': 0x93, 'OEM_FJ_TOUROKU': 0x94,
    'OEM_FJ_LOYA': 0x95, 'OEM_FJ_ROYA': 0x96,
    'LSHIFT': 0xA0, 'RSHIFT': 0xA1, 'LCONTROL': 0xA2, 'RCONTROL': 0xA3,
    'LMENU': 0xA4, 'RMENU': 0xA5,
    'BROWSER_BACK': 0xA6, 'BROWSER_FORWARD': 0xA7, 'BROWSER_REFRESH': 0xA8,
    'BROWSER_STOP': 0xA9, 'BROWSER_SEARCH': 0xAA, 'BROWSER_FAVORITES': 0xAB,
    'BROWSER_HOME': 0xAC,
    'VOLUME_MUTE': 0xAD, 'VOLUME_DOWN': 0xAE, 'VOLUME_UP': 0xAF,
    'MEDIA_NEXT_TRACK': 0xB0, 'MEDIA_PLAY_PAUSE': 0xB3,
    'MEDIA_PREV_TRACK': 0xB1, 'MEDIA_STOP': 0xB2,
    'LAUNCH_MAIL': 0xB4, 'LAUNCH_MEDIA_SELECT': 0xB5, 'LAUNCH_APP1': 0xB6,
    'LAUNCH_APP2': 0xB7,
    'SEMICOLON': 0xBA, '=': 0xBB, ',': 0xBC, '-': 0xBD, '.': 0xBE, '/': 0xBF,
    '`': 0xC0, 'ABNT_C1': 0xC1, 'ABNT_C2': 0xC2,
    '[': 0xDB, '|': 0xDC, ']': 0xDD, "'": 0xDE, 'OEM_8': 0xDF,
    'OEM_AX': 0xE1, 'OEM_102': 0xE2, 'ICO_HELP': 0xE3, 'ICO_00': 0xE4,
    'PROCESSKEY': 0xE5, 'ICO_CLEAR': 0xE6, 'PACKET': 0xE7, 'OEM_RESET': 0xE9,
    'OEM_JUMP': 0xEA, 'OEM_PA1': 0xEB, 'OEM_PA2': 0xEC, 'OEM_PA3': 0xED,
    'OEM_WSCTRL': 0xEE, 'OEM_CUSEL': 0xEF,
    'OEM_ATTN': 0xF0, 'OEM_FINISH': 0xF1, 'OEM_COPY': 0xF2, 'OEM_AUTO': 0xF3,
    'OEM_ENLW': 0xF4, 'OEM_BACKTAB': 0xF5, 'ATTN': 0xF6, 'CRSEL': 0xF7,
    'EXSEL': 0xF8, 'EREOF': 0xF9, 'PLAY': 0xFA, 'ZOOM': 0xFB, 'NONAME': 0xFC,
    'PA1': 0xFD, 'OEM_CLEAR': 0xFE, '_NONE_': 0xFF
}

def parseV(s):
    _ns = GetEUDNamespace()
    for k, v in _ns.items():
        if IsEUDVariable(v) and k in s:
            s = re.sub(r"\b{}\b".format(k), "_ns['\g<0>']", s)
    return s

def EncPlayer(s):  # str to int (Player)
    PlayerDict = {
        'p1': 0, 'p2': 1, 'p3': 2, 'p4': 3, 'p5': 4, 'p6': 5,
        'p7': 6, 'p8': 7, 'p9': 8, 'p10': 9, 'p11': 10, 'p12': 11,
        'player1': 0, 'player2': 1, 'player3': 2, 'player4': 3,
        'player5': 4, 'player6': 5, 'player7': 6, 'player8': 7,
        'player9': 8, 'player10': 9, 'player11': 10, 'player12': 11,
        'neutral': 11,
        'currentplayer': 13,
        'foes': 14, 'allies': 15, 'neutralplayers': 16,
        'allplayers': 17,
        'force1': 18, 'force2': 19, 'force3': 20, 'force4': 21,
        'nonalliedvictoryplayers': 26
    }
    if s.lower() in PlayerDict:
        return PlayerDict[s.lower()]
    else:
        return int(s)


def RegisterKeyOffset(k):
    try:
        offset = KeyCodeDict[k.upper()]
    except (KeyError):
        raise EPError("%s doesn't exist in VirtualKeyCode." % (k))
    else:
        KeyOffset.add(offset)


def RegisterMouseOffset(k):
    try:
        v = MouseButtonDict[k.upper()]
    except (KeyError):
        raise EPError("%s is NOT a MouseButton. Use 'L', 'R' or 'M'." % (k))
    else:
        MouseOffset.add(v)


def KeyUpdate():
    for offset in sorted(KeyOffset):
        r = offset % 4
        m = 256 ** r
        ka, n = _keybit(offset)
        RawTrigger(
            conditions=[  # KeyDown
                MemoryX(0x596A18 + offset - r, Exactly, m, m),
                MemoryX(ka, Exactly, 0, n),
            ],
            actions=SetMemoryX(ka, SetTo, n, n),
        )
        RawTrigger(
            conditions=[  # KeyUp
                MemoryX(0x596A18 + offset - r, Exactly, 0, m),
                MemoryX(ka, Exactly, n, n),
            ],
            actions=SetMemoryX(ka, SetTo, 0, n),
        )


def KeyDown(k):
    try:
        offset = KeyCodeDict[k.upper()]
    except (KeyError):
        raise EPError("%s doesn't exist in VirtualKeyCode." % (k))
    else:
        KeyOffset.add(offset)
        r = offset % 4
        m = 256 ** r
        ka, n = _keybit(offset)
        return [  # KeyDown
            MemoryX(0x596A18 + offset - r, Exactly, m, m),
            MemoryX(ka, Exactly, 0, n),
        ]


def KeyUp(k):
    try:
        offset = KeyCodeDict[k.upper()]
    except (KeyError):
        raise EPError("%s doesn't exist in VirtualKeyCode." % (k))
    else:
        KeyOffset.add(offset)
        r = offset % 4
        m = 256 ** r
        ka, n = _keybit(offset)
        return [  # KeyUp
            MemoryX(0x596A18 + offset - r, Exactly, 0, m),
            MemoryX(ka, Exactly, n, n),
        ]


def KeyPress(k):
    try:
        offset = KeyCodeDict[k.upper()]
    except (KeyError):
        raise EPError("%s doesn't exist in VirtualKeyCode." % (k))
    else:
        r = offset % 4
        m = 256 ** r
        return MemoryX(0x596A18 + offset - r, Exactly, m, m)


def MouseUpdate():
    for k in MouseOffset:
        RawTrigger(
            conditions=[  # MouseDown
                MemoryX(0x6CDDC0, Exactly, k, k),
                MemoryX(MouseArray, Exactly, 0, k),
            ],
            actions=SetMemoryX(MouseArray, SetTo, k, k),
        )
        RawTrigger(
            conditions=[  # MouseUp
                MemoryX(0x6CDDC0, Exactly, 0, k),
                MemoryX(MouseArray, Exactly, k, k),
            ],
            actions=SetMemoryX(MouseArray, SetTo, 0, k),
        )


def MouseDown(k):
    try:
        v = MouseButtonDict[k.upper()]
    except (KeyError):
        raise EPError("%s is NOT a MouseButton. Use 'L', 'R' or 'M'." % (k))
    else:
        MouseOffset.add(v)
        return [  # MouseDown
            MemoryX(0x6CDDC0, Exactly, v, v),
            MemoryX(MouseArray, Exactly, 0, v),
        ]


def MouseUp(k):
    try:
        v = MouseButtonDict[k.upper()]
    except (KeyError):
        raise EPError("%s is NOT a MouseButton. Use 'L', 'R' or 'M'." % (k))
    else:
        MouseOffset.add(v)
        return [  # MouseUp
            MemoryX(0x6CDDC0, Exactly, 0, v),
            MemoryX(MouseArray, Exactly, v, v),
        ]


def MousePress(k):
    try:
        v = MouseButtonDict[k.upper()]
    except (KeyError):
        raise EPError("%s is NOT a MouseButton. Use 'L', 'R' or 'M'." % (k))
    else:
        return MemoryX(0x6CDDC0, Exactly, v, v)


def NotTyping():
    return Memory(0x68C144, Exactly, 0)


def _IsMouseMoved():
    global isMouseMoved
    isMouseMoved << 1
    global cmpScreenX, cmpMouseX, cmpScreenY, cmpMouseY 
    MouseJump, MouseContinue, MouseTRIG = Forward(), Forward(), Forward()

    RawTrigger(actions=SetDeaths(EPD(MouseTRIG+0x4),SetTo,MouseContinue,0))
    MouseTRIG << RawTrigger(
        conditions=[
            cmpScreenX << Memory(0x62848C, Exactly, 0),
            cmpMouseX << Memory(0x6CDDC4, Exactly, 0),
            cmpScreenY << Memory(0x6284A8, Exactly, 0),
            cmpMouseY << Memory(0x6CDDC8, Exactly, 0),
        ],
        actions=[isMouseMoved.SetNumber(0),
            SetDeaths(EPD(MouseTRIG+0x4),SetTo,MouseJump,0),
        ],
    )
    MouseContinue << NextTrigger()

    global sX, sY, mX, mY, _csY, _cmY
    sX = f_mapXread_epd(EPD(0x62848C))
    sY, _csY = f_mapYread_epd(EPD(0x6284A8))
    mX = f_screenXread_epd(EPD(0x6CDDC4))
    mY, _cmY = f_screenYread_epd(EPD(0x6CDDC8))
    VProc(
        [sX, mX, _csY, _cmY],
        [
            sX.QueueAssignTo(EPD(cmpScreenX) + 2),
            mX.QueueAssignTo(EPD(cmpMouseX) + 2),
            _csY.QueueAssignTo(EPD(cmpScreenY) + 2),
            _cmY.QueueAssignTo(EPD(cmpMouseY) + 2),
        ],
    )

    MouseJump << NextTrigger()

def _IsScreenMoved():
    global isScreenMoved
    isScreenMoved << 1
    global cmpScreenX2, cmpScreenY2
    ScreenJump, ScreenContinue, ScreenTRIG = Forward(), Forward(), Forward()

    RawTrigger(actions=SetDeaths(EPD(ScreenTRIG+0x4),SetTo,ScreenContinue,0))
    ScreenTRIG << RawTrigger(
        conditions=[
            cmpScreenX2 << Memory(0x62848C, Exactly, 0),
            cmpScreenY2 << Memory(0x6284A8, Exactly, 0),
        ],
        actions=[isScreenMoved.SetNumber(0),
            SetDeaths(EPD(ScreenTRIG+0x4),SetTo,ScreenJump,0),
        ],
    )
    ScreenContinue << NextTrigger()

    global sX, sY, _csY
    sX = f_mapXread_epd(EPD(0x62848C))
    sY, _csY = f_mapYread_epd(EPD(0x6284A8))
    VProc(
        [sX, _csY],
        [
            sX.QueueAssignTo(EPD(cmpScreenX2) + 2),
            _csY.QueueAssignTo(EPD(cmpScreenY2) + 2),
        ],
    )

    ScreenJump << NextTrigger()

def _IsWideScreen():
    global isWideScreen, humans, map_x, map_y, PrevCp
    isWideScreen << 1

    LL, LU, LR, LD, SY, _SY, SX, _SX = EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable()
    ScreenRecover, LocationRecover = Forward(), Forward()

    PrevCp << f_getcurpl()

    LL = f_maskread_epd(EPD(0x58DC60),0xFFFFFFFF)
    LU = f_maskread_epd(EPD(0x58DC64),0xFFFFFFFF)
    LR = f_maskread_epd(EPD(0x58DC68),0xFFFFFFFF)
    LD = f_maskread_epd(EPD(0x58DC6C),0xFFFFFFFF)
    SX = f_mapXread_epd(EPD(0x62848C))
    SY2, SY = f_mapYread_epd(EPD(0x6284A8))
    
    RawTrigger(
        actions=[
            SetMemory(0x58DC60,SetTo,2**(map_x)),
            SetMemory(0x58DC68,SetTo,2**(map_x)),
            SetMemory(0x58DC64,SetTo,2**(map_y)),
            SetMemory(0x58DC6C,SetTo,2**(map_y)),
            SetDeaths(EPD(ScreenRecover)+87,SetTo,2**(map_x),0),
            SetDeaths(EPD(ScreenRecover)+95,SetTo,2**(map_x),0),
            SetDeaths(EPD(ScreenRecover)+103,SetTo,2**(map_y),0),
            SetDeaths(EPD(ScreenRecover)+111,SetTo,2**(map_y),0),
    ])
    for p in humans:
        RawTrigger(conditions=[Memory(0x512684,Exactly,p)],actions=[SetMemory(0x6509B0,SetTo,p),CenterView(1)])

    RawTrigger(
        conditions=[
            Memory(0x62848C,Exactly,2**(map_x) - 320)
        ],
        actions=[isWideScreen.SetNumber(0)],
    )

    _SX = f_mapXread_epd(EPD(0x62848C))
    _SY2, _SY = f_mapYread_epd(EPD(0x6284A8))

    VProc(
        [SX, SY, _SX, _SY],
        [
            SX.QueueAddTo(EPD(ScreenRecover) + 87),
            SY.QueueAddTo(EPD(ScreenRecover) + 103),
            _SX.QueueSubtractTo(EPD(ScreenRecover) + 87),
            _SY.QueueSubtractTo(EPD(ScreenRecover) + 103),          
        ],
    )
    VProc(
        [SX, SY, _SX, _SY],
        [
            SX.QueueAddTo(EPD(ScreenRecover) + 95),
            SY.QueueAddTo(EPD(ScreenRecover) + 111), 
            _SX.QueueSubtractTo(EPD(ScreenRecover) + 95),
            _SY.QueueSubtractTo(EPD(ScreenRecover) + 111),          
        ],
    )
    ScreenRecover << RawTrigger(
        actions=[
            SetMemory(0x58DC60,SetTo,0),
            SetMemory(0x58DC68,SetTo,0),
            SetMemory(0x58DC64,SetTo,0),
            SetMemory(0x58DC6C,SetTo,0),
    ])
    for p in humans:
        RawTrigger(conditions=[Memory(0x512684,Exactly,p)],actions=[SetMemory(0x6509B0,SetTo,p),CenterView(1)])

    VProc(
        [LL, LU, LR, LD],
        [
            LL.QueueAssignTo(EPD(LocationRecover) + 87),
            LU.QueueAssignTo(EPD(LocationRecover) + 103),
            LR.QueueAssignTo(EPD(LocationRecover) + 95),
            LD.QueueAssignTo(EPD(LocationRecover) + 111),          
        ],
    )
    LocationRecover << RawTrigger(
        actions=[
            SetMemory(0x58DC60,SetTo,0),
            SetMemory(0x58DC68,SetTo,0),
            SetMemory(0x58DC64,SetTo,0),
            SetMemory(0x58DC6C,SetTo,0),
    ])

    f_setcurpl(PrevCp)

def MouseMoved():
    return isMouseMoved.Exactly(1)

def ScreenMoved():
    return isScreenMoved.Exactly(1)

def WideScreen():
    return isWideScreen.Exactly(1)

def onInit():
    sys.stdout.reconfigure(encoding="utf-8")
    # get map size & human player
    chkt = GetChkTokenized()
    dim, ownr = chkt.getsection("DIM"), chkt.getsection("OWNR")
    global bit_xy, map_x, map_y
    dim_x, dim_y = b2i2(dim[0:2]), b2i2(dim[2:4])
    bit_x, bit_y = dim_x.bit_length() + 2, dim_y.bit_length() + 18
    bit_xy = [2 ** y for y in range(bit_y, 15, -1)] + [
        2 ** x for x in range(bit_x, -1, -1)
    ]
    map_x, map_y = (dim_x - 1).bit_length() + 4, (dim_y - 1).bit_length() + 4

    global humans, QCUnit, QCLoc, QCPlayer, QCX, QCY, QCDebug, QCDummy
    global qc_cons, qc_rets, xy_cons, xy_rets, QCCount, UseVal
    humans = [p for p in range(8) if ownr[p] == 6]

    # simple parsing settings
    global QCDummyk
    for k, v in settings.items():
        if k == "QCDummy":
            QCDummy = v
            QCDummyk = k
    if QCDummyk != -1:
        settings.pop(k)
    settings['Always(); val, 0x58A364'] = QCDummy
    for k, v in settings.items():
        def EncodeInput(string, encode_func, type_name, name):
            try:
                ret = encode_func(string)
            except (EPError, KeyError):
                try:
                    ret = int(v, 0)
                except ValueError:
                    raise EPError("%s shoud be %s or number." % (type_name, name))
            return ret

        if k == "QCUnit" or k == "QCUnitID":
            QCUnit = EncodeInput(v, EncodeUnit, k, "unit")
            continue
        elif k == "QCLoc":
            QCLoc = EncodeInput(v, GetLocationIndex, k, "location")
            continue
        elif k == "QCPlayer":
            QCPlayer = EncodeInput(v, EncPlayer, k, "player")
            continue
        elif k == "QC_XY":
            coord = v.split(",")
            try:
                QCX, QCY = int(coord[0], 0), int(coord[1], 0)
            except (IndexError, ValueError):
                raise EPError("QC_XY should be two numbers.")
            continue
        elif k == "QCDebug" or k == "QCSafety":
            if v.lower() == "true":
                QCDebug = True
            elif v.lower() == "false":
                QCDebug = False
            else:
                try:
                    QCDebug = int(v, 0)
                except ValueError:
                    raise EPError("QCDebug should be True/False or non-zero, 0.")
            continue

        con_final, ret_final = [], None
       	Usedword, ret_final2 = False, []

        # parse conditions
        con_count = 0
        conds = [c.strip() for c in k.split(";")]
        for cond in conds:
            if cond == "마우스" or cond.lower() == "mouse":
                try:
                    mouse_loc = GetLocationIndex(v)
                except (EPError, KeyError):
                    try:
                        mouse_loc = int(v, 0)
                    except ValueError:
                        raise EPError("MouseLocation should be location or index.")
                con_final.append(Always())
                global useMouseLocation
                useMouseLocation = True
                mouse_loc -= min(humans)
                ret_final = ["mouse", mouse_loc]
            elif cond == "화면" or cond.lower() == "screen":
                try:
                    screen_loc = GetLocationIndex(v)
                except (EPError, KeyError):
                    try:
                        screen_loc = int(v, 0)
                    except ValueError:
                        raise EPError("ScreenLocation should be location or index.")
                con_final.append(Always())
                global screenloc
                screenloc = screen_loc
                global useScreenLocation
                useScreenLocation = True
                screen_loc -= min(humans)
                ret_final = ["screen", screen_loc]

            elif cond[:8] == "KeyDown(" and cond[-1] == ")":
                RegisterKeyOffset(cond[8:-1])
                con_final.append(KeyDown(cond[8:-1]))
            elif cond[:6] == "KeyUp(" and cond[-1] == ")":
                RegisterKeyOffset(cond[6:-1])
                con_final.append(KeyUp(cond[6:-1]))
            elif cond[:9] == "KeyPress(" and cond[-1] == ")":
                con_final.append(KeyPress(cond[9:-1]))
            elif cond.upper() in KeyCodeDict:
                RegisterKeyOffset(cond)
                con_final.append(KeyDown(cond))

            elif cond[:10] == "MouseDown(" and cond[-1] == ")":
                RegisterMouseOffset(cond[10:-1])
                con_final.append(MouseDown(cond[10:-1]))
            elif cond[:8] == "MouseUp(" and cond[-1] == ")":
                RegisterMouseOffset(cond[8:-1])
                con_final.append(MouseUp(cond[8:-1]))
            elif cond[:11] == "MousePress(" and cond[-1] == ")":
                con_final.append(MousePress(cond[11:-1]))

            elif cond.lower() == "nottyping":
                con_final.append(NotTyping())
            elif cond.lower() == "mousemoved":
                con_final.append(MouseMoved())
                global useMouseMoved
                useMouseMoved = True
            elif cond.lower() == "screenmoved":
                con_final.append(ScreenMoved())
                global useScreenMoved
                useScreenMoved = True
            elif cond.lower() == "widescreen":
                con_final.append(WideScreen())
                global useWidescreen
                useWidescreen = True
            else:
                c = [con.strip() for con in cond.split(",")]
                if c[0].lower() == "val":
                    UseVal = True
                    _c, deaths_unit = c[1], v.strip()
                    try:
                        _c = EPD(int(_c, 0))
                    except ValueError:
                        pass
                    try:
                        deaths_unit = EncodeUnit(deaths_unit)
                    except EPError:
                        try:
                            deaths_unit = int(deaths_unit, 0)
                        except:
                            try:
                                deaths_unit = float(deaths_unit)
                            except ValueError:
                                pass
                        else:
                            deathsUnits.add(deaths_unit)
                    else:
                        deathsUnits.add(deaths_unit)
                    ret_final = ["val", _c, deaths_unit]
                elif c[0].lower() == "dword":
                    Usedword = True
                    Errorcode = 0xFFFFFFFF
                    ret = [r.strip() for r in v.split(",")]
                    _c, deaths_unit = c[1], ret[0]
                    if len(ret) == 2:
                       Errorcode = int(ret[1],16)
                    try:
                        _c = EPD(int(_c, 0))
                    except ValueError:
                        pass
                    try:
                        deaths_unit = EncodeUnit(deaths_unit)
                    except EPError:
                        try:
                            deaths_unit = int(deaths_unit, 0)
                        except:
                            try:
                                deaths_unit = float(deaths_unit)
                            except ValueError:
                                pass
                        else:
                            deathsUnits.add(deaths_unit)
                    else:
                        deathsUnits.add(deaths_unit)
                    ret_final = ["low", _c, deaths_unit, Errorcode]
                    ret_final2 = ["high", _c, deaths_unit, Errorcode]
                elif c[0].lower() == "xy":
                    ret = [r.strip() for r in v.split(",")]
                    if not 1 <= len(ret) <= 2:
                        raise EPError("xy send/receive number should be 1 or 2")
                    ret_final = ["xy"]
                    try:
                        for _c in c[1:1 + len(ret)]:
                            try:
                                _c = EPD(int(_c, 0))
                            except ValueError:
                                pass
                            ret_final.append(_c)
                    except IndexError:
                        raise EPError("xy send/receive number mismatched")
                    for i, du in enumerate(ret):
                        deaths_unit = du
                        try:
                            deaths_unit = EncodeUnit(du)
                        except EPError:
                            try:
                                deaths_unit = int(du, 0)
                            except:
                                try:
                                    deaths_unit = float(du)
                                except ValueError:
                                    pass
                            else:
                                deathsUnits.add(deaths_unit)
                        else:
                            deathsUnits.add(deaths_unit)
                        ret_final.append(deaths_unit)
                elif re.fullmatch(r"0[xX][0-9a-fA-F]+", c[0]):
                    try:
                        ptr, mod, val = int(c[0], 0), eval(c[1]), int(c[2], 0)
                    except (IndexError, SyntaxError):
                        ptr, val = int(c[0], 0), int(c[1], 0)
                        con_final.append(MemoryX(ptr, Exactly, val, val))
                    else:
                        con_final.append(Memory(ptr, mod, val))
                else:
                    con_final.append(cond)

        ep_assert(len(con_final) >= 1, "At least 1 condition is needed.")

        # parse returns
        if ret_final is None:
            ret = [r.strip() for r in v.split(",")]
            try:
                increment = int(ret[1], 0)
            except ValueError:
                raise EPError("Value to add deaths/array must be number.")

            try:
                death_unit = EncodeUnit(ret[0])
            except EPError:
                try:
                    death_unit = int(ret[0], 0)
                except ValueError:
                    ret_final = ["array", ret[0], increment]
                else:
                    deathsUnits.add(death_unit)
                    ret_final = ["deaths", death_unit, increment]
            else:
                deathsUnits.add(death_unit)
                ret_final = ["deaths", death_unit, increment]
            qc_cons.append(con_final)
            qc_rets.append(ret_final)
            if Usedword == True:
            	qc_cons.append(con_final)
            	qc_rets.append(ret_final2)
        else:
            xy_cons.append(con_final)
            xy_rets.append(ret_final)
            if Usedword == True:
                xy_cons.append(con_final)
                xy_rets.append(ret_final2)
#-----------------------------------------------------------------------------
    QCCount = len(xy_rets) + ceil(len(qc_rets) / len(bit_xy))
    ep_assert(QCCount >= 1, "Must add desync cond : sync return pair")
    print(
        "[NSQC] map size: {}x{}, {} men x {} QCUnits (ID: {}), QCDummy (UnitID: {})".format(
            dim_x, dim_y, len(humans), QCCount, QCUnit, QCDummy
        )
    )
    if useMouseLocation:
        mrgn = chkt.getsection("MRGN")
        try:
            strtb = TBL(chkt.getsection("STR"))
        except KeyError:
            strtb = TBL(chkt.getsection("STRx"), load_entry=4, save_entry=4)
        loc_list = []
        for p in humans:
            locid = (mouse_loc - 1 + p) * 20
            locstr = b2i2(mrgn[locid + 16 : locid + 18])
            try:
                locname = strtb.GetString(locstr)
            except AttributeError:  # location has no name string
                locname = mouse_loc + p
            else:
                try:  # Guess encoding of location name
                    locname = locname.decode("utf-8")
                except UnicodeDecodeError:
                    import locale

                    locname = locname.decode(locale.getpreferredencoding())
                except AttributeError:  # ambiguous location name
                    locname = mouse_loc + p
            loc_list.append("P%u:%s" % (p + 1, locname))
        print("MouseLoc=%s" % ", ".join(loc_list))
    if useScreenLocation:
        mrgn = chkt.getsection("MRGN")
        try:
            strtb = TBL(chkt.getsection("STR"))
        except KeyError:
            strtb = TBL(chkt.getsection("STRx"), load_entry=4, save_entry=4)
        loc_list = []
        for p in humans:
            locid = (screen_loc - 1 + p) * 20
            locstr = b2i2(mrgn[locid + 16 : locid + 18])
            try:
                locname = strtb.GetString(locstr)
            except AttributeError:  # location has no name string
                locname = screen_loc + p
            else:
                try:  # Guess encoding of location name
                    locname = locname.decode("utf-8")
                except UnicodeDecodeError:
                    import locale

                    locname = locname.decode(locale.getpreferredencoding())
                except AttributeError:  # ambiguous location name
                    locname = screen_loc + p
            loc_list.append("P%u:%s" % (p + 1, locname))
        print("ScreenLoc=%s" % ", ".join(loc_list))
    if QCDebug:
        print("QCDebug enabled. You can disable it by writing 'QCDebug: false'.")


onInit()

QC_EPDs = [  # QCUnits = QCCount * humans
    EUDVArray(QCCount)([EPD(0x59CFDE)] * QCCount) if p in humans else 0
    for p in range(8)
]  # ptr, epd of QC_EPDs. ArrayPtr is used in nextptr modification
ArrayPTRs = PVariable(QC_EPDs)
ArrayEPDs = PVariable([EPD(x) for x in QC_EPDs])
# detect if QCUnit is selected (0x6284B8)
MyQCptrs = [Forward() for _ in range(QCCount)]
# used in SendQC::QGC_Select
MyQCalphaids = [Forward() for _ in range(QCCount)]
cp = EUDVariable()
if QCDebug:
    QCShutdown = EUDLightVariable()
f_mapXread_epd = f_readgen_epd(2 ** (map_x + 1) - 1, (0, lambda x: x))
f_mapYread_epd = f_readgen_epd(
    2 ** (map_y + 1) - 1, (0, lambda y: y << 16), (0, lambda y: y)
)
f_screenXread_epd = f_readgen_epd(0x3FF, (0, lambda x: x))
f_screenYread_epd = f_readgen_epd(0x1FF, (0, lambda y: y << 16), (0, lambda y: y))
mapMask = 2 ** (map_x + 1) - 1 + ((2 ** (map_y + 1) - 1) << 16)
f_tosread_epd = f_readgen_epd(0xFF00, (0, lambda x: x * 8))
f_b1read_epd = f_readgen_epd(0xFF00, (0, lambda x: x >> 8))
valMask = 2 ** map_x - 1 + ((2 ** map_y - 1) << map_x)
v2pMask = 2 ** map_x - 1 + ((2 ** map_y - 1) << 16)
f_v2posread_epd = f_readgen_epd(valMask, (0, lambda x: x if x < 1 << map_x else x << (16 - map_x)))
f_pos2vread_epd = f_readgen_epd(v2pMask, (0, lambda x: x if x <= 0xFFFF  else x >> (16 - map_x)))
f_low2posread_epd = f_readgen_epd(0xFFFF, (0, lambda x: x if x <= 0xFF else x << 8))
f_pos2lowread_epd = f_readgen_epd(0xFF00FF, (0, lambda x: x if x <= 0xFF else x >> 8))
f_high2posread_epd = f_readgen_epd(0xFFFF0000, (0, lambda x: (x >> 16) if x <= 0xFF0000 else x>>8))
f_pos2highread_epd = f_readgen_epd(0xFF00FF, (0, lambda x: (x<<16) if x <= 0xFF else x<<8))
# fmt: on
if UseVal:
    print("Sendable value range for 'val' syntax: 0 to {}".format(valMask))


def EUDHumanLoop():
    def _footer():
        block = {"origcp": f_getcurpl()}

        minp, maxp = min(humans), max(humans)
        EUDWhile()(cp.AtMost(maxp))
        for p in range(minp, maxp):
            if p not in humans:
                EUDContinueIf(cp.Exactly(p))
        EUDContinueIfNot(f_playerexist(cp))
        f_setcurpl(cp)

        EUDCreateBlock("hloopblock", block)
        return True

    return CtrlStruOpener(_footer)


def EUDEndHumanLoop():
    block = EUDPopBlock("hloopblock")[1]
    origcp = block["origcp"]

    if not EUDIsContinuePointSet():
        EUDSetContinuePoint()

    EUDEndWhile()
    f_setcurpl(origcp)


@EUDFunc
def f_epd2alphaid(epd):
    epd += 43
    ret = epd // 84
    ret -= 226
    # alphaID = (ptr - 0x59CCA8) // 336 + 1
    # = (ptr - 56) // 336 - 17514
    # = (epd * 4 + 0x58A364 - 56) // 336 - 17514
    # = (epd + 1452235) // 84 - 17514
    EUDReturn(ret)


qc_epd = EUDVariable()
vr = EUDVArrayReader()


def onPluginStart():
    Respawn()


@EUDFunc
def Respawn():
    w4, r4 = divmod(QCUnit, 4)
    w2, r2 = divmod(QCUnit, 2)
    LOC_TEMP, LocEPD = EUDArray(5), EPD(0x58DC60) + QCLoc * 5
    global cp
    q4, q2 = 4 * w4, 4 * w2
    m4, m2 = 1 << (8 * r4), 1 << (16 * r2)
    DoActions(
        [
            # Set fligy to [94] Command Center
            SetMemoryX(0x6644F8 + q4, SetTo, 94 * m4, 0xFF * m4),
            # Units.dat: Unit Dimensions, Building Dimensions
            SetMemory(0x6617C8 + QCUnit * 8, SetTo, 0x20002),
            SetMemory(0x6617CC + QCUnit * 8, SetTo, 0x20002),
            SetMemory(0x662860 + QCUnit * 4, SetTo, 0),
            # Ground Weapon, Air Weapon
            SetMemoryX(0x6636B8 + q4, SetTo, 130 * m4, 0xFF * m4),
            SetMemoryX(0x6616E0 + q4, SetTo, 130 * m4, 0xFF * m4),
            # Seek Range, Sight Range
            SetMemoryX(0x662DB8 + q4, SetTo, 0, 0xFF * m4),
            SetMemoryX(0x663238 + q4, SetTo, 0, 0xFF * m4),
            # Advanced Flags, Editor Ability Flags, Group
            SetMemory(0x664080 + QCUnit * 4, SetTo, 0x38000025),
            SetMemoryX(0x661518 + q2, SetTo, 0x1CF * m2, 0xFFFF * m2),
            SetMemoryX(0x6637A0 + q4, SetTo, 0, 0xFF * m4),
            # MovementFlags & Elevation
            SetMemoryX(0x660FC8 + q4, SetTo, 0xC5 * m4, 0xFF * m4),
            SetMemoryX(0x663150 + q4, SetTo, 0x13 * m4, 0xFF * m4),
            # Temporary save previous data of QCLocation
            # [eudext hybrid, eudplib 0.81] LOC_TEMP + 4k 는 0.81 에서 원소 4k (배열 밖) -> 원소 k 의 EPD 로 쓴다
            SetMemoryEPD(LOC_TEMP._epd, SetTo, f_dwread_epd(LocEPD)),
            SetMemoryEPD(LOC_TEMP._epd + 1, SetTo, f_dwread_epd(LocEPD + 1)),
            SetMemoryEPD(LOC_TEMP._epd + 2, SetTo, f_dwread_epd(LocEPD + 2)),
            SetMemoryEPD(LOC_TEMP._epd + 3, SetTo, f_dwread_epd(LocEPD + 3)),
            SetMemoryEPD(LOC_TEMP._epd + 4, SetTo, f_dwread_epd(LocEPD + 4)),
            SetMemoryXEPD(LocEPD + 4, SetTo, 0, 0xFFFF0000),
            cp.SetNumber(min(humans)),
        ]
    )
    EUDHumanLoop()()
    i = EUDVariable()
    arrayEPD = ArrayEPDs[cp]
    DoActions(
        [
            i.SetNumber(0),
            arrayEPD.AddNumber(328 // 4 + 5),
            [
                DisplayText("\x13\x04[QCDebug] \x16Respawning QC Units...")
                if QCDebug
                else []
            ],
        ]
    )
    if EUDWhile()(i <= QCCount - 1):
        if EUDIf()(Memory(0x628438, Exactly, 0)):
            EUDReturn(-1)  # Cannot create more unit
        EUDEndIf()
        ptr, epd = f_cunitepdread_epd(EPD(0x628438))

        DoActions(
            [
                # reset QCLocation to QC_XY
                SetMemoryEPD(LocEPD, SetTo, QCX),
                SetMemoryEPD(LocEPD + 1, SetTo, QCY),
                SetMemoryEPD(LocEPD + 2, SetTo, QCX),
                SetMemoryEPD(LocEPD + 3, SetTo, QCY),
                CreateUnitWithProperties(
                    1, QCUnit, QCLoc + 1, max(humans), UnitProperty(intransit=True)
                ),
                SetMemoryEPD(arrayEPD, SetTo, epd),
            ]
        )
        pos_x, pos_y = f_posread_epd(epd + 0x28 // 4)
        SetLoc2UnitPos, Loc2PosTrg = Forward(), Forward()
        VProc(
            [pos_x, pos_y],
            [
                pos_x.QueueAssignTo(EPD(SetLoc2UnitPos) + 5),
                pos_y.QueueAssignTo(EPD(SetLoc2UnitPos) + 13),
            ],
        )
        RawTrigger(
            nextptr=pos_x.GetVTable(),
            actions=[
                SetMemory(pos_x._varact + 16, Add, 16),
                SetMemory(pos_y._varact + 16, Add, 16),
                SetNextPtr(pos_y.GetVTable(), Loc2PosTrg),
            ],
        )
        Loc2PosTrg << NextTrigger()
        DoActions(
            [
                # Move QCLocation to QCUnitq
                SetLoc2UnitPos << SetMemoryEPD(LocEPD, SetTo, 0),
                SetMemoryEPD(LocEPD + 1, SetTo, 0),
                SetMemoryEPD(LocEPD + 2, SetTo, 0),
                SetMemoryEPD(LocEPD + 3, SetTo, 0),
                GiveUnits(1, QCUnit, max(humans), QCLoc + 1, QCPlayer),
                SetMemoryEPD(epd + 0x10 // 4, SetTo, 64 * 65537),  # reset waypoint
                SetMemoryEPD(epd + 0x34 // 4, SetTo, 0),  # immobilize
                SetMemoryEPD(
                    epd + 0x4C // 4, Add, cp - QCPlayer
                ),  # modify unit's player
                SetMemoryEPD(epd + 0xDC // 4, Add, 0xA00000),  # stackable
                SetMemoryXEPD(epd + 0xA5 // 4, SetTo, 0, 0xFF00),  # uniqueIdentifier
            ]
        )
        if EUDIf()(Memory(0x512684, Exactly, cp)):
            MyQCptrsArray = EUDArray([EPD(t) + 2 for t in MyQCptrs])
            MyQCalphaidsArray = EUDArray([EPD(t) + 5 for t in MyQCalphaids])
            SetMyQC = Forward()
            myQCptr, myQCalphaID = MyQCptrsArray[i], MyQCalphaidsArray[i]
            alphaID = f_epd2alphaid(epd)

            VProc(
                [myQCptr, myQCalphaID, ptr, alphaID],
                [
                    myQCptr.QueueAssignTo(EPD(SetMyQC) + 4),
                    myQCalphaID.QueueAssignTo(EPD(SetMyQC) + 12),
                    ptr.QueueAssignTo(EPD(SetMyQC) + 5),
                    alphaID.QueueAssignTo(EPD(SetMyQC) + 13),
                ],
            )
            RawTrigger(
                actions=[
                    SetMyQC << SetMemory(0, SetTo, 0),  # ptr
                    SetMemory(0, SetTo, 0),  # alphaID
                ]
            )
        EUDEndIf()
        EUDSetContinuePoint()
        DoActions([i.AddNumber(1), arrayEPD.AddNumber(18)])
    EUDEndWhile()
    EUDSetContinuePoint()
    cp += 1
    EUDEndHumanLoop()

    DoActions(
        [
            # Restore previouse data of QCLocation
            SetMemoryEPD(LocEPD, SetTo, LOC_TEMP[0]),
            SetMemoryEPD(LocEPD + 1, SetTo, LOC_TEMP[1]),
            SetMemoryEPD(LocEPD + 2, SetTo, LOC_TEMP[2]),
            SetMemoryEPD(LocEPD + 3, SetTo, LOC_TEMP[3]),
            SetMemoryEPD(LocEPD + 4, SetTo, LOC_TEMP[4]),
            # Editor Ability Flags
            SetMemoryX(0x661518 + q2, SetTo, 0, 0xFFFF * m2),
        ]
    )
    EUDReturn(0)


def eqsplit(iterable, eqr):
    if isinstance(iterable, list):
        for i in range(0, len(iterable), eqr):
            yield iterable[i : i + eqr]

    else:
        it = iter(iterable)
        item = list(itertools.islice(it, eqr))
        while item:
            yield item
            item = list(itertools.islice(it, eqr))


@EUDFunc
def KillQCUnits():
    global cp
    cp << min(humans)
    EUDHumanLoop()()
    arrayPtr = ArrayPTRs[cp]
    arrayEPD = ArrayEPDs[cp]
    i = EUDVariable()
    vr.seek(arrayPtr, arrayEPD, qc_epd, i.SetNumber(0))
    if EUDWhile()(i <= QCCount - 1):
        vr.read(i.AddNumber(1))
        EUDContinueIf(MemoryEPD(qc_epd + 0xC // 4, Exactly, 0))
        DoActions(SetMemoryXEPD(qc_epd + 0x110 // 4, SetTo, 1, 0xFFFF))
    EUDEndWhile()
    EUDSetContinuePoint()
    cp += 1
    EUDEndHumanLoop()


def DebugQC():
    if not QCDebug:
        return
    something_bad_happend, fin = Forward(), Forward()
    err_type = EUDLightVariable()
    global cp
    cp << min(humans)
    EUDHumanLoop()()
    arrayPtr = ArrayPTRs[cp]
    arrayEPD = ArrayEPDs[cp]
    playercheck = Forward()
    VProc(
        [arrayPtr, arrayEPD, cp],
        [
            arrayPtr.QueueAssignTo(EPD(vr._trg) + 1),
            arrayEPD.AddNumber(1),
            arrayEPD.QueueAssignTo(EPD(vr._trg) + 360 // 4 + 4),
            cp.QueueAssignTo(EPD(playercheck) + 2),
            SetMemory(vr._trg + 328 + 20, SetTo, EPD(qc_epd.getValueAddr())),
        ],
    )
    i = EUDVariable()
    VProc(
        arrayEPD,
        [
            arrayEPD.AddNumber(328 // 4 + 3),
            SetMemory(arrayEPD._varact + 16, Add, -8),
            i.SetNumber(0),
        ],
    )
    if EUDWhile()(i <= QCCount - 1):
        vr.read(i.AddNumber(1))
        if EUDIf()(MemoryEPD(qc_epd + 0xC // 4, Exactly, 0)):
            RawTrigger(nextptr=something_bad_happend, actions=err_type.SetNumber(1))
        if EUDElseIf()(MemoryXEPD(qc_epd + 0xA5 // 4, AtLeast, 256, 0xFF00)):
            RawTrigger(nextptr=something_bad_happend, actions=err_type.SetNumber(2))
        if EUDElseIfNot()(
            [playercheck << MemoryXEPD(qc_epd + 0x4C // 4, Exactly, 0, 0xFF)]
        ):
            RawTrigger(nextptr=something_bad_happend, actions=err_type.SetNumber(3))
        EUDEndIf()
    EUDEndWhile()
    EUDSetContinuePoint()
    cp += 1
    EUDEndHumanLoop()

    PushTriggerScope()
    something_bad_happend << NextTrigger()
    cp << min(humans)
    if EUDHumanLoop()():
        DoActions(
            [
                # TODO: more helpful debug message
                DisplayText("\x13\x08NSQC FATAL ERROR! QC Unit has been removed.")
            ]
        )
        RawTrigger(
            conditions=err_type.Exactly(1), actions=DisplayText("\x13CSprite is 0")
        )
        RawTrigger(
            conditions=err_type.Exactly(2),
            actions=DisplayText("\x13TOS is more than 0"),
        )
        RawTrigger(
            conditions=err_type.Exactly(3),
            actions=DisplayText("\x13Player isn't equal"),
        )
        EUDSetContinuePoint()
        cp += 1
    EUDEndHumanLoop()
    KillQCUnits()
    if EUDIf()(Respawn() == -1):
        KillQCUnits()
        DoActions([cp.SetNumber(min(humans)), QCShutdown.SetNumber(60 * 23)])
        if EUDHumanLoop()():
            DoActions(
                [
                    # TODO: more helpful debug message
                    DisplayText(
                        "\x13\x08QC Respawn failed due to 'Cannot create more unit'\n\x13\x08* NSQC will shutdown for 1 minute."
                    )
                ]
            )
            EUDSetContinuePoint()
            cp += 1
        EUDEndHumanLoop()
    EUDEndIf()
    EUDJump(fin)
    PopTriggerScope()
    fin << NextTrigger()


SelCount, SelMem = EUDVariable(), EUDVArray(12)()
QGCActivated = EUDLightVariable()


@EUDFunc
def SendQC():
    global SelCount, SelMem, QGCActivated
    skipSelSave = Forward()
    global MyQC

    # 0x6284B8: (desync) *CUnits of units in selection (4 bytes * 12 units)
    for i in range(QCCount):  # skip if QCUnit is selected
        skipper, nextTrg = Forward(), Forward()
        skipper << RawTrigger(
            conditions=[MyQCptrs[i] << Memory(0x6284B8, Exactly, 0)],
            actions=[
                SetNextPtr(skipper, skipSelSave),
                SetMemory(skipSelSave + 344, SetTo, EPD(skipper) + 1),
                SetMemory(skipSelSave + 348, SetTo, nextTrg),
            ],
        )
        nextTrg << NextTrigger()
    SetSelMem = Forward()
    DoActions(
        [
            SetMemory(0x6509B0, SetTo, EPD(0x6284B8)),
            SetMemory(SetSelMem + 16, SetTo, EPD(SelMem) + 328 // 4 + 5),
            SelCount.SetNumber(0),
        ]
    )
    if EUDWhile()(Deaths(CurrentPlayer, AtLeast, 0x59CCA8, 0)):
        DoActions(
            [
                SetSelMem << SetMemory(0, SetTo, f_cunitepdread_cp(0)[1]),
                SetMemory(SetSelMem + 16, Add, 18),
                SelCount.AddNumber(1),
                SetMemory(0x6509B0, Add, 1),
            ]
        )
        EUDBreakIf(SelCount.AtLeast(12))
    EUDEndWhile()
    skipSelSave << RawTrigger(
        actions=[
            SetNextPtr(skipper, nextTrg),
            QGCActivated.SetNumber(0),
            cp.SetNumber(min(humans)),  # initialization for ReceiveQC
        ]
    )
    global useMouseLocation, useScreenLocation, useMouseMoved, useScreenMoved, useWidescreen
    if (useMouseLocation or useMouseMoved):
        _IsMouseMoved()
    if (useScreenLocation or useScreenMoved):
        _IsScreenMoved()
    if useWidescreen:
        _IsWideScreen()


    def parseCond(s):
        _ns = GetEUDNamespace()
        for k, v in _ns.items():
            if (
                IsEUDVariable(v)
                or isUnproxyInstance(v, EUDLightBool)
                or isUnproxyInstance(v, EUDLightVariable)
                or isUnproxyInstance(v, EUDXVariable)
            ) and k in s:
                s = re.sub(r"\b{}\b".format(k), "_ns['\g<0>']", s)
        return s

    RC = Db(b"...\x14XXYY\0\0\xE4\0\x00") # QGC : 우클릭<14>(1), u32 Position(4), u16 ???(2), u16 유닛타입(2), bool 큐 여부(큐 명령시 1,Bool)
    SEL = Db(b"..\x09\x0112..")
    f_setcurpl(f_getuserplayerid())

    _ns = GetEUDNamespace()
    qc_list = eqsplit(qc_cons, len(bit_xy))
    qc_count = 0
    for n, conds in enumerate(qc_list):
        qc_count += 1
        DoActions(SetMemory(RC + 4, SetTo, 65537 * 64))
        for con, bit in zip(conds, bit_xy):
            if len(con) == 1:
                if type(con[0]) is str:
                    condition = eval(parseCond(con[0]))
                else:
                    condition = con[0]
            else:
                condition = EUDSCAnd()
                for c in con:
                    if type(c) is str:
                        condition = condition(eval(parseCond(c)))
                    else:
                        condition = condition(c)
                condition = condition()
            if EUDIf()(condition):
                DoActions(SetMemory(RC + 4, Add, bit))
            EUDEndIf()
        if EUDIf()(Memory(RC + 4, AtLeast, 65537 * 64 + 1)):
            DoActions(
                [
                    MyQCalphaids[n] << SetMemory(SEL + 4, SetTo, 0),
                    QGCActivated.SetNumber(1),
                ]
            )
            # TODO: Optimize QueueGameCommand and f_memcpy
            QueueGameCommand(SEL + 2, 4)
            QueueGameCommand(RC + 3, 10)  # RightClick
        EUDEndIf()
    global sX, sY, mX, mY, screenloc, PrevCp, ScreenX, _csY, _cmY
    for n, (con, ret) in enumerate(zip(xy_cons, xy_rets)):
        if len(con) == 1:
            if type(con[0]) is str:
                condition = eval(parseCond(con[0]))
            else:
                condition = con[0]
        else:
            condition = EUDSCAnd()
            for c in con:
                if type(c) is str:
                    condition = condition(eval(parseCond(c)))
                else:
                    condition = condition(c)
            condition = condition()
        if ret[0] == "low":
            if isinstance(ret[1], int) and isinstance(ret[2], float):
                if EUDExecuteOnce()():
                    RawTrigger(actions=SetDeaths(ret[1],SetTo,ret[3],0))
                EUDEndExecuteOnce()
        EUDIf()(condition)
        if ret[0] == "mouse":
            addMouseCoord = Forward()
            VProc(
                [sX, sY, mX, mY],
                [
                    sX.QueueAssignTo(EPD(addMouseCoord) + 87),
                    sY.QueueAddTo(EPD(addMouseCoord) + 87),
                    mX.QueueAddTo(EPD(addMouseCoord) + 87),
                    mY.QueueAddTo(EPD(addMouseCoord) + 87),
                    MyQCalphaids[n + qc_count] << SetMemory(SEL + 4, SetTo, 0),
                    QGCActivated.SetNumber(1),
                ],
            )
            RawTrigger(conditions=DeathsX(EPD(addMouseCoord) + 87,AtLeast,2**(map_x+1),0,0xFFFF), actions=SetDeathsX(EPD(addMouseCoord) + 87,SetTo,2**(map_x+1)-1,0,0xFFFF))
            RawTrigger(conditions=DeathsX(EPD(addMouseCoord) + 87,AtLeast,2**(map_y+17),0,0xFFFF0000), actions=SetDeathsX(EPD(addMouseCoord) + 87,SetTo,2**(map_y+17)-65536,0,0xFFFF0000))

            addMouseCoord << RawTrigger(actions=SetMemory(RC + 4, SetTo, 0))
        elif ret[0] == "screen":
            addScreenCoord, addScreenRecover = Forward(), Forward()
            PrevCp << f_getcurpl()

            RawTrigger(
                actions=[SetDeaths(EPD(addScreenCoord) + 87,SetTo,2**(map_y+16)+2**(map_x),0),
                SetMemory(0x58DC60 + 0x14*(screenloc-1),SetTo,2**(map_x)),
                SetMemory(0x58DC68 + 0x14*(screenloc-1),SetTo,2**(map_x)),
                SetMemory(0x58DC64 + 0x14*(screenloc-1),SetTo,2**(map_y)),
                SetMemory(0x58DC6C + 0x14*(screenloc-1),SetTo,2**(map_y)),
                SetDeaths(EPD(addScreenRecover)+87,SetTo,2**(map_x),0),
                SetDeaths(EPD(addScreenRecover)+95,SetTo,2**(map_x),0),
                SetDeaths(EPD(addScreenRecover)+103,SetTo,2**(map_y),0),
                SetDeaths(EPD(addScreenRecover)+111,SetTo,2**(map_y),0),
                ])
            for p in humans:
                RawTrigger(conditions=[Memory(0x512684,Exactly,p)],
                actions=[SetMemory(0x6509B0,SetTo,p),CenterView(screenloc)])
                
            ScreenX << f_mapXread_epd(EPD(0x62848C))
            _ScreenY, ScreenY = f_mapYread_epd(EPD(0x6284A8))
            VProc(
                [sX, _csY, ScreenX, ScreenY],
                [
                    sX.QueueAddTo(EPD(addScreenRecover) + 87),
                    _csY.QueueAddTo(EPD(addScreenRecover) + 103),
                    ScreenX.QueueSubtractTo(EPD(addScreenRecover) + 87),
                    ScreenY.QueueSubtractTo(EPD(addScreenRecover) + 103),
                ],
            )
            VProc(
                [sX, _csY, ScreenX, ScreenY],
                [
                    sX.QueueAddTo(EPD(addScreenRecover) + 95),
                    _csY.QueueAddTo(EPD(addScreenRecover) + 111),
                    ScreenX.QueueSubtractTo(EPD(addScreenRecover) + 95),
                    ScreenY.QueueSubtractTo(EPD(addScreenRecover) + 111),
                ],
            )
            addScreenRecover << RawTrigger(
                actions=[
                SetMemory(0x58DC60 + 0x14*(screenloc-1),SetTo,0),
                SetMemory(0x58DC68 + 0x14*(screenloc-1),SetTo,0),
                SetMemory(0x58DC64 + 0x14*(screenloc-1),SetTo,0),
                SetMemory(0x58DC6C + 0x14*(screenloc-1),SetTo,0),
                ])
            for p in humans:
                RawTrigger(conditions=[Memory(0x512684,Exactly,p)],
                actions=[SetMemory(0x6509B0,SetTo,p),CenterView(screenloc)])

            VProc(
                [sX, sY, ScreenX, _ScreenY],
                [
                    sX.QueueAddTo(EPD(addScreenCoord) + 87),
                    sY.QueueAddTo(EPD(addScreenCoord) + 87),
                    ScreenX.QueueSubtractTo(EPD(addScreenCoord) + 87),
                    _ScreenY.QueueSubtractTo(EPD(addScreenCoord) + 87),
                    MyQCalphaids[n + qc_count] << SetMemory(SEL + 4, SetTo, 0),
                    QGCActivated.SetNumber(1),
                ],
            )

            addScreenCoord << RawTrigger(actions=[SetMemory(RC + 4, SetTo, 0)])
            f_setcurpl(PrevCp)
        elif ret[0] == "val":
            DoActions(SetMemory(RC + 4, SetTo, 64 * 65537 + 1))

            def parseSource(src, always=False):
                if isinstance(src, int):
                    return src
                try:
                    src = int(src, 0)
                except ValueError:
                    _ns = GetEUDNamespace()
                    src = eval(parseCond(src))
                    if isinstance(src, EUDLightVariable) or always:
                        src = EPD(src.getValueAddr())
                else:
                    src = EPD(src)
                return src

            src = parseSource(ret[1], always=True)
            src = f_v2posread_epd(src)
            VProc(
                src,
                [
                    src.QueueAddTo(EPD(RC) + 1),
                    MyQCalphaids[n + qc_count] << SetMemory(SEL + 4, SetTo, 0),
                    QGCActivated.SetNumber(1),
                ],
            )
        elif ret[0] == "low":
            DoActions(SetMemory(RC + 4, SetTo, 64 * 65537 + 1))

            def parseSource(src, always=False):
                if isinstance(src, int):
                    return src
                try:
                    src = int(src, 0)
                except ValueError:
                    _ns = GetEUDNamespace()
                    src = eval(parseCond(src))
                    if isinstance(src, EUDLightVariable) or always:
                        src = EPD(src.getValueAddr())
                else:
                    src = EPD(src)
                return src
            src = parseSource(ret[1], always=True)
            src = f_low2posread_epd(src)
            VProc(
                src,
                [
                    src.QueueAddTo(EPD(RC) + 1),
                    MyQCalphaids[n + qc_count] << SetMemory(SEL + 4, SetTo, 0),
                    QGCActivated.SetNumber(1),
                ],
            )
        elif ret[0] == "high":
            DoActions(SetMemory(RC + 4, SetTo, 64 * 65537 + 1))

            def parseSource(src, always=False):
                if isinstance(src, int):
                    return src
                try:
                    src = int(src, 0)
                except ValueError:
                    _ns = GetEUDNamespace()
                    src = eval(parseCond(src))
                    if isinstance(src, EUDLightVariable) or always:
                        src = EPD(src.getValueAddr())
                else:
                    src = EPD(src)
                return src

            src = parseSource(ret[1], always=True)
            src = f_high2posread_epd(src)
            VProc(
                src,
                [
                    src.QueueAddTo(EPD(RC) + 1),
                    MyQCalphaids[n + qc_count] << SetMemory(SEL + 4, SetTo, 0),
                    QGCActivated.SetNumber(1),
                ],
            )
        elif ret[0] == "xy":
            DoActions(SetMemory(RC + 4, SetTo, 0))

            def parseSource(src, always=False):
                if isinstance(src, int):
                    return src
                try:
                    src = int(src, 0)
                except ValueError:
                    _ns = GetEUDNamespace()
                    src = eval(parseCond(src))
                    if isinstance(src, EUDLightVariable) or always:
                        src = EPD(src.getValueAddr())
                else:
                    src = EPD(src)
                return src

            if len(ret) == 3:
                src = parseSource(ret[1])
                if type(src) not in (EUDVariable, EUDXVariable):
                    src = f_maskread_epd(src, mapMask)
            elif len(ret) == 5:
                x = parseSource(ret[1])
                y = parseSource(ret[2], always=True)
                if type(x) not in (EUDVariable, EUDXVariable):
                    x = f_mapXread_epd(x)
                if type(y) not in (EUDVariable, EUDXVariable):
                    y = f_mapYread_epd(y)[0]
                src = x + y
            VProc(
                src,
                [
                    src.QueueAddTo(EPD(RC) + 1),
                    MyQCalphaids[n + qc_count] << SetMemory(SEL + 4, SetTo, 0),
                    QGCActivated.SetNumber(1),
                ],
            )
        else:
            raise EPError("{} is Unknown type for return value".format(ret[0]))
        # TODO: Optimize QueueGameCommand and f_memcpy
        QueueGameCommand(SEL + 2, 4)
        QueueGameCommand(RC + 3, 10)  # RightClick
        EUDEndIf()


@EUDFunc
def ReceiveQC():
    global Check, ASM
    vi = EUDVariable()
    DoActions([cp.SetNumber(min(humans)), vi.SetNumber(min(humans) * 18), ASM.SetNumber(min(humans) * 604)])

    EUDHumanLoop()()
    arrayPtr = ArrayPTRs[cp]
    arrayEPD = ArrayEPDs[cp]
    vr.seek(arrayPtr, arrayEPD, qc_epd)
    DoActions([SetDeaths(CurrentPlayer, SetTo, 0, u) for u in deathsUnits])

    def parseArray(s):
        _ns = GetEUDNamespace()
        for k, v in _ns.items():
            if (
                isUnproxyInstance(v, EUDArray) or isUnproxyInstance(v, EUDVArray(8))
            ) and k in s:
                s = re.sub(r"\b{}\b".format(k), "_ns['\g<0>']", s)
        return s

    init_array = []
    _ns = GetEUDNamespace()
    for ret in qc_rets:
        if ret[0] == "array":
            array = eval(parseArray(ret[1]))
            if isUnproxyInstance(array, EUDArray):
                init_array.append(SetMemoryEPD(EPD(array) + cp, SetTo, 0))
            elif isUnproxyInstance(array, EUDVArray(8)):
                init_array.append(
                    SetMemoryEPD((EPD(array) + 328 // 4 + 5) + vi, SetTo, 0)
                )
            else:
                raise EPError("{} unknown type for return value".format(ret[1]))
    if init_array:
        DoActions(init_array)

    qr_list = eqsplit(qc_rets, len(bit_xy))
    for n, rets in enumerate(qr_list):
        vr.read()
        waypoint = qc_epd + 0x10 // 4
        EUDIf()(MemoryEPD(waypoint, AtLeast, 64 * 65537 + 1))
        f_dwsubtract_epd(waypoint, 64 * 65537)
        for ret, bit in zip(rets, bit_xy):
            EUDIf()(MemoryXEPD(waypoint, AtLeast, 1, bit))
            if ret[0] == "deaths":
                DoActions(SetDeaths(CurrentPlayer, Add, ret[2], ret[1]))
            elif ret[0] == "array":
                array = eval(parseArray(ret[1]))
                if isUnproxyInstance(array, EUDArray):
                    f_dwadd_epd(EPD(array) + cp, ret[2])
                elif isUnproxyInstance(array, EUDVArray(8)):
                    f_dwadd_epd((EPD(array) + 328 // 4 + 5) + vi, ret[2])
                else:
                    raise EPError("{} unknown type for return value".format(ret[1]))
            EUDEndIf()
        f_dwwrite_epd(waypoint, 64 * 65537)
        EUDEndIf()
    vinit_array = []
    for rets in xy_rets:
        for ret in rets:
            if ret == "xy" or ret == "mouse" or ret == "screen" or ret == "val" or ret == "low" or ret == "high":
                continue
            if type(ret) == str:
                try:
                    array = eval(parseArray(ret))
                except (NameError):
                    continue
                if isUnproxyInstance(array, EUDArray):
                    vinit_array.append(SetMemoryEPD(EPD(array) + cp, SetTo, -1))
                elif isUnproxyInstance(array, EUDVArray(8)):
                    vinit_array.append(
                        SetMemoryEPD((EPD(array) + 328 // 4 + 5) + vi, SetTo, -1)
                    )
                else:
                    raise EPError("{} unknown type for return value".format(ret))
    if vinit_array:
        DoActions(vinit_array)

    for n, ret in enumerate(xy_rets):
        vr.read()
        waypoint = qc_epd + 0x10 // 4
        if ret[0] == "low":
            RawTrigger(actions=Check.SetNumber(0))
        
        if ret[0] == "mouse":
            EUDIf()(MemoryEPD(waypoint, AtLeast, 1))
            f_dwsubtract_epd(waypoint, 0)
            x, y = f_posread_epd(waypoint)
            f_setloc(ret[1] + cp, x, y)
        elif ret[0] == "screen":
            EUDIf()(MemoryEPD(waypoint, AtLeast, 1))
            f_dwsubtract_epd(waypoint, 0)
            x, y = f_posread_epd(waypoint)
            f_setloc(ret[1] + cp, x, y)
        elif ret[0] == "val":
            EUDIf()(MemoryEPD(waypoint, AtLeast, 64 * 65537 + 1))
            f_dwsubtract_epd(waypoint, 64 * 65537 + 1)
            xy = f_pos2vread_epd(waypoint)
            if isinstance(ret[2], int):
                DoActions(SetDeaths(CurrentPlayer, SetTo, xy, ret[2]))
            elif isinstance(ret[2], float):
                f_dwwrite_epd(eval(parseV("NSQCASM"))+ASM+floor(ret[2])*604*8, xy)
            else:
                array = eval(parseArray(ret[2]))
                if isUnproxyInstance(array, EUDArray):
                    f_dwwrite_epd(EPD(array) + cp, xy)
                elif isUnproxyInstance(array, EUDVArray(8)):
                    f_dwwrite_epd((EPD(array) + 328 // 4 + 5) + vi, xy)
                else:
                    raise EPError("{} unknown type for return value".format(ret[2]))
        elif ret[0] == "low":
            EUDIf()(MemoryEPD(waypoint, AtLeast, 64 * 65537 + 1))
            RawTrigger(actions=Check.AddNumber(1))
            f_dwsubtract_epd(waypoint, 64 * 65537 + 1)
            xy = f_pos2lowread_epd(waypoint)
            if isinstance(ret[2], int):
                DoActions(SetDeathsX(CurrentPlayer, SetTo, xy, ret[2], 0xFFFF))
            elif isinstance(ret[2], float):
                DoActions(SetDeathsX(eval(parseV("NSQCASM"))+ASM+floor(ret[2])*604*8,SetTo,xy,0,0xFFFF))
            else:
                array = eval(parseArray(ret[2]))
                if isUnproxyInstance(array, EUDArray):
                    DoActions(SetDeathsX(EPD(array)+cp,SetTo,xy,0,0xFFFF))
                elif isUnproxyInstance(array, EUDVArray(8)):
                    DoActions(SetDeathsX((EPD(array)+ 328 // 4 + 5) + vi,SetTo,xy,0,0xFFFF))
                else:
                    raise EPError("{} unknown type for return value".format(ret[2]))
        elif ret[0] == "high":
            EUDIf()(MemoryEPD(waypoint, AtLeast, 64 * 65537 + 1))
            RawTrigger(actions=Check.AddNumber(2))
            f_dwsubtract_epd(waypoint, 64 * 65537 + 1)
            xy = f_pos2highread_epd(waypoint)
            if isinstance(ret[2], int):
                DoActions(SetDeathsX(CurrentPlayer, SetTo, xy, ret[2], 0xFFFF0000))
            elif isinstance(ret[2], float):
                DoActions(SetDeathsX(eval(parseV("NSQCASM"))+ASM+floor(ret[2])*604*8,SetTo,xy,0,0xFFFF0000))
            else:
                array = eval(parseArray(ret[2]))
                if isUnproxyInstance(array, EUDArray):
                    DoActions(SetDeathsX(EPD(array)+cp,SetTo,xy,0,0xFFFF0000))
                elif isUnproxyInstance(array, EUDVArray(8)):
                    DoActions(SetDeathsX((EPD(array)+ 328 // 4 + 5) + vi,SetTo,xy,0,0xFFFF0000))
                else:
                    raise EPError("{} unknown type for return value".format(ret[2]))
        elif ret[0] == "xy":
            EUDIf()(MemoryEPD(waypoint, AtLeast, 1))
            f_dwsubtract_epd(waypoint, 0)
            if len(ret) == 3:
                xy = f_maskread_epd(waypoint, mapMask)
                if isinstance(ret[2], int):
                    DoActions(SetDeaths(CurrentPlayer, SetTo, xy, ret[2]))
                elif isinstance(ret[2], float):
                    f_dwwrite_epd(eval(parseV("NSQCASM"))+ASM+floor(ret[2])*604*8, xy)
                else:
                    array = eval(parseArray(ret[2]))
                    if isUnproxyInstance(array, EUDArray):
                        f_dwwrite_epd(EPD(array) + cp, xy)
                    elif isUnproxyInstance(array, EUDVArray(8)):
                        f_dwwrite_epd((EPD(array) + 328 // 4 + 5) + vi, xy)
                    else:
                        raise EPError("{} unknown type for return value".format(ret[2]))
            elif len(ret) == 5:
                x, y = f_posread_epd(waypoint)
                if isinstance(ret[3], int) or isinstance(ret[4], int):
                    DoActions(
                        [
                            SetDeaths(CurrentPlayer, SetTo, x, ret[3])
                            if isinstance(ret[3], int)
                            else []
                        ]
                        + [
                            SetDeaths(CurrentPlayer, SetTo, y, ret[4])
                            if isinstance(ret[4], int)
                            else []
                        ]
                    )
                if isinstance(ret[3], float) and isinstance(ret[4], float):
                    f_dwwrite_epd(eval(parseV("NSQCASM"))+ASM+floor(ret[3])*604*8, x)
                    f_dwwrite_epd(eval(parseV("NSQCASM"))+ASM+floor(ret[4])*604*8, y)
                for s, v in zip([ret[3], ret[4]], [x, y]):
                    if type(s) != str:
                        continue
                    array = eval(parseArray(s))
                    if isUnproxyInstance(array, EUDArray):
                        f_dwwrite_epd(EPD(array) + cp, v)
                    elif isUnproxyInstance(array, EUDVArray(8)):
                        f_dwwrite_epd((EPD(array) + 328 // 4 + 5) + vi, v)
                    else:
                        raise EPError("%s unknown type for return value" % ret[2])
        else:
            EUDIf()(MemoryEPD(waypoint, AtLeast, 64 * 65537 + 1))
            raise EPError("%s is Unknown type for return value" % ret[0])
        f_dwwrite_epd(waypoint, 0)
        EUDEndIf()

        if ret[0] == "high":
            if EUDIf()([Check<=2]):
                if isinstance(ret[2], int):
                    DoActions(SetDeaths(CurrentPlayer, SetTo, ret[3], ret[2]))
                elif isinstance(ret[2], float):
                    DoActions(SetDeaths(eval(parseV("NSQCASM"))+ASM+floor(ret[2])*604*8,SetTo,ret[3],0))
                else:
                    array = eval(parseArray(ret[2]))
                    if isUnproxyInstance(array, EUDArray):
                        DoActions(SetDeaths(EPD(array)+cp,SetTo,ret[3],0))
                    elif isUnproxyInstance(array, EUDVArray(8)):
                        DoActions(SetDeaths((EPD(array)+ 328 // 4 + 5) + vi,SetTo,ret[3],0))
                    else:
                        raise EPError("{} unknown type for return value".format(ret[2]))
            EUDEndIf()


    EUDSetContinuePoint()
    DoActions([cp.AddNumber(1), vi.AddNumber(18), ASM.AddNumber(604)])
    EUDEndHumanLoop()

    KeyUpdate()
    MouseUpdate()


def beforeTriggerExec():
    origcp = f_getcurpl()

    if QCDebug:
        end = Forward()
        DebugQC()
        EUDJumpIf(QCShutdown.AtLeast(1), end)
    SendQC()
    ReceiveQC()
    if QCDebug:
        end << RawTrigger(
            conditions=QCShutdown.AtLeast(1), actions=QCShutdown.SubtractNumber(1)
        )
        
    f_setcurpl(origcp)


def RestoreSelUnits():
    global SelCount, SelMem, QGCActivated
    if EUDIf()([SelCount >= 1, QGCActivated >= 1]):
        NSEL = Db(b"...\x091234567890123456789012345.......")
        n = EUDVariable()
        DoActions([vr.seek(SelMem, EPD(SelMem), qc_epd), n.SetNumber(2)])
        bw = EUDByteWriter()
        bw.seekepd(EPD(NSEL) + 1)
        bw.writebyte(SelCount)
        if EUDWhile()(SelCount >= 1):
            vr.read([SelCount.SubtractNumber(1), n.AddNumber(2)])
            tos = f_tosread_epd(qc_epd + 0xA5 // 4)
            unitIndex = f_epd2alphaid(qc_epd)
            targetID = unitIndex + tos
            b1 = f_b1read_epd(EPD(targetID.getValueAddr()))
            DoActions(targetID.SetNumberX(0, 0xFFFFFF00))
            bw.writebyte(targetID)
            bw.writebyte(b1)
        EUDEndWhile()
        bw.flushdword()
        QueueGameCommand(NSEL + 3, n)
    EUDEndIf()


def afterTriggerExec():
    RestoreSelUnits()
