# 인게임 확인 목록

Ubuntu 에서는 스타크래프트를 돌릴 수 없으므로, 에뮬레이터(`testing/emu.py`)로 확인할 수 없는 동작을 여기에 모은다(DESIGN 6.2·6.4-7).
확인은 사용자가 Windows PC(StarCraft: Remastered)에서 한다. 결과를 알려 주면 해당 항목에 날짜와 결과를 적고, 설계·에뮬레이터를 고친다.

표기: **[필수]** = 결과가 나와야 다음 작업(또는 기능 공개)을 할 수 있다. 나머지는 확인되면 좋은 것.

## 2026-09-18 2~5차 인게임 결과 — 통합 맵 `00_auto_all` **완전 통과**

마지막 판정(14:51, 빌드 `301F7781`): **맵 항목 17/17 · 단계 19/19 · 실패 0**. 1차에서 걸린 세 가지의 원인이 모두
인게임에서 확정됐다. 값은 `C:\Program Files (x86)\StarCraft\Maps\eudext_checkesults.json`.

| 증상(1차) | 진짜 원인 | 고친 곳 |
|---|---|---|
| 도형 자리 102/211 밀림 (`D7-1 posbad 18 · nudged 82`) | **공중 유닛끼리 미는 반발** + 유닛 충돌 상자 | eds 에 `[noAirCollision]`(euddraft 0.11 번들) + `datpatch.all_unit_size(1)`(유닛 228개 충돌 상자 1,1,1,1). 2차에서 plot 통과, 판정을 전부 strict 로 되돌렸다 |
| 탄막이 **한 발도 안 만들어짐** (`D14-0 made 0/1`) | **units.dat 에디터 어빌리티 플래그**(0x661518). 문·함정 유닛(208·210·204)은 트리거 비트가 없어 `CreateUnit` 이 거절한다 | `BulletDat.star_edit = 0x1CF`(CtrigAsm v5.5 81406 줄 값). 배치 상자·충돌 상자·고도·Flyer·소속그룹·생산 가능을 바꿔 보는 좁히기 10단계가 **전부 1** 로 나와 이 칸 하나가 답임이 확정됐다 |
| 탄은 생겼는데 **안 날아감** (`D14-1 facing 8/8, dead 0/8`) | **탄 그림의 iscript** — image 360 이 문 유닛 것(244)이었다 | `BulletDat(image=360, image_iscript=395, image_draw=10)`(UE_RE `EUDEditorDat.lua` 와 같은 값) |

**함께 확인된 것 (사용자 맵에도 해당)**

- **로케이션 판정은 유닛의 충돌 상자로 한다.** 전 유닛 1,1,1,1 로 만든 뒤 점 로케이션이 커맨드 센터를 더는 잡지 못해
  `RemoveUnitAt` 이 실패했다(B10-6·8). 작은 로케이션으로 큰 유닛을 잡는 트리거(Bring·RemoveUnitAt·KillUnitAt·MoveUnit)는
  충돌 상자를 줄이면 같이 깨진다. → `datpatch.all_unit_size` 주의에 적었다.
- **`shell` 로 만든 탄은 유닛 수 표에 자국이 남는다.** 204 로 만들고 종류 칸(+0x64)만 210 으로 바꾸므로, 게임의 유닛 수
  표(`Command` 조건이 읽는 표)는 204 를 계속 센다. 탄 개수를 `Command` 로 세면 안 된다.
- 탄 사슬 `flingy 106 → sprite 344 → image 360` 은 **원판에서 아무도 쓰지 않는다**(stock dat 역추적: 106 을 쓰는 유닛·무기
  없음, 344 를 쓰는 flingy 는 147 하나뿐이고 그 147 도 쓰는 곳 없음, 360 을 쓰는 sprite 는 344 뿐). 다른 그림으로 바꿀 때는
  그 번호를 맵이 쓰는지 직접 확인해야 한다.
- 채팅 판정 D17-6 은 "무엇을 쳤는가" 대신 **"중계된 글이 있는가"** 로 바꿨다 — `éè` 를 못 치는 자판이 있고 SC:R 채팅은
  붙여넣기가 안 된다. 2바이트 UTF-8 은 맵이 스스로 찍는 D17-3 이 판정한다(줄 끝이 잘려 마지막 글자가 깨지는 것은 봐준다).

## 2026-09-18 1차 인게임 결과 (통합 맵 `00_auto_all`, 제작자 혼자 실행)

`work\ingame_auto_maps\results.json`·`results.log`(05:12~05:14, 초당 사이클 22.86 = 터보 켜짐). 단계 12개 통과,
3개 실패, display 에서 **게임이 EUD ERROR 로 멈춰** 뒤 3개(chat·final·assist)는 미실행.

| 결과 | 단계 | 비고 |
|---|---|---|
| 통과 12 | pool · switch · s8(**A-1**) · datpatch · i64 · i64_ops · i128 · numfmt · cmp_cell · mathx · players · spawn | + 맵 전체 **G-5**(터보), `clean.*` 정리 5개 |
| 값 확인 | units | B10-1·2·6·7·8·10·B15-3 통과. B10-3·4 는 빈 칸 목록이 **번호가 줄어드는 쪽**(기대식 부호), B10-5 F1 은 맵 리빌러가 순회에 안 나옴 |
| 실패(게임 동작) | plot | 순서·값은 맞고 **자리 102/211** 이 밀렸다 — 몸집 큰 공중 유닛 + 공중 충돌 켜짐 |
| 실패(라이브러리) | bullet | 탄이 **하나도 안 만들어졌다** — 탄막 유닛(208·210·204)이 Building 플래그라 `CreateUnit` 이 배치 상자로 거절. `BulletDat` 에 `bounds`·`placement` + Building 끄기를 넣어 고쳤다 |
| 멈춤 | display | E6-8(자체 점검 7/7, **13번째 줄·TBL 바이트 일치**) 통과 → 한 프레임 뒤 E6-3(13번째 줄 93바이트)에서 EUD ERROR `0xFF9BE98B`. 통합 맵에서 E6-3·4·4b 를 뺐고 **`25b_display_bisect`(18단계)** 로 좁힌다 |
| 미실행 | chat · final · assist · visual | display 멈춤 뒤 |

**EUD ERROR 자리 검산**(2026-09-18): `show_line13` 은 틀 길이 ≤ 217(`LINE13_MAX`)을 빌드 때 검사하고, 0x641598 부터
`(길이 + 1)` 을 4로 올림한 만큼을 dword 로 쓴다. 길이 92~93 이면 96바이트(+0..95) — **줄 버퍼 218 안**이다. 줄 밖을 창에
넣는 경우는 길이 ≥ 213 일 때뿐인데(마지막 마스크 dword 가 +216 → 0x641672~3 = 13번째 줄 밖 2바이트, 값은 마스크로
보존), 멈춘 호출은 93바이트여서 **해당 없다**. 이름 주소(0x57EEEB)·TBL 주소도 이 호출에는 없다. 그래서 길이·경계가
아니라 "쓰는 방식(상수 주소 `SetMemory` 대 eudplib 의 CP + `SetDeaths`)", "CreateUnit 실패 트릭", "TBL 쓰기" 중
하나로 좁혀야 한다 → 25b 맵의 단계 표(`examples/display_bisect.py` 머리말).

## 확인 순서 (2026-09-18 — 자동 판정판)

맵과 판정 도구는 **`work\ingame_auto_maps\`** 에 한 벌로 있다(`MAPS.md` 가 같은 표, `README.md` 가 사용자용 안내,
`RUN.bat` 이 판정 도구, `specs/` 가 판정 명세, `dbg/` 가 심볼 JSON — 지우면 판정이 안 된다). 다시 만들려면
`python eudext\tools\ingame_maps.py --out work\ingame_auto_maps`(맵은 그대로 두고 명세·문서만 고칠 때는 `--docs-only`).
맵을 StarCraft: Remastered 의 `Maps` 폴더에 복사하고 **`RUN.bat` 을 먼저 켜 둔 뒤** 아래 ① → ② → ③ → ④ 순서로 연다.
판정 결과는 `results.json`·`results.log` 에 쌓이므로, **사람이 눈·귀로 본 것만** 항목 번호와 함께 알려 주면 된다.

시간 안내는 모두 **터보 기준**이다. 모든 맵을 `[eudTurbo]`(euddraft 번들 플러그인 — 트리거를 매 프레임 실행)로 빌드했다:
트리거 한 사이클 = 게임 한 프레임, **24사이클 = 1초**. 2026-09-18 G-1 에서 터보 없이 빌드한 판은 한 사이클이 28~30프레임
(약 1.2초) 간격이어서 맵의 시간 안내가 30배 늦게 갔다(`work\G1_result.txt`). 판정 도구의 제한 시간·멈춤 판정도 터보
기준이고(명세 `timeout_cycles` = 프레임 창 + 여유, `timeout_s` = 그것 ÷ 24 + 여유), 초당 사이클이 8 밑이면 시간 초과
설명에 `[eudTurbo] 가 빠진 것 같습니다` 가 붙는다. 통합 맵은 첫 단계에서 터보 자체를 점검한다(**G-5**).

⏱ **터보가 보이는 속도를 바꾸는 점검** — 값은 같지만 사람이 보는 빠르기가 달라진다. 눈으로 볼 때 참고:
D16-1~9(배경음악 시계·조각 틈 — 소리는 그대로지만 곡 넘김 간격이 촘촘하다), E12-1~9(소환 간격이 빨라 패턴이 한꺼번에
보인다), B10-1~10(유닛 생성·죽음 확인이 1초 안에 지나간다), D14-1~13(총알이 훨씬 빨리 날아간다), D7-1~5(도형
스케줄·반복이 빠르다), D17-1(타자기 글자 간격), B13-1~12(동기화 펄스·재전송이 프레임마다 도니 왕복이 훨씬 빠르다 —
디싱크 판정 자체는 같다). 원래 속도로 보고 싶으면 그 맵 eds 의 `[eudTurbo]` 줄을 지우고 다시
빌드한다(그러면 자동 판정은 시간 초과로 끝난다 — 눈으로만 본다).

### ① 자동 — 통합 맵 `00_auto_all.scx` (혼자, 약 3분 30초 + 선택 1분)

혼자(싱글) 열고 기다리면 단계 19개가 차례로 돌며 **eudext 확인 항목 91개**(자동 판정 60 + 사람 조작 3 + 화면으로 보는
28)를 덮는다. `RUN.bat` 창에 `단계 … 시작/끝/통과` 가 실시간으로 뜨고, 맵 안에서도 단계마다 안내 줄과 CenterView 가
나오므로 옆에서 봐도 어디를 보는지 알 수 있다. 3분 26초(프레임 4952)에 자동 부분이 끝나고, 그 뒤 60초 동안 채팅 한 줄을
치면 assist 단계(선택)까지 판정된다. 안 치면 그 단계는 `건너뜀`(실패 아님)이고, 4분 29초부터 화면 확인 쪽이 6초마다 돈다.

| 단계 | 이름 | 프레임 창 (초) | 항목 |
|---|---|---|---|
| 1 | units | 1~56 (0~2초) | B10-1~8·10, B15-3 |
| 2 | pool | 1~60 (0~3초) | C11-1~7 |
| 3 | switch | 1~112 (0~5초) | A-2 |
| 4 | s8 | 2~3 (0초) | A-1, B15-5 |
| 5 | datpatch | 1~25 (0~1초) | B15-1, B15-10 |
| 6~11 | i64 · i64_ops · i128 · numfmt · cmp_cell · mathx | 60~212 (2~9초) | C3-1~3, D4-1, F20-1, D5-1·9, B1-1, C2-1, C9-2 |
| 12 | players | 230~232 (10초) | B8-4 (+F19-1b 기록) |
| 13 | plot | 300~853 (12~36초) | D7-1~5 |
| 14 | spawn | 900~1913 (37~80초) | A-3, E12-1~9, C11-9 |
| 15 | bullet | 1950~2748 (81~115초) | D14-1·2·4~9·13 |
| 16 | display | 2800~3258 (117~136초) | E6-5·8~10 (E6-3·4·4b 는 25·25b 맵 — 2026-09-18 EUD ERROR) |
| 17 | chat | 3400~4900 (142~204초) | D17-1~5·7~9 |
| 18 | final | 4950~4952 (206초) | B15-4, C11-1 재확인 |
| 19 | assist (선택) | 4960~6400 (207~267초) | D17-6, E6-2 — 채팅 한 줄 |
| 20 | visual (선택) | 6450~ (269초~) | 아래 ③ "화면 확인" 표 |

맵 전체로 보는 것: **G-5**(터보 — 24사이클이 게임 프레임 40 안에 지나는가), 단계마다의 정리 확인(`clean.*` — 만든 유닛·
도형·총알·화면을 되돌렸는가), `final.cp`(CP 가 제자리), 완료 표식 `aa.done`, 초당 사이클.

### ② 브리지 보조 맵 (사람이 조작하거나 통합 맵에 넣기 위험한 부분 — 판정은 자동)

`RUN.bat` 이 켜져 있으면 이 맵들도 자동으로 판정된다(사람이 조작한 값이 그대로 기록된다). 번호 순서대로 연다.

| 순서 | 맵 | 필수 항목 | 브리지가 자동 판정하는 것 | 여는 방법 |
|---|---|---|---|---|
| 01 | `01_S8_SubtractTest.scx` | **A-1** (SUBX·ADDX 두 줄) | A-1(마스크 식 비트마스크), B15-5 | 혼자. 19줄이 돈다 |
| 04 | `04_datpatch_check.scx` | **B15-1** (피해 배율 주소) | B15-1(0x515B80 덤프 32칸), B15-3·4·10 | 혼자. 1초 뒤 `[B15-1]` 두 줄, 2분 뒤 `[B15-4]` |
| 08 | `08_pool_check.scx` | **C11-1** (사슬 적재·되쓰기) | T1~T7 값 전부(결과는 C11-8 행에 적는다 — C11-1~7 은 ① 이 판정) | 혼자. 12프레임부터 2초마다 `[T1]`~`[T7]` |
| 11 | `11_bgm_check.scx` | **D16-1, D16-3** | D16-1·3·4·5·7 (문자열 칸·조각 틈·관전자·동기) ⏱ | 혼자(D16-4 는 관전자, D16-7 은 2인). 약 40초 |
| 14 | `14_scrdb_check.scx` | **D18-1~4, D18-6** | D18-2·3 (런처 응답·값) | 혼자 + **SCR_DB 런처** (D18-6 은 2인) |
| 17 | `17_exit_trap_check.scx` | **F19-4** (나가면 그 PC 만 멈춤 — **실험 기능, 위험**) | F19-4 (단계 표식까지 — 멈춘 자리가 결과) | 2인. 맵 안 경고 문구를 먼저 읽는다 |
| 18 | `18_sprite_check.scx` | **F21-1~7** (F21-7 은 CS_Photo 로 만든 `.cgrp` 필요) | F21-1~7·9 (점 수·실패 0·칸 가득) | 혼자(언리미터). 약 1분 |
| 20 | `20_players_check.scx` | — | B8-1·5·8 (관전자·사람 판정·동맹) | 2인 이상 + 관전자 1명 |
| 21 | `21_sync_check.scx` | **B13-1, B13-2** (2인 디싱크·펄스) | B13-1~6·8·9 | 2~3인 LAN(가능하면 배틀넷) |
| 22 | `22_pool_multi.scx` | — | C11-8 | 2인 이상 |
| 23 | `23_misc_obs_check.scx` | **F19-1** (관전자 2~4번 키) | F19-1·1b·3·6 | 사람 2명 + 관전자 2명 이상 |
| 25 | `25_display_check.scx` | **E6-1, E6-3~5, E6-7, E6-8** | E6-1·3·4·4b·8 + `m25.stage`(멈춘 쪽) | P1 혼자(E6-1 은 관전자 PC 하나 더). **튕길 위험** — 13번째 줄·TBL 쪽에서 멈출 수 있다 |
| 25b | `25b_display_bisect.scx` | **E6-3·4·4b 의 EUD ERROR 범인** | 18단계(`bx.stage`·`bx.ok` + 단계별 suite) | 혼자, 약 20초. **멈추면 그 상태로 `RUN.bat --once`** — 단계 표는 `examples/display_bisect.py` 머리말 |

### ③ 사람 확인 (판정 없음 — 눈·귀로 본다)

**화면 확인** — ① 통합 맵 안에서 본다(단계 20, 4분 29초부터 6초마다 한 쪽). 원래 맵을 따로 열어 봐도 된다:
D5-2~8(서식·색·전각 — 원래 맵 16), D6-1~5(StrDesign 색·정렬 — 09), E6-6·E6-7(13번째 줄·0x0D 폭 — 25).
값은 자동이지만 **모양**은 눈으로 보는 것: D7-1~3(12), E12-1~7(19), D14-1·2·8·9·13(10), E6-3·4·9(25), D17-1·3·7·8(13).

아래 맵들은 ① 이 이미 같은 값을 판정한다(명세가 없어 `판정 명세가 없어 건너뜁니다` 가 뜬다). **① 에서 값이 어긋났을 때
좁히려고** 또는 화면을 크게 보려고 여는 맵이다.

| 순서 | 맵 | 보는 것 | 여는 방법 |
|---|---|---|---|
| 02 | `02_i64_check.scx` | C3-1~3 | 혼자. 약 10초마다 한 줄, `[C3-7] 점검 23 / 23` ⏱ |
| 03 | `03_units_ingame.scx` | B10-1~10 (한도 부분은 ④) | 혼자. `[T1]`~`[T11]` 줄 ⏱ |
| 05 | `05_cmp_check.scx` | B1-1 (`점검 15 / 15`) | 혼자 |
| 06 | `06_cell_check.scx` | C2-1 (`점검 18 / 18`) | 혼자 |
| 07 | `07_mathx_check.scx` | C9-2 (`전체 일치 110 / 110`) — **C9-1** 은 맵이 아니라 `examples/mathx_tep_check.py` 로 Windows TEP 표 대조 | 혼자 |
| 09 | `09_strdesign_check.scx` | D6-1~5 (색·정렬) | 혼자. 6초마다 한 쪽씩 5쪽 |
| 10 | `10_bullet_check.scx` | D14-1~8 (탄이 간 쪽) | 혼자(P2 컴퓨터 표적). 약 1분 ⏱ |
| 12 | `12_plot_check.scx` | D7-1~5 (도형 모양·방향) — D7-6 은 맵이 아니라 SCMDraft 2 + TEP 3.0 | 혼자. 마지막 `[D7-5] 점검 15 / 15` ⏱ |
| 13 | `13_chat_check.scx` | D17-1~9 (타자기·채팅 줄) | 혼자. 18초 뒤 채팅으로 `!H안녕 éè 가나다` ⏱ |
| 15 | `15_i64_ops_check.scx` | D4-1 (`점검 56 / 56`) | 혼자 ⏱ |
| 16 | `16_numfmt_check.scx` | D5-1~10 (서식·색·전각·이름 표) | 혼자. 약 10초마다 `[D5-1]`~`[D5-9]` ⏱ |
| 19 | `19_spawn_check.scx` | E12-1~9 (+A-3 의 17·18·19) | 혼자(적 P2). 마지막 `점검 11 / 11` ⏱ |
| 24 | `24_i128_check.scx` | F20-1 (`점검 46 / 46`) | 혼자 ⏱ |
| 26 | `26_switch_check.scx` | A-2 (스위치 표 `0x58DC40` — 기대 `2147483653`·`129`, 조건 줄 둘) | 혼자 |

### ④ 튕길 위험 — 마지막에, 버려도 되는 방에서

| 순서 | 맵 | 항목 | 여는 방법 |
|---|---|---|---|
| 27 | `27_X_limit.scx` | **B10-1(b)**, **B10-8**(유닛 칸 한도), B10-9, D14-3, D14-2(출발=목표 한 발) | 혼자. 유닛 칸을 가득 채운다 — **멈추거나 튕길 수 있다**. 약 10초. 멈추면 강제 종료해도 된다(브리지가 어디까지 갔는지 남기는 것이 결과다) |

`17_exit_trap_check.scx`(F19-4)도 실험 기능이라 스타를 멈추게 만든다 — ② 에 있지만 여유 있을 때 마지막에 본다.
위험한 동작 자체는 손대지 않았다(단계 표식만 더했다).

- 맵 없이 사용자 결정만 필요한 것은 `eudext/DESIGN.md` 7절(D3, D13~D97 중 "구현:" 권장안으로 넣은 것들)에 있다.
- 게임이 필요 없는 항목: C9-1(TEP 표 대조), D7-6(SCMDraft), D18-9, B15-2·9.


## 배치 A (명세·WP0)

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| A-1 | **[필수]** SC 마스크 `Subtract`·`Add` 의 정확한 식 | `docs/spec/S8_ingame/build.bat` 로 `S8_SubtractTest.scx` 를 빌드해 혼자 연다. 화면에 도는 19줄 중 **`SUBX …` 줄과 `ADDX …` 줄 두 줄**을 알려 준다(답인 모형이 없으면 `S1~S5`, `X1~X3` 줄의 `got` 값). 자세한 것은 `docs/spec/S8_subtract.md` 8절 | 에뮬레이터 마스크 식 확정, 필드 포화 뺄셈 `field.isub_sat` 공개(DESIGN 3.5-8) | **2026-09-18 인게임: 통과** (s8 단계 — SUBX·ADDX 두 줄) |
| A-2 | 스위치 표 주소 `0x58DC40`(256비트, MRGN 표 바로 앞) | 스위치 몇 개를 켠 맵에서 `0x58DC40` 의 dword 를 읽어 표시 | `testing/scmodel.py` 의 `SWITCH_TABLE`, misc | **2026-09-18 인게임: 통과** (switch 단계) |
| A-3 | G_CB 로케이션 오프바이원 3곳 | `docs/spec/S1_gcb.md` 10.2절 17·18·19번(Order 로케이션 문자열이 한 칸 앞, `f_TempRepeat` 문자열 중심이 한 칸 앞, theSeed 스킬유닛 `PlotLoc = 102` 가 0-based) | spawn(WP12) | **2026-09-18 인게임: 통과** (spawn 단계) |

## 배치 B (WP1 cmp, WP8 players, WP10 units, WP13 local/sync, WP15 datpatch)

빌드 명령의 Windows 판: `C:\Users\whatd\.venvs\eud081\Scripts\python.exe eudext\tools\build.py euddraft <eds> --work %TEMP%\eudext_work\<이름>`
(euddraft 는 `C:\euddraft0.11.0.1` 을 자동으로 찾는다. 다른 곳이면 `EUDEXT_EUDDRAFT`).

### WP1 `cmp`

필수 항목은 없다(비교 결과는 에뮬레이터 경계값 차등 36,825 판정으로 확인). 아래는 에뮬레이터가 가정한 SC:R 동작을 한 번 보는 권장 항목이다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| B1-1 | 조건 칸을 실행 중에 채우는 비교가 SC:R 에서 맞는지 — ① 조건 비트마스크 칸(+0)에 값을 채워 그 칸을 읽는 조건(EUDX 표식 없음, eudplib 0.81 `a < b` 와 같은 방식) ② amount 칸(+8)을 채우는 조건 ③ 16·8비트 부호 확장 읽기 | `examples/cmp_example.eds` 를 빌드(`--work …\cmp` → `cmp_example_out.scx`)해 싱글로 연다. 시작 약 1초(24프레임) 뒤 `[eudext.cmp] 점검 15 / 15 (15 이면 정상)` 이 떠야 한다. 15 가 아니면 그 숫자를 알려 준다(`selftest` 순서로 좁힌다) | 없음(확인만) | **2026-09-18 인게임: 통과** (cmp_cell 단계) |

### WP8 `players`

시험 맵: `examples/players_example.eds` 를 빌드하거나 맵 코드에 아래 호출을 넣는다. **2인 이상 + 관전자 1명 이상**(리플레이 말고 실제 관전 슬롯)이 필요하다. 에뮬레이터는 아래 사실을 가정으로 두고 시험했다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| B8-1 | 관전자 PC 의 `0x512684`(`f_getuserplayerid()`)가 128~131(관전 슬롯 순서)이고 플레이어 PC 는 0~7 인지. `contains_user` 의 구간·마스크 조건이 이 가정에 기댄다 | 관전자 PC 에서만 `pl.display(pl.Observers, "관전자 표시")` 가 보이고, `if (pl.contains_user(pl.Observers)) { DisplayTextAll("관전 중"); setcurpl2cpcache(); }` 가 관전자 화면에만 뜨는지. 다른 값이 나오면 알려 준다 | contains_user 가정 확정 | |
| B8-2 | CP 128~131 로 표시 | `pl.run_as(pl.Observers, DisplayText("…"))`, `pl.play_wav(pl.Observers, "…")` 가 관전자에게 보이고/들리고 플레이어 화면에는 안 뜨는지(S3 11-3 과 같은 항목) | display(WP6) | |
| B8-3 | 한 트리거 안에서 CP 여러 번 바꾸기 | `pl.run_as(list(P1, P2), DisplayText("A"))` 가 P1·P2 화면에 **한 번씩** 뜨는지(원시 CP 쓰기 + DisplayText 쌍을 한 트리거에 이어 붙임 — RotatePlayer 와 같은 방식). `pl.run_as(pl.Everyone, DisplayText, PlayWAV)` 도 | run_as 방식 확정 | |
| B8-4 | run_as/each 뒤 CP | `f_setcurpl(P3)` → `pl.run_as(pl.Everyone, …)` / `foreach(p : pl.each(pl.Humans)) { … }` 뒤에 `SetResources(CurrentPlayer, Add, 1, Ore)` 가 P3 에게 가는지 | 없음(확인만) | **2026-09-18 인게임: 통과** (players 단계) |
| B8-5 | 사람 판정(형 바이트 `0x57EEE8 + 36·p` = 2)과 **나간 플레이어** | 2인 게임에서 한 명이 나간 뒤 `pl.is_human(1)`·`pl.human_mask()` 값, `pl.run_as(pl.Humans, SetResources(CurrentPlayer, Add, 1, Ore))` 가 나간 플레이어에게 안 가는지, `pl.each(pl.Humans)` 가 건너뛰는지 | Humans 판정 확정 | |
| B8-6 | 동맹 표 `0x58D634 + 12·p + q` | 게임 중 동맹 설정(`SetAllianceStatus`, 동맹 창)과 같게 바뀌는지. `pl.run_as(pl.Allies(P1), DisplayText("팀"))` 가 P1 이 동맹으로 둔 플레이어에게만 뜨는지 | Allies | |
| B8-7 | 관전자 CP 의 표시 액션 | `pl.run_as(pl.Observers, CenterView("Anywhere"))`, `MinimapPing`, `SetMissionObjectives` 가 오류·튕김 없이 관전자 화면에만 적용되는지(`LOCAL_ONLY_ACTS`) | 허용 목록 확정 | |
| B8-8 | 게임 시작 초기화("이 PC 비트") | 사람 슬롯이 0·2·3 처럼 띄어 있는 맵에서 `pl.contains_user(pl.Everyone)` 가 각 플레이어·관전자 PC 에서 참인지, 빈 슬롯 번호로 들어간 PC 가 없는지 | 없음(확인만) | |

### WP10 `units`

확인용 맵: `python eudext/tools/build.py euddraft eudext/examples/units_ingame.eds --work <작업 폴더>` 로 빌드한
`units_ingame_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1). 화면 줄 머리의
`[T번호]` 가 아래 항목이다. 괄호 안 숫자는 기대값이다. 약 50프레임(몇 초)이면 끝나고 마지막 줄은 `[T11] … 끝`.
결과는 화면 사진이나 줄 글로 알려 주면 된다. (Windows 빌드: `python eudext\tools\build.py euddraft eudext\examples\units_ingame.eds --work %TEMP%\eudext_work\units_ingame`)

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| B10-1 | **[필수]** 생성이 실패하면 `u.ok` 가 거짓이고 0x628438 이 그대로인가 — (a) 자리가 없어서(같은 자리에 건물 두 번), (b) 유닛 한도(1700)가 차서 | `[T4]` 겹친 CC `ok=0`, 머리 전 = 후. `[T9]` 채운 마리 수, 마지막 `ok=0 ptr=0 idx=1700 머리=1700`. 한도가 1700 이 아니면(리마스터 확장 한도 등) 그 수를 알려 준다 | units 공개(capture 의 성공 판정), bullet(S4 `f_bullet` 0 반환) | **2026-09-18 인게임: 통과** — 겹친 CC `ok=0`, 머리 전 = 후 (유닛 한도 (b) 는 27 맵) |
| B10-2 | **[필수]** 성공 때 `u.index_before`(= `u.index`)·`u.epd` 가 실제로 만들어진 유닛 칸인가 | `[T1]` `ok=1`, `종류=0`(마린), `주인=0`(P1), 주문이 0 이 아님, 머리 후 = 전 + 1(보통) | units 공개, spawn 의 on_create 훅(S1 11-6) | **2026-09-18 인게임: 통과** — `ok=1` 종류 0 주인 0, `idx == 머리 전` = 1635. **머리 후 = 전 − 1** (빈 칸 목록이 번호가 **줄어드는** 쪽으로 간다) |
| B10-3 | 터렛 유닛(골리앗·시즈탱크)은 **본체가 먼저** 칸을 가져가는가 | `[T2]` `종류=3`, 서브유닛 칸 = idx + 1(아니면 알려 준다), `서브 종류=4`, 머리 = idx + 2 | scmodel `DEFAULT_SUBUNITS` 순서 | **2026-09-18 인게임: 값 확인** — 종류 3·서브 종류 4 는 맞고, 머리 걸음이 **−2**(줄어드는 쪽)였다. 맵의 기대식을 절대값(`stepAbs`)으로 고쳤다. 서브유닛 칸도 idx **− 1** 로 본다 |
| B10-4 | 한 번에 여러 마리(`CreateUnit(3, …)`)일 때 `u.index` 가 첫 유닛이고 칸이 연속인가 | `[T3]` 머리 = 첫 칸 + 3 | Capture 문서("첫 유닛") | **2026-09-18 인게임: 값 확인** — 3마리 연속은 맞고 머리 걸음이 **−3** (줄어드는 쪽). 기대식 절대값으로 고침 |
| B10-5 | **[필수]** `new_units()` 실행 시점과 순서 — 같은 프레임 순회 **앞**에서 만든 유닛은 그 프레임에, **뒤**에서 만든 유닛은 다음 프레임에 나오는가. 미리 놓인 유닛(맵 리빌러 64·시작 위치)은 첫 프레임에 나오는가. 골리앗 터렛도 새 유닛으로 나오는가 | `[T5] F1`~`F12` 줄: F1 에 리빌러 수 + T1, F2 에 2마리(골리앗 + 터렛?), F3 3마리, F4 1마리(CC), **F6 1마리, F7 1마리**, 나머지 0 | new_units 문서, scmodel 활성 목록 모델("두 번째 자리 삽입") | **2026-09-18 인게임: 실패(기대값 문제)** — F1 = **2**(파이어뱃 + T1 마린). 미리 놓인 맵 리빌러 64기는 칸을 차지하지만(머리 1635 = 1700 − 65) `new_units` 순회에 **나오지 않는다**. F2~F12 는 기대와 같다. 기대 범위를 2~68 로 넓혔다(에뮬레이터 모델은 66) |
| B10-6 | 죽은 유닛 칸의 흐름 — 주문(+0x4D)이 0 이 되는가, 몇 프레임 동안 스프라이트가 남는가, 칸이 빈 칸 목록 **어디로** 돌아가는가(곧바로 0x628438 이 그 칸이 되는가 = 앞, 아니면 끝). RemoveUnit 도 주문 0 을 거치는가 | `[T6] F8~F20`: 칸 주문·HP·스프라이트·머리 변화. `[T8]` 새 칸이 죽은 칸(T1 칸)인지. `[T10]` CC(RemoveUnitAt)의 죽음 알림이 1회 나오는가 | scmodel `free_to` 기본값("back"), clear_on_death·dying 판정(주문 0) | **2026-09-18 인게임: 통과** — 주문 0 프레임 8, 새 칸 = 죽은 칸이 아님(`front=0`) |
| B10-7 | 칸이 다시 쓰일 때 고유 바이트(+0xA5)가 1 늘어나는가 | `[T8]` 죽은 칸 고유 전 → 지금 (새 유닛이 그 칸에 들어갔을 때만 +1) | scmodel 고유 바이트 모델, eudplib EUDLoopNewUnit 판정 | **2026-09-18 인게임: 통과** — 고유 바이트 1 → 1 (새 유닛이 그 칸에 안 들어감) |
| B10-8 | `dying()` 이 죽는 유닛마다 **한 번만** 알리고 행을 지우는가, `clear_on_death()` 가 죽은 칸의 값을 지우는가. `limit=40` 일 때 남은 칸이 다음 프레임에 이어서 나오는가 | `[T7]` F8 에 마린 6마리 각 1줄, `[T10] … CC 죽음 알림 1회(1), mark=0 tag=0`. F32 뒤 알림 합계가 프레임마다 40씩 늘다 멈추는가(`[T10]` 합계) | dying·clear_on_death 공개 | **2026-09-18 인게임: 통과** — F8 죽음 6마리, CC 죽음 알림 1회, mark·tag 0 |
| B10-9 | 순회 실행량 체감 — `clear_on_death`·`dying` 이 각각 사이클당 약 2,000 트리거, `[T9]` 는 한 프레임에 약 5만 트리거 + 유닛 1,600여 마리 생성 | 맵 전체에서 끊김이 느껴지는지(특히 F30 전후) | 사용 안내(몇 프레임에 한 번 부르기) | |
| B10-10 | `units.CUnit(u.epd).removeTimer = 0` 이 먹는가(40번 유닛 시한부 규칙 대비 — 메모 `sc-unit40-remove-timer-reset-after-create`) | `[T11]` `removeTimer 쓰기 → 0` | 없음(eudplib CUnit 확인) | **2026-09-18 인게임: 통과** — removeTimer 쓰기 → 0 |

