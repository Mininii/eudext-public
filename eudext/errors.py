"""eudext 오류 도우미 — 컴파일 시점 입력 검사를 한국어 메시지로 (DESIGN 3.10).

eudext 가 내는 오류는 모두 `EudextError` 다. eudplib `EPError` 를 상속하므로
euddraft 의 오류 출력과 기존 `except EPError` 처리에 그대로 걸린다.

epScript 에서 쓸 일은 거의 없지만 `import eudext.errors as er;` 로 불러오면
`er.EudextError`(대문자라 이름 번역이 없다)를 쓸 수 있다.
"""

from eudplib import EPError, ep_warn

__all__ = [
    "EudextError",
    "check_choice",
    "check_range",
    "fail",
    "require",
    "warn",
]


class EudextError(EPError):
    """eudext 컴파일 시점 오류.

    인자: 메시지(문자열). 앞에 "[eudext] " 가 붙는다.
    반환: -
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `const E = er.EudextError;` (대문자 이름은 번역되지 않는다)
    출처: 새로 작성
    """

    def __init__(self, message="", *args):
        text = str(message)
        if not text.startswith("[eudext]"):
            text = "[eudext] " + text
        super().__init__(text, *args)


def _format(msg, args):
    if args:
        try:
            return msg % args
        except (TypeError, ValueError):
            return msg + " " + " ".join(repr(a) for a in args)
    return msg


def fail(msg, *args):
    """`EudextError` 를 낸다. `msg % args` 로 서식을 채운다.

    인자: msg(문자열, % 서식), args(서식 값)
    반환: 돌아오지 않는다
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다(파이썬 라이브러리 내부용)
    출처: 새로 작성
    """
    raise EudextError(_format(msg, args))


def require(cond, msg, *args):
    """`cond` 가 거짓이면 `EudextError` 를 낸다.

    인자: cond(파이썬 값 — eudplib 조건이 아니다), msg/args(메시지)
    반환: None
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib `ep_assert` 의 한국어판
    """
    if not cond:
        fail(msg, *args)


def warn(msg, *args):
    """빌드 경고(`EPWarning`)를 낸다. 빌드는 계속된다.

    인자: msg/args(메시지)
    반환: None
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudplib `ep_warn` 감싸기
    """
    ep_warn("[eudext] " + _format(msg, args))


def check_range(name, value, lo, hi):
    """정수 상수 `value` 가 [lo, hi] 안인지 검사하고 그대로 돌려준다.

    인자: name(인자 이름, 메시지용), value(int), lo/hi(포함 경계)
    반환: value
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    if isinstance(value, bool) or not isinstance(value, int):
        fail("%s: 정수 상수여야 합니다 (받은 값 %r)", name, value)
    if not lo <= value <= hi:
        fail("%s: 범위 밖 상수 %d (허용 %d ~ %d)", name, value, lo, hi)
    return value


def check_choice(name, value, choices):
    """`value` 가 `choices` 중 하나인지 검사하고 그대로 돌려준다.

    인자: name(옵션 이름), value, choices(허용 값 모음)
    반환: value
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    if value not in choices:
        fail("%s: 잘못된 옵션 %r (허용: %s)", name, value, ", ".join(repr(c) for c in choices))
    return value
