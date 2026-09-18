# eudext

스타크래프트: 리마스터드 유즈맵용 **eudplib 0.81 확장 라이브러리**다. CtrigAsm(TEP Lua)으로 짜던 기능을 eudplib 관례로 다시 짰다.
여기에는 64비트·128비트 정수와 수 출력, 서식 있는 글 표시, 도형 계산·찍기, 스포너, 건물 스택·오브젝트 풀, 탄막, dat 고치기,
키 입력 동기화, BGM, 채팅 효과, SCR_DB 가 들어 있다.
CtrigAsm 트리거와 한 맵에 섞어 쓰는 **어셈블러 하이브리드** 안내(`hybrid/`)도 함께 있다.

파이썬 플러그인과 epScript 양쪽에서 쓸 수 있다.

```js
import eudext.i64 as i64;
import eudext.numfmt as nf;

const hp = i64.Int64(0x100000000);      // 64비트 값. const 로 묶는다 (var 에 담으면 32비트가 된다)
var mp;

function afterTriggerExec() {
    hp.v += 5;                          // const 객체는 .v 통로로 고친다
    if (hp >= 0x100000005) {
        printAll("HP {}", hp.fmt());
        printAll("MP {}", nf.Dec(mp, width=5, fill="0"));
    }
}
```

## 상태 (2026-09-18)

- 모듈: `i64` `i128` `numfmt` `cmp` `cell` `mathx` `display` `textfx` `strdesign` `chat` `players` `units` `pool` `spawn`
  `shape` `plot` `bullet` `cgrp` `datpatch` `local` `sync` `bgm` `misc` `scrdb` `dbg`.
- 시험: 트리거 에뮬레이터(`eudext/testing/`)로 약 124만 판정 통과.
- 인게임: 통합 점검 맵(맵 항목 17개·단계 19개) 통과. 아직 확인하지 않은 인게임 항목(눈·귀로 볼 것, 2인, 튕길 위험 등)은
  `eudext/docs/INGAME_CHECKLIST.md` 에 있다.
- 하이브리드: 빌드 자체는 인게임에서 확인했다. 그 위에서 돌려 본 eudext 코드는 글 한 줄 띄우기뿐이다. 자세한 것은 `hybrid/README.md`.

## 폴더

| 폴더 | 내용 |
|---|---|
| `eudext/` | 라이브러리 본체. `DESIGN.md`(설계도·모듈별 API·결정), `docs/`(조사·명세·비용·인게임 목록), `testing/`(트리거 에뮬레이터), `tests/`, `tools/`(빌드·eds 생성·비용), `examples/` |
| `hybrid/` | 어셈블러 하이브리드용 주의사항, eudplib 0.81 플러그인 사본(STRCtrig v5.5·CPLP·NSQC), eds 틀 |

## 준비

1. **euddraft 0.11.0.1** — GitHub `armoha/euddraft` 릴리스 `v0.11.0.1`.
   Windows 는 `C:\euddraft0.11.0.1\euddraft.exe` 를 기본으로 찾는다. 다른 자리면 환경 변수 `EUDEXT_EUDDRAFT` 로 알려 준다.
2. **개발용 파이썬**(3.10~3.14, 시험·빌드 도구용): `pip install eudplib==0.81.0 lupa==2.8`
3. **euddraft 용 lupa**(빌드 때 Lua 를 돌리는 `shape`·`scrdb`, 그리고 도형을 쓰는 `plot`·`spawn` 을 맵에 쓸 때만) — euddraft 번들 파이썬이 3.14 이므로
   파이썬 3.14 로 `pip install --target <폴더> lupa==2.8` 을 하고, 그 폴더를 부트의 `VenvSite` 와 환경 변수 `EUDEXT_LUPA_SITE` 로 준다.

## 쓰기

eds 맨 앞에 부트 플러그인을 둔다. 그 뒤로는 어느 플러그인·eps 에서든 `import eudext.<모듈>` 이 된다.

```
[main]
input : 입력.scx
output : 출력.scx

[<이 저장소>\eudext\boot.py]
EudextRoot : <이 저장소>
Preload : players
:: lupa 를 쓰는 모듈이 있으면: VenvSite : <lupa 폴더>  (그 모듈도 Preload 에)

[내 코드.eps]

[freeze]
freeze : 0
```

