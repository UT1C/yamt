from typing import Annotated, ParamSpec, TypeVar, Generic, Callable, Concatenate, Any
import functools

T = TypeVar("T")
P = ParamSpec("P")
InstanceT = TypeVar("InstanceT")
InitFuncT = TypeVar("InitFuncT", bound=Callable[Concatenate[InstanceT, P], None])
SubP = ParamSpec("SubP")
UnboundFuncT = TypeVar("UnboundFuncT", bound=Callable[Concatenate[InstanceT, SubP], T])
BoundFuncT = TypeVar("BoundFuncT", bound=Callable[SubP, T])


class DecorationTrigger(Generic[InstanceT, P]):
    """ Decorator-postponing thing """

    decorators: list[
        tuple[
            Annotated[str, "FuncName"],
            Callable[[BoundFuncT], BoundFuncT | Any]
        ]
    ]

    def __init__(self) -> None:
        self.decorators = list()

    def on(self, init: InitFuncT) -> InitFuncT:
        @functools.wraps(init)
        def wrapper(instance: InstanceT, *args: P.args, **kwargs: P.kwargs) -> None:
            for name, decorator in self.decorators:
                func = getattr(instance, name)
                decorated = decorator(func)
                if isinstance(decorated, Callable):
                    try:
                        functools.update_wrapper(decorated, func)
                    except Exception as e:
                        ...
                setattr(instance, name, decorated)
            return init(instance, *args, **kwargs)
        return wrapper

    def apply(
        self,
        decorator: Callable[[BoundFuncT], BoundFuncT | Any],
        name: str | None = None
    ) -> Callable[[UnboundFuncT], UnboundFuncT]:
        def wrapper(func: UnboundFuncT) -> UnboundFuncT:
            nonlocal name

            if name is None:
                name = func.__name__
            self.decorators.append((name, decorator))
            return func
        return wrapper
