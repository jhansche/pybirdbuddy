"""Data models relating to bird Species"""

from __future__ import annotations
from collections import UserDict


class Species(UserDict[str, str]):
    """Species"""

    @property
    def id(self) -> str:
        """Species id or code"""
        return self["id"]

    @property
    def name(self) -> str:
        """Species name"""
        return self["name"]
