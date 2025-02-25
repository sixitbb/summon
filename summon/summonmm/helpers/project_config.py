# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
class LocalProjectConfig
"""

import json5

from summonmm.common import *
from summonmm.plugins.fileorigins import config_file_origin_plugins
from summonmm.install.install_github import (
    GithubFolder,
    clone_github_project,
    github_project_exists,
)
from summonmm.plugins.modmanagers import (
    ModManagerConfig,
    all_modmanager_config_names,
    find_modmanager_config,
    config_dir_path,
)


def make_dirs_for_file(fname: str) -> None:
    os.makedirs(os.path.split(fname)[0], exist_ok=True)


def folder_size(rootpath: str):
    total = 0
    for dirpath, _, filenames in os.walk(rootpath):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            assert not os.path.islink(fp)
            total += os.path.getsize(fp)
    return total


class GithubModpack(GithubFolder):
    subfolder: str

    def __init__(self, combined2or3: str) -> None:
        spl = GithubFolder.ghsplit(combined2or3)
        assert spl is not None
        super().__init__(spl[0])
        self.subfolder = spl[1]

    @staticmethod
    def modpack_is_ok(combined2or3: str) -> bool:
        return GithubFolder.ghsplit(combined2or3) is not None

    def mpfolder(self, rootgitdir: str) -> str:
        parentdir = self.folder(rootgitdir)
        return (
            parentdir
            if self.subfolder == ""
            else parentdir + self.subfolder.lower() + "\\"
        )

    def mpto_str(self) -> str:
        parent = self.to_str()
        return parent if self.subfolder == "" else parent + "/" + self.subfolder


class GithubModpackConfig:
    is_root: bool
    # for root:
    game_universe: str | None
    origin_configs: ConfigData | None
    ignored_file_patterns: list[str]

    # for non-root:
    dependencies: list[GithubModpack]
    own_mod_names: list[str]

    def __init__(self, jsonconfigfname: str, jsonconfig: ConfigData) -> None:
        is_root = jsonconfig.get("isroot", 0)
        raise_if_not(is_root == 1 or is_root == 0)
        self.is_root = is_root != 0
        if self.is_root:
            unused_config_warning(
                jsonconfigfname,
                jsonconfig,
                ["isroot", "origins", "gameuniverse", "ignorepatterns"],
            )
            self.origin_configs = jsonconfig.get("origins", {})
            raise_if_not("gameuniverse" in jsonconfig)
            self.game_universe = jsonconfig["gameuniverse"]
            self.dependencies = []
            self.own_mod_names = []
            ignored_file_patterns: Any = jsonconfig.get("ignorepatterns", [])
            if isinstance(ignored_file_patterns, str):
                self.ignored_file_patterns = [ignored_file_patterns]
            else:
                raise_if_not(isinstance(ignored_file_patterns, list))
                self.ignored_file_patterns = coerce_list_raise_if_not(
                    ignored_file_patterns, str
                )

            assert isinstance(self.ignored_file_patterns, list)
        else:
            unused_config_warning(
                "ModpackConfig", jsonconfig, ["isroot", "dependencies", "ownmods"]
            )
            self.origin_configs = None
            self.game_universe = None
            self.dependencies = [GithubModpack(d) for d in jsonconfig["dependencies"]]
            self.own_mod_names = [
                normalize_file_name(om) for om in jsonconfig.get("ownmods", [])
            ]


def _val_to_config(data: Any) -> Any:
    if isinstance(data, (int, float, str)):
        return data
    elif isinstance(data, list):
        return [_val_to_config(it) for it in data]  # type: ignore (kinda spurious)
    else:
        raise_if_not(isinstance(data, dict))
        assert isinstance(data, dict)
        return _dict_to_config(data)


def _dict_to_config(data: Any) -> ConfigData:
    assert isinstance(data, dict)
    data1: dict[Any, Any] = data
    out: ConfigData = {}
    for k, v in data1.items():
        raise_if_not(isinstance(k, str))
        out[k] = _val_to_config(v)
    return out


def install_github_project_with_dependencies(
    ui: LinearUI, ghproject: str, githubrootdir: str, allmodpackconfigs: ConfigData
) -> str | None:
    rootmodpack: str | None = None
    if ghproject in allmodpackconfigs:
        return

    gh = GithubModpack(ghproject)
    ok = github_project_exists(githubrootdir, gh)
    match ok:
        case -1:
            critical(
                "Fatal error: folder {} exists, but does not contain {}/{}".format(
                    gh.folder(githubrootdir), gh.author, gh.project
                )
            )
            raise_if_not(False)
        case 0:
            info("Cloning GitHub project: {}".format(ghproject))
            clone_github_project(githubrootdir, gh, ui.network_error_handler(2))
            info("GitHub project {} cloned successfully".format(ghproject))
        case _:
            assert ok == 1

    jsonconfigfname = gh.mpfolder(githubrootdir) + "summon.json5"
    with open_3rdparty_txt_file_autodetect(jsonconfigfname) as rf:
        jsonconfig: Any = json5.load(rf)  # type: ignore (spurious?)
        assert isinstance(jsonconfig, dict)
        mpcfg = GithubModpackConfig(jsonconfigfname, _dict_to_config(jsonconfig))
        allmodpackconfigs[ghproject] = mpcfg

        if mpcfg.is_root:
            raise_if_not(rootmodpack is None)
            rootmodpack = ghproject

        for d in mpcfg.dependencies:
            rmp = install_github_project_with_dependencies(
                ui, d.mpto_str(), githubrootdir, allmodpackconfigs
            )
            raise_if_not(rmp is None or rootmodpack is None)
            if rmp is not None:
                rootmodpack = rmp

    return rootmodpack


class LocalProjectConfig:
    config_dir: str
    mod_manager_config: ModManagerConfig
    download_dirs: list[str]
    cache_dir: str
    tmp_dir: str
    github_root_dir: str
    all_modpack_configs: dict[str, GithubModpackConfig]
    this_modpack: str
    root_modpack: str | None
    github_username: str | None

    # TODO: check that summonmm itself, cache_dir, and tmp_dir don't overlap with any of the dirs
    def __init__(self, ui: LinearUI, jsonconfigfname: str) -> None:
        self.config_dir = normalize_dir_path(os.path.split(jsonconfigfname)[0])
        with open_3rdparty_txt_file_autodetect(jsonconfigfname) as f:
            jsonconfig: Any = json5.loads(f.read())
            unused_config_warning(
                jsonconfigfname,
                jsonconfig,
                [
                    "modmanager",
                    "downloads",
                    "cache",
                    "tmp",
                    "githubroot",
                    "modpack",
                    "githubusername",
                ]
                + all_modmanager_config_names(),
            )

            raise_if_not(
                "modmanager" in jsonconfig, "'modmanager' must be present in config"
            )
            modmanager = jsonconfig["modmanager"]
            mmcfg = find_modmanager_config(modmanager)
            raise_if_not(
                mmcfg is not None,
                lambda: "config.modmanager must be one of [{}]".format(
                    ",".join(all_modmanager_config_names())
                ),
            )
            assert mmcfg is not None
            self.mod_manager_config = mmcfg

            raise_if_not(
                self.mod_manager_config.mod_manager_name in jsonconfig,
                lambda: "'{}' must be present in config for modmanager={}".format(
                    self.mod_manager_config.mod_manager_name,
                    self.mod_manager_config.mod_manager_name,
                ),
            )
            mmc_config = jsonconfig[self.mod_manager_config.mod_manager_name]
            raise_if_not(
                isinstance(mmc_config, dict),
                lambda: "config.{} must be a dictionary, got {}".format(
                    self.mod_manager_config.mod_manager_name, repr(mmc_config)
                ),
            )

            if "downloads" not in jsonconfig:
                dls = self.mod_manager_config.default_download_dirs()
            else:
                dls = jsonconfig["downloads"]
            if isinstance(dls, str):
                dls = [dls]
            raise_if_not(
                isinstance(dls, list),
                lambda: "'downloads' in config must be a string or a list, got "
                + repr(dls),
            )
            self.download_dirs = [
                config_dir_path(dl, self.config_dir, jsonconfig) for dl in dls
            ]

            self.mod_manager_config.parse_config_section(
                mmc_config, self.config_dir, jsonconfig, self.download_dirs
            )

            self.cache_dir = config_dir_path(
                jsonconfig.get("cache", self.config_dir + ".\\summon.cache\\"),
                self.config_dir,
                jsonconfig,
            )
            self.tmp_dir = config_dir_path(
                jsonconfig.get("tmp", self.config_dir + ".\\summon.tmp\\"),
                self.config_dir,
                jsonconfig,
            )

            self.github_root_dir = config_dir_path(
                jsonconfig.get("githubroot", ".\\"), self.config_dir, jsonconfig
            )

            raise_if_not("modpack" in jsonconfig)
            ghmodpack = jsonconfig["modpack"]
            raise_if_not(
                isinstance(ghmodpack, str) and GithubModpack.modpack_is_ok(ghmodpack)
            )

            self.all_modpack_configs = {}
            self.this_modpack = ghmodpack
            self.root_modpack = install_github_project_with_dependencies(
                ui, ghmodpack, self.github_root_dir, self.all_modpack_configs
            )
            raise_if_not(self.root_modpack is not None)
            raise_if_not(self.root_modpack != self.this_modpack)
            assert self.root_modpack in self.all_modpack_configs
            cfg = self.all_modpack_configs[self.root_modpack].origin_configs
            assert cfg is not None
            config_file_origin_plugins(cfg)

            raise_if_not("githubusername" in jsonconfig)
            self.github_username = jsonconfig["githubusername"]

    def root_modpack_config(self) -> GithubModpackConfig:
        assert self.root_modpack is not None
        assert self.root_modpack in self.all_modpack_configs
        return self.all_modpack_configs[self.root_modpack]

    def active_source_vfs_folders(self) -> FolderListToCache:
        return self.mod_manager_config.active_source_vfs_folders()

    def github_folders(self) -> list[GithubFolder]:
        return [GithubModpack(mp) for mp in self.all_modpack_configs.keys()]

    def this_modpack_folder(self) -> str:
        return GithubModpack(self.this_modpack).mpfolder(self.github_root_dir)

    def modfile_to_target_vfs(
        self, mf: ModFile
    ) -> str:  # returns path relative to target vfs root
        return self.mod_manager_config.modfile_to_target_vfs(mf)

    def modfile_to_source_vfs(self, mf: ModFile) -> str:
        return self.mod_manager_config.modfile_to_source_vfs(mf)

    def resolve_vfs(self, srcfiles: Iterable[FileOnDisk]) -> ResolvedVFS:
        return self.mod_manager_config.resolve_vfs(srcfiles)

    def parse_source_vfs(self, path: str) -> ModFile:
        return self.mod_manager_config.parse_source_vfs(path)


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