참고(모델 가정, 결과에 따라 `testing/scmodel.py` 를 고친다): 새 유닛은 활성 목록(0x628430)의 두 번째 자리, 죽은 칸은 빈 칸 목록 끝,
생성 위치는 로케이션 중심, 고유 바이트는 생성마다 +1, 터렛은 본체 다음 칸.

### WP13 `local`, `sync`

준비: `python eudext/examples/sync_build.py --work <폴더> --map <사람 슬롯이 2개 이상인 맵>` 으로 `sync_example_out.scx` 를 만든다
(Windows 는 `EUDEXT_EUDDRAFT` 또는 `C:\euddraft0.11.0.1\euddraft.exe`. 기본 맵 `testing/base.scx` 는 P1 만 사람이라 혼자 확인용이다.
맵에서 유닛 49 를 쓰지 않아야 한다 — 놓여 있으면 빌드가 멈춘다).
예제 조작: SPACE = 점수 +1(동기화 펄스)·누르는 동안 누름 수 증가(레벨), LCTRL+좌클릭 = 점수 +10, F5 = 내 점수·누름 수·동기화된
마우스 좌표 출력(로컬 표시), TAB = 로컬 표시 토글, TAB 켜진 상태에서 우클릭 = 로컬 마우스 좌표 출력.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| B13-1 | **[필수]** 2인 이상 디싱크 없음 | LAN(가능하면 배틀넷도) 2~3인으로 5분 동안 SPACE 연타·누르고 있기, LCTRL+좌클릭, F5, TAB, 우클릭, 채팅을 섞어 한다. 드롭·"동기화 오류" 가 없어야 한다 | sync·local 공개 | |
| B13-2 | **[필수]** 펄스가 모든 PC 에서 같은 값 | 두 PC 에서 번갈아 SPACE 를 누르고 각자 F5 로 두 사람의 점수를 비교(예제는 자기 점수만 출력 — 상대 PC 의 F5 결과를 서로 말로 비교). 한 번 누를 때 +1 인지, 빠르게 연타할 때 빠지는 횟수가 있는지(한 턴 안 엣지 소실, INT 5.1) 적는다 | pulse 문서의 소실 설명 | |
| B13-3 | 레벨(Down/Up 짝) | SPACE 를 3초 누르고 있다 떼기 → F5 의 누름 수가 누르는 동안만 늘고 떼면 멈추는지. 아주 짧게 톡 치기(한 턴 안에 Down+Up) → 누름 수가 늘지 않아야 한다. 이때 Down·Up 이 같은 QC 유닛의 다른 프레임 명령이면 뒤 명령(Up)만 남아 **점수 +1 도 빠질 수 있다**(INT 5.1) — 빠지는 빈도를 적는다. **SPACE 를 누른 채 Enter 로 채팅창을 열고 SPACE 를 뗀 뒤 채팅창 닫기** → 누름 수가 멈춰야 한다(Up 짝은 guard 없음) | level 규칙 확정 | |
| B13-4 | 걸쇠(val) 지연·공백 | TAB 켜고 마우스를 움직이며 F5 → "동기화 마우스 x, y" 가 로컬 좌표를 몇 프레임 늦게 따라오는지(싱글·LAN·배틀넷). 마우스를 **가만히** 두고 F5 를 여러 번 → 값이 흔들리거나 0/엉뚱한 값으로 튀지 않는지(MSQC Move 가 150프레임마다 다시 시작돼 그 사이클 값이 빈다는 SNQC 조사 — 걸쇠는 빈 사이클을 무시해야 한다) | latch 문서, SNQC 전송 검토 | |
| B13-5 | 채팅 중 판정 | 채팅창을 연 채 SPACE·LCTRL+좌클릭 → 점수가 늘지 않아야 한다(guard `NotTyping`). 채팅창을 연 채 TAB → 표시 토글이 바뀌지 않아야 한다(`key_toggle` guard). F5 는 채팅 중에도 출력된다(guard 없음 — 의도) | guard 문서 | |
| B13-6 | 키·마우스 엣지(로컬) | F5 를 오래 누르고 있어도 출력이 한 번인지, 우클릭 한 번에 한 줄인지(`local.key_pressed`/`mouse_pressed` + update 캐시). 두 PC 에서 각자 눌러도 자기 화면에만 뜨는지(`local.only(CurrentPlayer)`) | local 엣지 | |
| B13-7 | 관전자 | 관전자 슬롯으로 들어와 전 항목을 반복 → 관전자 PC 에서 게임이 멈추거나 디싱크 나지 않는지, 관전자 화면에는 F5 출력이 없는지(`EUDLoopPlayer` 는 관전자를 돌지 않는다). 관전자는 입력을 보낼 수 없다(MSQC 는 사람만) | local.is_observer, players 와 함께 | |
| B13-8 | 선택 복원 | 유닛 여러 기를 고른 채 SPACE·좌클릭 → 선택이 유지되는지, 부대 지정(Ctrl+숫자) 후에도 QC 유닛이 섞여 들어가지 않는지(MSQC `RestoreSelUnits`, INT 3.7) | MSQC 사용 안내 | |
| B13-9 | QC 유닛·크래시 | 10분 이상 진행해도 크래시가 없는지(QCUnit 49, QCDebug false). 맵에 49 를 놓은 사본으로 빌드하면 빌드가 멈추는지(`sync.verify` — Ubuntu 에서 101 로 확인함) | — | |
| B13-10 | 턴이 여러 프레임인 방 | 배틀넷(또는 지연 설정이 큰 방)에서 B13-2~4 를 반복해 소실·지연이 LAN 과 어떻게 다른지 | TurnSim 모델 확인, SNQC 합치기 비교 | |
| B13-11 | (선택) NSQC | 0.9.10.11 판 `NSQC.py` 를 eds 폴더에 두고 `Bus("nsqc", deaths=…)` 로 `dword(0x6CDDC4)`·`key_press`·`when(sync.mouse_moved())` 를 쓴 맵(`tests/t_sync.py` 의 `NSQC_EPS`)을 2인으로 → 값이 오는지, 못 받은 사이클이 에러코드인지 | NSQC 지원 범위 | |
| B13-12 | (선택) `mouse_location` | 사람 수만큼 연속 로케이션을 둔 맵에서 `bus.mouse_location("MouseP1")` 로 로케이션이 각자 마우스를 따라가는지, 첫 사람 번호가 0 이 아닐 때 번호 규칙(첫 로케이션 + p − 가장 작은 사람 번호) | sync 문서 | |

### WP15 `datpatch`

