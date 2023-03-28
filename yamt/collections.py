from typing import (
    TYPE_CHECKING,
    TypeVar,
    Generic,
    Iterator,
    SupportsIndex,
    Literal,
    Callable,
    Any,
    overload,
)
from collections.abc import Iterable, MutableSequence
from collections import deque
import itertools
import random

from .typing import SupportsRichComparison

if TYPE_CHECKING:
    from typing_extensions import Self

T = TypeVar("T")
MSeqT = TypeVar("MSeqT", bound=MutableSequence)


class ChainedSequence(MutableSequence, Generic[MSeqT, T]):
    seqs: tuple[MSeqT | MutableSequence[T]]

    @overload
    def __init__(self, *seqs: MSeqT | MutableSequence[T]) -> None:
        ...

    @overload
    def __init__(
        self,
        *seqs: Iterable[T],
        class_: type[MSeqT] | type[MutableSequence]
    ) -> None:
        ...

    def __init__(
        self,
        *seqs: MSeqT | MutableSequence[T] | Iterable[T],
        class_: type[MSeqT] | type[MutableSequence] | None = None
    ) -> None:
        assert seqs
        if class_ is not None:
            seqs = tuple(map(class_, seqs))
        self.seqs = seqs

    def __contains__(self, value: Any) -> bool:
        for i in self.seqs:
            if value in i:
                return True
        return False

    def __iter__(self) -> Iterator[T]:
        return iter(itertools.chain(*self.seqs))

    def __len__(self) -> int:
        return sum(map(len, self.seqs))

    def __reversed__(self) -> Iterator[T]:
        return reversed(tuple(iter(self)))

    @overload
    def __getitem__(self, index: SupportsIndex) -> T:
        ...

    @overload
    def __getitem__(self, index: slice) -> MSeqT | MutableSequence[T]:
        ...

    def __getitem__(self, index: SupportsIndex | slice) -> T | MSeqT | MutableSequence[T]:
        index = self._resolve_index(index)
        if isinstance(index, int):
            index, seq = self._get_seq_by_overall_index(index)
            return seq[index]

        start, stop, step, rev = index
        chained = tuple(reversed(self) if rev else self)
        return self.seqs[0].__class__(chained[start:stop:step])

    @overload
    def __setitem__(self, index: SupportsIndex, value: T):
        ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[T]):
        ...

    def __setitem__(self, index: SupportsIndex | slice, value: T | Iterable[T]):
        index = self._resolve_index(index)
        if isinstance(index, SupportsIndex):
            index, seq = self._get_seq_by_overall_index(index)
            seq[index] = value

        start, stop, step, rev = index
        if rev:
            value = reversed(value)
        for i, cur_val in zip(range(start, stop + 1, step), value):
            self[i] = cur_val

    def __delitem__(self, index: SupportsIndex | slice):
        index = self._resolve_index(index)
        if isinstance(index, SupportsIndex):
            index, seq = self._get_seq_by_overall_index(index)
            del seq[index]
        else:
            start, stop, step, _ = index
            for i in range(start, stop + 1, step):
                del self[i]

    def __bool__(self) -> bool:
        return any(self.seqs)

    def __repr__(self) -> str:
        return f"<{self}>"

    def __str__(self) -> str:
        items_repr = ", ".join(map(repr, self.seqs))
        return f"ChainedSequence({items_repr})"

    def __format__(self, format_spec: str) -> str:
        return str(self).__format__(format_spec)

    def __copy__(self) -> "Self | MSeqT | MutableSequence[T]":
        return self.__class__(*(i.copy() for i in self.seqs))

    @property
    def specs(self) -> Iterator[tuple[int, int, MSeqT | MutableSequence[T]]]:
        """ Yields contained sequences and its start and end indices """
        index = 0
        for seq in self.seqs:
            if len(seq) == 0:
                yield index, index, seq
            else:
                yield index, (index := index + len(seq)) - 1, seq

    def index(
        self,
        value: Any,
        start: SupportsIndex = 0,
        stop: SupportsIndex = -1
    ) -> int:
        return tuple(self).index(value, start, stop)

    def count(self, value: Any) -> int:
        return tuple(self).count(value)

    def insert(self, index: SupportsIndex, value: T):
        index, seq = self._get_seq_by_overall_index(index)
        seq.insert(index, value)

    def append(self, value: T):
        self.seqs[-1].append(value)

    def extend(self, values: Iterable[T]):
        self.seqs[-1].extend(values)

    def pop(self, index: SupportsIndex = -1) -> T:
        index, seq = self._get_seq_by_overall_index(index)
        return seq.pop(index)

    def remove(self, value: T):
        for i in self.seqs:
            ln = len(i)
            i.remove(value)
            if ln != len(i):
                return

    def copy(self) -> "Self | MSeqT | MutableSequence[T]":
        return self.__copy__()

    @overload
    def reverse(self, *, only_containers: Literal[True]):
        ...

    @overload
    def reverse(self, *, only_contained: Literal[True]):
        ...

    def reverse(
        self,
        *,
        only_containers: bool = False,
        only_contained: bool = False
    ):
        assert not (only_containers and only_contained)
        if not only_containers:
            for i in self.seqs:
                i.reverse()
        if not only_contained:
            self.seqs = tuple(reversed(self.seqs))

    def clear(self):
        for i in self.seqs:
            i.clear()

    @overload
    def _resolve_index(self, index: SupportsIndex) -> int:
        ...

    @overload
    def _resolve_index(self, index: slice) -> tuple[int | None, int | None, int | None, bool]:
        ...

    @overload
    def _resolve_index(self, index: None) -> None:
        ...

    def _resolve_index(
        self,
        index: SupportsIndex | slice | None
    ) -> int | tuple[int | None, int | None, int | None, bool] | None:
        if index is None:
            return None
        ln = len(self)

        if isinstance(index, SupportsIndex):
            if not isinstance(index, int):
                index = index.__index__()
            if index < 0:
                return ln + index
            return index

        start, stop = map(
            self._resolve_index,
            (index.start, index.stop)
        )
        step = index.step
        r = False
        if step is not None and step < 0:
            r = True
            if start is not None:
                start = ln - start
            if stop is not None:
                stop = ln - stop
            step = abs(step) - 1
        return start, stop, step, r

    def _get_seq_by_overall_index(
        self,
        index: SupportsIndex
    ) -> tuple[int, MSeqT | MutableSequence[T]]:
        index = self._resolve_index(index)
        for start, end, seq in self.specs:
            if start == end:
                continue
            if start <= index <= end:
                break
        return index - start, seq  # true shit

    def shuffle(self):
        for i in self.seqs:
            if i:
                random.shuffle(i)


class ChainedList(ChainedSequence[list[T], T], Generic[T]):
    def sort(
        self,
        *,
        key: Callable[[T], SupportsRichComparison] | None = None,
        reverse: bool = False
    ):
        for i in self.seqs:
            i.sort(key=key, reverse=reverse)


class ChainedDeque(ChainedSequence[deque[T], T], Generic[T]):
    @property
    def maxlen(self) -> int | None:
        maxlens = tuple(i.maxlen for i in self.seqs)
        if not any(maxlens):
            return None
        return sum(i for i in maxlens if i is not None)

    def pop(self, index: SupportsIndex = -1) -> T:
        index, seq = self._get_seq_by_overall_index(index)
        val = seq[index]
        del seq[index]
        return val

    def popleft(self) -> T:
        for i in self.seqs:
            if i:
                break
        return i.popleft()

    def appendleft(self, value: T):
        self.seqs[-1].appendleft(value)

    def extendleft(self, value: Iterable[T]):
        self.seqs[-1].extendleft(value)

    def rotate(self, n: int):
        for i in self.seqs:
            i.rotate(n)
