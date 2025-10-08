from __future__ import annotations

import abc
import builtins
import re
from functools import lru_cache
from typing import Any

builtins.id(re.compile("a").search("a".lower(), 0, endpos=1))

r"raw string"

A = [
    3.14,
    10.,
    .001,
]

B = (
    1e100,
    3.14e-10,
    0e0,
    3.14_15_93,
)

C = {
    3.14j,
    10.j,
    10j,
}

# $anchor1

D = {
    '''A''': .001j,
    br'bytes\\': 1e100j,
    # comment
    f"""formatted {id(f'{
        Any                       # $anchor2
    }')} string""": 3.14e-10j,
    " \N{NULL} \000 \x00 \u0000 \U00000000 \" ": 3.14_15_93j,
}


class AClass:
    ...  # $anchor3


class Class(abc.ABC, metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def a(self):
        pass

    @lru_cache(1, typed=True)
    def b(self):
        return self.__class__.SubClass.__init__

    class SubClass:

        @staticmethod
        def method():
            dictionary = {
                "a": 1,
                "b": 2,  # $anchor4
            }
            return dictionary["a"]

    def __init__(self):
        self.b = 1

# $anchor5


def func(a: int = (
    # comment
), b: str = "a", *c: Class, d: dict[str, int] = None, **e: int) -> None:
    def func2():
        pass  # comment

    class C:
        pass

    c = C()

    return None
