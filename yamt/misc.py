from typing import (
    TYPE_CHECKING,
    Generator,
    TypeVar,
    Callable,
    Annotated,
    Iterator,
    Generic,
    Literal,
    ClassVar,
    Any,
    overload,
)
from collections.abc import Iterable
from collections import UserString
from enum import Enum
import itertools
import random

from .exceptions import InjectionError

if TYPE_CHECKING:
    from typing_extensions import Self
    from .typing import SameAs

T = TypeVar("T")
TT = TypeVar("TT")
InstanceT = TypeVar("InstanceT", bound=object)
NoneT = TypeVar("NoneT")
DefaultT = TypeVar("DefaultT")
ReturnT = TypeVar("ReturnT")
SingletonT = TypeVar("SingletonT", bound="SingletonMeta")


def recursive_base_attributes(cls: type) -> Iterator[tuple[str, Any]]:
    if cls is object:
        return

    yield from cls.__dict__.items()
    for i in cls.__bases__:
        yield from recursive_base_attributes(i)


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

        self.__dict__.update((i.value, locs.get(i, "")) for i in WordForm)
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


@overload
def simple_chain(*items: Iterable[T] | T) -> Generator[T, None, None]:
    ...


@overload
def simple_chain(*items: Iterable[Any] | Any) -> Generator[Any, None, None]:
    ...


def simple_chain(*items: Iterable[Any] | Any) -> Generator[Any, None, None]:
    for i in items:
        if isinstance(i, Iterable):
            yield from i
        else:
            yield i


_mapper_sentinel = Sentinel()


def mapdefault(
    func: Callable[[T], ReturnT] | None,
    *iterables: Iterable[T] | NoneT,
    default: DefaultT | None = None,
    default_factory: Callable[[], DefaultT] | None = None,
    empty_check: bool = False,
    none: NoneT = None,
    check_values_before: bool = False,
    check_values_after: bool = False,
    weak_value_check: bool = False,
    as_tuple: bool = False
) -> tuple[ReturnT, ...] | Iterator[ReturnT] | DefaultT:
    """ Map iterables. Return default if all values is none.
        Can check not only iterables, but also values on none.
        Always calculates first element on call.
    """

    items = itertools.chain.from_iterable(
        i
        for i in iterables
        if i != none and (not empty_check or i)
    )
    if func is not None:
        items = (
            _mapper_sentinel if (
                check_values_before
                and (
                    (weak_value_check and not i)
                    or i == none
                )
            ) else func(i)
            for i in items
        )

    result = _mapdefault_generator(
        items,
        none,
        check_values_after,
        weak_value_check
    )
    if not next(result):
        if default_factory is not None:
            default = default_factory()
        return default
    if as_tuple:
        result = tuple(result)
    return result


def _mapdefault_generator(
    items: "Iterable[ReturnT | NoneT | Sentinel]",
    none: NoneT = None,
    check_values_after: bool = False,
    weak_value_check: bool = False
) -> Annotated[
    Iterator[ReturnT | bool],
    bool, ReturnT, ReturnT, ...
]:
    first = True

    for i in items:
        if i is _mapper_sentinel:
            continue
        if check_values_after:
            if not (weak_value_check and i):
                continue
            elif i == none:
                continue

        if first:
            yield True
            first = False
        yield i

    if first:
        yield False


class SingletonMeta(type, Generic[SingletonT]):
    __instance: SingletonT | None = None

    def __call__(cls: type[SingletonT], *args, **kwargs) -> SingletonT:
        if cls.__instance is None:
            cls.__instance = super().__call__(*args, **kwargs)
        return cls.__instance

    @classmethod
    def _wipe_singleton(cls):
        del cls.__instance
        cls.__instance = None


class IterativeRandomizer(Generic[T]):
    data: list[T]

    def __init__(self, data: Iterable[T]) -> None:
        self.data = list(data)

    def get(self) -> T:
        if len(self.data) == 1:
            return self.data[0]
        else:
            i = random.randint(0, len(self.data) - 2)
            value = self.data.pop(i)
            self.data.append(value)
            return value


def anyvalue(iterable: Iterable[T]) -> T | Literal[False]:
    try:
        return next(itertools.dropwhile(lambda x: not x, iterable))
    except StopIteration:
        return False


class DependencyInjector(Generic[T, InstanceT]):
    container: ClassVar[dict[str | type, Any]] = dict()
    key: str | type[T]

    def __init__(self, key: str | type[T]) -> None:
        self.key = key

    @property
    def value(self) -> T:
        return self.get(self.key)

    @overload
    def __get__(self, instance: InstanceT, cls: type[InstanceT] | None = None) -> T:
        ...

    @overload
    def __get__(self, instance: Literal[None], cls: type[InstanceT]) -> "Self":
        ...

    def __get__(
        self,
        instance: InstanceT | None,
        cls: type[InstanceT] | None = None
    ) -> T | "Self":
        if instance is None:
            return self
        return self.value

    @classmethod
    def store(cls, value: Annotated[TT, "SameAs[T]"], key: str | type[TT] | None = None) -> TT:
        if key is None:
            key = type(value)
        cls.container[key] = value
        return value

    @classmethod
    def get(cls, key: str | type[Annotated[TT, "SameAs[T]"]]) -> TT:
        value = cls.container.get(key)
        if value is None:
            raise InjectionError(key)
        return value
