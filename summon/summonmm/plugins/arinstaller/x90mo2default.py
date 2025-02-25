# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
MO2DEFAULT archive installer. Guess-only: we'll be trying to guess what MO2 did when installed,
but we won't install like this ourselves, preferring SIMPLEUNPACK.

MO2DEFAULT is almost the same as SIMPLEUNPACK installer, just copying non-data files to the root too.
Very unusually for plugins, MO2DEFAULT plugin relies on another plugin ('SIMPLEUNPACK' one).
"""

from summonmm.common import *
from summonmm.gitdata.stable_json import StableJsonJsonSomething
from summonmm.plugins.archives import Archive, FileInArchive
from summonmm.plugins.arinstallers import (
    ArInstallerPluginBase,
    ArInstaller,
    ExtraArchiveDataFactory,
)
from summonmm.helpers.file_retriever import ArchiveFileRetriever
from summonmm.plugins.arinstaller.x99simpleunpack import (
    SimpleUnpackArInstaller,
    SimpleUnpackArInstallerPlugin,
)


class Mo2DefaultArInstaller(SimpleUnpackArInstaller):
    def __init__(self, archive: Archive):
        super().__init__(archive)

    def name(self) -> str:
        return "MO2DEFAULT"

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:  # list[relpath]
        out: list[tuple[str, FileInArchive]] = list(super().all_desired_files())
        assert self.install_from_root is not None
        assert self.install_from_root.endswith("data\\")
        xtrapath = self.install_from_root[: -len("data\\")]
        lxtrapath = len(xtrapath)
        for fia in self.archive.files:
            if fia.intra_path.startswith(xtrapath) and not fia.intra_path.startswith(
                self.install_from_root
            ):
                out.append((fia.intra_path[lxtrapath:], fia))
        return out

    def install_params(self) -> Any:
        return super().install_params()

    @classmethod
    def from_root(cls, archive: Archive, root: str) -> "Mo2DefaultArInstaller":
        out = cls(archive)
        out.install_from_root = root
        return out


class Mo2DefaultArInstallerPlugin(ArInstallerPluginBase):
    def name(self) -> str:
        return "MO2DEFAULT"

    def guess_arinstaller_from_vfs(
        self,
        archive: Archive,
        modname: str,
        modfiles: dict[str, list[ArchiveFileRetriever]],
    ) -> ArInstaller | None:
        simple = SimpleUnpackArInstallerPlugin()
        simpleinst = simple.guess_arinstaller_from_vfs(archive, modname, modfiles)
        if simpleinst is None:
            return None
        assert isinstance(simpleinst, SimpleUnpackArInstaller)
        assert simpleinst.install_from_root is not None
        if not simpleinst.install_from_root.endswith("data\\"):
            return None

        candidate = Mo2DefaultArInstaller.from_root(
            archive, simpleinst.install_from_root
        )
        nsimple = sum(1 for _ in simpleinst.all_desired_files())
        ncandidate = sum(1 for _ in candidate.all_desired_files())
        return candidate if ncandidate > nsimple else None

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
