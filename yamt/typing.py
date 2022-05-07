from typing import Protocol, Any


class SupportsRichComparison(Protocol):
    def __lt__(self, other: Any) -> bool:
        ...

    def __gt__(self, other: Any) -> bool:
        ...