에뮬레이터로는 메모리 값까지만 확인했다(시작 1회·매 프레임·조건 목록·now·temporary 되돌리기). 게임이 그 값을 어떻게 쓰는지는 아래를 Windows 에서 본다.
시험 맵: `python eudext/tools/build.py euddraft eudext/examples/datpatch_example.eds --work <작업 폴더>` 로 만든 `datpatch_out.scx`
(마린 체력 80·아머 2·미네랄 75, 208번 공중·무적, 무기 1 스플래시 7/14/21, 마린 생산 P1~P5, 매 프레임 유닛 0·1 요구사항 오프셋 0 등).

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| B15-1 | **[필수]** 피해 배율 표 주소 `0x515B88`(CtrigAsm·theSeed) 대 `0x515B84`(eudplib 주석) (S5 A.9-4) | 두 주소의 dword 를 표시(`dat.addr("damage", "ratio", 1*5+1)` 등)해 바닐라 값 128·192·256(폭발형 소형·중형·대형)이 어느 쪽에서 시작하는지 본다. 또는 `dat.damage_ratio(3, 1, 512)` 뒤 일반형 무기로 소형 유닛을 때려 피해가 2배인지 | `dat.damage_ratio`·`dat.tep.SetDamageRatio` 의 경고 해제(맞으면) / 주소 수정(틀리면) | **2026-09-18 인게임: 통과** (datpatch 단계) |
| B15-2 | 맵 CHK(UNIx·PUNI·UPGR·PTEC)로 넣은 값과 트리거 패치 결과가 게임 시작 뒤 같은 메모리 값인지 (A.9-1) | SCMDraft 로 한 유닛의 체력·생산 가능을 바꾼 맵과, 같은 값을 `dat.unit(u).set(maxHp=…)`·`dat.player_unit_enable(…)` 로 넣은 맵에서 `0x662350+4u`, `0x57F27C+228p+u` 를 표시해 비교 | 문서의 "CHK 로 되는 값은 맵 편집기" 권장 확정 | |
| B15-3 | 시작 1회 목록이 적용되는 사이클과 **맵에 미리 놓인 유닛**의 체력·실드 (A.9-2) | 예제 맵에 마린을 미리 놓고 시작 직후 체력 표시가 40/80 인지 80/80 인지(최대 체력만 바뀌고 현재 체력은 그대로인지) | 문서에 "미리 놓인 유닛은 …" 안내 | **2026-09-18 인게임: 통과** (units 단계 — 미리 놓인 파이어뱃 HP 12800 / 최대 25600) |
| B15-4 | `every_frame` 이 필요한 필드 목록 (A.9-3) | 요구사항 오프셋(`requirementOffset`) 외에 게임이 되돌리는 칸이 있는지: 시작 목록으로 바꾼 값(예: `timeCost`, `supplyUsed`)을 몇 분 뒤·저장 불러오기 뒤 다시 표시 | `every_frame` 권장 필드 목록 | **2026-09-18 인게임: 절반 통과** — datpatch 단계에서 timeCost 777·supplyUsed 7 확인. 몇 분 뒤 유지(final 단계)는 display 멈춤으로 미실행 |
| B15-5 | 마스크 Add/Subtract 의 wrap/포화 (A.9-5, **S8 A-1 과 같은 시험**) | datpatch 는 마스크 Add 를 만들지 않는다(EUD Editor 목록은 마스크 없는 Add). S8 결과가 나오면 에뮬레이터 식만 확인 | 필드 `add`·`sub` API (지금 없음) | **2026-09-18 인게임: 통과** (s8 단계) |
| B15-6 | `temporary()` 를 프레임을 넘겨 유지했을 때(`restore=False` + 나중 `dat.unpatch_all()`) 저장·불러오기·리플레이 문제 없음 (A.9-6) | 예제 맵의 `dat.now.weapon(phase).set(damage=phase)` 를 restore=False 로 바꿔 몇 프레임 뒤 되돌리고, 그 사이 저장·불러오기·리플레이 재생 | temporary 문서의 "같은 프레임 한정" 문구 완화 여부 | |
| B15-7 | TEP `WhatSndInit`/`WhatSndEnd` 반대 이름(D19) 체감 | `dat.tep.SetUnitsDatX(u, {"WhatSndInit": a, "WhatSndEnd": b})` 와 `dat.unit(u).set(whatSoundStart=a, whatSoundEnd=b)` 두 맵에서 유닛 선택 음성이 어느 쪽이 기존 TEP 맵과 같은지 | **D19 사용자 결정**(TEP 동작 보존 + 경고 = 권장안으로 구현됨) | |
| B15-8 | images `grpFile`·overlay 6종 쓰기가 SC:R 에서 먹는지(읽기 전용 표기) | `dat.image(i).set(attackOverlay=…)` 뒤 해당 이미지의 오버레이가 바뀌는지, 오류·튕김이 없는지 | 경고 해제 또는 필드 제거 | |
| B15-9 | `from_eud_editor` 로 옮긴 M2/UERE 표가 원래 DataEditor.py 플러그인과 같은 결과인지 | M2 를 `dat.from_eud_editor("EUDEditorDat.lua")` 로 빌드해 원래 맵과 유닛 그래픽·무기·업그레이드 비용 몇 개를 비교 | EUD Editor 이식 안내 확정 | |
| B15-10 | 매 프레임 목록이 beforeTriggerExec **앞**(게임 루프 시작점)에서 도는 것이 TEP Prsv(트리거 목록 안)와 체감 차이가 없는지 | 요구사항 오프셋을 매 프레임 0 으로 두는 기존 맵 동작(버튼 활성)이 같은지 | 없음(확인만) | **2026-09-18 인게임: 통과** (datpatch 단계) |

## 배치 C (WP2 cell, WP3 i64 1차, WP9 mathx, WP11 pool)

### WP2 `cell`

**필수 항목은 없다.** `Cell` 의 연산은 SC 동작 가운데 이미 여러 근거로 확실한 것(마스크 없는 `Subtract` 의 0 포화, 음수 `Add` 의 wrap, 마스크 SetTo·마스크 조건)과
eudplib 이 늘 쓰는 방식(변수 트리거, 조건 칸 채우기, `EUDArray` 칸 쓰기)만 쓴다. 에뮬레이터 차등 시험(`tests/t_cell.py`, 약 5만 판정)으로 값은 확인했다.
마스크 `Add`·`Subtract`(A-1 에서 확인 대기)는 쓰지 않는다 — 변수 색인 wrap 뺄셈도 eudplib `EUDArray.isubitem` 의 마스크 Add 반전 대신 `−v` 를 만들어 더한다.
아래는 에뮬레이터가 가정한 SC:R 동작을 한 번에 보는 **권장** 항목이다.

확인용 맵: 예제가 겸한다. `python eudext/tools/build.py euddraft eudext/examples/cell_example.eds --work <작업 폴더>` 로 빌드한
`cell_example_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`).
(Windows 빌드: `python eudext\tools\build.py euddraft eudext\examples\cell_example.eds --work %TEMP%\eudext_work\cell`)

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| C2-1 | (권장) `Cell` 연산이 SC:R 에서 에뮬레이터 가정대로인지 — ① 마스크 없는 SC `Subtract` 가 0 에서 멈춤(`isub_sat`·`SubCD`·변수 색인 `isub_sat`) ② 음수 `Add` wrap(`c.v -= x`·`arr[i] -= x`·같은 칸 `c.isub(c)` = 0) ③ 조건 amount 칸·자기 칸 깃발을 실행 중에 채우는 비교(`hp >= x`, `hp < x`, `hp != x` — B1-1 과 같은 방식) ④ 조건의 플레이어(EPD) 칸을 실행 중에 채우는 변수 색인 비교(`arr[i] == v`, `arr[i] < v`) ⑤ `DoActions(SetCD(a, x), AddCD(a, 1), SetCD(b, y), SubCD(b, x))` 처럼 한 트리거 안의 변수 값 액션 여러 개 ⑥ `PCell` 의 `CurrentPlayer` 색인 | 맵을 열고 약 1초(24프레임) 뒤 화면에 **`[C2-1] eudext.cell 점검 18 / 18 (18 이면 정상)`** 이 뜨는지 본다. 18 이 아니면 그 숫자를 알려 준다(`examples/cell_example.eps` 의 `selftest` 주석 번호 1~18 순서로 좁힌다 — 1·2 = ①, 3·4 = ②, 5~10 = ③, 11~14 = ④, 15 = ⑥, 16·17 = ⑤, 18 = Flag) | 없음(확인만) | **2026-09-18 인게임: 통과** (cmp_cell 단계) |

### WP3 `i64` (1차)

64비트 연산 결과는 에뮬레이터 차등 시험(`tests/t_i64.py` 307,019 판정)으로 확인했다. 에뮬레이터가 **가정**으로 둔 SC:R 동작
세 가지를 확인용 맵 한 장으로 본다.

확인용 맵: `python eudext/tools/build.py euddraft eudext/examples/i64_ingame.eds --work <작업 폴더>` 로 빌드한
`i64_ingame_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1).
(Windows: `C:\Users\whatd\.venvs\eud081\Scripts\python.exe eudext\tools\build.py euddraft eudext\examples\i64_ingame.eds --work %TEMP%\eudext_work\i64_ingame`)
첫 사이클에 `[C3] eudext.i64 인게임 점검 — …` 한 줄이 뜨고, 약 10초(120 트리거 사이클)마다 `[C3-1]`~`[C3-7]` 일곱 줄이
한 줄씩 뜬다. 괄호 안이 기대값이다. **`[C3-7] 점검 23 / 23`** 이면 모두 맞은 것이다. 한 바퀴를 사진이나 글로 알려 주면 된다.
에뮬레이터에서 같은 맵은 `점검 23 / 23`, `[C3-1]` 세 값 0·0·2147483647 이다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| C3-1 | **[필수]** 마스크 없는 SC `Subtract` 액션이 **부호 없는 비교로 0 에서 멈추는가** — `Int64` 포화 뺄셈의 hi 반쪽, 상수 포화(S8 SK), 10진 출력이 이 가정에 기댄다(DESIGN 3.5-7). S8 인게임 맵(A-1)의 P1·P2 줄과 같은 사실을 i64 맵에서 한 번 더 본다 | `[C3-1] SC Subtract 3−5 = 0 (0), 5−0xFFFFFFFF = 0 (0), 0x80000001−2 = 2147483647 (2147483647)`. 괄호와 다른 값이면 그대로 알려 준다(예: 5−0xFFFFFFFF 가 6 이면 부호 있는 비교) | `i64` 포화 뺄셈 공개 확정, WP4(곱셈·나눗셈)·WP5(numfmt 10진 본문 재사용) | **2026-09-18 인게임: 통과** (i64 단계) |
| C3-2 | **[필수]** 64비트 **포화** 뺄셈이 SC:R 에서 맞는가 — 인라인(`[C3-2]`)·상수(`[C3-3]`)·공유 함수(`[C3-4]`, 기본 경로). 2^32 − 1 빌림 경계, hi 가 작음, hi 같고 빌림, 같은 값. 인라인·공유 함수 판은 **조건의 +12 칸(비교·종류 바이트)을 실행 중에 Always 로 바꾸고 준비 트리거가 되살리는** 방법과 조건 칸 채우기(+0 비트마스크 칸, +8 amount 칸)에 기댄다 | `[C3-2] 포화(변수·인라인) 4294967295 0 2 0 0 9800000000`, `[C3-3] 포화(상수) 4294967295 0 2 0`, `[C3-4] 포화(공유 함수) 4294967295 0 2` — 괄호 안과 같아야 한다 | `i64` 포화 뺄셈 공개 확정(DESIGN 4.4 위험 항목) | **2026-09-18 인게임: 통과** (i64 단계) |
| C3-3 | wrap 뺄셈·부호 반전·올림·비교·10진 출력 | `[C3-5] wrap 18446744073709551615 4294967295 부호 반전 18446744073709551615 올림 4294967296`, `[C3-6] 비교 5 5 7 … 출력 18446744073709551615 -1`, 마지막 `[C3-7] 점검 23 / 23` | 없음(확인만) | **2026-09-18 인게임: 통과** (i64 단계) |

참고: `[C3-6]` 의 출력은 부호 없는 10진(`x.fmt()`)과 부호 있는 10진(`i64.fmt(x, signed=True)`)이다. 한 줄에 `fmt()` 가 여러 개여도
호출 자리마다 버퍼가 따로라 값이 섞이지 않아야 한다(섞이면 알려 준다).

### WP9 `mathx`

`mathx` 의 값은 CtrigAsm 원본(Lua 를 줄 단위로 옮긴 참조 구현 `tests/ref_mathx.py`)과 에뮬레이터 차등(기본 약 6.6만 판정, 전체 실행 lengthdir·atan2 각 20만 개)으로 확인했다.
남은 것은 두 가지다. ① 원본 표 값이 **Windows TEP** 에서도 정확 반올림 값과 같은가(원본 값 자체의 전제) ② SC:R 이 에뮬레이터 가정대로 도는가.

**C9-1 도구** (Windows, 개발 venv 파이썬 — scx 를 읽으려면 eudplib 0.81 이 있어야 한다):

```
C:\Users\whatd\.venvs\eud081\Scripts\python.exe eudext\examples\mathx_tep_check.py lua %TEMP%\mathx_tables.lua
  → SCMDraft 2 로 빈 맵(예: eudext\testing\base.scx 사본)을 열고, TrigEditPlus 에 mathx_tables.lua 내용을 붙여 넣어 컴파일한 뒤 맵을 저장한다
    (CtrigAsm 을 불러오지 않는 평범한 스크립트다. 트리거 약 260개가 생긴다)
C:\Users\whatd\.venvs\eud081\Scripts\python.exe eudext\examples\mathx_tep_check.py check <저장한 맵.scx>
  → 마지막 줄이 "C9-1 일치" 면 끝. 아니면 위의 "다른 칸" 줄을 알려 준다
```

**C9-2 확인용 맵**: `python eudext/tools/build.py euddraft eudext/examples/mathx_ingame.eds --work <작업 폴더>` 로 빌드한 `mathx_ingame_out.scx` 를
StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1). 1초쯤 동안 `[C9-2]` 줄 14개가 뜬다.
(Windows 빌드: `python eudext\tools\build.py euddraft eudext\examples\mathx_ingame.eds --work %TEMP%\eudext_work\mathx_ingame`)

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| C9-1 | **[필수]** 원본 TEP(Windows SCMDraft 2 플러그인, MSVC 런타임)가 CtrigAsm 수학 표를 정확 반올림 값과 같게 만드는가 — 특히 경계에 붙은 `0x10000·sin 30°`(32767.999… → **32767**)와 `0x10000·tan 45°`(65535.999… → **65535**, 그래서 atan2(1, 1) = **46**) | 위 C9-1 도구(`lua` → TEP 컴파일·저장 → `check`). Linux 헤드리스 TEP(glibc)는 261칸 모두 일치했다. 다르면 "다른 칸" 줄을 알려 준다 — 그 경우 mathx 표를 Windows 원본 값에 맞춘다 | D5(결과 값까지 CtrigAsm 과 같게)의 전제 확정 | |
| C9-2 | (권장) mathx 연산이 SC:R 에서 에뮬레이터와 같은 값을 내는가 — lengthdir(변수 각 공유 엔진·상수 각·범위 밖 반지름), Rotator(CA_Rotate), rotate3d(CA_Rotate3D), atan2(f_Atan2)·atan2_sc(f_Atan2X)·to_dir256, sdivmod(f_iDiv 두 정책)·ratio(CA_RatioXY), isqrt(f_Sqrt)·ilog2(f_Log2), 고정밀 lengthdir(LengthdirX, 주기 8 표). 쓰는 SC 동작: eudplib 시프트·부호 반전의 마스크 SetTo/Add/Subtract(A-1 과 같은 식), 실행 중에 채우는 조건 비교값(B1-1 과 같은 방식), 조건이 같은 트리거의 액션 값 칸을 읽기, 액션 값 칸 패치, 파일 표(Db) 읽기 | 맵을 열고 약 1초 뒤 **`[C9-2] 전체 일치 110 / 110 (같으면 정상)`** 이 뜨는지 본다. 그 위 줄들: `lengthdir 일치 19 / 19`, `Rotator(CA_Rotate) 일치 8 / 8`, `rotate3d(CA_Rotate3D) 일치 4 / 4`, `atan2(f_Atan2) 일치 15 / 15`, `atan2_sc(f_Atan2X) 일치 6 / 6`, `to_dir256 일치 16 / 16`, `sdivmod(f_iDiv) 일치 9 / 9`, `ratio(CA_RatioXY) 일치 9 / 9`, `isqrt(f_Sqrt) 일치 10 / 10`, `ilog2(f_Log2) 일치 7 / 7`, `lengthdir precise(LengthdirX, 주기 8) 일치 7 / 7`, 표본 두 줄(`lengthdir(100, 45) = (70, 70) (70, 70), atan2(1, 1) = 46 (46), isqrt(99) = 9 (9)`, `lengthdir(-100, 30) = (FFFFFFAA, FFFFFFCF) …`). "다름" 줄(빨간 글자)이 있으면 그 줄을 사진·글로 알려 준다 | 없음(확인만). A-1 결과가 eudplib 가정과 다르면 이 맵도 틀린다 | **2026-09-18 인게임: 통과** (mathx 단계 — 전체 일치) |

### WP11 `pool`

**필수 항목은 C11-1 하나다**(S2 7.3-1: 사슬 적재가 실제 SC:R 에서 도는가 — 에뮬레이터 밖 첫 확인).
pool 은 eudplib 이 이미 쓰는 기법만 쓴다: 72B 변수 원소로 점프해 값 적재(`EUDQueue`), 트리거가 **자기 next 칸을 액션으로 고친 뒤**
그 값으로 가는 것(`EUDQueue` 의 `iter_jump`), CP 상대 `SetDeaths`/`Deaths`·`DeathsX`(eudplib `f_dwread_cp` 계열),
`Memory(0x6509B0, Exactly, …)` 조건(eudplib CP 캐시 검사), 조건 amount 칸 채우기(B1-1 과 같은 방식).
다만 pool 은 **변수 원소가 자기 next 칸에 쓰는** 조합(살아 있는 목록 원소)과 **레코드 마지막 원소의 next 칸을 생존 표시로 쓰는** 방식을 새로 쓴다.
에뮬레이터 차등 시험(`tests/t_pool.py`, 1,590 판정 — 참조 모델과 무작위 1,450 걸음)으로 값은 확인했다.

확인용 맵: `python eudext/tools/build.py euddraft eudext/examples/pool_ingame.eds --work <작업 폴더>` 로 빌드한
`pool_ingame_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`).
(Windows 빌드: `python eudext\tools\build.py euddraft eudext\examples\pool_ingame.eds --work %TEMP%\eudext_work\pool`)
1~10프레임에 시험 동작이 끝나고, **12프레임부터 2초(48프레임)마다** `[pool] …` 머리줄과 `[T1]`~`[T7]` 요약 줄이 다시 뜬다.
줄 끝 괄호 안이 기대값이고, 각 줄의 `판정 1` 이 통과다. 한 바퀴를 사진이나 글로 알려 주면 된다.
에뮬레이터에서 이 맵은 200프레임 동안 판정 일곱 개가 모두 1 이다(`t_pool.py` `ingame_emulate`).

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| C11-1 | **[필수]** 사슬 적재·되쓰기(S2 7.3-1) — 레코드 5개(`a b! c d`, b 는 readonly)를 만들고 매 프레임 방문해 레지스터에 실린 값이 저장 값과 같은지, `a += 1` 이 되쓰이는지. 큰 값(0x80000000+i, 0xFFFFFFF0+i) 포함 | `[T1] #0~#4 a=… (…) b=… (…) c=… (…)` 다섯 줄이 괄호와 같고, `[T1] 사슬 적재: 방문 N (N) 불일치 0 (0) 판정 1 (1)`. 불일치가 0 이 아니거나 맵이 멈추면(트리거 흐름 오류) 그대로 알려 준다 | `pool` 공개 확정, WP12 `spawn`(작업 레코드) | **2026-09-18 인게임: 통과** (pool 단계. final 단계 재확인은 display 멈춤으로 미실행) |
| C11-2 | 넘침(S2 7.3-2) — 36칸 풀에 37개를 넣으면 한 번 실패하고 원본과 같은 문구·경고음이 나는가 | 2프레임에 `『 ERROR : Over의 목록이 가득 차 alloc을 실행할 수 없습니다! …』` 한 줄 + Buzz 3번. 요약 `[T2] 넘침: count=36 (36) dropped=1 (1) 판정 1 (1)` | 없음(확인만) | **2026-09-18 인게임: 통과** (pool 단계) |
| C11-3 | 방문 중 반납·할당이 섞인 패턴(S2 7.3-3) — 자기 반납 + 새 레코드(다음 프레임부터), 이미 돈 레코드 반납(다음 프레임부터 안 돎), 순서 유지 | 3~6프레임에 `[T3] 프레임 3: 방문 순서 1234 (1234)`, `프레임 4: 1234 (1234)`, `프레임 5: 1345 (1345)`, `프레임 6: 345 (345)` 네 줄(빨리 지나가면 요약만 봐도 된다). 요약 `[T3] … 불일치 0 (0) 마지막 순서 345 (345) 판정 1 (1)` | 없음(확인만) | **2026-09-18 인게임: 통과** (pool 단계) |
| C11-4 | 느린 경로(방문 밖): `set`/`get`(CP 상대 쓰기·`f_dwread_epd`), `is_alive`·`free`(핸들을 CP 에 두고 `Memory(0x6509B0, Exactly, 방문 중 핸들)` 로 가름), `index_of`(비트 조건 사슬) | `[T4] 느린 경로: get 99 (99) 11 (11) is_alive 1 (1) → 0 (0) index_of 1 (1) 합 132 (132) 판정 1 (1)` | 없음(확인만) | **2026-09-18 인게임: 통과** (pool 단계) |
| C11-5 | 128칸 풀 + 살아 있는 10개(S2 7.3-5) — 빈 칸 비용이 없으니 원본(슬롯 128개 매 프레임 검사)보다 가벼워야 한다 | `[T5] 128칸 풀 + 10개 방문 중: count 10 (10) 판정 1 (1)`. 게임 속도 최고에서 끊김이 원본 건작 맵보다 심한지 **체감**을 알려 준다(수치가 아니어도 된다) | 없음(체감) | **2026-09-18 인게임: 통과** (pool 단계) |
| C11-6 | 부호 필드 비교(`g.dir >= -10`, `Line(0, AtMost, -1)`)와 옛 줄 번호 `SetLine(…, Subtract, …)` 의 포화(3 − 5 → 0) | `[T6] 부호 필드·Subtract 포화: 방문 N 불일치 0 (0) 판정 1 (1)` | 없음(확인만) | **2026-09-18 인게임: 통과** (pool 단계) |
| C11-7 | 등록 안 된 유형(`dispatch` 기본 가지, 원본 `GunCaseErrT`) — 문구 + 경고음 2번 + 반납 | 10프레임에 `『 ERROR : Kind: 등록되지 않은 kind 값이 작동하여 자동으로 반납하였습니다. …』` 한 줄 + Buzz 2번. 요약 `[T7] 미등록 유형: 방문 1 (1) count 0 (0) 판정 1 (1)` | 없음(확인만) | **2026-09-18 인게임: 통과** (pool 단계) |
| C11-8 | (권장) 멀티 디싱크 없음(S2 7.3-6) — 풀 상태는 공유 값만 쓴다. 같은 맵을 2인 이상으로 연다 | 2인 이상에서 C11-1~7 과 같은 줄이 모든 PC 에 같게 뜨고 디싱크가 나지 않는지 | (요청) `tools/ingame_maps.py` 에 `pool_ingame.eds` 를 `base_multi.scx` 로도 빌드하는 줄 | |
| C11-9 | (나중) 건작 본문에서 G_CB(spawn) 호출 → 중심 좌표가 그 레코드의 x, y(S2 7.3-4) | WP12 `spawn` 확인 맵에서 | WP12 | **2026-09-18 인게임: 통과** (spawn 단계) |

