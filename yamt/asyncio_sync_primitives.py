from typing import Literal
import asyncio
import inspect
import traceback
import types
import logging

logger = logging.getLogger("yamt")


class ContextSkip(Exception):
    ...


class Grab:
    is_grabbed: bool = False

    async def __aenter__(self) -> None:
        if self.is_grabbed:
            raise ContextSkip()

        self.is_grabbed = True
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None
    ) -> Literal[True] | None:
        if isinstance(exc, ContextSkip):
            return True
        self.is_grabbed = False
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

    async def __aenter__(self) -> None:
        cur_frame = inspect.currentframe().f_back
        cur_hash = hash(cur_frame.f_code)

        if self.locked():
            for i, (frame, _) in enumerate(traceback.walk_stack(cur_frame)):
                if i == self.stack_limit:
                    break
                if hash(frame.f_code) in self.locked_stack:
                    self.locked_stack.append(cur_hash)
                    return None

        await super().__aenter__()
        self.locked_stack.append(cur_hash)
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None
    ) -> None:
        cur_frame = inspect.currentframe().f_back
        self.locked_stack.remove(hash(cur_frame.f_code))
        if self.locked():
            await super().__aexit__(exc_type, exc, tb)
        return None


class SemaphorePerSecond(asyncio.Semaphore):
    deffer_time: float
    _lock: asyncio.Lock

    def __init__(self, value: int = 1) -> None:
        super().__init__(value)
        self.deffer_time = 1 / value
        self._lock = asyncio.Lock()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None
    ) -> None:
        asyncio.create_task(self._deffered_exit(exc_type, exc, tb))
        return None

    async def _deffered_exit(self, *args, **kwargs):
        async with self._lock:
            await asyncio.sleep(self.deffer_time)
            await super().__aexit__(*args, **kwargs)
