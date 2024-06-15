from typing import Protocol, Generic, TypeVar, Any

T = TypeVar("T")


class SupportsRichComparison(Protocol):
    def __lt__(self, other: Any) -> bool:
        ...

    def __gt__(self, other: Any) -> bool:
        ...


class SameAs(Generic[T]):
    """ Annotation, marks exactly the same type in context.
        Exists for compatability reasons.
    """
    ...