- eds 줄 끝에는 주석을 달 수 없다(euddraft 가 값으로 읽는다). 주석 줄은 `::` 로 시작한다.
- 가장 작은 예제는 `eudext/examples/hello.eds`. 빌드: `python eudext/tools/build.py euddraft eudext/examples/hello.eds --work <작업 폴더>`.
  모듈마다 `examples/<모듈>_example.eds/.eps` 가 있다.
- 부트 설정 키는 `eudext/boot.py` 머리 주석에 있다.

**원본 Lua 가 필요한 모듈**

| 모듈 | 필요한 것 | 알려 주는 법 |
|---|---|---|
| `shape` | `CB Paint v2.5.lua`(+ `CSMakeSpiral.lua` 등 쓰는 도형 Lua) | 환경 변수 `EUDEXT_CBPAINT_DIR` 또는 `CX(lib_dir=…)` |
| `scrdb` | `SCR_DB_Core.lua`(레이아웃 7) 와 SCR_DB 런처 | 환경 변수 `EUDEXT_SCRDB_CORE` 또는 `scrdb.setup(core=…)`. 이 저장소 옆(`../MapSource/Library`)에 있으면 저절로 찾는다. SCR_DB 런처를 쓰는 맵 전용 |

두 파일 다 공개 저장소 [Mininii/MapSource](https://github.com/Mininii/MapSource) 의 `Library` 폴더에 있다.

## 문서 읽는 순서

1. `eudext/DESIGN.md` 0절(한눈에) · 3절(공통 규약 — CP·로컬·뺄셈 의미·금지 목록)
2. 쓸 모듈의 `DESIGN.md` 4.x 절과 `eudext/docs/spec/`
3. 하이브리드로 쓸 거면 `hybrid/README.md`

문서에 나오는 `reference/…`, `C:\Users\…`, `MapSource\…` 경로는 원래 작업 저장소 기준이다. 이 공개판에는 원본 맵 소스(`reference/`)가 들어 있지 않다.

## 시험

```
python eudext/tests/run_all.py [파일 이름 일부 …]
```

산출물은 환경 변수 `EUDEXT_WORK`(Windows 는 `C:\…` 역슬래시 경로로)에 쌓인다. 기본값은 임시 폴더다.

시험은 저장소 안의 아래 자리를 본다. 없으면 그 부분을 건너뛰거나 그 시험 파일이 도중에 멈춘다.

| 자리 | 넣을 것 | 쓰는 시험 |
|---|---|---|
| `.tools/euddraft0.11.0.1/` | euddraft 0.11.0.1. Windows 는 `EUDEXT_EUDDRAFT` 도 그 안의 `euddraft.exe` 로 준다 | euddraft 로 빌드하는 부분 전부, `t_sync`·`t_scrdb`(번들 MSQC 를 읽는다) |
| `.tools/euddraft_site/` | 파이썬 3.14 용 lupa 2.8 (`pip install --target`) | Lua 를 쓰는 모듈의 euddraft 빌드. Windows 의 SCR_DB 빌드 예제만은 `%USERPROFILE%\.venvs\euddraft011_site` 를 본다 |
| `reference/MapSource/` | 공개 MapSource 의 `Library`·`MSF_UE_RE`·`MSF_Memory_2` 폴더 | 도형(`t_shape`·`t_plot`·`t_spawn`·`t_auto_all`), `t_sprite`, `t_bullet`, `t_lua_consts`, `t_strdesign`, `t_datpatch` 일부 |
| `reference/euddraft-0.9.10.11-plugins/` | euddraft 0.9.10.11 의 `MSQC.py`·`NSQC.py` | `t_sync`, `t_local` |
| `../MapSource/` (이 저장소 옆) | 공개 MapSource | `t_scrdb` — SCR_DB 코어를 `reference/` 사본에서 읽으면 경고가 나서 "경고 없음" 판정이 실패한다 |

이 배치로 이 공개판을 Windows 에서 돌린 결과(2026-09-19): 시험 파일 36개 중 **33개 통과**.
`t_scrdb` 는 판정 2개가 실패했는데, 둘 다 SCR_DB 빌드 예제가 찾는 lupa 자리(`%USERPROFILE%\.venvs\euddraft011_site`)가
비어 있어서였다(그 자리를 채운 실행에서는 통과). `t_shape`·`t_strdesign` 은 공개되지 않은 원본(theSeed·MSF-Template 소스)과
대조하는 부분이 있어 이 공개판만으로는 도중에 멈춘다.

## 이 저장소에 대해

비공개 작업 저장소에서 `eudext/` 와 `hybrid/` 만 옮긴 공개판이다(2026-09-18 판).
