# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


from summonmm.common import *
from summonmm.helpers.modlist import ModList
from summonmm.plugins.modmanagers import (
    ModManagerConfig,
    ModManagerPluginBase,
    config_dir_path,
    normalize_source_vfs_dir_path,
)


class Mo2Plugin(ModManagerPluginBase):
    def mod_manager_name(self) -> str:
        return "mo2"

    def config_factory(self) -> ModManagerConfig:
        return Mo2ProjectConfig(self.mod_manager_name())


class Mo2ProjectConfig(ModManagerConfig):
    mo2dir: str | None
    ignore_dirs: list[str]
    master_profile: str | None
    generated_profiles: dict[str, str] | None
    master_modlist: ModList | None
    _vfs_files: dict[str, list[str]] | None

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.mo2dir = None
        self.master_profile = None
        self.generated_profiles = None
        self.master_modlist = None
        self._vfs_files = None

    def parse_config_section(
        self,
        section: ConfigData,
        configdir: str,
        fullconfig: ConfigData,
        download_dirs: list[str],
    ) -> None:
        unused_config_warning(
            "mo2", section, ["mo2dir", "ignores", "masterprofile", "generatedprofiles"]
        )

        raise_if_not(
            "mo2dir" in section,
            "'mo2dir' must be present in config.mo2 for modmanager=mo2",
        )
        mo2dir = config_dir_path(section["mo2dir"], configdir, fullconfig)

        ignores = section.get("ignores", ["{DEFAULT-MO2-IGNORES}"])
        raise_if_not(
            isinstance(ignores, list),
            lambda: "config.mo2.ignores must be a list, got " + repr(ignores),
        )
        self.ignore_dirs = []
        for ignore in ignores:
            if ignore == "{DEFAULT-MO2-IGNORES}":
                self.ignore_dirs += [
                    normalize_dir_path(mo2dir + defignore)
                    for defignore in [
                        "overwrite\\Root\\Logs",
                        "overwrite\\Root\\Backup",
                        "overwrite\\ShaderCache",
                    ]
                ]
            else:
                self.ignore_dirs.append(normalize_source_vfs_dir_path(ignore, mo2dir))

        assert self.mo2dir is None
        self.mo2dir = mo2dir

        assert self.master_profile is None
        assert self.generated_profiles is None
        self.master_profile = section.get("masterprofile")
        raise_if_not(
            self.master_profile is not None,
            lambda: "'masterprofile' in config must be a string, got "
            + repr(self.master_profile),
        )
        assert self.master_profile is not None
        raise_if_not(os.path.isdir(self.mo2dir + "profiles\\" + self.master_profile))

        self.generated_profiles = section.get("generatedprofiles", {})
        raise_if_not(
            isinstance(self.generated_profiles, dict),
            lambda: "'generatedprofiles' in config must be a dict, got "
            + repr(self.generated_profiles),
        )
        assert self.generated_profiles is not None
        for gp in self.generated_profiles.keys():
            raise_if_not(os.path.isdir(self.mo2dir + "profiles\\" + gp))

        assert self.master_modlist is None
        self.master_modlist = ModList(
            normalize_dir_path(self.mo2dir + "profiles\\" + self.master_profile + "\\")
        )

    def is_path_ignored(self, path: str) -> bool:
        for ig in self.ignore_dirs:
            if path.startswith(ig):
                return True
        return False

    def active_source_vfs_folders(self) -> FolderListToCache:
        assert self.mo2dir is not None
        assert self.master_modlist is not None
        overwritef = self.mo2dir + "overwrite\\"
        if FolderToCache.ok_to_construct(overwritef, self.ignore_dirs):
            overwrite = [FolderToCache(overwritef, self.ignore_dirs)]
        else:
            overwrite = []
        out: FolderListToCache = FolderListToCache(overwrite)
        exdirs = self.ignore_dirs

        for mod in self.master_modlist.all_enabled():
            folder = normalize_dir_path(self.mo2dir + "mods\\" + mod + "\\")
            if FolderToCache.ok_to_construct(
                folder, exdirs
            ) and not self.is_path_ignored(folder):
                out.append(FolderToCache(folder, exdirs))
        return out

    def default_download_dirs(self) -> list[str]:
        return ["{mo2.mo2dir}downloads\\"]

    def modfile_to_target_vfs(
        self, mf: ModFile
    ) -> str:  # returns path relative to target vfs root
        if mf.mod is None:
            return mf.intramod

        # MO2 RootBuilder plugin
        if mf.intramod.startswith("root\\"):
            return mf.intramod[len("root\\") :]

        return "data\\" + mf.intramod

    def modfile_to_source_vfs(self, mf: ModFile) -> str:
        assert self.mo2dir is not None
        if mf.mod is None:
            return self.mo2dir + "overwrite\\" + mf.intramod

        return self.mo2dir + "mods\\" + mf.mod + "\\" + mf.intramod

    def resolve_vfs(self, sourcevfs: Iterable[FileOnDisk]) -> ResolvedVFS:
        assert self.mo2dir is not None
        assert self.master_modlist is not None
        info("MO2: Starting resolving VFS...")

        allenabled = list(self.master_modlist.all_enabled())
        modsrch = FastSearchOverPartialStrings(
            [(self.mo2dir + "overwrite\\", -1)]
            + [
                (self.mo2dir + "mods\\" + allenabled[i].lower() + "\\", i)
                for i in range(len(allenabled))
            ]
        )

        source_to_target: dict[str, str] = {}
        target_files0: dict[str, list[tuple[int, FileOnDisk]]] = {}
        nsourcevfs = 0
        for f in sourcevfs:
            mf = self.parse_source_vfs(f.file_path)
            relpath = self.modfile_to_target_vfs(mf)
            assert relpath is not None
            nsourcevfs += 1

            res = modsrch.find_val_for_str(f.file_path)
            assert res is not None
            _, modidx = res
            assert isinstance(modidx, int)
            if __debug__:
                if modidx < 0:
                    assert modidx == -1
                    assert f.file_path.startswith(self.mo2dir + "overwrite\\")
                else:
                    assert f.file_path.startswith(
                        self.mo2dir + "mods\\" + allenabled[modidx].lower() + "\\"
                    )

            if relpath not in target_files0:
                target_files0[relpath] = []
            target_files0[relpath].append((modidx, f))

            assert f.file_path not in source_to_target
            source_to_target[f.file_path] = relpath

        assert nsourcevfs == len(source_to_target)

        target_files: dict[str, list[FileOnDisk]] = {}
        for key, val in target_files0.items():
            val = sorted(val, key=lambda x: x[0])
            assert key not in target_files
            target_files[key] = [f[1] for f in val]
            assert len(target_files[key]) == len(set(target_files[key]))

        info(
            "MO2: ResolvedVFS: {} files resolved, with {} overwrites".format(
                nsourcevfs, nsourcevfs - len(target_files)
            )
        )
        return ResolvedVFS(source_to_target, target_files)

    def parse_source_vfs(self, path: str) -> ModFile:
        assert self.mo2dir is not None
        assert is_normalized_file_path(path)
        overwrite = self.mo2dir + "overwrite\\"
        if path.startswith(overwrite):
            return ModFile(None, path[len(overwrite) :])
        modsdir = self.mo2dir + "mods\\"
        assert path.startswith(modsdir)
        lmodsdir = len(modsdir)
        slash = path.find("\\", lmodsdir)
        assert slash >= 0
        return ModFile(path[lmodsdir:slash], path[slash + 1 :])


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
