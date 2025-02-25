# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
BAIN installer. In practice very rare, mostly superseded by FOMOD
"""

import re

from summonmm.common import *
from summonmm.plugins.archives import Archive, FileInArchive
from summonmm.plugins.arinstallers import (
    ArInstallerPluginBase,
    ArInstaller,
    ExtraArchiveDataFactory,
)
from summonmm.helpers.file_retriever import ArchiveFileRetriever
from summonmm.gitdata.stable_json import (
    StableJsonJsonSomething,
    StableJsonTypeDescriptor,
)


class _BainArInstallerInstallData:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("bain_folders", "bain", str)]
    bain_folders: list[str]

    def __init__(self, bf: list[str]) -> None:
        self.bain_folders = bf

    @classmethod
    def for_summon_stable_json_load(cls):
        return cls([])


class BainArInstaller(ArInstaller):
    bain_folders: list[str]

    def __init__(self, archive: Archive):
        super().__init__(archive)

    def name(self) -> str:
        return "BAIN"

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:
        if self.bain_folders[0].startswith("04"):
            pass

        out: list[tuple[str, FileInArchive]] = []
        returned: dict[str, bytes] = (
            {}
        )  # detect and remove duplicates: we must never return duplicate path

        srch = FastSearchOverPartialStrings([(bf, True) for bf in self.bain_folders])
        for fia in self.archive.files:
            found = srch.find_val_for_str(fia.intra_path)
            if found is not None and found[1]:
                assert fia.intra_path.startswith(found[0])
                rpath = fia.intra_path[len(found[0]) :]
                if rpath in returned:
                    if returned[rpath] != fia.file_hash:
                        # overwriting
                        for i in range(len(out)):
                            if out[i][0] == rpath:
                                out[i] = (rpath, fia)
                                break
                    pass  # do nothing; this target file is already installed with the same hash
                else:
                    out.append((rpath, fia))
                    returned[rpath] = fia.file_hash
        return out

    def install_params(self) -> Any:
        return _BainArInstallerInstallData(self.bain_folders)


class BainArInstallerPlugin(ArInstallerPluginBase):
    def name(self) -> str:
        return "BAIN"

    def guess_arinstaller_from_vfs(
        self,
        archive: Archive,
        modname: str,
        modfiles: dict[str, list[ArchiveFileRetriever]],
    ) -> ArInstaller | None:
        bainfolders: dict[str, int] = {}
        ntotal = 0
        nbain = 0
        bainpattern = re.compile(r"([0-9][0-9]+ [^\\]*\\)")
        for f in archive.files:
            ntotal += 1
            m = bainpattern.match(f.intra_path)
            if m:
                m1 = m.group(1)
                if m1 not in bainfolders:
                    bainfolders[m1] = 0
                nbain += 1

        if len(bainfolders) < 2:
            return None

        bfsorted = sorted([bf for bf in bainfolders])
        if not bfsorted[0].startswith("00 ") and not bfsorted[0].startswith("000 "):
            return None

        srch = FastSearchOverPartialStrings([(bf, True) for bf in bainfolders])
        for rlist in modfiles.values():
            if __debug__:
                r0 = rlist[0]
                for r in rlist:
                    assert r.file_hash == r0.file_hash

            unique_folder = None
            for r in rlist:
                assert isinstance(r, ArchiveFileRetriever)
                if r.archive_hash() == archive.archive_hash:
                    inarrpath = r.single_archive_retrievers[
                        0
                    ].file_in_archive.intra_path
                    found = srch.find_val_for_str(inarrpath)
                    if found is not None and found[1]:
                        assert inarrpath.startswith(found[0])
                        if unique_folder is None:
                            unique_folder = found[0]
                        else:
                            unique_folder = False
                            break

            if unique_folder is not None and unique_folder is not False:
                assert isinstance(unique_folder, str)
                bainfolders[unique_folder] += 1

        out = BainArInstaller(archive)
        out.bain_folders = sorted([bf for bf in bainfolders if bainfolders[bf] > 0])
        return out

    def init_from_load_json_data(self, data: StableJsonJsonSomething) -> None:
        assert False

    def data_for_save_json(self) -> StableJsonJsonSomething:
        assert False

    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        return None

    def add_extra_data(self, arh: bytes, data: Any | None | Exception) -> None:
        assert False


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