참고: 문구의 이름 부분은 풀 이름이다(원본의 "f_Gun" 자리). 원본 `G_SendErrT` 의 "G_Send" 는 새 API 에 없는 이름이라 "alloc" 으로 바꿨다.

## 배치 D (WP4 i64 2차, WP5 numfmt, WP6a strdesign, WP7 shape/plot, WP14 bullet, WP16 bgm)

### WP4 `i64` 2차 (곱셈·나눗셈·부호 나눗셈·비트·시프트·to32·abs) — 맵 15

2차 연산 결과는 에뮬레이터 차등 시험(`tests/t_i64_ops.py` 195,805 판정)으로 확인했다. 2차 본문이 쓰는 기법은 eudplib 이
스스로 쓰는 것(트리거 next 자기 수정 — `_eud_mul`·`_eud_div`, 조건 amount·액션 값 칸 채우기, 변수 트리거 사슬 — VProc,
마스크 SetTo·마스크 조건)과 "값 ≥ 빼는 값" 이 보장된 SC `Subtract`(C3-1 과 같은 사실)뿐이라 **새 가정은 없다**. 그래서 필수 항목은
없고, 권장 항목 한 장으로 실제 게임에서 한 번 돌려 본다. 마스크 Add/Subtract 식(S8 A-1)은 쓰지 않는다.

확인용 맵: `python eudext/tools/build.py euddraft eudext/examples/i64_ops_ingame.eds --work <작업 폴더>` 로 빌드한
`i64_ops_ingame_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1).
(Windows: `C:\Users\whatd\.venvs\eud081\Scripts\python.exe eudext\tools\build.py euddraft eudext\examples\i64_ops_ingame.eds --work %TEMP%\eudext_work\i64_ops_ingame`)
첫 사이클에 `[D4] eudext.i64 2차 인게임 점검 — …` 한 줄이 뜨고, 약 10초(120 트리거 사이클)마다 `[D4-1]`~`[D4-9]` 스무 줄이
한 줄씩 뜬다(한 바퀴 약 10초 × 20). 괄호 안이 기대값이다. **마지막 줄 `[D4-9] 점검 56 / 56`** 이면 모두 맞은 것이다.
에뮬레이터에서 같은 맵은 `점검 56 / 56` 이다. 맞지 않으면 틀린 줄(괄호 밖 값)을 사진이나 글로 알려 준다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| D4-1 | (권장) `i64` 2차 연산 — 변수 곱셈(16비트 쪼개기, 64×64·32×32), 상수 곱(비트 누적·배가·덧셈), 부호 없는 나눗셈(32비트 제수 d ≤ 2^31 / d > 2^31, 64비트 제수 D < 2^63 / D ≥ 2^63, 0 나눗셈), 상수 제수(10000, 2^32 + 1, 1024), 부호 있는 나눗셈(부호 조합, −2^63 ÷ −1, 0 나눗셈 두 규칙), 비트 연산, 시프트(상수 63, 변수 64·33·5), to32(포화·부호), abs. 모두 트리거 next 자기 수정·조건/액션 칸 채우기에 기대므로 SC:R 에서 에뮬레이터와 같게 도는지 본다 | 위 맵. 줄 예: `[D4-1] 곱셈(변수) 1 18446744065119617025 12800038400000000 (1 18446744065119617025 12800038400000000)`, `[D4-3] 나눗셈(32비트 제수) 1844674407370955161 5 8589934588 (…)`, `[D4-6] 부호 있는 나눗셈(부호 있는 10진) -3 -1 -3 (-3 -1 -3)`, 마지막 `[D4-9] 점검 56 / 56 (56 / 56)` | 없음(확인만). 틀리면 `i64` 2차 본문을 고친다 | **2026-09-18 인게임: 통과** (i64_ops 단계) |

참고: 한 줄의 값 세 개는 각각 따로 `fmt()` 버퍼를 쓴다(C3-3 참고와 같음). `[D4-9]` 의 두 수가 같으면 나머지 줄은 보지 않아도 된다.

### WP5 `numfmt` — 맵 16

확인용 맵: `eudext/examples/numfmt_ingame.eds` (+ `numfmt_ingame.eps`, 기준 맵 `testing/base.scx`, 혼자 연다).
빌드: `python eudext/tools/build.py euddraft eudext/examples/numfmt_ingame.eds --work <작업 폴더>` → `numfmt_ingame_out.scx`.
첫 프레임에 서식 22개 + 셀 왕복 1개를 만들어 기대 바이트와 비교하고, 약 10초(120 사이클)마다 `[D5-1]`~`[D5-9]` 을 한 줄씩(대부분 결과 줄 + `기대:` 줄) 띄운다.
에뮬레이터에서는 `[D5-1] 자체 점검 23 / 23`, 틀린 번호 0, 셀 왕복 1 이 나온다(tests/t_numfmt.py `ingame_emulate`). euddraft 0.11 빌드 통과.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| D5-1 **[필수]** | 서식 트리거가 실제 게임에서도 에뮬레이터와 같은가 — 작업 변수 값 칸 마스크 SetTo·마스크 Exactly(EUDX), CP 기준 `DeathsX` 셀 조건, CP 옮겨 셀 쓰기 | 맵을 열고 `[D5-1] 자체 점검 N / M` 줄을 본다. **23 / 23, 틀린 번호 0** 이면 통과. 다르면 틀린 번호를 알려 준다 | 없음 (numfmt 전체의 전제) | **2026-09-18 인게임: 통과** (numfmt 단계 — 자체 점검 23 / 23) |
| D5-2 | 반각 결과(0 채움·부호·세 자리 묶음)가 기대 줄과 같게 보이는가 | `[D5-2]` 줄과 바로 아래 `기대:` 줄 비교 — `[00042] [-1,234,567] [+0,001,234]` | 없음 | |
| D5-3 | 전각 셀 `[0D][EF BC 9x]` 이 글자 사이 빈틈 없이 보이고, 앞의 `0D×4` 빈 셀이 자리를 차지하지 않는가 | `[D5-3]` — `[４２９４９６７２９５] [１２３４]` | 없음 | |
| D5-4 | 자리마다 색(반각 2B `[색][숫자]`, 전각 셀 앞 바이트) | `[D5-4]` — 987654 가 앞에서부터 P6 갈색, P5 주황, P4 보라, P3 청록, P2 파랑, P1 빨강(둘째는 전각) | 없음 | |
| D5-5 | 만 단위 색(`Man(colors="dps", after=0x04)`, `dp.man18(color=True)`)이 옛 DPS 화면과 같은가 | `[D5-5]` — `1억2345만`(1 은 색 1D, 2345 는 1C), `1844경6744조`(1B, 19), 억·만·경·조는 흰색. 옛 DPS 의 `SetNumX` 색과 같은지도 | 없음 | |
| D5-6 | `Per`·`dp.per8`·`dp.gauge40`·`dp.dig2` 표시 | `[D5-6]` — `[12.5] [1234.567] [l 20개: 앞 3개 초록, 나머지 흰색] [05]` | 없음 | |
| D5-7 | 한자 글자표(`glyphs`, 3바이트 글자를 등차가 아닌 표로)·16진 | `[D5-7]` — `[四二九四九六七二九五] [00ABCDEF] [ff]` | 없음 | |
| D5-8 | 0x0D 채움 고정 폭(`dp.dec16`·`dp.hex12`·`dp.dec20`)과 가림(`cut_low`)이 옛 DisplayPrint 처럼 보이는가 — 0x0D 가 폭을 차지하는지(S3 8.3-7 과 같은 질문) | `[D5-8]` 결과 줄의 대괄호 사이 간격을 옛 맵의 같은 원소와 비교해 알려 준다. 글자는 `[-10][00ABCDEF][-0000000000000000005] [12,800,000,000] [  9876] [-00005]` | display(WP6) 의 고정 폭 판단 | |
| D5-9 | DPL 이름 표(0x6D0FDC, `dp.name20`)와 eudplib 이름(0x57EEEB, `{:n}`)이 같은가 (S3 8.3-5, DESIGN 7절 D15) + 셀 왕복 | `[D5-9]` — 두 이름이 같고 첫 이름이 빨간색(P1 색 0x08), `셀 왕복 1`. 클랜 태그·한글 이름이면 더 좋다 | WP6 의 D15 결정 | **2026-09-18 인게임: 통과** (numfmt 단계) |
| D5-10 | 첫 프레임 부담 | 맵을 열 때 첫 프레임에 약 31,000 트리거가 돈다(비교 루프 — 맵 자체의 부담). 시작할 때 멈춤·렉이 눈에 띄는지 알려 준다 | 없음 | **2026-09-18 인게임: 통과** (초당 사이클 22.86) |

- 필수는 D5-1 하나다. D5-2~D5-9 는 한 번 보면 되는 표시 확인(권장)이고, D5-8·D5-9 는 WP6(display) 결정에 쓰인다.
- `tools/ingame_maps.py` 의 목록에 넣어 달라고 요청했다(설계 조각 5절) — 번호 제안 09 `numfmt_check`.

### WP6a `strdesign` — 맵 09

**필수 항목은 없다.** `sd.design()` 결과 바이트가 원본 Lua(6개 파일)와 같고, eudplib 이 맵 문자열 표에 그 바이트를 그대로 넣는 것을
에뮬레이터로 확인했다(시험 `tests/t_strdesign.py`). 아래는 화면에서 원본 맵과 같게 보이는지 눈으로 보는 **권장** 항목이다.

확인용 맵: `eudext/examples/strdesign_ingame.eds`(+ `.eps`) — 기준 맵 `testing/base.scx`, 혼자 연다.
빌드: `python eudext/tools/build.py euddraft eudext/examples/strdesign_ingame.eds --work <작업 폴더>` → `strdesign_ingame_out.scx`.
(일괄 빌드 `tools/ingame_maps.py` 의 `MAPS` 표에 넣으려면: `("07", "strdesign_ingame", os.path.join(EX, "strdesign_ingame.eds"), "single", "eds", "D6-1~5 (StrDesign 장식 4판·정렬, 권장)", "혼자. 6초마다 한 쪽씩 5쪽")` — 번호는 합칠 때 정한다.)

맵은 약 6초(144 사이클)마다 한 쪽씩 5쪽을 보여 주고 다시 1쪽부터 돈다. 각 쪽 첫 줄이 `[D6-번호]` 머리말이다. 화면 사진이나 "D6-2 같음" 같은 글로 알려 주면 된다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| D6-1 | `mcf` 판(Library 판) 장식이 DPS강화하기·UE_RE·Breeze 화면의 `『 』` 장식과 같은 색·모양이고, 2·3번째 줄이 가운데 정렬되는가 (권장) | 1쪽: 왼쪽 정렬 1줄 + 가운데 정렬 2줄을 원본 맵의 같은 모양 줄과 비교 | 없음(표시만) | |
| D6-2 | `seed` 판 장식(`。˙+˚ … 。+.˚`)이 theSeed·Stella_II 화면과 같은가. 전역 const + `printAll` 줄도 같은 모양인가 (권장) | 2쪽 3줄 | 없음 | |
| D6-3 | `respect` 판이 MSF_Respect_V 화면과 같은가(seed 와 맨 앞·맨 끝 기호 색만 다름). `"\x13"+pre+글+post`(StrD 모양) 줄이 가운데로 가는가 (권장) | 3쪽 3줄 | 없음 | |
| D6-4 | `memory` 판(`·【 … 】·`)이 MSF_Memory_2 화면과 같은가. **줄 머리 `\r\r` 뒤에 `\x13` 이 있어도 가운데 정렬되는가**(S7 9-1, 2번째 줄), `\r\r` 없는 StrDesignX2(3번째 줄)와 같은 위치인가 (권장) | 4쪽 3줄 | 없음 | |
| D6-5 | 원본에서 확인 못 한 모양 (권장): ① `\x13` 이 두 번 든 줄이 가운데에 한 번만 정렬되고 이상한 글자가 없는가(S7 9-2) ② `right=True`(`\x12`) 줄이 오른쪽 정렬되는가(Stella_II `"\x12"..StrD[1]` 모양) ③ 줄바꿈이 든 줄: 장식이 첫 줄 앞과 둘째 줄 뒤에만 붙는가 | 5쪽 3줄 + "한 바퀴 끝" 줄 | 없음 | |

참고
- 새 판(`sd.Style(...)`)을 만들 때는 그 기호가 SC:R 글꼴에서 보이는지 눈으로 확인한다(S7 5.5).
- `\x00` 이 든 문자열은 맵 문자열 표에서 거기서 끝나므로(에뮬레이터 확인) 인게임 확인이 필요 없다(S7 9-3).
- 원본 맵의 실제 STRx 산출물(TEP 경로)과의 대조는 하지 않았다(S7 9-4) — eudext 는 원본 Lua 함수 결과와 바이트가 같다.

### WP7 `shape`·`plot` — 맵 12

에뮬레이터에서는 찍힌 좌표·순서·프레임이 참조 모델과 같고(맵 자체 점검 15 / 15), 좌표는 헤드리스 TEP 와 같다(`tests/t_shape.py`).
남은 것은 **SC:R 화면에서 모양·방향이 CB Paint 원본과 같게 보이는지**(눈으로 보는 항목)와 속도 체감이다.

**확인용 맵**: `python eudext/tools/build.py euddraft eudext/examples/plot_ingame.eds --work <작업 폴더>` 로 빌드한 `plot_ingame_out.scx` 를
StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1). 화면이 맵 가운데(2048, 2048)로 옮겨지고 약 23초 동안 단계 5개가 돈다.
(Windows 빌드: `python eudext\tools\build.py euddraft eudext\examples\plot_ingame.eds --work %TEMP%\eudext_work\plot_ingame`.
도형 계산에 lupa 가 필요하다 — eds 에 VenvSite 를 적지 않았고, `eudext.shape` 가 `%USERPROFILE%\.venvs\euddraft011_site` 를 찾는다.
다른 곳에 두었으면 환경 변수 `EUDEXT_LUPA_SITE` 로 알려 주거나 eds 부트 줄에 `VenvSite : <폴더>` 를 더한다.)
만든 유닛은 P1 것이다 — 끝날 때까지 건드리지 않는다. 공중 유닛이라 서로 겹치면 조금 밀릴 수 있다(모양만 보면 된다).
결과는 화면 사진·짧은 영상이나 글로 알려 주면 된다. 화면 줄 머리 `[D7-n]` 이 아래 항목이다.

좌표는 정확 반올림 수학 — 원본 플러그인 측정과 일치(2026-09-17 Windows). `shape.CX` 는 Lua `math.sin/cos/tan/asin/acos/atan/exp/log` 를
`eudext._crmath` 로 바꿔 계산한다(OS 무관). 원본 플러그인 TrigEditPlus3.0.sdp 의 CRT 수학을 기계어 그대로 불러 잰 값과 도형 표본 1,592개에서
좌표가 모두 같았다. `work\ingame_auto_maps\12_plot_check.scx` 와 통합 맵 단계 13 은 2026-09-18 에 Windows 에서 다시 빌드해 지금 값이다
(그 전 Ubuntu glibc 빌드는 별(②)의 4점이 1px 달랐다 — 점 5·7 의 y 24 → 23, 점 19·23 의 y 48 → 47). `19_spawn_check.scx` 의 좌표표는 그대로다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| D7-1 | **[필수]** 정적 도형(CB Paint → lupa → 좌표표 → 루프 찍기)의 **모양·방향·찍는 순서**가 CB Paint 원본(CtrigAsm CSPlot/CAPlot)과 같은가, 그리고 런타임 회전(`pt.rotate`, CtrigAsm CA_Rotate)이 정적 회전(`CS_Rotate`)과 같은 쪽으로 도는가 | 맵 시작부터 약 5초. 4프레임마다 한 점씩 찍힌다. 기대 모양: **① 위 왼쪽 원(스커지, 중심 (1850, 1880))** — 가운데 한 마리 → **바로 위(12시, 32px)** → 시계 방향으로 6마리(육각형) → 다시 **12시(64px)** → 시계 방향 12마리(큰 고리). **② 위 오른쪽 별(뮤탈, 중심 (2230, 1880), `CSMakeStar(5, 144, 48, 0, CS_Level('Star', 5, 3), 0)`, 31마리)** — 가운데 → 안쪽 오각 → 바깥 별. 바깥 끝점은 아래 한 개 (0, +96), 좌우 (±91, +29), 위쪽 두 개 (±56, −77) — 원본 CB Paint 로 같은 식을 찍은 모양과 같으면 된다. **③ 아래 왼쪽 막대(레이스)** — 중심 (1800, 2260)에서 **위쪽(12시)** 으로 32px 간격 5마리. **④ 아래 가운데 막대(스카우트, 정적 `CS_Rotate(막대, 90)`)** — 중심 (1950, 2230)에서 **오른쪽(3시)** 으로 5마리. **⑤ 아래 오른쪽 막대(커세어, ③ 막대를 실행 중 `pt.rotate(90)`)** — 중심 (2150, 2230)에서 **오른쪽(3시)** 으로 5마리, ④ 와 같은 모양. 약 5초 뒤 `[D7-1] 찍기 끝` 줄. 모양·순서가 다르거나 ④·⑤ 가 서로 다른 방향이면 사진과 함께 알려 준다 | shape 공개(D5·D6 확정), spawn(WP12)의 도형 좌표·회전 방향 | **2026-09-18 인게임: 실패(게임 동작)** — 순서·원 2번째 점(0, −32)은 맞고 **자리 102/211 이 어긋났다**. 몸집이 큰 공중 유닛(뮤탈·레이스·스카웃·커세어)은 점 간격(6~32px)이 충돌 상자보다 작아 게임이 만든 유닛을 **밀어낸다**(`NoAirCollision` 을 쓰지 않는다). 자리 판정은 스커지 플로터만 하고 밀린 수는 기록만 한다 |
| D7-2 | 속도(per_tick·delay)가 뜻대로인가 | 약 8초 뒤 `[D7-2]` 줄과 함께 원 두 개: **왼쪽(스커지)은 한 프레임에 6마리씩 4프레임(약 0.2초)에 끝**, **오른쪽(뮤탈)은 8프레임마다 6마리씩 25프레임(약 1초)에 끝**. `[D7-2] 두 원 끝` 줄. 체감이 크게 다르면 알려 준다(초당 프레임은 게임 속도 "가장 빠름" 기준 약 24) | plot 문서(프레임 단위 설명) | **2026-09-18 인게임: 통과** (plot 단계 — 프레임별 생성 수 [6,6,6,1], 간격 3·24) |
| D7-3 | LoopMax 스케줄(`Shape.sweep`, theSeed GunFadeShape 방식)이 선단을 고른 속도로 옮기는가 | 약 12.5초 뒤 `[D7-3]` 줄. 가운데 가로로 긴 다이아몬드(가로 512 × 세로 192, 스커지 51마리)가 **왼쪽 끝부터 한 열(32px)씩 4프레임마다 오른쪽으로** 채워진다(17열, 약 2.7초). 가운데 열(7마리)도 가장자리 열(1마리)과 같은 박자로 나아가면 정상 | spawn 의 페이드 연출(WP12) | **2026-09-18 인게임: 통과** (plot 단계 — 17열 스케줄, 간격 64) |
| D7-4 | repeat·stop 과 점 순서 | 약 17.5초 뒤 `[D7-4]` 줄. 가운데 원(레이스)이 2프레임마다 2마리씩 그려지고(12시부터 시계 방향), 다 그리면 **지워지고 다시** 그려진다. 세 번 그린 뒤 멈추고 마지막 원이 남는다. `[D7-4] 원 3 번 그림 (3), 만든 점 211 (211)` | plot 문서(repeat) | **2026-09-18 인게임: 통과** (plot 단계 — 3바퀴, 만든 점 211) |
| D7-5 | 맵 자체 점검(런타임 회전 = 정적 회전 5점, busy/done 시점 7개, 반복 횟수, 만든 수) | 약 22.5초 뒤 **`[D7-5] 점검 15 / 15 (같으면 정상, 기대 15)`**. 빨간 `[D7] 점검 n 다름 (프레임 f)` 줄이 뜨면 그 줄을 알려 준다 | 없음(확인만) | **2026-09-18 인게임: 통과** (plot 단계 — 점검 15/15) |
| D7-6 | (권장) 원본 TEP(SCMDraft 2 + TrigEditPlus 3.0, 실제 SCMDraft 프로세스)가 CB Paint 별의 경계 좌표를 eudext 와 같게 내는가 — `CSMakeStar(5,144,96,0,CS_Level('Star',5,3),0)` 의 `S[7]`(6번째 점, y 참값 48 → double 계산 47.99999999999999)과 `S[21]`(20번째 점, 95.99999999999999). 플러그인 기계어를 따로 불러 잰 값은 47·95 였다. SCMDraft 안에서는 x87 정밀도 설정 등 호스트 환경이 다를 수 있어 확인해 두면 좋다 | 아래 스크립트를 SCMDraft 2 의 TEP 3.0 에 붙여 넣고(`dofile` 경로는 실제 `CB Paint v2.5.lua` 위치로) 컴파일·저장한 뒤 맵을 **혼자** 연다. 맵 시작 직후 **`D7-6: 47 95 (eudext 와 같음)`** 이 뜨면 정상. `D7-6: 48 …` 이나 `D7-6: 다른 값` 이 뜨면 그 줄을 알려 준다(TEP 트리거 편집기에서 P1 데스 칸 0·1 의 SetDeaths 값을 직접 읽어도 된다 — 47·95 기대) | 없음(확인만). 다르면 `_crmath`(정확 반올림)과 원본의 차이 → `shape` 수학을 원본 값에 맞출지 결정 | |

D7-6 스크립트 (TEP 3.0, 빈 맵이나 `testing/base.scx` 사본에):

```lua
dofile("C:/Users/whatd/Desktop/Stormcoast Fortress/ScmDraft 2/MapSource/Library/CB Paint v2.5.lua")
local S = CSMakeStar(5,144,96,0,CS_Level('Star',5,3),0)
Trigger { players={P1}, conditions={Always()}, actions={
  SetDeaths(P1, SetTo, bit32.band(S[7][2],0xFFFFFFFF), 0),
  SetDeaths(P1, SetTo, bit32.band(S[21][2],0xFFFFFFFF), 1) }, flag={preserved} }
