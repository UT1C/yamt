from typing import (
    Awaitable,
    TypeVar,
    Iterable,
    Generic,
    NoReturn,
    Callable,
)
import asyncio

from typing_extensions import Self

from .misc import Sentinel

T = TypeVar("T")
NoneT = TypeVar("NoneT")
DefaultT = TypeVar("DefaultT")
ReturnT = TypeVar("ReturnT")


def autogather(
    *coros: Awaitable[T] | T | Iterable[Awaitable[T]] | Iterable[T],
    return_exceptions: bool = False
) -> Awaitable[tuple[T | BaseException, ...]]:
    actual_coros = list()
    for i in coros:
        if isinstance(i, Iterable):
            actual_coros.extend(i)
        else:
            actual_coros.append(i)
    return asyncio.gather(
        *map(_autogather_executor, actual_coros),
        return_exceptions=return_exceptions
    )


def _autogather_executor(coro: Awaitable[T] | T) -> T:
    if asyncio.iscoroutine(coro):
        return coro
    return _AwaitableWrap(coro)


class _AwaitableWrap(Generic[T]):
    val: T

    def __init__(self, val: T) -> None:
        self.val = val

    def __await__(self) -> Self:
        return self

    def __next__(self) -> NoReturn:
        raise StopIteration(self.val)


# TODO: make it generators
_mapper_sentinel = Sentinel()


async def amapdeafult(
    func: Callable[[T], Awaitable[ReturnT]] | None,
    *iterables: Iterable[T] | NoneT,
    default: DefaultT | None = None,
    default_factory: Callable[[], DefaultT | Awaitable[DefaultT]] | None = None,
    empty_check: bool = False,
    none: NoneT = None,
    check_values_before: bool = False,
    check_values_after: bool = False,
    weak_value_check: bool = False
) -> tuple[ReturnT, ...] | DefaultT:
    """ async version of mapdefault with coro support """

    if func is None:
        maps = [
            i
            for i in iterables
            if (empty_check and i) or i != none
        ]

    else:
        async def amapper(val: T) -> ReturnT | Sentinel:
            if (
                check_values_before
                and ((weak_value_check and not val) or val == none)
            ):
                return _mapper_sentinel
            return await func(val)

        maps = list()
        for i in iterables:
            if (empty_check and i) or i != none:
                maps.append((amapper(val) for val in i))

    result = await _amapdefault_validator(
        maps,
        none,
        check_values_after,
        weak_value_check
    )
    if result is None:
        if default_factory is not None and callable(default_factory):
            default = default_factory()
        if asyncio.iscoroutine(default_factory):
            default = await default
        return default
    return result


async def _amapdefault_validator(
    maps: "list[map[ReturnT | NoneT | Sentinel]]",
    none: NoneT = None,
    check_values_after: bool = False,
    weak_value_check: bool = False
) -> tuple[ReturnT, ...] | None:
    if not maps:
        return None
    vals = tuple(
        i
        for i in (await autogather(*maps))
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
