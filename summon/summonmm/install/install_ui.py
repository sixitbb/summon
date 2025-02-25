# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
install_ui is a part of summonmm.install, and as such is not allowed to use anything which is not a part of 
  default Python install (i.e. it is not allowed to use anything which requires pip modules)

Provides InstallUI : a purely console-based incarnation of summonmm.install_common.LinearUI. 
"""

import logging

from summonmm.install.install_common import *
from summonmm.install.install_logging import log_with_level


class _BoxUINetworkErrorHandler(SummonBaseNetworkErrorHandler):
    ui: "InstallUI"
    initial_retries: int
    remaining_retries: int

    def __init__(self, ui: "InstallUI", retries: int) -> None:
        self.ui = ui
        self.initial_retries = retries
        self.remaining_retries = retries

    def handle_error(self, op: str, errno: int) -> bool:
        self.remaining_retries -= 1
        if self.remaining_retries <= 0:
            choice = self.ui.message_box(
                "{} failed. Please check your Internet connection. Do you want to retry?".format(
                    op
                ),
                ["Yes", "no"],
            )
            return choice != "no"
        else:
            return True


class InstallUI(LinearUI):
    """
    A purely console-based incarnation of summonmm.install_common.LinearUI.
    """

    _silent_mode: bool

    def __init__(self) -> None:
        self._silent_mode = False

    def set_silent_mode(self) -> None:
        self._silent_mode = True

    def message_box(
        self,
        prompt: str,
        spec: list[str],
        level: LinearUIImportance = LinearUIImportance.Default,
    ) -> str:
        assert len(spec) > 0
        assert len(set([s[0].lower() for s in spec])) == len(spec)
        specstr = "/".join(spec)
        while True:
            log_with_level(
                InstallUI._translate_level(level), "{} ({})".format(prompt, specstr)
            )
            got = "" if self._silent_mode else input().lower().strip()
            if got == "":
                log_with_level(level, spec[0])
                return spec[0]
            for i in range(len(spec)):
                if spec[i].lower() == got or spec[i][0].lower() == got:
                    return spec[i]

    def input_box(
        self,
        prompt: str,
        default: str,
        level: LinearUIImportance = LinearUIImportance.Default,
    ) -> str:
        log_with_level(
            InstallUI._translate_level(level), "{} [{}]".format(prompt, default)
        )
        got = "" if self._silent_mode else input()
        if got.strip() == "":
            log_with_level(InstallUI._translate_level(level), default)
            return default
        return got

    def confirm_box(
        self, prompt: str, level: LinearUIImportance = LinearUIImportance.Default
    ) -> None:
        log_with_level(InstallUI._translate_level(level), prompt)
        if not self._silent_mode:
            input()

    def network_error_handler(self, nretries: int) -> SummonBaseNetworkErrorHandler:
        return _BoxUINetworkErrorHandler(self, nretries)

    def wizard_page(
        self,
        wizardpage: LinearUIGroup,
        validator: Callable[[LinearUIGroup], str | None] | None = None,
    ) -> None:
        stack: list[str] = []
        while True:
            if len(stack) == 0:
                curgrp = wizardpage
                curgrptype = "wizard page"
            else:
                curgrp = wizardpage.find_control_by_path(stack)
                curgrptype = "current group page"
                info("Current group: {}".format(repr(stack)))
            assert isinstance(curgrp, LinearUIGroup)
            for i, ctrl in enumerate(curgrp.controls):
                InstallUI._print_control(i, ctrl)
            info("[p] to print the whole {}".format(curgrptype))
            info("[x] to exit {} with current settings".format(curgrptype))

            got = "x" if self._silent_mode else input().lower().strip()
            if got == "x":
                if len(stack) == 0:
                    if validator is not None:
                        errmsg = validator(wizardpage)
                    else:
                        errmsg = None
                    if errmsg is None:
                        break
                    else:
                        alert("Error validating wizard page: {}".format(errmsg))
                else:
                    stack.pop()
            elif got == "p":
                for i, ctrl in enumerate(curgrp.controls):
                    InstallUI._print_control(i, ctrl, True)
            elif got.isdigit():
                idx = int(got)
                if 0 <= idx <= len(curgrp.controls):
                    ctrl = curgrp.controls[idx]
                    if isinstance(ctrl, LinearUIGroup):
                        stack.append(ctrl.name)
                        continue
                    elif isinstance(ctrl, LinearUICheckbox):
                        if not ctrl.disabled:
                            if ctrl.is_radio:
                                assert curgrp.checkboxes_are_radio
                                for c2 in curgrp.controls:
                                    if isinstance(c2, LinearUICheckbox):
                                        c2.value = False
                                ctrl.value = True
                            else:
                                assert not curgrp.checkboxes_are_radio
                                ctrl.value = not ctrl.value
                    else:
                        assert isinstance(ctrl, LinearUITextInput)
                        assert not self._silent_mode
                        if not ctrl.disabled:
                            got2 = input().strip()
                            ctrl.value = got2
            else:
                pass

    @staticmethod
    def _print_control(
        i: int | str, ctrl: LinearUIControl, recursive: bool = False
    ) -> None:
        assert isinstance(i, (int, str))
        prefix = "[{}]".format(i) if isinstance(i, int) else i
        if isinstance(ctrl, LinearUITextInput):
            info("{}{}:{}".format(prefix, ctrl.name, ctrl.value))
        elif isinstance(ctrl, LinearUICheckbox):
            info("{}{}:[{}]".format(prefix, ctrl.name, "X" if ctrl.value else " "))
        else:
            assert isinstance(ctrl, LinearUIGroup)
            if recursive:
                info("{}{{{}}}:".format(prefix, ctrl.name))
                if isinstance(i, int):
                    for ctrl in ctrl.controls:
                        InstallUI._print_control("  ", ctrl)
                else:
                    for ctrl in ctrl.controls:
                        InstallUI._print_control(prefix + "  ", ctrl)
            else:
                info(
                    "{}{{{}}} (group of {} elements)".format(
                        prefix, ctrl.name, len(ctrl.controls)
                    )
                )
        # else:
        #    assert False

    @staticmethod
    def _translate_level(level: LinearUIImportance = LinearUIImportance.Default) -> int:
        match level:
            case LinearUIImportance.Default:
                return logging.INFO
            case LinearUIImportance.Important:
                return logging.ERROR
            case LinearUIImportance.VeryImportant:
                return logging.CRITICAL


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