-- 확인 줄 (위 트리거 다음에 실행된다)
Trigger { players={P1}, conditions={Deaths(P1, Exactly, 47, 0), Deaths(P1, Exactly, 95, 1)}, actions={DisplayText("D7-6: 47 95 (eudext 와 같음)", 4)} }
Trigger { players={P1}, conditions={Deaths(P1, Exactly, 48, 0)}, actions={DisplayText("D7-6: 48 (eudext 는 47 - 알려 주세요)", 4)} }
Trigger { players={P1}, conditions={Deaths(P1, AtMost, 46, 0)}, actions={DisplayText("D7-6: 다른 값 (47 보다 작음 - 알려 주세요)", 4)} }
Trigger { players={P1}, conditions={Deaths(P1, AtLeast, 49, 0)}, actions={DisplayText("D7-6: 다른 값 (48 보다 큼 - 알려 주세요)", 4)} }
```

`S[1]` 은 점 수(31)라 `S[7]` = 6번째 점(34.87…, 47.99…), `S[21]` = 20번째 점(69.75…, 95.99…)이다(eudext `tests/t_shape.py` 가 같은 식을 확인한다).
헤드리스 tepc(Windows mingw 판·Linux glibc 판)는 이 두 칸을 48·96 으로 낸다 — C 수학 라이브러리 차이(t_shape 의 알려진 예외).

참고: 찍기 로케이션은 기준 맵의 26번(이름 "Location 0", (0,0,0,0))이고 점마다 옮겨진다. 스커지·뮤탈·레이스·스카우트·커세어는 단계가 바뀔 때 `RemoveUnit` 으로 지운다(맵 리빌러는 남는다).

### WP14 `bullet` — 맵 10

`bullet` 의 칸 쓰기·실패 판정·방향 계산은 에뮬레이터(유닛 모델 + 실패 주입, 5,462 판정)로 확인했다. 남은 것은 **SC:R 이 그 칸들을
어떻게 쓰는가**(탄이 실제로 어느 쪽으로 날아가는지, 음수 최고속도 관례, 의도를 모르는 칸)다. 정본 명세 `docs/spec/S4_bullet.md` 7절.

**확인용 맵**: `python eudext/tools/build.py euddraft eudext/examples/bullet_ingame.eds --work <작업 폴더>` 로 빌드한
`bullet_ingame_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1 사람 + P2 컴퓨터 = 표적 주인).
(Windows 빌드: `python eudext\tools\build.py euddraft eudext\examples\bullet_ingame.eds --work %TEMP%\eudext_work\bullet_ingame`)
약 1분(700 트리거 사이클) 동안 차례로 쏘고 화면에 `[D14-번호]` 줄을 띄운다. 괄호 안이 기대값이다. **화면 줄 사진 + 눈으로 본 것**
(탄이 날아간 쪽, 표적 마린이 죽었는지, 선택·드래그)을 알려 주면 된다. dat 설정은 맵 안에서 `BulletDat` 로 한다(EUD Editor 없음):
208 = UE_RE 탄막 유닛(무기 127 → flingy 106, 그림 344 마그나 펄스, 최고속도 −8001), 210 = 무기 128(flingy 158 야마토, 최고속도 −2561,
수명 64), 204 = 껍데기(지상 무기 127).

화면 위치(4096 × 4096 맵): D14-3 가운데 → D14-1 위쪽 줄(y 700, 왼쪽부터 8발) → D14-2 둘째 줄(y 1600, 8발) → 가까운/먼/같은 점(y 2400·2900)
→ D14-5 (y 3400) → D14-6 (y 3000 다섯 개) → D14-7 (오른쪽 아래) → D14-8 (y 3700 세 발).

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| D14-1 | **[필수]** `bullet`(ue_re, 음수 최고속도 flingy)의 탄이 **facing + 128** 쪽으로 날아가 그쪽 표적을 맞히는가. 8방향 | 위쪽 줄 8곳에서 한 발씩(2초 간격). `[D14-1] 진행 h 로 쏨 … facing=f(f)` 뒤 1초에 `[D14-1] 진행 h 표적 죽음=1`. 탄이 표적 반대쪽으로 가면(facing 쪽) 알려 준다. 표적이 안 죽으면 탄이 간 쪽·멈춘 곳을 알려 준다(무기 설정에 따라 끝점에서만 터질 수 있음) | bullet 공개(`reverse=True` 기본 관례), spawn(WP12) 총알 콜백 | **2026-09-18 인게임: 실패** — 탄이 **하나도 안 만들어졌다**(19발 전부 `epd=0`, 표적 8기 모두 살아 있음). 원인: 탄막 유닛 208·210·204 는 문·함정 = **Building 플래그**라 `CreateUnit` 이 배치 상자(`buildingDimensions`)로 자리를 검사해 거절한다. `BulletDat` 이 `bounds`·`placement` 를 쓰고 Building 을 끄도록 고쳤다(UE_RE EUD Editor 와 같은 칸 — S4 2.6). D14-0 계측을 더했다 |
| D14-2 | **[필수]** `bullet_to` 가 8방향·가까운 목표(1~2픽셀)·먼 목표(2000픽셀)에서 목표를 지나가는가, 출발 = 목표에서 튕기지 않는가 | 둘째 줄: 표적 300 픽셀 앞에서 표적 쪽으로 8발, `[D14-2] … facing=f(f) … 표적 죽음=1`. 이어서 `[D14-2] 가까운 목표 … 먼 목표 … 출발=목표 facing=128(128)` 과 `가까운 표적 죽음 … 먼 표적 죽음` | bullet_to 공개, S4 6.1 방향표(= CtrigAsm `f_Atan2`) 확정 | **2026-09-18 인게임: 실패** — D14-1 과 같은 원인(생성 실패). 고친 뒤 다시 본다 |
| D14-3 | **[필수]** 유닛 칸이 가득(1700)일 때 `bullet`·`bullet_to`·`bullet_at` 이 0 을 돌려주고 오류·튕김이 없는가 | 시작 직후 P2 맵 리빌러로 칸을 채운 뒤 `[D14-3] 유닛 칸 가득(…): bullet=0(0) bullet_to=0(0) bullet_at=0(0)` 줄이 뜨고 게임이 계속되면 OK. 채운 수(기준 맵이면 1634 근처)도 알려 준다 | bullet 공개(실패 판정 = units B-10-1 과 같음) | |
| D14-5 | 만든 탄막 유닛의 위치(+0x28)가 로케이션 좌표 (x, y + y_offset) 와 같은가 — 같으면 본문에서 위치 읽기(실행 34)를 뺄 수 있다(R4a A.5). `y_offset` 0 과 +10 의 발사 위치 차이 | `[D14-5] 만든 위치 y_offset 0: (x,y) 기대 (1000,3400) / +10: (x,y) 기대 (1200,3410)` 줄 + 두 탄의 출발점이 눈에 띄게 다른지 | 위치 읽기 생략(결정 요청 D?14-3) | **2026-09-18 인게임: 실패** — 생성 실패 |
| D14-6 | **[필수]** ue_re 가 쓰는 **의도를 모르는 칸** `+0xA3 ← 0`(energy 윗바이트)·`+0xDC ← 0x200104`(마스크 0x300104: 공중·탐지 필요·충돌 없음 켬, IsNormal 끔)·`+0xE4 ← 0`(visibilityStatus)이 무엇을 바꾸는가 | y 3000 에 10초 사는 탄막 유닛 5개(왼쪽부터 ①세 칸 모두 ②안 씀 ③A3 만 ④DC 만 ⑤E4 만, 아래로 계속 쏨). 각각 **클릭 선택·드래그 선택이 되는지, 서로 밀리는지(겹쳐 있는지), 안개 속에서 보이는지**를 비교해 알려 준다. `[D14-6] 만든 직후(②) … / ue_re 뒤(①) …` 줄의 값도 | recipe 기본값(ue_re 의 세 칸을 남길지 — 결정 요청 D?14-3) | **2026-09-18 인게임: 실패** — 생성 실패(선택 표도 빈 채) |
| D14-7 | 수명(+0x110)을 쓰지 않으면 쏜 뒤 탄막 유닛이 남는가(주문 135 가 유닛을 없애는가) | 오른쪽 아래 두 곳(3200 = 수명 안 씀, 3600 = 수명 12). 3초 뒤 `[D14-7] … 주문=… 종류=… 스프라이트=…` — 수명 안 씀 쪽이 화면에 남아 있는지도 | recipe `minimal` 의 수명 기본값(None) | **2026-09-18 인게임: 판정 못 함** — 생성 실패로 값이 모두 0 |
| D14-8 | **[필수]** `shell`(204 로 만들고 +0x64 만 210 으로) 방식에서 **바뀐 종류의 무기**로 쏘는가 | y 3700 에서 위로 세 발: 왼쪽 = 204→210(`종류=210(210)`), 가운데 = 210 직접(야마토), 오른쪽 = 208(마그나 펄스). 왼쪽 탄이 가운데와 같은 모양이면 바뀐 종류의 무기, 오른쪽과 같으면 껍데기(204, 무기 127)의 무기 | shell 옵션 공개(G2R·Galaxy.py 이식) | **2026-09-18 인게임: 실패** — 생성 실패(껍데기 204 → 210 도) |
| D14-4 | 같은 프레임에 같은 flingy 로 다른 속도를 쓰면 모두 마지막 속도로 나가는가(문서화용) | 이 맵에는 없다. 맵 코드에서 `DoActions(k.speed_actions(500)); bullet.bullet(…); DoActions(k.speed_actions(4000)); bullet.bullet(…);` 을 한 프레임에 | 문서(R4a A.4) | **2026-09-18 인게임: 실패** — 생성 실패. flingy 최고속도 칸은 −4001(= reverse(4000))로 **제대로 써졌다** → dat 쓰기 자체는 된다 |
| D14-9 | `height_actions`(올바른 elevation 주소)로 총알 높이·그리기 층이 바뀌는가, 생성 전에 써야 하는가 | 이 맵에는 없다(예제 `bullet_example` 이 `height=12`·`height_actions(20)` 을 쓴다) | height 문서 | **2026-09-18 인게임: 판정 못 함** — 생성 실패. 맵의 `elevation[208]` 읽기 주소가 틀려 있었다(`dat.addr` 값에 번호를 또 더했다) — 고쳤다 |
| D14-10 | 소유자 사람/컴퓨터에 따른 시야·총알 약 4096 표시 한도(GB 8605~8610) | 대량 패턴 맵에서 | 사용 안내 | |
| D14-11 | `[unlimiter]` 켬/끔에서 한 프레임 80발 이상(UE_RE Sans 규모) | 대량 패턴 맵에서 | 사용 안내 | |
| D14-12 | 2인 이상 멀티에서 디싱크 없음(공유 상태만 씀) | 멀티 맵에서 `bullet` 을 매 프레임 | 없음(확인만) | |
| D14-13 | `BulletDat` 로만 설정한(EUD Editor 없이) 새 맵에서 UE_RE 208 과 같은 모양·동작 | 이 맵이 그 경우다(208 은 UE_RE 값 그대로 — 시험이 UE_RE `EUDEditorDat.lua` 의 결과값과 대조함). D14-1 의 탄 모양이 UE_RE 와 같은지 | BulletDat 기본값 확정 | |

에뮬레이터가 이 맵에서 확인한 것(`tests/t_bullet.py` `ingame_emulate`, 700 사이클): 오류 없음, 탄 31발 생성(D14-3 에서는 0 반환 3번),
방향 불일치 0, 표적 18, 종류 교체 210, dat 값(flingy 106 최고속도 0xFFFFE0BF, 204 지상 무기 127, 210 지상 무기 128·특수 능력 0x20000004).
모델에는 탄·피해가 없으므로 `표적 죽음` 은 인게임에서만 본다.

"확인 순서" 표(`tools/ingame_maps.py` `MAPS`)에 넣을 줄(번호는 합칠 때):
`("10", "bullet_check", os.path.join(EX, "bullet_ingame.eds"), "single", "eds", "D14-1~8 (총알 방향·실패 0·의도 모르는 칸·종류 교체)", "혼자(P2 컴퓨터). 약 1분 — [D14-번호] 줄과 탄이 간 쪽")`

### WP16 `bgm` — 맵 11

확인 맵: `examples/bgm_ingame.eps` + `examples/bgm_ingame.eds`(기준 맵 `testing/base_multi.scx`, `[MSQC]` 포함).
저장소에는 소리 파일이 없으므로 **빌드 도우미로 빌드**한다(소리 합성 → `[MSQC]` 줄 확인 → euddraft):

```
C:\Users\whatd\.venvs\eud081\Scripts\python.exe eudext\examples\bgm_ingame_build.py --work %TEMP%\eudext_work\bgm_ingame [--ogg <진짜 .ogg 파일>]
→ %TEMP%\eudext_work\bgm_ingame\build\bgm_ingame_out.scx
```

(Ubuntu: `.venv/bin/python eudext/examples/bgm_ingame_build.py --work /tmp/eudext_work/bgm_ingame`.)
혼자 열어도 D16-1·2·3·5·6·8·9 가 차례로 돈다(게임 속도 **가장 빠름** 기준 시각, 화면 줄머리 `[D16-번호]`).
D16-4 는 관전자로 들어간 PC, D16-7 은 2인 이상에서 본다(약 40초 뒤 `[D16-7]` 안내가 뜬 다음 N·M·B 키).
에뮬레이터는 이 맵의 소리 순서·횟수를 확인했다(`t_bgm.py` ingame_emulate — 1,000 사이클, 이 PC 소리만: d16_a 4, d16_b 2,
d16_c 3, 스윕 144, 없는 파일 2, 없는 알림 2, ogg 이름 2, 효과음 8). 소리가 실제로 들리는지·틈이 있는지는 인게임에서만 알 수 있다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| D16-1 | **[필수]** `PlayWAV` 문자열 칸을 실행 중에 채워도(방식 2, `method="patch"`) SC:R 이 **새 소리**를 내는지 (S5 B.11-1) | 약 1초 뒤 ① 440Hz(스위치 방식), 약 4초 뒤 ② 660Hz(문자열 칸 채우기). **②가 ①과 다른(높은) 음으로 들리는지**, 안 들리거나 ①과 같은 음인지 알려 준다 | 7절 D18 — 기본 재생 방식(지금 `switch`, 칸마다 트리거 1. `patch` 는 칸 수와 무관한 12 트리거) | |
| D16-2 | `PlayWAV` 를 2~3번 연속 부르는 기존 관례의 이유(음량? 누락?) — 1번으로 충분한지 (B.11-2) | 약 7초 뒤 ③ 880Hz 를 PlayWAV **1번**, 약 9초 뒤 ④ 같은 음을 **2번**. 크기 차이·빠짐(가끔 안 들림)이 있는지 | `Player(repeat=)` 기본값(지금 2) | |
| D16-3 | **[필수]** 조각 이어 재생의 틈·겹침(실측 길이 그대로 vs −42ms 보정), 일시정지 중 `0x51CE8C` 가 흐르는지 (B.11-3) | 약 12초 뒤 ⑤ 300→900Hz 스윕을 250ms × 24조각(보정 0), 약 19초 뒤 ⑥ 같은 스윕(−42ms). 이어진 소리처럼 들리는지, 조각 사이 **틈·딸깍·겹침**이 있는지 ⑤⑥ 각각 알려 준다. ⑤ 도중에 **F10 으로 일시정지**했다 풀고: 멈춘 동안 소리가 계속 나는지, 풀린 뒤 `[D16-3] 조각 n` 숫자가 건너뛰는지(dt 가 2500 을 넘으면 그 사이클은 0 으로 본다) | `lead_ms` 기본값(지금 0), `max_elapsed` 를 local 모드에도 적용하는 것(7절 D30) | |
| D16-4 | 관전자(128~131) PC 에서 `f_getuserplayerid()` 값과 재생 여부, `DELETE` 로 이 PC 만 끄기 (B.11-4) | 2인 이상 + 관전자 1명. 관전자 화면의 `[D16-4/7] 이 PC n` 값(128~131), ①~⑩ 소리가 관전자에게도 들리는지, D16-7 의 동기 곡이 들리는지, `DELETE` 를 누를 때마다 동기 곡(다음 음부터)이 꺼지고 켜지는지(채팅 중에는 안 바뀜) | 관전자 칸 설계(칸 8 하나를 관전자 넷이 같이 씀) | |
| D16-5 | MPQ 에 없는 파일 이름으로 `PlayWAV` 할 때 동작 (B.11-5, UERE 의 `BGM_Skip.ogg` 사례) | 약 26초 뒤 ⑦ 없는 파일 재생, 약 28초 뒤 ⑧ 재생 중 요청 → 없는 알림 소리. **게임이 멈추거나 오류 창이 뜨지 않고** ① 음이 끝까지 나면 정상 | `busy_sound`·`add=False` 안내 | |
| D16-6 | 확장자만 `.wav` 인 Ogg 재생 (B.11-6, S5 B.6 실패 5개 파일) | 빌드 때 `--ogg <아무 .ogg 곡>` 을 준다(그 파일이 `d16_ogg_as.wav` 로 들어간다). 약 30초 뒤 ⑨ 에서 그 곡이 들리는지. `--ogg` 없이 빌드했으면 건너뛴다 | 형식 판별 안내(지금: 앞 4바이트로 판별해 길이를 잰다) | |
| D16-7 | synced: 2인 이상에서 공유 상태가 같게 흐르는지(디싱크 없음), **방장이 나가도** 경과 시간 공급이 이어지는지 (B.11-7) | 2~3인(가능하면 배틀넷). 약 40초 뒤 아무나 **N** → 모든 PC 에 음 20개(500ms 씩)가 이어지고 `[D16-4/7] … 조각 n` 이 **모든 PC 에서 같게** 오르는지. **M** = 누른 사람만 소리 끄기/켜기(공유 끔 비트 — 다른 PC 에는 그대로), **B** = 정지. 재생 중 가장 작은 번호의 플레이어(방장 몫)가 나가도 조각 번호가 계속 오르는지, 디싱크가 나지 않는지 | synced 모드 공개(sync 의 B13 과 함께), 7절 D28(걸쇠 방식) | |
| D16-8 | 동시에 울릴 수 있는 소리 수 한도 (B.11-8) | 약 33초 뒤 ⑩ 스윕 + 효과음 8개(낮은 음부터 8단)를 한 프레임에. 효과음이 몇 개 들리는지, 스윕이 끊기는지 | 안내(조각 곡 + 효과음 수) | |
| D16-9 | 음원 수백 개 넣은 맵의 로딩 시간 (B.11-9) | 이 맵에는 소리 파일이 약 370개(20ms 무음 300개 포함) 들어 있다. 방 만들기~게임 시작까지 걸린 시간(초), 소리 파일 없는 맵(`units_ingame`)과의 차이 | 안내 | |

