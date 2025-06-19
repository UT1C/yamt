from typing import (
    TYPE_CHECKING,
    TypeVar,
    Generic,
    NoReturn,
    Annotated,
    Any,
)
from collections.abc import (
    Iterable,
    Generator,
    Callable,
    AsyncIterator,
    Awaitable,
    Hashable,
    Sequence,
)
from collections import defaultdict
import itertools
import functools
import asyncio

from .misc import Sentinel

if TYPE_CHECKING:
    from typing_extensions import Self

T = TypeVar("T")
NoneT = TypeVar("NoneT")
DefaultT = TypeVar("DefaultT")
ReturnT = TypeVar("ReturnT")
CallableT = TypeVar("CallableT", bound=Callable)
KeyT = TypeVar("KeyT", bound=Hashable)
InstanceT = TypeVar("InstanceT")


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

    def __await__(self) -> "Self":
        return self

    def __next__(self) -> NoReturn:
        raise StopIteration(self.val)


_mapper_sentinel = Sentinel()


async def amapdefault(
    func: Callable[[T], Awaitable[ReturnT]] | None,
    *iterables: Iterable[T] | NoneT,
    default: DefaultT | None = None,
    default_factory: Callable[[], DefaultT | Awaitable[DefaultT]] | None = None,
    empty_check: bool = False,
    none: NoneT = None,
    check_values_before: bool = False,
    check_values_after: bool = False,
    weak_value_check: bool = False,
    as_list: bool = False
) -> list[ReturnT] | AsyncIterator[ReturnT] | DefaultT:
    """ async version of mapdefault with coro support """

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
            ) else await func(i)
            for i in items
        )

    result = _amapdefault_generator(
        items,
        none,
        check_values_after,
        weak_value_check
    )
    if not next(result):
        if default_factory is not None:
            default = default_factory()
        if asyncio.iscoroutine(default_factory):
            default = await default
        return default
    if as_list:
        result = [i async for i in result]
    return result


async def _amapdefault_generator(
    items: "Iterable[ReturnT | NoneT | Sentinel]",
    none: NoneT = None,
    check_values_after: bool = False,
    weak_value_check: bool = False
) -> Annotated[
    AsyncIterator[ReturnT | bool],
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


class AsyncEventManager(Generic[KeyT]):
    handlers: dict[KeyT, list[tuple[Callable, bool]]]
    _loop: asyncio.AbstractEventLoop | None

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop
        self.handlers = defaultdict(list)

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        return self._loop

    async def emit(self, name: KeyT, *args, **kwargs) -> Sequence:
        return await asyncio.gather(
            *(
                func(name, *args, **kwargs) if with_name else func(*args, **kwargs)
                for func, with_name in self.handlers[name]
            )
        )

    def dispatch(self, name: KeyT, *args, **kwargs) -> asyncio.Task[Sequence]:
        return self.loop.create_task(self.emit(name, *args, **kwargs))

    def dispatcher(self, name: KeyT, *args, **kwargs) -> functools.partial["dispatch"]:
        return functools.partial(self.dispatch, name, *args, **kwargs)

    def on(self, name: KeyT, with_name: bool = False) -> Callable[[CallableT], CallableT]:
        def wrapper(func: CallableT) -> CallableT:
            self.handlers[name].append((func, with_name))
            return func
        return wrapper


class AwaitableDescriptor(Generic[T, InstanceT]):
    func: Callable[[InstanceT], Awaitable[T]]
    _instance: InstanceT

    def __init__(self, func: Callable[[InstanceT], Awaitable[T]]) -> None:
        self.func = func

    def __get__(self, instance: InstanceT, owner=None) -> "Self":
        self._instance = instance
        return self

    def __await__(self) -> Generator[Any, Any, T]:
        return self.get().__await__()

    async def get(self) -> T:
        return await self.func(self._instance)


class CachedAwaitableDescriptor(AwaitableDescriptor[T, InstanceT], Generic[T, InstanceT]):
    @property
    def key(self) -> str:
        return f"_cache_{id(self)}"

    async def get(self) -> T:
        key = self.key
        value = getattr(self._instance, key, None)
        if value is None:
            value = await super().get()
            setattr(self._instance, key, value)
        return value
