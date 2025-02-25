# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
Loader for fileorigin plugins
"""

from summonmm.gitdata.stable_json import (
    StableJsonJsonSomething,
    StableJsonTypeDescriptor,
)
import summonmm.tasks as tasks
from summonmm.common import *
from summonmm.plugins import load_plugins


class FileOrigin(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def eq(self, b: "FileOrigin") -> bool:
        pass


### MetaFileParser


class MetaFileParser(ABC):
    meta_file_path: str

    def __init__(self, meta_file_path: str) -> None:
        self.meta_file_path = meta_file_path

    @abstractmethod
    def take_ln(self, ln: str) -> None:
        pass

    @abstractmethod
    def make_file_origin(self) -> FileOrigin | None:
        pass


### plugins


class FileOriginPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def config(self, cfg: ConfigData) -> None:
        pass

    @abstractmethod
    def meta_file_parser(self, metafilepath: str) -> MetaFileParser:
        pass

    @abstractmethod
    def init_from_load_json_data(self, data: StableJsonJsonSomething) -> None:
        pass

    @abstractmethod
    def data_for_save_json(self) -> StableJsonJsonSomething:
        pass

    @abstractmethod
    def add_file_origin(self, h: bytes, fo: FileOrigin) -> bool:
        pass

    @abstractmethod
    def extra_hash_factory(
        self,
    ) -> ExtraHashFactory:  # returned factory function cannot be a lambda
        pass

    @abstractmethod
    def add_hash_mapping(self, h: bytes, xh: bytes) -> bool:
        pass


_file_origin_plugins: dict[str, FileOriginPluginBase] = {}


def _found_origin_plugin(plugin: FileOriginPluginBase):
    global _file_origin_plugins
    assert plugin.name() not in _file_origin_plugins
    _file_origin_plugins[plugin.name()] = plugin


load_plugins(
    "plugins/fileorigin/",
    FileOriginPluginBase,
    lambda plugin: _found_origin_plugin(plugin),
)


def file_origins_for_file(fpath: str) -> list[FileOrigin] | None:
    global _file_origin_plugins
    assert is_normalized_file_path(fpath)
    assert os.path.isfile(fpath)
    metafpath = fpath + ".meta"
    if os.path.isfile(metafpath):
        with open_3rdparty_txt_file_autodetect(metafpath) as rf:
            metafileparsers = [
                plugin.meta_file_parser(metafpath)
                for plugin in _file_origin_plugins.values()
            ]
            for ln in rf:
                for mfp in metafileparsers:
                    mfp.take_ln(ln)

            origins = [mfp.make_file_origin() for mfp in metafileparsers]
            origins = [o for o in origins if o is not None]
            return origins if len(origins) > 0 else None


def file_origin_plugins() -> Iterable[FileOriginPluginBase]:
    global _file_origin_plugins
    return _file_origin_plugins.values()


def file_origin_plugin_by_name(name: str) -> FileOriginPluginBase:
    global _file_origin_plugins
    return _file_origin_plugins[name]


def _config_file_origin_plugins(cfg: ConfigData, _: None) -> None:
    global _file_origin_plugins
    unused_config_warning(
        "file_origin_plugins", cfg, [p.name() for p in _file_origin_plugins.values()]
    )
    for p in _file_origin_plugins.values():
        if p.name() in cfg:
            p.config(cfg[p.name()])


def config_file_origin_plugins(cfg: ConfigData) -> None:
    _config_file_origin_plugins(cfg, None)
    init = tasks.LambdaReplacement(_config_file_origin_plugins, cfg)
    tasks.add_global_process_initializer(init)


### known-tentative-archive-names.json


class _TentativeNameList:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("names", None, str)]
    names: list[str]

    def __init__(self) -> None:
        self.names = []


class GitTentativeArchiveNames:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("tentative_names", "tentative_names", (bytes, _TentativeNameList)),
    ]
    tentative_names: dict[bytes, _TentativeNameList]

    def __init__(self) -> None:
        self.tentative_names = {}

    def from_plugin(
        self,
        tentative_names: dict[bytes, list[str]],
    ) -> None:
        assert len(self.tentative_names) == 0
        for h, nl in tentative_names.items():
            if h not in self.tentative_names:
                self.tentative_names[h] = _TentativeNameList()
            for n in nl:
                self.tentative_names[h].names.append(n)

    def to_plugin(
        self,
    ) -> dict[bytes, list[str]]:
        out: dict[bytes, list[str]] = {}
        for h, nl in self.tentative_names.items():
            if h not in out:
                out[h] = []
            for n in nl.names:
                out[h].append(n)
        return out


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
