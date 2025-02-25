# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


import zipfile

from summonmm.common import *
from summonmm.plugins.archives import ArchivePluginBase


class ZipArchivePlugin(ArchivePluginBase):
    def extensions(self) -> list[str]:
        return [".zip"]

    def extract(
        self, archive: str, listoffiles: list[str], targetpath: str
    ) -> list[str | None]:
        info("Extracting {} file(s) from {}...".format(len(listoffiles), archive))
        z = zipfile.ZipFile(archive)
        names = {n.lower(): n for n in z.namelist()}
        lof_normalized: list[str] = []
        for f in listoffiles:
            normf = f.replace("\\", "/")
            if __debug__ and normf not in names:
                assert False
            lof_normalized.append(names[normf])
        out: list[str | None] = []
        for f in lof_normalized:
            z.extract(f, path=targetpath)
            if os.path.isfile(targetpath + f):
                out.append(targetpath + f)
            else:
                warn("{} NOT EXTRACTED from {}".format(f, archive))
                out.append(None)
        z.close()
        print("Extraction done")
        return out

    def extract_all(self, archive: str, targetpath: str) -> None:
        info("Extracting all from {}...".format(archive))
        z = zipfile.ZipFile(archive)
        z.extractall(targetpath)
        z.close()
        info("Extraction done")


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
