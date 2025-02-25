# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
Loader for archive plugins
"""

from summonmm.common import *
from summonmm.plugins import load_plugins


class FileInArchive:
    file_hash: bytes
    intra_path: str
    file_size: int

    def __init__(self, file_hash: bytes, file_size: int, intra_path: str) -> None:
        self.file_hash = file_hash
        self.file_size = file_size
        self.intra_path = intra_path


class Archive:
    archive_hash: bytes
    archive_size: int
    files: list[FileInArchive]
    by: str

    def __init__(
        self,
        archive_hash: bytes,
        archive_size: int,
        by: str,
        files: list[FileInArchive] | None = None,
    ) -> None:
        self.archive_hash = archive_hash
        self.archive_size = archive_size
        self.files = files if files is not None else []
        self.by = by


class ArchivePluginBase(ABC):
    @abstractmethod
    def extensions(self) -> list[str]:
        pass

    @abstractmethod
    def extract(
        self, archive: str, listoffiles: list[str], targetpath: str
    ) -> list[str | None]:
        pass

    @abstractmethod
    def extract_all(self, archive: str, targetpath: str) -> None:
        pass

    @staticmethod
    def unarchived_list_helper(
        archive: str, listoffiles: list[str], targetpath: str
    ) -> list[str | None]:
        out: list[str | None] = []
        for f in listoffiles:
            if os.path.isfile(targetpath + f):
                out.append(targetpath + f)
            else:
                warn("{} NOT EXTRACTED from {}".format(f, archive))
                out.append(None)
        return out

    @staticmethod
    def prepare_file_spec(listoffiles: list[str], targetpath: str) -> str:
        if len(listoffiles) == 1:
            return listoffiles[0]
        else:
            listfilename = targetpath + "__@#$summonmm$#@__.lst"
            with open(listfilename, "wt") as listfile:
                for f in listoffiles:
                    listfile.write(f + "\n")
            return "@" + listfilename


_archive_plugins: dict[str, ArchivePluginBase] = (
    {}
)  # file_extension -> ArchivePluginBase
_archive_exts: list[str] = []


def _found_archive_plugin(plugin: ArchivePluginBase) -> None:
    global _archive_plugins
    global _archive_exts
    for ext in plugin.extensions():
        _archive_plugins[ext] = plugin
        assert ext not in _archive_exts
        _archive_exts.append(ext)


load_plugins(
    "plugins/archive/", ArchivePluginBase, lambda plugin: _found_archive_plugin(plugin)
)


def archive_plugin_for(path: str) -> ArchivePluginBase | None:
    global _archive_plugins
    ext = os.path.splitext(path)[1].lower()
    return _archive_plugins.get(ext)


def all_archive_plugins_extensions() -> list[str]:
    global _archive_exts
    return _archive_exts


def normalize_archive_intra_path(fpath: str):
    assert is_short_file_path(fpath.lower())
    return fpath.lower()


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
