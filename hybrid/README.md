# 어셈블러 하이브리드로 쓰기 — 준비물과 주의사항

**어셈블러 하이브리드**는 CtrigAsm(TEP Lua)으로 만든 트리거를 STRCtrig 어셈블러로 그대로 싣고,
같은 맵에 eudext(eudplib 0.81) 코드를 얹는 방식이다. 기존 맵을 한 번에 옮기지 않고 시스템 단위로 옮길 때 쓴다.

```
맵 + Lua ─TEP(또는 tepc)─▶ 컴파일된 맵 ─STRCtrigAssembler.exe─▶ Ctemp\TRIGP*.chk
                                  │                                  │
                                  └───────▶ euddraft 0.11 ◀──────────┘
                                           (eudext 부트 + STRCtrig 0.81 사본 + 새 코드)
```

## 1. 지금 확인된 범위 (2026-09-18)

| 항목 | 상태 |
|---|---|
| TEP 트리거 + euddraft 0.11 한 맵 빌드, STRCtrig 재배치 | **인게임 통과** — MSF 시리즈 3개 맵(UE_RE·Memory 1·Memory 2) 기능 정상, 시작 직후 멈춤 없음. CPLP 를 넣은 판도 정상 |
| 하이브리드 맵 위의 eudext 코드 | **확인용 한 줄만** — `players.display` 로 글 한 줄 띄우기. 다른 모듈은 하이브리드에서 돌려 보지 않았다 |
| eudext 모듈 자체 | 에뮬레이터 약 124만 판정 통과 + 순수 eudplib 통합 점검 맵 인게임 통과 |
| 적층 포크(`STRCtrig Assembler v5.5 Stack`) | **0.81 에서 돌려 본 적 없음** — 사본도 두지 않았다 |
| freeze 를 켠 하이브리드 | 확인 안 함 |

## 2. 준비물

| 준비물 | 어디서 |
|---|---|
| euddraft 0.11.0.1 | GitHub `armoha/euddraft` 릴리스 `v0.11.0.1` (Windows·Linux·macOS 판) |
| TEP(또는 tepc) + `STRCtrigAssembler.exe` | 원래 쓰던 것 그대로. 이 저장소에는 없다 |
| eudext 부트 | `eudext/boot.py` (설정 키는 그 파일 머리 주석) |
| 0.81 플러그인 사본 | `hybrid/plugins/` — STRCtrig v5.5·CPLP·NSQC. 다시 만들기: `python hybrid/make_plugins.py --orig <euddraft 0.9.10.11 의 plugins 폴더>` (`--check` 는 비교만) |
| eds 틀 | `hybrid/example.eds` |
| lupa (lupa 를 쓰는 모듈을 쓸 때만) | euddraft 번들 파이썬이 3.14 라 그 판의 lupa 2.8 을 따로 푼다(최상위 README "준비"). 푼 폴더를 부트의 `VenvSite` 로 준다 |

## 3. 주의사항

**플러그인**

1. **원본 0.9 플러그인을 그대로 쓰지 않는다.** STRCtrig v5.5·CPLP 는 `from eudx import *` 에서 불러오기부터 실패한다.
   NSQC 는 빌드는 되지만 키 0x40 이상(O·P·F12 …)을 쓰면 배열 밖을 덮어 디싱크가 난다. → `hybrid/plugins/` 사본을 쓴다.
2. NSQC 사본도 **배열 출력·이름 원본·키 엣지** 기능은 고치지 않았다. 0.81 에서 수신 코드가 TypeError 로 멈추거나 배열 밖에 쓴다 — 쓰지 않는다.
3. 다른 0.9 플러그인도 0.81 에서 뜻이 바뀔 수 있다. **`EUDArray` 값이 0.76 은 주소, 0.81 은 EPD** 라서 `배열 + 숫자` 로 주소를 만드는
   플러그인은 오류 없이 배열 밖에 쓴다. 빌드 로그의 `EPD on EPD value` 경고가 그 자리다.
4. STRCtrig 플러그인은 불러올 때 `PRT_SetInliningRate(0)` 으로 인라이닝을 끈다. **다시 켜지 않는다** — CtrigAsm 트리거는 자기 위치를 기준으로
   자기를 고치므로 eudplib 이 옮기면 깨진다.