에뮬레이터가 가정한 것(인게임 결과로 고친다): PlayWAV 는 그 순간 CP 의 PC 에서만 들린다(관전자 CP 128~131 포함), SC `Subtract` 는
0 에서 멈춘다, `0x51CE8C` 는 실제 시간 ms 의 보수라 시간이 흐르면 줄어든다(bgmplayer 와 같은 가정), MSQC `val` 은 받지 못한 사이클에 −1.

## 배치 E (WP6b display, WP12 spawn, WP17 textfx/chat, WP18 scrdb)

### WP6b `display` — 맵 25

확인용 맵: `eudext/examples/display_ingame.eds` (+ `display_ingame.eps`, 기준 맵 **`testing/base_multi.scx`** — P1~P4 사람 칸).
빌드: `python eudext/tools/build.py euddraft eudext/examples/display_ingame.eds --work <작업 폴더>` → `display_ingame_out.scx`.
(일괄 빌드 `tools/ingame_maps.py` 의 `MAPS` 표 줄 제안: `("NN", "display_check", os.path.join(EX, "display_ingame.eds"), "multi", "eds",
"E6-1~10 (DisplayPrint 대체: 관전자·13번째 줄·TBL NUL·이름 주소·0x0D 폭)", "혼자 P1(E6-1 은 관전자 PC 하나 더). 6초마다 한 쪽씩 9쪽")` — 번호는 합칠 때.)

여는 방법
- 대부분은 **혼자 P1** 로 연다. 시작하면 P1 마린 한 기가 생긴다(E6-4 용).
- **E6-1(관전자)** 은 PC 두 대: 한 대는 P1, 다른 한 대는 **관전자 칸**(커스텀 게임 방에서 관전자 슬롯을 열고 들어감)으로 같은 맵에 들어간다.
  관전자 PC 화면을 본다. (관전자 슬롯을 열 수 없는 방식이면 알려 달라 — 다른 방법을 찾는다.)
- 맵은 첫 사이클에 버퍼 7개를 기대 바이트와 비교하고(자체 점검), 약 6초(72 사이클)마다 한 쪽씩 9쪽을 돈다. 쪽마다
  `[E6-8] 자체 점검 N / M (틀린 번호 X)` 줄과, 매 프레임 같은 줄에 고정된 `[E6-2] 고정 줄 1·2` 가 함께 보인다.
  에뮬레이터에서는 자체 점검 **7 / 7, 틀린 번호 0** 이고 모든 `[E6-n]` 줄이 뜬다(tests/t_display.py `ingame_emulate`). euddraft 0.11 빌드 통과.
- 화면 사진이나 "E6-3 보임" 같은 글로 알려 주면 된다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| E6-8 **[필수]** | 자체 점검: display 의 틀 버퍼·13번째 줄·TBL 쓰기가 실제 게임에서도 에뮬레이터와 같은 바이트인가 (numfmt 직접 쓰기·Man 배치·Pick 단어 복사·Bytes 마스크 쓰기·넓힌 Per 포함) | 아무 쪽에서나 `[E6-8] 자체 점검 7 / 7 (틀린 번호 0)` 인지 본다. 다르면 틀린 번호를 알려 준다 | 없음 (display 전체의 전제) | **2026-09-18 인게임: 통과** — 자체 점검 7 / 7 (틀린 번호 0). **13번째 줄·TBL 바이트까지 게임에서도 에뮬레이터와 같았다** — 그 뒤 E6-3 에서 멈췄으므로 쓰기 자체는 되고 무엇이 EUD ERROR 를 냈는지는 25b 맵으로 좁힌다. 통합 맵에서는 이 두 항목을 빼 5 / 5 가 된다 |
| E6-1 **[필수]** | **관전자 표시**(S3 8.3-1, 11-3): CP 128~131 로 DisplayText 하면 관전자 화면에 뜨는가. `players.Everyone`·`players.Observers`·`dp.LOCAL` 세 경로 | 0쪽: 관전자 PC 에 `[E6-1] 모두…` · `[E6-1] 관전자에게만…` · `[E6-1] LOCAL: 이 PC 번호 = 128~131` 세 줄이 뜨는지, P1 PC 에는 "관전자에게만" 줄이 **안** 뜨고 LOCAL 번호가 0 인지 | 관전자에게 글을 띄우는 맵 전부(9맵 HumanPlayers) | |
| E6-3 **[필수]** | **13번째 줄**(S3 8.3-3, G8 1.7): `show_line13` 이 CreateUnit 실패 트릭 뒤에 우리 글을 보이는가(오류 문구·오류 소리가 우리 글에 덮이는가) | 1쪽: 화면 아래 오류 줄에 `[E6-3] 13번째 줄 <숫자> — 오류 소리 없이…` 가 뜨는지, SC 의 "유닛을 더 만들 수 없습니다" 문구가 보이는지·소리가 나는지 알려 준다 | DPS 69곳·UERE 15곳의 Er 옮기기 | **2026-09-18 인게임: 실패(게임이 EUD ERROR 0xFF9BE98B 로 멈춤)** — 13번째 줄에 글은 **써졌지만**(스냅숏에 '[E6-3] 13번째 줄 2 — …' 남음) 바로 뒤 `dbg.mark` 부터 기록이 없다. 자체 점검(E6-8)의 짧은 13번째 줄 쓰기는 한 프레임 앞에서 통과했다. 통합 맵에서 뺐고 25b_display_bisect 18단계로 좁힌다 |
| E6-4 **[필수]** | **TBL 끝 NUL**(S3 8.3-4, D16): `set_tbl(eos=True)` 로 쓴 뒤 버튼·이름 칸 글이 정상이고 뒤에 옛 글자가 남지 않는가 | 2쪽: 마린을 선택하고 이름 칸이 `[E6-4] 마린 <숫자>` 로 바뀌는지(뒤에 "Terran Marine" 잔재 없음), 숫자가 6초 동안 한 번 바뀌는지 | DPS TBL 83곳 | **2026-09-18 인게임: 미실행(튕길 위험)** — E6-3 에서 멈췄다. 다만 **같은 TBL 쓰기가 E6-8 자체 점검(한 프레임 앞)에서는 통과**했으므로 TBL 쓰기 자체는 SC:R 에서 된다. 통합 맵에서 뺐고 25·25b 맵에서만 돈다 |
| E6-4b | 원본 방식(`eos=False`, U+2009 없음): 짧게 쓰면 앞 쪽 글자가 뒤에 남아 보이는가 (원본 DisplayPrintTbl 동작 확인) | 3쪽: 이름 칸이 `[E6-4b]` 뒤에 앞 쪽 글의 나머지(`마린 …`)가 붙어 보이는지 | D16 권장안 확정 | **2026-09-18 인게임: 미실행(튕길 위험)** — E6-3 에서 EUD ERROR. 통합 맵에서 뺐고 25·25b 맵에서만 돈다 |
| E6-5 **[필수]** | **이름 두 주소**(S3 8.3-5, 11-1, D15): 0x57EEEB(eudplib·display `PName`)와 0x6D0FDC(DPL 표, `numfmt.dp.name20`)가 같은 이름인가 — 시작 때 담은 캐시(`cache=True`)·이 PC 이름(`LocalName`)도 | 4쪽: 네 이름이 모두 같은지(클랜 태그·한글·16바이트 넘는 이름이면 더 좋다 — name20 은 16바이트까지만). 모두 P1 색(빨강) | D15 확정, PName 옮기기 | **2026-09-18 인게임: 미실행** — 그 앞 E6-3 에서 게임이 멈췄다 |
| E6-7 **[필수]** | **0x0D 가 폭을 차지하지 않는가**(S3 8.3-7) — display 틀 방식의 전제(자리의 남는 바이트가 0x0D). 옛 DisplayPrint 고정 폭(`numfmt.dp.*`)이 옛 맵과 같은 위치에 보이는가 | 5쪽: `[E6-7] |-10|1234만5678|12.5|42|42|` 모양으로 대괄호 사이에 빈틈이 없는지(두 번째 줄 기대와 비교). 틈이 보이면 사진 | display 전체(D?6-1), numfmt D5-8 | |
| E6-2 | `begin_pinned/end_pinned`(FixText) 안의 두 줄이 매 프레임 같은 줄에 고정되는가, 채팅을 치면 어떻게 되는가 (S3 8.3-2) | 모든 쪽: `[E6-2] 고정 줄 1 — 프레임 N` 과 `고정 줄 2` 가 위로 밀려 올라가지 않고 숫자만 바뀌는지. 채팅을 몇 번 쳐 보고 줄이 어떻게 되는지 알려 준다 | FixText 18곳 | **2026-09-18 인게임: 미실행** — display 단계에서 멈춰 assist 단계까지 못 갔다 |
| E6-6 | `Template` + `SetMissionObjectives`(S3 8.3-6): 임무 목표 창을 연 채로 카운터가 바뀌는가, 창을 다시 열 때만 바뀌는가 | 시작 때 임무 목표를 `[E6-6] 임무 목표 카운터 N` 으로 정했다. 8쪽 안내가 뜨면 메뉴(F10) → 임무 목표를 열어 숫자가 움직이는지 본다 | Seed MissionObjective 옮기기 | **2026-09-18 인게임: 미실행** — visual 구간까지 못 갔다 |
| E6-9 | **긴 줄**(S3 11-12, D?6-10): 틀이 218바이트를 넘는 줄(0x0D 자리 포함 약 245B, 보이는 글은 짧음)의 끝 글자가 보이는가 | 6쪽: `[E6-9] 긴 줄 424242…42 끝(이 글자가 보이는지)` 에서 "끝(…)" 이 보이는지 | 줄 길이 검사를 경고/오류/무시 중 무엇으로 둘지 | **2026-09-18 인게임: 미실행** — 그 앞 E6-3 에서 게임이 멈췄다 |
| E6-10 | `every=24` + `pin=True`: 표시는 매 프레임 같은 줄, 숫자는 약 2초마다 바뀌는가 | 7쪽: `[E6-10] every=24 … → 숫자` 가 한 줄에 머물고 숫자가 2초 간격으로 바뀌는지 | 없음 | **2026-09-18 인게임: 미실행** — 그 앞 E6-3 에서 게임이 멈췄다 |

참고
- 옛 UERE `PName(V)` Er 경로가 실제로 틀린 이름을 찍는지(S3 8.3-8)는 **옛 맵(UERE)** 에서만 볼 수 있다 — eudext 에는 그 경로가 없다(변수 PName 은 값대로 찍힌다). 옮길 때 고칠지 판단용으로만 필요하면 UERE 에서 기부 문구를 확인해 알려 달라.
- 13번째 줄이 **유닛 1700 가득(0x628438 = 0)** 일 때도 보이는지(S3 8.3-3 뒷부분)는 이 맵으로는 볼 수 없다(유닛을 가득 채우는 맵이 필요). eudplib `f_raise_CCMU` 가 그 경우 저장·복원 액션을 끄는 것은 에뮬레이터로 확인했다.
- `hold=`(UERE 식 잠금)는 공유 SetDeaths 한 개라 에뮬레이터 확인으로 충분하다고 보았다(시험 hold·hold_fn).

### WP12 `spawn` (G_CB 식 소환 대기열) — 맵 19

에뮬레이터에서는 S1 9.1 표 A~P·9.2 벡터 전부·무작위 20만 점이 참조 모델과 같고, 확인 맵도 끝까지 돌아 자체 점검 11 / 11 이 나온다
(`tests/t_spawn.py`, `tests/t_spawn_xform.py`). 남은 것은 **SC:R 에서 실제로 그렇게 보이고 움직이는지**(유닛 생성 자리·명령·페이드 속도)와
원본과의 체감 비교다.

**확인용 맵**: `python eudext/tools/build.py euddraft eudext/examples/spawn_ingame.eds --work <작업 폴더>` 로 빌드한 `spawn_ingame_out.scx` 를
StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1).
(Windows: `python eudext\tools\build.py euddraft eudext\examples\spawn_ingame.eds --work %TEMP%\eudext_work\spawn_ingame`.
도형 계산에 lupa 가 필요하다 — `%USERPROFILE%\.venvs\euddraft011_site` 에 없으면 `EUDEXT_LUPA_SITE` 나 eds 부트 줄 `VenvSite : <폴더>`.)
- 기준 맵에는 P1(사람)·P2(컴퓨터)만 있어 **소환 주인은 P2(적)** 다(원본 theSeed·Stella 의 P6~P8 자리). P2 유닛이 보이도록 시작하자마자
  P1 맵 리빌러 121개를 격자로 깐다(12×12 격자 중 맵 밖 23점은 소환기의 경계 검사로 빠진다 — 그 자체가 확인 항목).
- 약 42초 동안 단계 7개가 돈다. 화면 줄 머리 `[E12-n]` 이 아래 항목이고, 줄마다 **기대 모양·수**가 들어 있다.
  결과는 화면 사진·짧은 영상이나 글로 알려 주면 된다. 빨간 `[E12] 점검 n 다름 (프레임 f)` 줄이 뜨면 그 줄을 알려 준다.
- 로케이션(기준 맵): 8 = (2048, 1365), 12 = (1365, 2048), 13 = 맵 가운데 (2048, 2048), 14 = (2731, 2048), 15 = (3413, 2048),
  16 = (683, 2731), 18 = (2048, 2731), 23 = (2048, 3413) = "본진". 26·27 은 소환기가 점마다 옮기는 로케이션이다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| E12-1 | **[필수]** 해처리 건작(S1 9.4-1): 부순 건물 자리(anchor)에 41점 저글링, lm max, 기본 어택 — **맵 오른쪽 끝·아래쪽 끝** 소환, 연속 두 건물, 넘침 문구 없음 | 1초 뒤 `[E12-1]` 줄. **오른쪽 끝 (4050, 1200)** 과 **아래 끝 (1500, 4050)** 에 저글링 네모(41점짜리 `CSMakePolygon(4, 32, 0, 41, 0)`)가 한 프레임 차이로 나타난다. 맵 밖으로 나가는 점은 빠져서 **줄에 적힌 수(32마리·32마리 — 41점 중 맵 경계 W−1·H−1 밖 9점씩 빠짐)** 만큼만 나오고, 모두 **아래 가운데 로케이션 23(본진)** 으로 어택 이동한다. 곧 `[E12-1] 만든 저글링 64 (기대 64), 넘침 0 (기대 0)`. 저글링이 맵 가장자리에서 **밀려나거나 안 생긴** 것이 있으면 수를 알려 준다(원본 theSeed 가 맵 오른쪽 1/3 에 건작이 안 나오던 버그의 확인) | S1 10.1-5·7, 맵 경계 규칙 | **2026-09-18 인게임: 통과** (spawn 단계) |
| E12-2 | **[필수]** 블랙홀 건작(S1 9.4-2): 좌표 중심, 페이드 스케줄(`Shape.sweep`), 옵저버 이펙트 "Vision", 몹은 사용자 핸들러(무적·제자리) | 15초 뒤 `[E12-2]` 줄. 화면 가운데에 **왼쪽 고리 + 오른쪽 구멍** 모양(73점)이 **왼쪽 끝부터 한 열(32px)씩 매 프레임** 채워진다(18열, 약 0.8초). 가운데 빈 6열에서도 **멈추거나 끊기지 않고** 이어진다(원본은 "G_CBPlot Not Found" 로 버리던 곳). 옵저버(시야)와 히드라가 같은 박자, 옵저버는 0.8초 간격으로 세 번 연달아 그려진다. 히드라 73마리는 **무적으로 서 있다가** 약 6초 뒤 `[E12-2] 히드라 풀림` 과 함께 본진으로 어택. 원본(theSeed 인페스티드 커맨드센터 130)과 **페이드 속도를 나란히 비교**할 수 있으면 알려 준다 — eudext 는 스케줄 포인터가 작업마다라 밴드 크기대로 나간다(원본 코드는 매 사이클 첫 밴드 수, S1 10-16) | S1 10-13·16 판단, D13 | **2026-09-18 인게임: 통과** (spawn 단계) |
| E12-3 | **[필수]** 보스 워프(S1 9.4-3) + **A-3 의 17·18**: 로케이션 중심, 한 도형에 네 유닛 층, 명령 `{Attack, 보스 로케이션}`, 보스 한 기 직접 소환 | 25초 뒤 `[E12-3]` 줄. 가운데(로케이션 13)에 Stella `SH_Warp` 36점 모양으로 **레이스 → 배틀 → 벌처 → 골리앗**이 2프레임 간격으로 차례로 나타나(층 사이 빈 프레임 1개 — 눈으로는 거의 동시) 모두 **오른쪽 로케이션 14 (2731, 2048)** 로 어택 이동한다. 원본의 오프바이원이면 한 칸 앞 로케이션 13(가운데 — 제자리)을 목표로 삼는다(S1 10-17). 0.4초 뒤 **영웅 배틀(노라드 II) 한 기가 로케이션 14 에** 나타난다(가운데면 다름 — `f_TempRepeat` 문자열 중심 오프바이원 S1 10-18). 곧 `[E12-3] 층 프레임 600 602 604 606 (2씩 커지면 정상)` | A-3(17·18), D13 | **2026-09-18 인게임: 통과** (spawn 단계) |
| E12-4 | A-3 의 19: 중심을 **1부터 번호**(15)로 준 작업이 그 로케이션에 나오는가 | E12-3 과 같은 때 `[E12-4] (A-3 의 19)` 줄. **오른쪽 끝 로케이션 15 (3413, 2048)** 에 영웅 질럿(피닉스) 5기가 가로줄로. 로케이션 14(2731, 2048)나 16(왼쪽 아래 (683, 2731))이면 다름 | A-3(19) | **2026-09-18 인게임: 통과** (spawn 단계) |
| E12-5 | (보조) 전역 회전(`rotate=sp.GLOBAL`, 원본 RotateTable "Main"): 소환 순간의 전역각을 점마다 읽는가, 회전 방향 | 32.5초 뒤 `[E12-5]` 줄. 가운데에 스커지가 3프레임마다 한 기씩, **12시 쪽에서 시작해 시계 방향으로 도는 나선**(10기)을 그린다. 반시계면 다름 | D5 확인(런타임 회전) | **2026-09-18 인게임: 통과** (spawn 단계) |
| E12-6 | (보조) 스킬 유닛(원본 RepeatType 8 SkillUnit + 명령 속성): 로케이션 중심·명령·removeTimer | 36초 뒤 `[E12-6]` 줄. 위 가운데(로케이션 8)에 브루들링 19마리 원 → **아래(로케이션 18)로 순찰**하다 **약 0.6초(15프레임) 만에 사라진다** | 스킬 유닛 이식 | **2026-09-18 인게임: 통과** (spawn 단계) |
| E12-7 | (보조) 스캔 이펙트(`scan_effect`, 원본 G_CB_TScanEff): 스프라이트 이미지·Draw Function 바꾸기와 되돌리기 | 38초 뒤 `[E12-7]` 줄. 왼쪽(로케이션 12)에 **이미지 429·색 16** 의 이펙트 원(19점)이 번쩍이고 **스캐너 스윕 유닛은 남지 않는다**. 그 뒤로 보통 스캔(있다면)·다른 유닛의 모양이 이상해지지 않는다(이미지 546·Draw Function 되돌림). 이미지 429 가 무엇으로 보이는지 알려 주면 된다 | S1 12-5(0x666458 = 스캐너 스윕 스프라이트 이미지 칸) | **2026-09-18 인게임: 통과** (spawn 단계) |
| E12-8 | 맵 자체 점검(생성 수·넘침·빈 열 사이클·층 간격·보스·마커·남은 작업) | 약 42초 뒤 **`[E12-8] 점검 11 / 11 (같으면 정상, 기대 11), 남은 작업 0 (0)`** | 없음(확인만) | **2026-09-18 인게임: 통과** (spawn 단계) |
| E12-9 | (권장) 체감 부하: 한 프레임 최대 255점 × 작업 수 — 원본은 점당 약 400~500 실행(추정), eudext 는 점당 약 58(후처리 없음)~140(기본 어택) | 위 단계에서 프레임이 끊기는 곳이 있으면 알려 준다(E12-1 의 두 무리 64기, E12-2 의 옵저버·히드라 겹침) | 비용 목표 확인 | **2026-09-18 인게임: 통과** (spawn 단계) |

