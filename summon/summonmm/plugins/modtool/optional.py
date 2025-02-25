# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import re

from summonmm.common import *
from summonmm.plugins.archives import FileInArchive
from summonmm.plugins.modtools import (
    ModToolPluginBase,
    ModToolGuessParam,
    ModToolGuessDiff,
)
from summonmm.gitdata.stable_json import StableJsonTypeDescriptor


class OptionalModToolData:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("opt", "opt", str),
        ("unopt", "unopt", str),
    ]
    opt: list[str]
    unopt: list[str]


class OptionalModToolPlugin(ModToolPluginBase):
    def name(self) -> str:
        return "OPTIONAL"

    def supported_games(self) -> list[str]:
        return ["SKYRIM"]

    def guess_applied(
        self, param: ModToolGuessParam
    ) -> None | tuple[Any, ModToolGuessDiff]:
        pattern = re.compile(r"optional\\([ 0-9a-z_-]*\.es[plm])")
        mv: list[tuple[str, str]] = []
        opt: list[str] = []
        for f, retr in param.remaining_after_install_from.items():
            fh = truncate_file_hash(retr[0].file_hash)
            m = pattern.match(f)
            if m:
                fname = m.group(1)
                lmv = len(mv)
                for ar in param.install_from:
                    if fname in ar[1].skip:
                        for ff, fia in ar[0].all_desired_files():
                            if ff == fname:
                                assert len(fia.file_hash) == len(fh)
                                if fia.file_hash == fh:
                                    mv.append((fname, "optional\\" + fname))
                                    opt.append(fname)
                                break
                assert len(mv) - lmv <= 1
                assert len(opt) == len(mv)

        unopt: list[str] = []
        for ar in param.install_from:
            for ff in ar[1].skip:
                m = pattern.match(ff)
                if m:
                    found: FileInArchive | None = None
                    for ff2, fia in ar[0].all_desired_files():
                        if ff2 == ff:
                            found = fia
                            break
                    assert found is not None

                    fname = m.group(1)
                    if fname in param.remaining_after_install_from:
                        retr = param.remaining_after_install_from[fname]
                        fh = truncate_file_hash(retr[0].file_hash)
                        assert len(found.file_hash) == len(fh)
                        if found.file_hash == fh:
                            mv.append(("optional\\" + fname, fname))
                            unopt.append(fname)

        assert len(opt) + len(unopt) == len(mv)

        if len(mv) == 0:
            return None
        out = ModToolGuessDiff()
        out.moved = mv
        data = OptionalModToolData()
        data.opt = opt
        data.unopt = unopt
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
