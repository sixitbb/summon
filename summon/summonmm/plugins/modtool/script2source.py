# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


import re

from summonmm.common import *
from summonmm.plugins.modtools import (
    ModToolPluginBase,
    ModToolGuessParam,
    ModToolGuessDiff,
)
from summonmm.gitdata.stable_json import StableJsonTypeDescriptor


class Script2SourceModToolData:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("script2source", "script2source"),
    ]
    script2source: bool


class Script2SourceModToolPlugin(ModToolPluginBase):
    def name(self) -> str:
        return "SCRIPT2SOURCE"

    def supported_games(self) -> list[str]:
        return ["SKYRIM"]

    def guess_applied(
        self, param: ModToolGuessParam
    ) -> None | tuple[Any, ModToolGuessDiff]:
        g = Script2SourceModToolPlugin._guess_s2s_forward(param)
        return g

    # yes, s2s tool renames whole folder, so it is "all or nothing" tool
    @staticmethod
    def _guess_s2s_forward(
        param: ModToolGuessParam,
    ) -> None | tuple[Any, ModToolGuessDiff]:
        pattern = re.compile(r"source\\scripts\\([ 0-9a-z_-]*\.psc)")
        pattern2 = re.compile(r"scripts\\source\\([ 0-9a-z_-]*\.psc)")
        mv: list[tuple[str, str]] = []
        n2 = None
        for f, retr in param.remaining_after_install_from.items():
            fh = truncate_file_hash(retr[0].file_hash)
            m = pattern.match(f)
            if m:
                fname = m.group(1)
                lmv = len(mv)
                for ar in param.install_from:
                    if "scripts\\source\\" + fname in ar[1].skip:
                        n2a = 0
                        for ff, fia in ar[0].all_desired_files():
                            if ff == "scripts\\source\\" + fname:
                                assert len(fia.file_hash) == len(fh)
                                if fia.file_hash == fh:
                                    mv.append(
                                        (
                                            "scripts\\source\\" + fname,
                                            "source\\scripts\\" + fname,
                                        )
                                    )
                                else:
                                    return None  # all or nothing
                            if pattern2.match(ff):
                                n2a += 1

                        if n2 is None:
                            n2 = n2a
                        else:
                            assert n2 == n2a
                    else:
                        return None  # all or nothing
                assert len(mv) - lmv <= 1

        if len(mv) == 0:
            return None
        if n2 != len(mv):
            return None  # all or nothing
        out = ModToolGuessDiff()
        out.moved = mv
        data = Script2SourceModToolData()
        data.script2source = True
        return data, out


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
