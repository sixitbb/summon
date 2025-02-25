# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import re

from summonmm.plugins import load_plugins
from summonmm.common import *


class ModManagerConfig:
    mod_manager_name: str

    def __init__(self, modmanagername: str) -> None:
        self.mod_manager_name = modmanagername

    @abstractmethod
    def parse_config_section(
        self,
        section: ConfigData,
        configdir: str,
        fullconfig: ConfigData,
        download_dirs: list[str],
    ) -> None:
        pass

    @abstractmethod
    def default_download_dirs(self) -> list[str]:
        pass

    @abstractmethod
    def active_source_vfs_folders(self) -> FolderListToCache:
        pass

    @abstractmethod
    def modfile_to_target_vfs(
        self, mf: ModFile
    ) -> str:  # returns path relative to target vfs root
        pass

    @abstractmethod
    def resolve_vfs(self, sourcevfs: Iterable[FileOnDisk]) -> ResolvedVFS:
        pass

    @abstractmethod
    def parse_source_vfs(self, path: str) -> ModFile:
        pass

    @abstractmethod
    def modfile_to_source_vfs(self, mf: ModFile) -> str:
        pass


class ModManagerPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def mod_manager_name(self) -> str:
        pass

    @abstractmethod
    def config_factory(self) -> ModManagerConfig:
        pass


def _normalize_config_dir_path(
    path: str, configdir: str
) -> str:  # relative to config dir
    if os.path.isabs(path):
        return normalize_dir_path(path)
    else:
        return normalize_dir_path(configdir + path)


def config_dir_path(path: str, configdir: str, config: ConfigData) -> str:
    path = _normalize_config_dir_path(path, configdir)
    path = path.replace("{CONFIG-DIR}", configdir)
    replaced = False
    pattern = re.compile(r"\{(.*)}")
    m = pattern.search(path)
    if m:
        found = m.group(1)
        spl = found.split(".")
        cur = config
        for name in spl:
            raise_if_not(
                name in cur,
                lambda: "unable to resolve {} in {}".format(found, configdir),
            )
            cur = cur[name]
        raise_if_not(
            isinstance(cur, str),
            lambda: "{} in {} must be a string".format(found, configdir),
        )
        assert isinstance(cur, str)
        path = pattern.sub(cur, path)
        replaced = True

    if replaced:
        return config_dir_path(path, configdir, config)
    else:
        return path


def normalize_source_vfs_dir_path(
    path: str, rootvfsdir: str
) -> str:  # relative to vfs dir
    if os.path.isabs(path):
        out = normalize_dir_path(path)
    else:
        out = normalize_dir_path(rootvfsdir + path)
    raise_if_not(
        out.startswith(rootvfsdir),
        lambda: "expected path within vfs, got " + repr(path),
    )
    return out


_modmanager_plugins: list[ModManagerPluginBase] = []


def _found_plugin(plugin: ModManagerPluginBase):
    global _modmanager_plugins
    _modmanager_plugins.append(plugin)


load_plugins(
    "plugins/modmanager/", ModManagerPluginBase, lambda plugin: _found_plugin(plugin)
)


def find_modmanager_config(name: str) -> ModManagerConfig | None:
    global _modmanager_plugins
    for mm in _modmanager_plugins:
        if mm.mod_manager_name() == name:
            mmc = mm.config_factory()
            assert mmc.mod_manager_name == name
            return mmc
    return None


def all_modmanager_config_names() -> list[str]:
    global _modmanager_plugins
    return [mm.mod_manager_name() for mm in _modmanager_plugins]


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
