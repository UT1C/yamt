from typing import Generator, TypeVar, Callable, Iterable
from collections import UserString
from enum import Enum
import itertools

T = TypeVar("T")
NoneT = TypeVar("NoneT")
DefaultT = TypeVar("DefaultT")
ReturnT = TypeVar("ReturnT")


def split_on_chuncks(size: int, *items: T) -> Generator[tuple[T, ...], None, None]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


class WordForm(str, Enum):
    SINGLE = "si"
    PLURAL = "plu"
    MIXED = "mix"


class FormedWord(UserString):
    default_form: str
    si: str
    plu: str
    mix: str
    _data: str | None = None

    def __init__(
        self,
        default_form: WordForm | str = WordForm.SINGLE,
        *,
        si: str | None = None,
        plu: str | None = None,
        mix: str | None = None,
        **kwargs: str
    ) -> None:
        locs = locals().copy()
        del locs["self"], locs["default_form"], locs["kwargs"]

        if not (set(locs) <= set(WordForm)):
            raise NameError("word forms not matched with FormedWord init args")
        elif not (any(locs.values()) or any(kwargs.values())):
            self._data = default_form
            return

        self.__dict__.update(
            (i.value, locs[i] or "")
            for i in WordForm
        )
        self.__dict__.update(kwargs)
        self.default_form = default_form

    @property
    def data(self) -> str:
        return self._data or getattr(self, self.default_form)


class Sentinel:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<SENTINEL ({id(self)})>"


sentinel = Sentinel()


# TODO: make it generators
_mapper_sentinel = Sentinel()


def mapdeafult(
    func: Callable[[T], ReturnT] | None,
    *iterables: Iterable[T] | NoneT,
    default: DefaultT | None = None,
    default_factory: Callable[[], DefaultT] | None = None,
    empty_check: bool = False,
    none: NoneT = None,
    check_values_before: bool = False,
    check_values_after: bool = False,
    weak_value_check: bool = False
) -> tuple[ReturnT, ...] | DefaultT:
    """ Map iterables. Return default if all values is none.
        Can check not only iterables, but also values on none.
    """

    if func is None:
        maps = [
            i
            for i in iterables
            if (empty_check and i) or i != none
        ]

    else:
        def mapper(val: T) -> ReturnT | Sentinel:
            if (
                check_values_before
                and ((weak_value_check and not val) or val == none)
            ):
                return _mapper_sentinel
            return func(val)

        maps = list()
        for i in iterables:
            if (empty_check and i) or i != none:
                maps.append(map(mapper, i))

    result = _mapdefault_validator(maps, none, check_values_after, weak_value_check)
    if result is None:
        if default_factory is not None and callable(default_factory):
            default = default_factory()
        return default
    return result


def _mapdefault_validator(
    maps: "list[map[ReturnT | NoneT | Sentinel]]",
    none: NoneT = None,
    check_values_after: bool = False,
    weak_value_check: bool = False
) -> tuple[ReturnT, ...] | None:
    if not maps:
        return None
    vals = tuple(
        i
        for i in itertools.chain(*maps)
        if (
            i is not _mapper_sentinel
            and (
                not check_values_after
                or (i != none and (not weak_value_check or i))
            )
        )
    )
    if not vals:
        return None
    return vals
