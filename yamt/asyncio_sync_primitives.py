from typing import TYPE_CHECKING, Literal
import asyncio
import inspect
import traceback
import types
import logging

if TYPE_CHECKING:
    from typing_extensions import Self

logger = logging.getLogger("yamt")


class ContextSkip(Exception):
    ...


class Grab:
    """ Usage example:
        ```
        async with Grab() as grab, grab.skip:
            ...
        ```
    """

    class Skip:
        grab: "Grab"

        def __init__(self, grab: "Grab") -> None:
            self.grab = grab

        async def __aenter__(self):
            if self.grab.grab_count > 1:
                raise ContextSkip()

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: types.TracebackType | None
        ):
            ...

    grab_count: int = 0
    skip: Skip

    def __init__(self) -> None:
        self.skip = self.Skip(self)

    async def __aenter__(self) -> "Self":
        self.grab_count += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None
    ) -> Literal[True] | None:
        if isinstance(exc, ContextSkip):
            return True
        self.grab_count -= 1
        return None


# TODO: fix stack inspection in recursive call (rework locked_stack)
class StackLimitedLock(asyncio.Lock):
    stack_limit: int | None
    locked_stack: list[int]

    def __init__(self, stack_limit: int | None = None) -> None:
        logger.warning("unstable synchronization primitive used")
        self.stack_limit = stack_limit
        self.locked_stack = list()
        super().__init__()

    async def acquire(self):
        cur_frame = inspect.currentframe().f_back
        cur_hash = hash(cur_frame.f_code)

        if self.locked():
            for i, (frame, _) in enumerate(traceback.walk_stack(cur_frame)):
                if i == self.stack_limit:
                    break
                if hash(frame.f_code) in self.locked_stack:
                    self.locked_stack.append(cur_hash)
                    return None

        await super().acquire()
        self.locked_stack.append(cur_hash)

    def release(self):
        cur_frame = inspect.currentframe().f_back
        self.locked_stack.remove(hash(cur_frame.f_code))
        if self.locked():
            super().release()


class PerSecondSemaphore(asyncio.Semaphore):
    deffer_time: float
    _lock: asyncio.Lock

    def __init__(self, value: int = 1) -> None:
        super().__init__(value)
        self.deffer_time = 1 / value
        self._lock = asyncio.Lock()

    def release(self):
        asyncio.create_task(self._deffered_exit())

    async def _deffered_exit(self):
        async with self._lock:
            await asyncio.sleep(self.deffer_time)
            super().release()


# deprecated
SemaphorePerSecond = PerSecondSemaphore


class LockOverflowError(Exception):
    ...


class OverflowLock(asyncio.Lock):
    limit: int
    counter: int = 0

    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__()

    async def acquire(self):
        if self.limit <= self.counter:
            raise LockOverflowError()

        await super().acquire()
        self.counter += 1

    def release(self):
        super().release()
        self.counter -= 1


class SkippedOverflowLock(OverflowLock):
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None
    ) -> bool | None:
        if isinstance(exc, LockOverflowError):
            return True
        return await super().__aexit__(exc_type, exc, tb)