**eds**

5. 순서: eudext 부트 → STRCtrig 사본 → 나머지 플러그인(NSQC 는 STRCtrig 아래) → eudext 코드(eps). 부트가 뒤에 있으면 `import eudext.…` 가 안 된다.
6. eds 줄 끝에 주석을 달지 않는다(euddraft 가 `; …` 까지 값으로 읽는다). 주석 줄은 `::` 로 시작한다.
7. `[freeze]` 섹션이 없으면 0.11 은 freeze 를 켠다. 키가 있으면 값과 상관없이 끈다. 확인된 하이브리드는 모두 끈 판이다.

**게임 동작**

8. **오류 줄(13번째 줄)에 긴 글을 쓰지 않는다.** 한도를 넘는 글을 쓰면 게임이 EUD ERROR(`0xFF9BE98B`,
   "이 EUD 지도는 지원되지 않습니다")로 멈춘다(제작자 경험). eudext 시험에서도 `display.show_line13` 으로 93바이트를 쓴 직후 멈춘 기록이 있다.
   그 쓰기는 줄 버퍼(218바이트) 안이었으므로 **실제 한도는 버퍼보다 작다.** 정확한 값은 아직 재지 않았다
   (좁히기 맵 `25b_display_bisect` 가 4·16·32·93·212·216바이트를 차례로 쓴다). `show_line13` 의 빌드 검사(`LINE13_MAX` = 217)는
   버퍼 기준이라 이 한도를 막아 주지 않는다. 한도가 정해질 때까지 오류 줄에는 짧은 글만 쓴다.
9. **자원이 겹치는지는 직접 확인한다.** TEP 쪽이 쓰는 데스값·빈 메모리 주소·스위치·로케이션과 eudext 코드가 같은 칸을 쓰면 서로 덮는다.
   eudext 변수·배열은 페이로드 안에 따로 잡히므로 겹치지 않지만, 고정 주소(데스 표, `0x58F4xx` 같은 빈 메모리, dat)를 쓰는 기능은 겹칠 수 있다.
   eudext 가 빌드 때 스스로 검사하는 것은 SCR_DB 칸(MSQC 채널 7)뿐이다.
10. **같은 dat 칸을 양쪽에서 바꾸지 않는다.** `datpatch`·`bullet` 이 바꾸는 칸을 TEP 쪽(`SetMemory` 로 dat 를 고치는 코드)도 바꾸면
    어느 쪽이 나중에 도느냐에 따라 값이 갈린다. 한쪽에서만 바꾼다.
11. **유닛 충돌 상자를 줄이면 로케이션 트리거가 깨진다.** 로케이션 판정은 유닛의 충돌 상자로 하므로, `datpatch.all_unit_size` 로 충돌 상자를
    줄이면 작은 로케이션으로 유닛을 잡는 TEP 트리거(Bring·RemoveUnitAt·KillUnitAt·MoveUnit)가 실패한다(인게임 확인).

**빌드**

12. tepc 결과는 판마다 100% 같지 않았다(이식판 세 맵에서 같은 트리거 안의 액션 **차례** 등만 달랐고 내용은 같았다).
    판정은 트리거 수·chk 크기로 하고, 똑같은 산출물이 필요하면 Ctemp 를 스냅숏으로 두고 그걸로 빌드한다.

## 4. 파일

| 파일 | 내용 |
|---|---|
| `example.eds` | 하이브리드 eds 틀 |
| `make_plugins.py` | euddraft 0.9.10.11 원본 플러그인(`--orig`) → `plugins/` 사본. 원본 md5(줄 끝 LF 기준)가 다르면 멈춘다 |
| `plugins/STRCtrig_v55_eud081.py` | STRCtrig Assembler v5.5 — `from eudx import *` 한 줄만 주석 |
| `plugins/CPLP_eud081.py` | CPLP — 같은 한 줄 |
| `plugins/NSQC_eud081.py` | NSQC — 눌림 기억 칸·로케이션 임시 저장 수정(자세한 것은 `make_plugins.py` 머리 주석) |

세 사본은 인게임에서 돈 이식판(MSF_Memory_2)의 사본과 머리 주석만 다르고 내용이 같다.
