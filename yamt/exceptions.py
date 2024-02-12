from typing import Any


class InjectionError(Exception):
    def __init__(self, key: Any) -> None:
        super().__init__(f"'{key}' instance is inaccessible")
