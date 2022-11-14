from typing import TYPE_CHECKING, Any
from enum import EnumMeta, Enum

from .misc import recursive_base_attributes

if TYPE_CHECKING:
    from typing_extensions import Self


# TODO: try to fix typehints (maybe with typestubs?)
class DataRichEnumMeta(EnumMeta):
    @classmethod
    def __prepare__(
        metacls,
        cls: str,
        bases: tuple[type, ...],
        *,
        extender: type | None = None
    ) -> Any:
        return super().__prepare__(cls, bases)

    def __new__(
        metacls,
        cls_name: str,
        bases: tuple[type, ...],
        classdict: dict[str, Any],
        *,
        extender: type | None = None
    ) -> "Self":
        containers: list[tuple[str, Any]] = list()
        containers_names: tuple[str, ...] | None

        if extender is not None:
            annotations: dict | None = classdict.get("__annotations__")
            if annotations is not None:
                annotations.update(extender.__annotations__)
            for k, v in recursive_base_attributes(extender):
                classdict.setdefault(k, v)

        containers_names = classdict.pop("__containers__", None)
        if containers_names is not None:
            assert isinstance(containers_names, tuple)
            for name in containers_names:
                containers.append((name, classdict.pop(name)))

            classdict._member_names = sorted(
                set(classdict._member_names).difference(containers_names),
                key=tuple(classdict._member_names).index
            )
            classdict._ignore.extend(containers_names)
            classdict["_ignore_"] = classdict._ignore

        cls = super().__new__(metacls, cls_name, bases, classdict)

        if containers:
            for k, v in containers:
                setattr(cls, k, v)
        return cls


class DataRichEnum(Enum, metaclass=DataRichEnumMeta):
    ...


class IntDataRichEnum(int, DataRichEnum):
    ...
