# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
SIMPLEUNPACK archive installer. Simply unpacking archive, starting from root.
Very unusually for plugins, it is being relied on by another plugin: MO2DEFAULT one
"""

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


class SimpleUnpackArInstallerInstallData:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("install_from_root", "root")]
    install_from_root: str

    def __init__(self, ifr: str) -> None:
        self.install_from_root = ifr

    @classmethod
    def for_summon_stable_json_load(cls):
        return cls("")


class SimpleUnpackArInstaller(ArInstaller):
    install_from_root: str | None

    def __init__(self, archive: Archive):
        super().__init__(archive)
        self.install_from_root = None

    def name(self) -> str:
        return "SIMPLEUNPACK"

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:
        assert self.install_from_root is not None
        out: list[tuple[str, FileInArchive]] = []
        lifr = len(self.install_from_root)
        for fia in self.archive.files:
            if fia.intra_path.startswith(self.install_from_root):
                out.append((fia.intra_path[lifr:], fia))
        return out

    def install_params(self) -> Any:
        assert self.install_from_root is not None
        return SimpleUnpackArInstallerInstallData(self.install_from_root)


class SimpleUnpackArInstallerPlugin(ArInstallerPluginBase):
    def name(self) -> str:
        return "SIMPLEUNPACK"

    def guess_arinstaller_from_vfs(
        self,
        archive: Archive,
        modname: str,
        modfiles: dict[str, list[ArchiveFileRetriever]],
    ) -> ArInstaller | None:
        candidate_roots: dict[str, int] = {}
        for modpath, rlist in modfiles.items():
            if __debug__:
                r0 = rlist[0]
                for r in rlist:
                    assert r.file_hash == r0.file_hash
            for r in rlist:
                assert isinstance(r, ArchiveFileRetriever)
                if r.archive_hash() == archive.archive_hash:
                    inarrpath = r.single_archive_retrievers[
                        0
                    ].file_in_archive.intra_path
                    if inarrpath.endswith(modpath):
                        candidate_root = inarrpath[: -len(modpath)]
                        if candidate_root == "" or candidate_root.endswith("\\"):
                            if candidate_root not in candidate_roots:
                                candidate_roots[candidate_root] = 1
                            else:
                                candidate_roots[candidate_root] += 1

        if len(candidate_roots) == 0:
            return None
        out = SimpleUnpackArInstaller(archive)
        out.install_from_root = sorted(candidate_roots.items(), key=lambda x: x[1])[-1][
            0
        ]

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
