# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
Loader for arinstaller plugins
"""

from summonmm.common import *
from summonmm.gitdata.stable_json import StableJsonJsonSomething
from summonmm.plugins.archives import Archive, FileInArchive
from summonmm.helpers.file_retriever import ArchiveFileRetriever
from summonmm.plugins import load_plugins


class ArInstaller:
    archive: Archive

    def __init__(self, archive: Archive):
        self.archive = archive

    @abstractmethod
    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def install_params(self) -> Any:  # return must be stable_json-compatible
        pass


class ArInstallerDetails:
    ignored: set[str]
    skip: set[str]
    files: dict[str, FileInArchive]
    modified_since_install: dict[str, FileInArchive]

    def __init__(self) -> None:
        self.ignored = set()
        self.skip = set()
        self.files = {}
        self.modified_since_install = {}


class ExtraArchiveDataFactory:
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def extra_data(
        self, fullarchivedir: str
    ) -> Any | None:  # returns stable_json-compatible data
        pass


class ArInstallerPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def guess_arinstaller_from_vfs(
        self,
        archive: Archive,
        modname: str,
        modfiles: dict[str, list[ArchiveFileRetriever]],
    ) -> ArInstaller | None:
        pass

    @abstractmethod
    def init_from_load_json_data(self, data: StableJsonJsonSomething) -> None:
        pass

    @abstractmethod
    def data_for_save_json(self) -> StableJsonJsonSomething:
        pass

    @abstractmethod
    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        pass

    @abstractmethod
    def add_extra_data(self, arh: bytes, data: Any | None | Exception) -> None:
        pass


_arinstaller_plugins: dict[str, ArInstallerPluginBase] = {}


def _found_arinstaller_plugin(plugin: ArInstallerPluginBase) -> None:
    global _arinstaller_plugins
    _arinstaller_plugins[plugin.name()] = (
        plugin  # order is preserved since Python 3.6 or so
    )


load_plugins(
    "plugins/arinstaller/",
    ArInstallerPluginBase,
    lambda plugin: _found_arinstaller_plugin(plugin),
)


def all_arinstaller_plugins() -> Iterable[ArInstallerPluginBase]:
    global _arinstaller_plugins
    return _arinstaller_plugins.values()


def arinstaller_plugin_by_name(name: str) -> ArInstallerPluginBase:
    global _arinstaller_plugins
    return _arinstaller_plugins[name]


def arinstaller_plugin_add_extra_data(name: str, arh: bytes, data: Any) -> None:
    global _arinstaller_plugins
    _arinstaller_plugins[name].add_extra_data(arh, data)


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
