# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
install_common is a part of summonmm.install, and as such is not allowed to use anything which is not a part of 
  default Python install (i.e. it is not allowed to use anything which requires pip modules)

install_common provides lots of basic functionality, and is imported using `from summonmm.install.install_common import *` 
  in most, if not all, summonmm py files
"""

# noinspection PyUnresolvedReferences
import os
import traceback as _traceback
import typing

# noinspection PyUnresolvedReferences
from abc import ABC, abstractmethod  # pyright: ignore

# noinspection PyUnresolvedReferences
from collections.abc import Callable, Generator, Iterable  # pyright: ignore

# noinspection PyUnresolvedReferences
from enum import Enum, IntEnum, Flag, IntFlag  # pyright: ignore

# noinspection PyUnresolvedReferences
from types import TracebackType, NoneType  # pyright: ignore

Any = typing.Any
ConfigData = dict[str, Any]

# noinspection PyUnresolvedReferences
from summonmm.install.install_logging import (
    debug,  # pyright: ignore
    info,  # pyright: ignore
    perf_warn,  # pyright: ignore
    warn,  # pyright: ignore
    alert,  # pyright: ignore
    critical,  # pyright: ignore
    info_or_perf_warn,  # pyright: ignore
    log_with_level,  # pyright: ignore
    enable_extended_logging,  # pyright: ignore
    start_file_logging,  # pyright: ignore
)


### error-handling related


class SummonBaseNetworkErrorHandler:
    """
    SummonBaseNetworkErrorHandler is a base class for network error handling
      (which may even involve UI interaction with user, see LinearUI class).
    """

    @abstractmethod
    def handle_error(self, op: str, errno: int) -> bool:
        pass


class SummonError(Exception):
    """
    SummonError is summonmm's own error
    """

    pass


def raise_if_not(cond: bool, msg: Callable[[], str] | str | None = None):
    """
    Can be seen as 'always assert', i.e. raise an exception even if __debug__ is False.

    :msg: is a string or lambda which returns error message
    """
    if not cond:
        msg1 = "raise_if_not() failed"
        if msg is not None:
            if callable(msg):
                msg1 += ": " + msg()
            else:
                assert isinstance(msg, str)
                msg1 += ": " + msg
            # else:
            #    assert False
        where = _traceback.extract_stack(limit=2)[0]
        critical(
            msg1
            + " @line "
            + str(where.lineno)
            + " of "
            + os.path.split(where.filename)[1]
        )
        raise SummonError(msg1)


### helpers


def open_3rdparty_txt_file_with_encoding(fname: str, encoding: str) -> typing.TextIO:
    """
    Opens 3rd-party file, trying to be as liberal as possible without pip modules installed.

    In summonmm.common there is an even more liberal function open_3rdparty_txt_file_autodetect(), with autodetecting encoding.
       In general, open_3rdparty_txt_file_autodetect() is preferred over open_3rdparty_txt_file_with_encoding() in NON-install contexts.
    """
    return open(fname, "rt", encoding=encoding, errors="replace")


def normalize_dir_path(path: str) -> str:
    """
    All summonmm dir names are always in lowercase, and always end with '\\'
    """
    path = os.path.abspath(path)
    assert "/" not in path
    assert not path.endswith("\\")
    return path.lower() + "\\"


def is_normalized_dir_path(path: str) -> bool:
    """
    All summonmm dir names are always in lowercase, and always end with '\\'
    """
    return path == os.path.abspath(path).lower() + "\\"


def normalize_file_path(path: str) -> str:
    """
    All summonmm file names are always in lowercase
    """
    assert not path.endswith("\\") and not path.endswith("/")
    path = os.path.abspath(path)
    assert "/" not in path
    return path.lower()


def is_normalized_file_path(path: str) -> bool:
    """
    All summonmm file names are always in lowercase
    """
    return path == os.path.abspath(path).lower()


def is_normalized_path(path: str) -> bool:
    """
    All summonmm paths are always in lowercase
    """
    return path == os.path.abspath(path).lower()


def to_short_path(base: str, path: str) -> str:
    assert path.startswith(base)
    return path[len(base) :]


def is_short_file_path(fpath: str) -> bool:
    assert not fpath.endswith("\\") and not fpath.endswith("/")
    if not fpath.islower():
        return False
    return not os.path.isabs(fpath)


def is_short_dir_path(fpath: str) -> bool:
    return fpath.islower() and fpath.endswith("\\") and not os.path.isabs(fpath)


def is_normalized_file_name(fname: str) -> bool:
    if "/" in fname or "\\" in fname:
        return False
    return fname.islower()


def normalize_file_name(fname: str) -> str:
    assert "\\" not in fname and "/" not in fname
    return fname.lower()


### UI


class LinearUIImportance(IntEnum):
    Default = 0
    Important = 1
    VeryImportant = 2


class LinearUITextInput:
    """
    Abstract text box, used as a part of abstract LinearUI
    """

    name: str
    value: str
    disabled: bool
    extra_data: Any

    def __init__(self, name: str, initvalue: str) -> None:
        self.name = name
        self.value = initvalue
        self.disabled = False
        self.extra_data = None


class LinearUICheckbox:
    """
    Abstract checkbox, used as a part of abstract LinearUI
    """

    name: str
    value: bool | None  # None is a special case meaning 'unknown'
    is_radio: bool
    disabled: bool
    extra_data: Any

    def __init__(self, name: str, initvalue: bool, isradio: bool = False) -> None:
        self.name = name
        self.value = initvalue
        self.is_radio = isradio
        self.disabled = False
        self.extra_data = None


type LinearUIControl = LinearUITextInput | LinearUICheckbox | "LinearUIGroup"
"""
Abstract control, used as a part of abstract LinearUI
"""


class LinearUIGroup:
    """
    Abstract group of controls, used as a part of abstract LinearUI
    """

    name: str
    controls: list[LinearUIControl]
    checkboxes_are_radio: bool | None
    extra_data: Any

    def __init__(self, name: str, controls: list[LinearUIControl]) -> None:
        self.name = name
        self.controls = controls
        self.checkboxes_are_radio = None
        self.extra_data = None
        for ctrl in controls:
            if isinstance(ctrl, LinearUICheckbox):
                if self.checkboxes_are_radio is None:
                    self.checkboxes_are_radio = ctrl.is_radio
                    if __debug__:
                        break
                else:
                    assert self.checkboxes_are_radio == ctrl.is_radio

    def add_control(self, ctrl: LinearUIControl) -> None:
        self.controls.append(ctrl)
        if isinstance(ctrl, LinearUICheckbox):
            if self.checkboxes_are_radio is None:
                self.checkboxes_are_radio = ctrl.is_radio
            else:
                assert self.checkboxes_are_radio == ctrl.is_radio

    def find_control(self, name: str) -> LinearUIControl | None:
        for ctrl in self.controls:
            if ctrl.name == name:
                return ctrl
        return None

    def find_control_by_path(self, path: list[str]) -> LinearUIControl | None:
        for ctrl in self.controls:
            if ctrl.name == path[0]:
                if isinstance(ctrl, LinearUIGroup):
                    return ctrl.find_control_by_path(path[1:])
                else:
                    return None
        return None


class LinearUI:
    """
    Abstract "linear" UI, i.e. UI with the flow defined by the program, and user only making limited choices
      within this flow.
    Still, can be used all the way up to multi-page wizards.

    An abstract class, so specific implementations are needed.

    TODO: add functionality to allow showing information to the user (moving stuff currently handled by direct logging
          calls such as info() into summonmm.install.install_ui.InstallUI as applicable).
    """

    @abstractmethod
    def set_silent_mode(self) -> None:
        pass

    @abstractmethod
    def message_box(
        self,
        prompt: str,
        spec: list[str],
        level: LinearUIImportance = LinearUIImportance.Default,
    ) -> str:
        pass

    @abstractmethod
    def input_box(
        self,
        prompt: str,
        default: str,
        level: LinearUIImportance = LinearUIImportance.Default,
    ) -> str:
        pass

    @abstractmethod
    def confirm_box(
        self, prompt: str, level: LinearUIImportance = LinearUIImportance.Default
    ) -> None:
        pass

    @abstractmethod
    def network_error_handler(self, nretries: int) -> SummonBaseNetworkErrorHandler:
        pass

    @abstractmethod
    def wizard_page(
        self,
        wizardpage: LinearUIGroup,
        validator: Callable[[LinearUIGroup], str | None] | None = None,
    ) -> None:
        pass


"""
The 3-Clause BSD License

Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.

Contributors: Mx Onym, Sherry Ignatchenko

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software
without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