참고: 소환 유닛은 단계가 바뀔 때 `RemoveUnit` 으로 지운다(맵 리빌러는 남는다). E12-1 의 저글링·E12-2 의 히드라는 P1 유닛이 없어 본진에 도착해 서 있을 뿐이다.
INGAME_CHECKLIST.md 배치 A 의 **A-3**(G_CB 로케이션 오프바이원 3곳)은 E12-3·E12-4 로 확인한다 — eudext 는 원본 의도대로(이름 = 그 로케이션,
번호 = 1부터) 구현했고, 원본 맵 쪽 확인(Stella `Set_Warp` 의 `Order={Attack,"Location 24"}` 가 실제로 23 을 향하는지, theSeed 스킬유닛
`PlotLoc = 102`)은 원본 맵을 고칠 때 따로 본다. 배치 C 의 **C11-9**(건작 본문에서 spawn 호출 → 중심 좌표가 그 레코드의 x, y)는
E12-1(anchor = 건물 자리)과 같은 방식이라 E12-1 결과로 대신한다.

### WP17 `textfx`·`chat` (타자기) — 맵 13

**필수 항목은 D17-1·D17-2·D17-4·D17-6** 이다(S6 5.2-1·2 와 채팅 버퍼 배치 사실). 에뮬레이터에서는 채팅 버퍼 모델
(`testing/chatmodel.py` — 11줄·홀짝 정렬·0x640B58, 표시 시간·사용자 채팅 줄 바이트는 **가정**) 위에서 원본 블록(HTextEff + CDPrint)을
옮긴 참조 모델과 프레임마다 버퍼 바이트가 같은지 봤다(`tests/t_chat.py`). 화면에 실제로 어떻게 보이는지(0x0D 가 안 보이는지,
가운데 정렬, 212/214바이트 NUL 자르기, U+200B 표식이 안 보이는지)는 에뮬레이터로 알 수 없다.
eudext 가 새로 쓰는 SC 동작: 한 트리거 안에서 `SetMemory(0x6509B0, Add, 1)` 뒤 `SetDeaths(CurrentPlayer, …)`(CP 를 바꿔 가며 셀 쓰기),
`DeathsX(CurrentPlayer, AtLeast, 1, 0, 비트)` 비트 읽기(eudplib readtable 과 같은 방식), 조건 트리거가 자기 next 칸을 고쳐 갈라지기
(eudplib EUDBranch 원리)와 프레임마다 되돌리기, 변수 트리거 next 사슬로 칸 변수 두 개 읽기(eudplib VProc 원리).
마스크 Add/Subtract(A-1 확인 전)와 유닛 번호 오프셋(`unit=u` → CP+12u)은 쓰지 않는다.

확인용 맵: `python eudext/tools/build.py euddraft eudext/examples/chat_ingame.eds --work <작업 폴더>` 로 빌드한
`chat_ingame_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, 게임 속도 **가장 빠름**).
(Windows 빌드: `python eudext\tools\build.py euddraft eudext\examples\chat_ingame.eds --work %TEMP%\eudext_work\chat_ingame`)
약 50초 동안 `[D17-n]` 줄이 차례로 나온다. **영상**(휴대폰 촬영도 좋다)이 가장 좋고, 안 되면 줄마다 사진이나 글로 알려 주면 된다.
0~40초는 타자기 A(1프레임에 1글자, 소리 없음), 40초 뒤는 타자기 B(2프레임에 1글자, 글자마다 `sound\glue\bnetclick.wav`)다.
에뮬레이터에서 이 맵은 1,250프레임 동안 아래 줄이 모두 기대대로 드러나고(`t_chat.py` `ingame_emulate`), 채팅 흉내 줄도 다시 드러난다.
(요청) `tools/ingame_maps.py` 의 `MAPS` 에 `("08", "chat_check", …/chat_ingame.eds, "single", "eds", "D17-1~9 (타자기·채팅 줄)", "혼자, 가장 빠름. 18초 뒤 채팅으로 !H안녕 éè 가나다")` 한 줄.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| D17-1 | **[필수]** 타자기 기본 — 표식(`\r\r!H`) 줄이 찍힌 프레임에 빈 줄로 바뀌고 다음 프레임부터 한 글자씩 나타나는가. `!H` 와 U+200B 표식이 끝까지 보이지 않는가. 가운데 정렬(`\x13`) 줄이 드러나는 동안 어떻게 움직이는가(빈칸 셀 0x0D 가 폭이 없으면 글자가 늘 때마다 가운데로 다시 맞춰진다 — 원본 맵과 같은지) | 2초에 `[D17-1] 가운데 정렬 — 한 글자씩: 가나다라마바사 ABC` 가 약 1.5초에 걸쳐 나온다. 줄 앞에 이상한 네모·물음표·`!H` 가 보이면 알려 준다. 원본 맵(ResV 건작 189, Mem2 3초 뒤)과 모양이 다르면 그 차이 | `chat.Typewriter` 공개, WP19 ObserverChat(`typewriter=`) | **2026-09-18 인게임: 미실행** — display 단계에서 멈췄다 |
| D17-2 | **[필수]** 여러 줄 문구·홀수 slot — 문구의 줄바꿈마다 표식이 붙어 세 줄 모두 효과가 나는가(짝수·홀수 slot 이 섞인다. 홀수 slot 은 원문 +2 바이트부터 셀) | 5초에 `[D17-2] 첫째 줄 …`, `둘째 줄`, `셋째 줄 — 모두 표식 없이` 세 줄이 **동시에** 한 글자씩 나온다. 한 줄이라도 원문 그대로(`!H` 가 보이거나 한꺼번에) 나오면 그 줄이 몇 번째인지 | 홀짝 정렬 가정(R4a E.1) 확정 | **2026-09-18 인게임: 미실행** |
| D17-3 | 2바이트 UTF-8 — 원본 CtrigAsm 스캐너는 2바이트 글자를 3바이트로 읽어 깨졌다(S6 1.7). eudext 는 고쳤다 | 8초에 `[D17-3] 2바이트 UTF-8: é ñ ü ß ç ø Ω — 깨지지 않으면 정상` 이 깨짐 없이 나오는가 | 없음(확인만) | **2026-09-18 인게임: 미실행** |
| D17-4 | **[필수]** 셀 53 NUL 부수효과(원본과 같게 매 프레임 11줄 모두) — 보통 긴 줄이 짝수 slot 212바이트, 홀수 slot 214바이트에서 잘리는가 | 12초에 `[D17-4] even slot: expect 12 chars after colon: 0123456789AB` 또는 `… odd slot: expect 14 chars …: 0123456789ABCD` 한 줄(원문은 16글자 `…ABCDEF`, 사이에 보이지 않는 색 코드 150여 개). **콜론 뒤에 보이는 글자**를 그대로 알려 준다. 16글자가 다 보이면 NUL 쓰기가 안 먹은 것이고, 줄이 두 줄로 꺾이거나 이상하면 그 모양 | 셀 배치(짝수 +0 / 홀수 +2)와 `nul_cell` 문서 확정 | **2026-09-18 인게임: 미실행** |
| D17-5 | 52칸 한도 — 원본처럼 한 줄에서 셀 52개(지운 `!H` 2칸 포함)까지만 드러나는가 | 15초에 `[D17-5] 52칸 한도: 0123…` 숫자가 **`…890123`** 에서 끝나는가 | 없음(확인만) | **2026-09-18 인게임: 미실행** |
| D17-6 | **[필수]** 사용자 채팅 — 사용자 채팅 줄은 앞에 이름이 붙어 표식으로 시작하지 않는다. 확인 맵은 새 줄에서 `!H` 를 찾으면 이름 부분을 지우고 `\r\r!H…` 로 당겨 쓴다(로컬, 표시 전용) → 타자기가 변환한다 | 18초 안내가 뜬 뒤 채팅(Enter)으로 `!H안녕 éè 가나다` 를 보낸다. ① 그 줄이 이름 없이 `안녕 éè 가나다` 로 한 글자씩 다시 나오는가 ② 바로 아래에 뜨는 `[D17-6] 채팅 줄 원문 앞 12바이트 0x… 0x… 0x… / 표식 위치 N` 줄의 **16진 값 세 개와 N** 을 사진으로 보내 준다(SC:R 채팅 줄 바이트 배치 — `chatmodel` 가정을 고친다). ③ `!H` 없는 보통 채팅이 그대로 보이는가 | `chatmodel` 사용자 채팅 가정, WP19 | **2026-09-18 인게임: 미실행** |
| D17-7 | 소리(UERE 판) — 드러낸 셀이 빈칸·공백이 아니면 `PlayWAV`(이 PC 에서만), 2프레임마다 한 글자(`every=2`) | 40초에 `[D17-7] 소리 판: …` 이 A 판보다 느리게 나오고 **글자마다 딸깍**, 띄어쓰기 자리에서는 소리가 없는가. 소리가 겹쳐 끊기거나 안 나면 알려 준다(파일은 SC 기본 `sound\glue\bnetclick.wav`) | 없음(확인만) | **2026-09-18 인게임: 미실행** |
| D17-8 | 줄 표시 시간 — 효과가 끝난 줄도 보통 채팅처럼 시간이 지나면 사라지는가(멈춘 채 남지 않는가). 사라지기까지 걸린 초도 적어 주면 `chatmodel` 표시 시간 가정을 채운다 | 45초에 `[D17-8] …` 이 뜬 뒤 모든 줄이 사라질 때까지 지켜본다. 채팅창을 열면(Enter) 사라진 줄이 다시 보이는지, 다시 보이면 표식·빈칸이 섞여 보이는지도 | `chatmodel.expire` 가정, R4a E.5 | **2026-09-18 인게임: 미실행** |
| D17-9 | (선택) 속도 단위 — 트리거 한 사이클 = 한 프레임인가(S6 8-8). 타자기 A 는 1프레임에 한 글자 | D17-5 줄(숫자 50자)이 다 나오기까지 몇 초인가(가장 빠름 24fps 면 약 2초) | 문서의 속도 설명 | **2026-09-18 인게임: 미실행** |

### WP18 `scrdb` (SCR_DB 네이티브 코어, 런처 레이아웃 7) — 맵 14

에뮬레이터로는 런처(외부 프로그램)가 게임 메모리를 찾고 읽고 쓰는 부분, 실제 MSQC 전송(게임 명령), 알림음, 2인 동기화를 볼 수 없다.
**SCR_DB 런처가 필요하다** — `DPS_Enhance/tools/scr_db_launcher.py`(`py -3.10 scr_db_launcher.py`) 또는 배포본 exe(v1.3.0 이상, 레이아웃 6·7 지원).

#### 확인용 맵 만들기 (Windows)

1. `eudext/examples/scrdb_ingame.eds` 의 `VenvSite` 를 euddraft 용 lupa 폴더(`C:\Users\whatd\.venvs\euddraft011_site`)로 바꾼다.
   Lua 코어는 `MapSource\Library\SCR_DB_Core.lua` 를 기본 자리에서 찾는다(못 찾으면 `set EUDEXT_SCRDB_CORE=<폴더 또는 파일>`).
2. `python eudext\tools\build.py euddraft eudext\examples\scrdb_ingame.eds --work <작업 폴더>` → `<작업 폴더>\scrdb_ingame_out.scx`.
   빌드 로그에 `[eudext.scrdb] Lua 코어 …(레이아웃 7 …)` 와 `[eudext.scrdb] 매니페스트 C:\Temp\SCR_DB_manifest_eudext_scrdb_check.json (빌드 …, 지문 371B81DA, 항목 5)` 가 보여야 한다.
   (훅 방식: `python eudext\examples\scrdb_build.py --work <작업 폴더> --map eudext\testing\base_multi.scx --stash <런처>\manifests` — 2인 확인용, 매니페스트를 런처 폴더에 복사.)
3. 런처는 `C:\Temp\SCR_DB_manifest*.json` 과 `<런처>\manifests\*.json` 에서 매니페스트를 찾는다. 세이브 이름표는 `eudext_scrdb_check`.
4. 맵 화면: `[D18-1]` 상태 줄(약 3초마다), `[D18-2]` 불러오기, `[D18-3]` 저장. **F8** = 저장 요청(동기화 입력). 1초마다 Gold +1(불러온 뒤).

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| D18-1 | **[필수]** 런처가 표지 블록을 찾고 매니페스트를 고른다 | 런처를 켜고 맵을 혼자 연다. 런처 로그: "연결되었습니다 … 빌드 N, P1" → "매니페스트 : SCR_DB_manifest_eudext_scrdb_check.json (빌드 일치, 항목 5개)". 맵 `[D18-1]` 줄의 Seq 가 늘고 LocalPlayer = 1. 연결 알림음(ZRescue) | 런처 연동 전체 | |
| D18-2 | **[필수]** 불러오기(세이브 없음 → 준비 신호) | 처음 열 때 런처가 "저장된 파일이 없습니다" 뒤 준비 신호(0xFFFE) → 맵 `[D18-2] P1 불러오기 끝` 과 값 줄(Gold 0, Level 0, Big 0x12345678, Stat 7, Flags 0xABCDEF01). 상태 줄 "받은 워드 P1" ≥ 1 | 수신기(MSQC 채널·토글·꼬리표) | |
| D18-3 | **[필수]** 저장 | 몇 초 뒤 F8 → `[D18-3] P1 저장 신호 1번째` → 런처 로그 "저장 시작 … 저장 완료. (5개 항목)" → 맵 `[D18-3] P1 저장 완료` 와 값 줄(Level 1). 저장 완료 알림 | save_signal·0xFFFD | |
| D18-4 | **[필수]** 저장한 값 불러오기(상위 16비트 포함) | 맵을 나갔다가 다시 연다(런처는 켠 채). 런처 "불러오기 시작. (P1, 보낼 항목 k개)" → "불러오기 완료" + 불러오기 완료 알림음(TDrTra01) → 맵 `[D18-2]` 에 저장했던 Gold·Level·Big 0x12345678·Stat 7·Flags 0xABCDEF01. 런처 로그에 "어긋난 항목" 경고가 없어야 한다 | 워드 3개(키·하위·상위) 조립, 기본 쓰기 함수(ordinal) | |
| D18-5 | 알림음 | 런처를 게임 도중에 끄면 연결 끊김 소리(tscFir00), 오류 상황(매니페스트를 치운 채 연결)에 오류 소리(PError). 소리는 그 PC 에서만 | notify (PlayWAVAll 방식) | |
| D18-6 | **[필수]** 2인 LocalPlayer·디싱크 | `testing/base_multi.scx` 로 빌드한 맵(가)(나) 중 하나를 2인 LAN 으로. 두 PC 모두 런처를 켜면 각 런처 로그의 플레이어가 P1/P2 로 맞게 나온다. **한 PC 에만** 런처를 켠 판도 해 본다 — 불러오기·저장·알림음 동안 디싱크(게임 끊김)가 없어야 한다. 런처 없는 PC 는 `[D18-2]` 가 뜨지 않는다 | LocalPlayer 칸·로컬 칸 규칙(4.18 (f)) | |
| D18-7 | 빌드 ID 가 바뀌어도 같은 항목이면 예전 매니페스트로 붙는다 | 맵을 다시 빌드(빌드 ID 바뀜)하고 `C:\Temp` 매니페스트를 지운 뒤 `<런처>\manifests\eudext_scrdb_check_371B81DA.json`(--stash) 만 남겨 연다. 런처 "매니페스트 : … (항목 지문 일치 …)" | FieldHash (Lua 와 바이트 일치 — 에뮬레이터에서 확인됨) | |
| D18-8 | 채널 시험 | 런처를 `--dev` 로 켜고 "MSQC 채널 시험" 버튼. 오류율·도착률이 DPS 맵과 비슷한지(꼬리표 3 워드는 에코·카운트만) | 수신기 에코 | |
| D18-9 | 맵 크기 | 빌드 로그 `Sendable value range for 'val' syntax: 0 to 4194303`(128×128 = 22비트 ≥ 워드 20비트). 64×64 미만 맵은 `scrdb.setup` 이 빌드 오류로 막는다 | setup 검사 | |

기록 요청: 런처 로그 전체(Log.txt)와 맵 화면 사진. D18-4 에서 값이 어긋나면 런처 로그의 "다시 보냄/어긋난 항목" 줄을 같이 알려 주세요.

## 배치 F (WP19 misc, WP20 i128, WP21 스프라이트/cgrp)

### WP19 `misc` (관전자 채팅·나가면 멈춤) — 맵 23·17

에뮬레이터로 확인할 수 없어 Windows(SC:R)에서 봐야 할 항목. 번호 머리 `F19-`(합칠 때 정식 번호).
확인용 맵: `examples/misc_ingame.{eps,eds}`(관전자 채팅, 기준 맵 `testing/base_multi.scx`), `examples/misc_exit_trap.{eps,eds}`(나가면 멈춤, 기준 맵 `testing/base.scx`).

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| F19-1 | **[필수]** 관전자 채팅 B1 수정 — 관전자 2·3·4번(129·130·131) PC 에서도 키(END/HOME/INSERT)로 모드를 **두 번 이상** 바꿀 수 있는가(원본은 첫 입력 뒤 막혔다). 관전자 PC 의 0x512684 가 슬롯마다 128~131 로 다른가(모두 128 이면 B1 이 드러나지 않는다) | `misc_ingame_out.scx` 를 SC:R 사용자 지정 게임 방에 올려 사람 2명 + **관전자 2명 이상**으로 연다. 각 관전자가 채팅창을 닫고 END→관전자·HOME→전체·INSERT→대상없음 을 여러 번 눌러 본 뒤, 채팅창을 열어 실제로 누구에게 가는지 본다 | WP19 misc.ObserverChat | |
| F19-5 | 관전자 안내 문구가 타자기 없이도 보이는가(효과 블록 없는 맵), button3.wav 소리가 나는가 | 위 맵에서 키를 누를 때 문구·소리 확인 | WP19 | |
| F19-6 | `0x68C144` 값 2/3/5 에서 실제 채팅이 누구에게 가는지(특히 3 "대상없음") | 관전자가 모드를 정하고 실제 채팅을 쳐 본다 | WP19 (S6 5.2-4 와 같음) | |
| F19-2 | 부대 지정 표(0x57FE60) 공유성 — 모든 PC·리플레이에서 `HotkeyUnit`/`SetHotkeyUnit` 값이 같은가(공유 로직에 써도 되는지) | 부대 지정을 읽어 표시하는 맵을 2인 이상으로 연다(별도 확인 맵 필요 시 요청) | WP19 misc.HotkeyUnit | |
| F19-1b | 방장 표(0x6D0FDC) 공유성·싱글 동작 — `host_player()` 가 모든 PC·싱글플레이·리플레이에서 같은 방장 번호를 주는가 | 방장 번호를 표시하는 맵을 2인 이상·혼자에서 연다(별도 확인 맵 필요 시 요청) | WP19 misc.host_player | |
| F19-3 | 와이드 스크린 판정 — `misc.is_widescreen(loc)` 가 4:3 에서 0, 와이드에서 1 을 주는가(에뮬레이터는 CenterView 를 흉내 못 냄). 판정 뒤 화면이 제자리로 돌아오는가 | is_widescreen 을 쓰는 맵을 4:3·와이드 두 해상도로 연다(별도 확인 맵 필요 시 요청) | WP19 misc.is_widescreen | |
| F19-4 | **[필수]** 나가면 멈춤 — `unsafe_exit_trap(P1)` 을 켠 뒤 P1 이 게임을 떠날 때(나가기·패배) 스타가 멈추는가(크래시), 그리고 **다른 PC 는 멈추지 않는가**(list_owner=P8 컴퓨터 목록). 실험 기능이라 이 확인 전까지 unsafe | `misc_exit_trap_out.scx` 를 **혼자 또는 버려도 되는 방**에서 연다. 화면 경고를 확인하고, P1 이 게임을 떠나 본다. 확인 뒤 스타를 강제 종료해야 할 수 있다 | WP19 misc.unsafe_exit_trap | |

- **[필수]** = S6 5.2 필수 항목(관전자 채팅 B1)과 완료 추가 조건(exit_trap 은 인게임 전까지 unsafe).
- `tools/ingame_maps.py` 에 `misc_ingame`(multi)·`misc_exit_trap`(single) 을 확인 순서에 넣으면 한꺼번에 빌드된다(합칠 때 요청).

### WP20 `i128` — 맵 24

128비트 연산 결과는 에뮬레이터 차등 시험(`tests/t_i128.py` 기본 234,778 판정)으로 확인했다. 본문이 쓰는 기법은 i64 2차와 같다 —
트리거 next 자기 수정(갈림 트리거·공유 비교 트리거), 조건 amount·액션 값 칸 채우기(amount 칸을 읽는 막이 조건 포함), 변수 트리거 사슬,
"값 ≥ 빼는 값" 이 보장된 SC `Subtract`(C3-1 과 같은 사실), `0xFFFFFFFF ⊖ y`, EUDLightVariable 깃발. 마스크 Add/Subtract 식(S8 A-1)은
쓰지 않는다. **새 가정이 없어 필수 항목은 없고**, 권장 항목 한 장으로 실제 게임에서 한 번 돌려 본다.

확인용 맵: `python eudext/tools/build.py euddraft eudext/examples/i128_ingame.eds --work <작업 폴더>` 로 빌드한
`i128_ingame_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1).
(Windows: `C:\Users\whatd\.venvs\eud081\Scripts\python.exe eudext\tools\build.py euddraft eudext\examples\i128_ingame.eds --work %TEMP%\eudext_work\i128_ingame`)
첫 사이클에 시험 46개를 한 번 돌리고 `[F20] eudext.i128 인게임 점검 — …` 한 줄이 뜬 뒤, 약 1초(24 트리거 사이클)마다 `[F20-1]`~`[F20-9]`
스물네 줄이 한 줄씩 뜨고 약 27초마다 처음부터 다시 뜬다. 한 줄에 값이 둘이고 괄호 안이 기대값이다. **마지막 줄 `[F20-9] 점검 46 / 46`**
이면 모두 맞은 것이다. 에뮬레이터에서 같은 맵은 `점검 46 / 46` 이다. 맞지 않으면 틀린 줄(괄호 밖 값)을 사진이나 글로 알려 준다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| F20-1 | (권장) `i128` 연산 — 덧셈(칸 셋 올림 사슬·2^128 wrap)·wrap 뺄셈(칸 셋 빌림)·포화 뺄셈(2^64 경계 — 반쪽별이 아닌 128비트 전체 기준), 비교 6종(칸 경계 값), 64×64 전체 곱(16비트 쪼개기 누적기 16개, 32×32 는 i64 본문), 128×128 wrap 곱, 상수 곱(비트 누적 10^16·6.5×10^12), 나눗셈 — 32비트 제수(10, 2^31 + 1), 64비트 제수(2^64 − 1, 0x123456789ABCDEF — 넘침 비트 경로 포함), 128비트 제수(2^70 + 1, 2^127 + 1, N < D), 0 나눗셈, 상수 제수(5000·100·3 — i64 상수 본문 세 번), to64·to32(포화·하위), 10진 39자리 출력. 모두 트리거 next 자기 수정·조건/액션 칸 채우기에 기대므로 SC:R 에서 에뮬레이터와 같게 도는지 본다 | 위 맵. 줄 예: `[F20-1] 덧셈·뺄셈(wrap·포화) 0 18446744073709551616 (0 18446744073709551616)`, `[F20-3] 곱셈 64×64·32×32 340282366920938463426481119284349108225 6500000000000000000000000000000 (…)`, `[F20-6] 나눗셈 128비트 제수·0 …`, 마지막 `[F20-9] 점검 46 / 46 (46 / 46) — 두 수가 같으면 통과` | 없음(확인만). 틀리면 `i128` 본문을 고친다 | **2026-09-18 인게임: 통과** (i128 단계) |

