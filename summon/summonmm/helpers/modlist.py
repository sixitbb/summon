# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
class ModList
"""

from summonmm.common import *


class ModList:
    modlist: list[str] | None

    def __init__(self, dirpath: str) -> None:
        assert is_normalized_dir_path(dirpath)
        fname = dirpath + "modlist.txt"
        self.modlist = None
        with open_3rdparty_txt_file_autodetect(fname) as rf:
            self.modlist = [line.rstrip() for line in rf]
        self.modlist = list(
            filter(
                lambda s: s.endswith("_separator") or not s.startswith("-"),
                self.modlist,
            )
        )
        self.modlist.reverse()  # 'natural' order

    def write(self, path: str) -> None:
        assert self.modlist is not None
        fname = path + "modlist.txt"
        with open_3rdparty_txt_file_w(fname) as wfile:
            wfile.write("# This file was automatically modified by S.U.M.M.O.N.\n")
            for line in reversed(self.modlist):
                wfile.write(line + "\n")

    def write_disabling_if(self, path: str, f: Callable[[str], bool]) -> None:
        assert self.modlist is not None
        fname = path + "modlist.txt"
        with open_3rdparty_txt_file_w(fname) as wfile:
            wfile.write("# This file was automatically modified by S.U.M.M.O.N.\n")
            for mod0 in reversed(self.modlist):
                if mod0[0] == "+":
                    mod = mod0[1:]
                    if f(mod):
                        wfile.write("-" + mod + "\n")
                    else:
                        wfile.write(mod0 + "\n")
                else:
                    wfile.write(mod0 + "\n")

    def all_enabled(self) -> Generator[str]:
        assert self.modlist is not None
        for mod in self.modlist:
            if mod[0] == "+":
                yield mod[1:]

    @staticmethod
    def is_separator(
        modname: str,
    ) -> str | None:  # returns separator name if applicable
        if modname.endswith("_separator"):
            return modname[: len(modname) - len("_separator")]
        return None


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