참고: `[F20-2]` 줄의 값은 비교 결과 비트(1 = ≥, 2 = >, 4 = ≤, 8 = <, 16 = =, 32 = ≠)의 합이다. 한 줄의 두 값은 각각 따로 `fmt()` 버퍼를
쓴다. `[F20-9]` 의 두 수가 같으면 나머지 줄은 보지 않아도 된다.
`tools/ingame_maps.py` 에 `i128_check`(single) 를 확인 순서에 넣으면 한꺼번에 빌드된다(합칠 때 요청 — design.md 5절 4).

### WP21 `bullet` 3단계(28장 스프라이트)·`cgrp` — 맵 18

에뮬레이터로 확인한 것(`tests/t_sprite.py` 2,500·`tests/t_cgrp.py` 978 판정): 만든 유닛·CUnit 칸 값이 **CtrigAsm Lua 원문의 쓰기 줄과
같은지**(원문을 읽어 계산), 생성 순간의 dat(높이·스캐너 대기 주문)·로케이션, 빈 칸 없음·생성 실패, CP 보존, 엉뚱한 메모리 쓰기 없음,
합성 CGRP 파일 파싱·층 나누기·그리기 순서와 대기. **SC:R 이 그 칸·dat 로 실제로 무엇을 그리는지**(스프라이트 모양·영구 여부·드래그
방지·리콜)와 **실제 CS_Photo 파일 형식**은 에뮬레이터로 볼 수 없다.

**확인용 맵**: `python eudext/tools/build.py euddraft eudext/examples/sprite_ingame.eds --work <작업 폴더>` 로 빌드한
`sprite_ingame_out.scx` 를 StarCraft: Remastered 에서 **혼자** 연다(기준 맵 `testing/base.scx`, P1 맵 리빌러로 시야 전체).
eds 가 `[unlimiter]`(euddraft 0.11 동봉)를 켠다 — CtrigAsm 가이드북: 28장은 언리미터 권장, CGRP 는 필수.
(Windows 빌드: `python eudext\tools\build.py euddraft eudext\examples\sprite_ingame.eds --work %TEMP%\eudext_work\sprite_ingame`)
약 1분(710 트리거 사이클) 동안 차례로 만들고 `[F21-번호]` 줄을 띄운다. 괄호 안이 기대값이다. **화면 줄 사진 + 눈으로 본 것**을 알려 주면 된다.
dat 는 맵 안에서 가이드북 예제 값으로 설정한다(`CtrigKind.install()` = `BulletInitSetting`): 점 = 203(반공중) → 무기 2 → flingy 147 →
스프라이트 231 → 이미지 233(뉴크 점, 화면 출력 0 빨강), 스톰 = 19 → 무기 0 → flingy 162 → 스프라이트 356 → 이미지 380(iscript 236),
튕기는 스프라이트 = 20 → 무기 1 → flingy 164 → 스프라이트 344 → 이미지 360. 레이스(8)·아비터(86) 크기 1, 리콜 마나 0(예제 28-1).

**F21-7 준비 — 실제 CGRP 파일(사용자 몫)**: CS_Photo.exe 로 만든 `.cgrp` 한 개(가능하면 가이드북 예제 29-4~29-6 처럼 팔레트·명암이 있는
작은 그림, 32×32 칸 정도)를 `sprite_user.cgrp` 라는 이름으로
- `build.py` 로 빌드하면 `--work` 폴더에, euddraft 로 eds 를 직접 열면 eds 폴더(euddraft 작업 폴더)에 두거나,
- 환경 변수 `EUDEXT_CGRP_DIR` 에 그 파일이 있는 폴더를 적고 빌드한다(`tools/ingame_maps.py` 로 빌드할 때는 이 방법).
파일을 읽지 못하면(형식이 문서와 다름) **빌드가 한국어 오류로 멈춘다 — 그 메시지를 그대로 알려 준다**. 원본 BMP 와 CS_Photo 에 넣은
값(변환 모드·색상 코드·명암 단계·높이·이미지 ID·점 간격)도 함께 알려 주면 헤더·비트 풀이를 대조할 수 있다. 파일 자체를 보내 주면
합성 파일 시험에 실제 파일 시험을 더한다.

화면 위치(4096 × 4096 맵): 위쪽 줄 y 480(F21-1) → y 1000 줄(F21-2 스톰 1200·1500, F21-3 레이스 2000·2100, F21-4 스캔 2600~3000)
→ y 1300 움직이는 레이스 → (3000, 400)·(3200, 1600) 리콜(F21-5) → (400, 2000) 합성 그림(F21-6) → (2000, 2000) 실제 그림(F21-7)
→ F21-9 (y 3000, 칸 가득).

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| F21-1 | **[필수]** `perma_sprite`(CtrigAsm `CreateSprite`, 투사 방식 7) 로 만든 점이 **보이고, 움직이지 않고, 계속 남는가**. 높이 0~15 에 따라 겹침 순서가 다른가. 속도 1280 스프라이트는 어떻게 움직이는가(튕김) | 2초쯤 `[F21-1] … 만듦 16(16) 실패 0(0)` — (400,480)~(760,480) 빨간 점 16개. 22초쯤 `[F21-1] 20초 뒤 …` 줄이 뜰 때 점이 그대로면 OK. (1000,480) 스프라이트의 움직임을 적어 준다 | 영구 스프라이트·CGRP 그리기 확정, −speed(원문)·투사 방식 7·이미지 256 iscript 86 가정 확인 | |
| F21-2 | **[필수]** `storm`(CtrigAsm `CreateStorm`, 투사 방식 3·이미지 iscript 236) 이 스톰 모양으로 보였다 사라지는가, 수명 30 과 60 의 차이 | 4초쯤 (1200,1000) `epd=…(0 아님), 수명 30`, 6초쯤 (1500,1000) 변수 인자 `수명 60`. 모양·지속 시간을 적어 준다 | storm 공개, 변수 이미지 공유 본문 | |
| F21-3 | **[필수]** `unit_sprite`: (2000,1000) 레이스가 **수명 96 뒤 사라지고 드래그 선택이 안 되는가**(+0xE4 ← 0, +0xDC 0x100), 클로킹 소리가 나는가. (2100,1000) `track=False` 레이스는 보통 유닛인가. y 1300 에서 매 프레임 수명 2 로 다시 만든 레이스가 끊김 없이 움직여 보이는가 | 8초쯤 `[F21-3] … +0xDC=256(0x100 비트 켜짐) +0xE4=0(0) 수명 96`. 레이스를 드래그·클릭해 보고 사라지는 시점을 적는다 | 드래그 방지 옵션(결정 요청 D?21-6), 가변 그림 C 방식 | |
| F21-4 | **[필수]** `scan_sprite`(스캐너 스윕 33, 스캔 이미지 391): (2600,1000)·(2800,1000)×3·(3000,1000) 에 모양이 보이는가, **remove=True(앞 둘)는 스캐너 유닛이 남지 않고 remove=False(마지막)만 남는가**, 높이 4 | 14초쯤 `[F21-4] …` 줄. 스캐너 유닛이 선택되는지로 남았는지 본다 | 스캐너 대기 주문 0→140 원리(원문) 확인 | |
| F21-5 | **[필수]** `recall_sprite`(아비터 86, 리콜 이미지 379): (3000,400) 제자리 아비터와 (3200,1600) 목표(아비터는 (3413,3413))에 **리콜 모양이 뜨는가**. (3200,1600) 의 P1 마린이 (3413,3413) 근처로 끌려가는가(R4a A.8 추측) | 16초쯤 `[F21-5] 리콜 … epd=… epd=…`, 19초쯤 `[F21-5] 3초 뒤: 마린 위치 = (x,y)` | recall 공개, 주문 137·수명 3 원리 | |
| F21-6 | **[필수]** 합성 CGRP 그림(`CGRPPainter`, 24×6 칸 × 6px): (400,2000) 에 **빨강·초록·파랑 네모 테두리 3개**, 왼쪽 안은 붉은 겹침(적색 명암 1), 가운데 안은 빨강(Fill 만 → 종류 색 0), 오른쪽 안은 어두운 겹침(흑색 명암 2)이 보이는가. 색이 섞이거나 빠지지 않는가(층 사이 4프레임 대기) | 20초에 그리기 시작, 30초쯤 `[F21-6] … 다 그림=1(1) 점 120(120) 실패 0(0)`. 사진 | 층 전환 대기(delay) 기본값, 명암 층 높이(+1·+2) | |
| F21-7 | **[필수]** **실제 CS_Photo `.cgrp` 파일**(위 "F21-7 준비")을 읽고 그리기: 헤더 풀이 줄(`CGRP sprite_user.cgrp: W x H 칸, 점 a x b px, 헤더 점 수 N (뜻), Fill …, 이미지 …, 높이 …`)이 넣은 값과 맞는가, (2000,2000) 에 그린 그림이 원본 BMP 와 같은 모양·색인가 | 1초쯤 헤더 줄(파일이 없으면 "파일 없음"), 32초부터 그리고 50초쯤 `[F21-7] 실제 CGRP 그림: 다 그림=1(1) 점 n(n) 실패 0(0)`. 사진 + 원본 BMP·CS_Photo 입력값 | **cgrp 형식 확정(DESIGN 6.1 WP21 완료 조건)** — 헤더 +0 의 뜻, 점 크기 워드 순서, 명암 비트 폭(결정 요청 D?21-1), 이미지·높이 비트 | |
| F21-8 | 맵에 진짜 벌처·스캐너가 있으면 모양·스캔 크기가 깨지는가(영구 부작용: 이미지 256 iscript 86, 스캐너 크기 0) | 이 맵에는 없다. 28장 함수를 쓰는 맵에서 문서화용 | 문서(R4a A.8) | |
| F21-9 | 유닛 칸이 가득(1700)일 때 `storm`·`perma_sprite`·`unit_sprite`·`recall_sprite` 가 0 을 돌려주고, 칸 연산 없는 `scan_sprite`·`unit_sprite(track=False)` 도 튕기지 않는가 | 53초쯤 P2 맵 리빌러로 칸을 채운 뒤 `[F21-9] 유닛 칸 가득(…): storm=0(0) perma=0(0) unit_sprite=0(0) recall=0(0)` 줄이 뜨고 게임이 계속되면 OK | 실패 판정(= D14-3 와 같은 본문) | |
| F21-10 | 언리미터 없이(`[unlimiter]` 줄을 지우고) 28장 함수·CGRP 가 어떻게 되는가, 한 프레임 점 수 한도 | 필요할 때. 대량 그림 맵에서 | 사용 안내(가이드북: 28장 권장·CGRP 필수) | |
| F21-11 | 2인 이상 멀티에서 디싱크 없음(공유 상태만 씀) | 멀티 맵에서 `perma_sprite`·`CGRPPainter` 를 매 프레임 | 없음(확인만) | |

에뮬레이터가 이 맵에서 확인한 것(`tests/t_sprite.py` `ingame_emulate`, 710 사이클): 오류 없음, 점 16·실패 0, 튕기는 스프라이트·스톰 2·레이스·리콜 2·마린
epd 가 0 이 아님, 움직이는 레이스 61번, 합성 그림 120점 다 그림·실패 0, 칸 가득 때 0 반환(채운 수 1424), 사용자 파일 없음(found 0),
이미지 256 iscript 86·리콜 마나 0. 모델에는 스프라이트·수명·리콜 효과가 없으므로 모양·사라짐·끌려옴은 인게임에서만 본다.

"확인 순서" 표(`tools/ingame_maps.py` `MAPS`)에 넣을 줄(번호는 합칠 때):
`("11", "sprite_check", os.path.join(EX, "sprite_ingame.eds"), "single", "eds", "F21-1~7 (28장 스프라이트·CGRP — 실제 CGRP 파일 포함)", "혼자. 약 1분 — [F21-번호] 줄과 모양. 실제 CGRP 는 EUDEXT_CGRP_DIR 에 sprite_user.cgrp")`

## 배치 G (WP-D `dbg` 디버그 브리지·자동 판정) — 2026-09-18, 브랜치 `feat/debugbridge`

맵: 이 worktree 의 **`work\dbg_example.scx`**(`examples/dbg_example.{eps,eds}` 빌드, 심볼 `work\dbg\DebugBridge_dbg_example_<빌드>.json`).
`StarCraft\Maps` 로 복사해 **혼자** 연다(싱글·LAN 전용 — 배틀넷에서 리더를 켜지 않는다). 명령은 모두 이 worktree 폴더
(`C:\Users\whatd\Documents\eudext_dbg`)에서 개발 venv 파이썬(`C:\Users\whatd\.venvs\eud081\Scripts\python.exe`, 64비트)으로 실행한다
— 리더가 기본으로 `work\dbg` 에서 심볼을 찾는다. 맵은 4초 동안 점검 단계 두 개(g1·g2)를 돌고 `[G-1] eudext dbg 예제 끝` 줄을 한 번 띄운다.
G-1 결과(2026-09-18)로 통합 맵(`auto_all`, `docs/ingame_auto/classification.md` 5절·DESIGN 5.6) 계측을 끝냈다 —
평소 확인은 이 예제 맵이 아니라 맨 앞 "확인 순서" ①(`00_auto_all.scx` + `RUN.bat`)으로 한다. 아래 G-1~G-5 는 브리지 자체의 확인이다.

| # | 항목 | 방법 | 기다리는 작업 | 결과 |
|---|---|---|---|---|
| G-1 | **[필수]** 디버그 브리지 블록이 **SC:R 에서 찾히고 값이 흐르는가** — eudplib 맵이 void 맨 위(0x596280)에 쓴 블록을 리더가 서명으로 찾고, seq·감시 값이 늘어나는가 | 맵을 혼자 열고 5초 뒤 `python eudext\tools\debugbridge\dbg_reader.py --once`. 기대: 첫 줄 `블록 0x… (EUD 0x596280)`, `빌드 … [심볼 일치]`, `seq`·`게임 프레임` 이 0 이 아님, 감시 `frame`·`sec`·`big`(10억씩)·`elapsed`, 아래 `-- eudext: 맵 dbg_example` 칸에 `단계 g1 끝 프레임 24~24`, `단계 g2 끝 프레임 48~72  맵 판정 통과`, `판정 g1.frame 1 / 1  통과`, `결과 g.total 3 / 3`, `표식 done 1`, `글 line 'eudext dbg N sec'`. 몇 초 뒤 한 번 더 실행하면 seq·`tick` 이 늘어 있어야 한다. 블록을 못 찾으면 `--diag` 출력 전체를 알려 준다 | 통합 맵 계측(`auto_all`) 전제 확인, 기본 자리(D98) 확정 | **2026-09-18 통과**: 블록 `0x1C5BDBF71A0`(EUD `0x596280`), 빌드 2132052544 [심볼 일치], seq·감시 값이 흐름. 다만 **터보가 없어 한 사이클이 28~30프레임(약 1.2초) 간격**이었다(seq 10 일 때 게임 프레임 281) → 확인 맵을 모두 `[eudTurbo]` 로 다시 빌드하고 G-5 를 더했다. 날 출력 `work\G1_result.txt` |
| G-2 | 자동 판정 도구가 예제 맵을 판정하는가 | 맵을 열기 **전에** `python eudext\tools\ingame_auto.py --specs eudext\examples\dbg_example_spec.json --maps 1` 을 켜 두고 맵을 연다. 기대: `판정 시작` → `단계 g1 … 시작/끝/통과`, `단계 g2 …` → `맵 dbg_example (빌드 …): 실패 — 완료 표식 …` 이 **아니라** 통과 줄(사람 확인 항목 `G-2h` 는 따로 표시), `>>> 다음 맵을 여세요`. 결과 파일 `%TEMP%\eudext_work\ingame_auto\results.json`(또는 `EUDEXT_WORK`). `G-2g`(초당 프레임) 값도 알려 주면 좋다 | 판정 명세 형식 확정 | |
| G-3 | (선택) 시간순 기록 | 맵을 연 채 `python eudext\tools\debugbridge\dbg_reader.py --record work\g3.tsv --record-seconds 10 --record-watch g2.sec done --record-keys` 뒤, 기록 중에 아무 키나 몇 번 누른다. 기대: `박동` 줄이 초마다, `단계 g1 시작/끝`, `값 done`, 키를 누를 때 `키 0x.. 누름/뗌`(키 표 0x596A18 이 블록과 같은 오프셋으로 읽히는 경우 — 안 보이면 `--diag` 에 0x596A18 이 "직접 읽히는 영역" 안인지 알려 준다) | 키 표 기록(AUTO_ASSIST) 방식 확정 | |
| G-4 | (선택) 페이로드 판 블록(`dbg.setup(addr="payload")`)도 찾히는가, 게임을 끝낸 뒤 옛 블록이 메모리에 남는가 | 예제 eps 의 `dbg.setup(map_name="dbg_example")` 에 `addr="payload"` 를 더해 다시 빌드(`python eudext\tools\build.py euddraft eudext\examples\dbg_example.eds --work work\dbg_payload`)하고 G-1 과 같게. 게임을 나간 뒤 `dbg_reader.py --diag` 의 `[스캔]` 줄에 블록이 몇 개 보이는지 | D98(페이로드 판 안내) | |
| G-5 | **[필수]** 터보(`[eudTurbo]`)가 켜져 통합 맵의 시간 설계가 맞는가 — 트리거 한 사이클 = 게임 한 프레임인가 | `00_auto_all.scx` 를 열면 첫 1초 안에 판정된다(`RUN.bat`). 기대: 결과 `G-5 통과`, `G-5.frames` 가 **24~40**(24사이클 동안 지난 게임 프레임 수 — 터보면 24, 여유 40). 맵 화면에도 `[G-5] 터보 …` 줄이 한 번 뜬다. 40 이 넘으면 그 맵에 `[eudTurbo]` 가 빠진 것이고, 시간 초과 설명에 관측한 초당 사이클이 붙는다 | 통합 맵·계측판의 프레임 창 설계 근거(DESIGN 4.21) | **2026-09-18 인게임: 통과** — 24사이클에 게임 프레임 24 (터보 켜짐) |

에뮬레이터가 이 맵에서 확인한 것(`tests/t_dbg.py` `eps_checks`, 100 사이클): 판정 g1.frame·g1.big·g2.sec 각 1/1, 결과 3/3·보고 1, 표식 done 1,
hit tick 100·second 4, 감시 frame 99·sec 4·big 99×10⁹·elapsed(0x57F23C 사본) = 사이클 시작 값, 글 `eudext dbg 4 sec`, 단계 g1(24~24)·g2(48~72, 맵 판정 통과).
Win32 읽기 경로(서명 스캔·seqlock·심볼 고르기·자동 판정·확인 문서 빈 칸 쓰기)는 가짜 게임 프로세스로 시험했다 — SC:R 메모리 배치만 인게임에서 본다.
