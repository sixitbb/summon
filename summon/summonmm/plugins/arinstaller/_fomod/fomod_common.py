# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
Common FOMOD data structures (ModuleConfig.xml will be parsed to them using fomod_parser)
"""

from bisect import bisect_left

from summonmm.common import *
from summonmm.gitdata.stable_json import StableJsonFlags, StableJsonTypeDescriptor
from summonmm.plugins.archives import Archive, FileInArchive
from summonmm.plugins.arinstallers import ArInstaller


class FomodInstallerSelection:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("step_name", "step"),
        ("group_name", "grp"),
        ("plugin_name", "plugin"),
    ]
    step_name: str
    group_name: str
    plugin_name: str

    def __init__(self, step: str, group: str, plugin: str) -> None:
        self.step_name = step
        self.group_name = group
        self.plugin_name = plugin

    def __hash__(self) -> int:
        return hash((self.step_name, self.group_name, self.plugin_name))

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, FomodInstallerSelection)
        return (self.step_name, self.group_name, self.plugin_name) == (
            other.step_name,
            other.group_name,
            other.plugin_name,
        )

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodInstallerSelection":
        return cls("", "", "")


### FomodModuleConfig and its dependencies


class FomodSrcDstFlags(IntFlag):
    NoFlags = 0
    AlwaysInstall = 0x1
    InstallIfUsable = 0x2


class FomodSrcDst:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("src", "src", ""),
        ("dst", "dst", ""),
        ("priority", "pri", 0),
        ("flags", "flags", FomodSrcDstFlags.NoFlags),
    ]
    src: str | None
    dst: str | None
    priority: int
    flags: FomodSrcDstFlags

    def __init__(self) -> None:
        self.src = None
        self.dst = None
        self.priority = -1
        self.flags = FomodSrcDstFlags.NoFlags

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodSrcDst":
        out = cls()
        out.src = ""
        out.dst = ""
        return out


class ArchiveForFomodFilesAndFolders:
    arfiles: dict[str, FileInArchive] = {}
    arfiles4folders: list[tuple[str, FileInArchive]] = []

    def __init__(self, archive: Archive) -> None:
        self.arfiles = {}
        self.arfiles4folders = []
        for f in archive.files:
            self.arfiles[f.intra_path] = f
            self.arfiles4folders.append((f.intra_path, f))
        self.arfiles4folders.sort(key=lambda x: x[0])

    def for_all_starting_with(
        self, src: str, f: Callable[[str, FileInArchive], None]
    ) -> None:
        found = bisect_left(self.arfiles4folders, src, key=lambda x: x[0])
        if found == len(self.arfiles4folders):
            return
        assert 0 <= found < len(self.arfiles4folders)
        assert src < self.arfiles4folders[found][0]
        assert (
            found == len(self.arfiles4folders) - 1
            or self.arfiles4folders[found + 1][0] > src
        )
        idx = found
        while True:
            if idx == len(self.arfiles4folders):
                break
            fsrc = self.arfiles4folders[idx][0]
            if not fsrc.startswith(src):
                break

            af = self.arfiles4folders[idx][1]
            assert af.intra_path == fsrc

            remainder = af.intra_path[len(src) :]
            f(remainder, af)

            idx += 1


class FomodFilesAndFolders:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("files", "files", FomodSrcDst, StableJsonFlags.Unsorted),
        ("folders", "folders", FomodSrcDst, StableJsonFlags.Unsorted),
    ]
    files: list[FomodSrcDst]
    folders: list[FomodSrcDst]

    def __init__(self) -> None:
        self.files = []
        self.folders = []

    def merge(self, b: "FomodFilesAndFolders") -> None:
        self.files += b.files
        self.folders += b.folders

    def copy(self) -> "FomodFilesAndFolders":
        out = FomodFilesAndFolders()
        out.files = self.files.copy()
        out.folders = self.folders.copy()
        return out

    def all_files(
        self, fomodroot: str, ar4: ArchiveForFomodFilesAndFolders
    ) -> Iterable[tuple[str, int, FileInArchive]]:
        assert not fomodroot.endswith("\\")
        fomodroot1 = "" if fomodroot == "" else fomodroot + "\\"

        out: dict[str, tuple[int, FileInArchive]] = {}

        for f in self.files:
            assert f.src is not None
            assert f.dst is not None
            src = FomodFilesAndFolders.normalize_file_path(fomodroot1 + f.src)
            assert src in ar4.arfiles
            dst = FomodFilesAndFolders.normalize_file_path(f.dst)
            FomodFilesAndFolders._add_to_out(out, dst, f.priority, ar4.arfiles[src])

        for f in self.folders:
            assert f.src is not None
            assert f.dst is not None
            src = FomodFilesAndFolders.normalize_folder_path(fomodroot1 + f.src)
            dst = FomodFilesAndFolders.normalize_folder_path(f.dst)

            ar4.for_all_starting_with(
                src,
                lambda remainder, af: FomodFilesAndFolders._add_to_out(
                    out, dst + remainder, f.priority, af
                ),
            )
        return [(dst, pfia[0], pfia[1]) for dst, pfia in out.items()]

    @staticmethod
    def normalize_file_path(src: str) -> str:
        src = src.lower().replace("/", "\\")
        if src.startswith(".\\"):
            src = src[len(".\\") :]
        assert not src.endswith("\\")
        return src

    @staticmethod
    def normalize_folder_path(src: str) -> str:
        src = src.lower().replace("/", "\\")
        if src.startswith(".\\"):
            src = src[len(".\\") :]
        return src if src.endswith("\\") or len(src) == 0 else src + "\\"

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodFilesAndFolders":
        return cls()

    def is_for_load(self) -> bool:
        return self.files == [] and self.folders == []

    @staticmethod
    def _add_to_out(
        out: dict[str, tuple[int, FileInArchive]],
        dst: str,
        priority: int,
        af: FileInArchive,
    ) -> None:
        # if dst.startswith('.'):
        #    pass
        if dst in out:
            oldpri, oldaf = out[dst]
            if priority > oldpri:
                out[dst] = priority, af
            elif priority == oldpri:
                if af.file_hash != oldaf.file_hash:
                    # warn('Ambiguous overwriting of a file {} in FomodArInstaller'.format(dst))
                    out[dst] = (
                        priority,
                        af,
                    )  # it looks that with equal priorities, newer one should win
                    # (which is also consistent with usual "later overrides earlier" general modder philosophy
        else:
            out[dst] = priority, af


class FomodDependencyEngineRuntimeData:
    flags: dict[str, str]

    def __init__(self, flags: dict[str, str]) -> None:
        self.flags = flags


class FomodFlagDependency:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("name", "name"), ("value", "value")]
    name: str | None
    value: str | None

    def __init__(self) -> None:
        self.name = None
        self.value = None

    def is_satisfied(self, runtimedata: FomodDependencyEngineRuntimeData) -> bool:
        return (
            self.name in runtimedata.flags
            and runtimedata.flags[self.name] == self.value
        )

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodFlagDependency":
        out = cls()
        out.name = ""
        out.value = ""
        return out

    def is_for_load(self) -> bool:
        return self.name == "" and self.value == ""


class FomodFileDependencyState(IntEnum):
    NotInitialized = 0
    Active = 1
    Inactive = 2
    Missing = 3


class FomodFileDependency:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("file", "file"),
        ("state", "state", FomodFileDependencyState.NotInitialized),
    ]
    file: str | None
    state: FomodFileDependencyState

    def __init__(self) -> None:
        self.file = None
        self.state = FomodFileDependencyState.NotInitialized

    def is_satisfied(self, runtimedata: FomodDependencyEngineRuntimeData) -> bool:
        return True  # TODO!

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodFileDependency":
        out = cls()
        out.file = ""
        return out

    def is_for_load(self) -> bool:
        return self.file == "" and self.state == FomodFileDependencyState.NotInitialized


class FomodGameDependency:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("version", "version")]
    version: str | None

    def __init__(self) -> None:
        self.version = None

    def is_satisfied(self, runtimedata: FomodDependencyEngineRuntimeData) -> bool:
        return True  # TODO!

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodGameDependency":
        out = cls()
        out.version = ""
        return out

    def is_for_load(self) -> bool:
        return self.version == ""


class FomodSomeDependency:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("file_dependency", "filedep"),
        ("flag_dependency", "flagdep"),
        ("game_dependency", "gamedep"),
        ("dependencies", "deps"),
    ]
    file_dependency: FomodFileDependency | None
    flag_dependency: FomodFlagDependency | None
    game_dependency: FomodGameDependency | None
    dependencies: "FomodDependencies | None"

    def __init__(
        self,
        dep: "FomodFlagDependency|FomodFileDependency|FomodGameDependency|FomodDependencies",
    ) -> None:
        self.flag_dependency = None
        self.file_dependency = None
        self.game_dependency = None
        self.dependencies = None
        if isinstance(dep, FomodFlagDependency):
            self.flag_dependency = dep
        elif isinstance(dep, FomodFileDependency):
            self.file_dependency = dep
        elif isinstance(dep, FomodGameDependency):
            self.game_dependency = dep
        else:
            assert isinstance(dep, FomodDependencies)
            self.dependencies = dep

    def is_satisfied(self, runtimedata: FomodDependencyEngineRuntimeData) -> bool:
        if self.flag_dependency is not None:
            assert self.game_dependency is None
            assert self.file_dependency is None
            assert self.dependencies is None
            return self.flag_dependency.is_satisfied(runtimedata)
        elif self.game_dependency is not None:
            assert self.flag_dependency is None
            assert self.file_dependency is None
            assert self.dependencies is None
            return self.game_dependency.is_satisfied(runtimedata)
        elif self.file_dependency is not None:
            assert self.flag_dependency is None
            assert self.game_dependency is None
            assert self.dependencies is None
            return self.file_dependency.is_satisfied(runtimedata)
        elif self.dependencies is not None:
            assert self.flag_dependency is None
            assert self.file_dependency is None
            assert self.game_dependency is None
            return self.dependencies.is_satisfied(runtimedata)
        else:
            assert False

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodSomeDependency":
        out = cls(FomodFileDependency.for_summon_stable_json_load())
        out.flag_dependency = FomodFlagDependency.for_summon_stable_json_load()
        out.game_dependency = FomodGameDependency.for_summon_stable_json_load()
        out.dependencies = FomodDependencies.for_summon_stable_json_load()
        return out

    def summon_stable_json_make_canonical(self) -> None:
        if self.flag_dependency is not None and self.flag_dependency.is_for_load():
            self.flag_dependency = None
        if self.file_dependency is not None and self.file_dependency.is_for_load():
            self.file_dependency = None
        if self.game_dependency is not None and self.game_dependency.is_for_load():
            self.game_dependency = None
        if self.dependencies is not None and self.dependencies.is_for_load():
            self.dependencies = None


class FomodDependencies:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("oroperator", "or", False),
        ("dependencies", "deps", FomodSomeDependency, StableJsonFlags.Unsorted),
    ]
    oroperator: bool
    dependencies: list[FomodSomeDependency]

    def __init__(self) -> None:
        self.oroperator = False
        self.dependencies = []

    def is_satisfied(self, runtimedata: FomodDependencyEngineRuntimeData) -> bool:
        if len(self.dependencies) == 0:
            return True
        if self.oroperator:
            for dep in self.dependencies:
                if dep.is_satisfied(runtimedata):
                    return True
            return False
        else:
            for dep in self.dependencies:
                if not dep.is_satisfied(runtimedata):
                    return False
            return True

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodDependencies":
        return cls()

    def is_for_load(self) -> bool:
        return self.dependencies == [] and self.oroperator is False


class FomodType(IntEnum):
    NotInitialized = 0
    NotUsable = 1
    CouldBeUsable = 2
    Optional = 3
    Recommended = 4
    Required = 5


class FomodPattern:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("dependencies", "deps"),
        ("type", "type", FomodType.NotInitialized),
        ("files", "files"),
    ]
    dependencies: FomodDependencies | None
    type: FomodType
    files: FomodFilesAndFolders | None

    def __init__(self) -> None:
        self.dependencies = None
        self.type = FomodType.NotInitialized
        self.files = None

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodPattern":
        out = cls()
        out.dependencies = FomodDependencies()
        out.files = FomodFilesAndFolders()
        return out

    def summon_stable_json_make_canonical(self) -> None:
        if self.files is not None and self.files.is_for_load():
            self.files = None


class FomodTypeDescriptor:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("type", "type"),
        ("patterns", "patterns", FomodPattern, StableJsonFlags.Unsorted),
    ]
    type: FomodType
    patterns: list[FomodPattern]

    def __init__(self) -> None:
        self.type = FomodType.NotInitialized
        self.patterns = []

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodTypeDescriptor":
        return cls()


class FomodPlugin:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("name", "name"),
        ("description", "descr"),
        ("image", "img"),
        ("files", "files"),
        ("type_descriptor", "tdescr"),
        ("condition_flags", "conditionflags", FomodFlagDependency),
    ]
    name: str | None
    description: str | None
    image: str | None
    files: FomodFilesAndFolders | None
    type_descriptor: FomodTypeDescriptor | None
    condition_flags: list[FomodFlagDependency]

    def __init__(self) -> None:
        self.name = None
        self.description = None
        self.image = None
        self.files = None
        self.type_descriptor = None
        self.condition_flags = []

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodPlugin":
        out = cls()
        out.name = ""
        out.description = ""
        out.image = ""
        out.files = FomodFilesAndFolders.for_summon_stable_json_load()
        out.type_descriptor = FomodTypeDescriptor()
        return out

    def summon_stable_json_make_canonical(self) -> None:
        if self.files is not None and self.files.is_for_load():
            self.files = None


class FomodGroupSelect(IntEnum):
    NotInitialized = 0
    SelectAny = 1
    SelectAll = 2
    SelectExactlyOne = 3
    SelectAtMostOne = 4
    SelectAtLeastOne = 5


class FomodOrder(IntEnum):
    Ascending = 0
    Explicit = 1
    Descending = 2


class FomodGroup:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("name", "name"),
        ("select", "sel", FomodGroupSelect.SelectAny),
        ("order", "ord", FomodOrder.Ascending),
        ("plugins", "plugins", FomodPlugin, StableJsonFlags.Unsorted),
    ]
    name: str | None
    select: FomodGroupSelect
    plugins: list[FomodPlugin]

    def __init__(self) -> None:
        self.name = None
        self.select = FomodGroupSelect.NotInitialized
        self.order = FomodOrder.Ascending
        self.plugins = []

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodGroup":
        out = cls()
        out.name = ""
        return out


class FomodInstallStep:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("name", "name"),
        ("order", "ord", FomodOrder.Explicit),
        ("groups", "groups", FomodGroup, StableJsonFlags.Unsorted),
        ("visible", "visible"),
    ]
    name: str | None
    order: FomodOrder
    groups: list[FomodGroup]
    visible: FomodDependencies

    def __init__(self) -> None:
        self.name = None
        self.order = FomodOrder.Ascending
        self.groups = []
        self.visible = FomodDependencies()

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodInstallStep":
        out = cls()
        out.name = ""
        return out


class FomodModuleConfig:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("module_name", "modulename"),
        ("eye_candy_attr", "eyecandy", (str, str)),
        ("module_dependencies", "deps", FomodFileDependency, StableJsonFlags.Unsorted),
        ("required", "required"),
        ("install_steps_order", "order", FomodOrder.Ascending),
        ("install_steps", "isteps", FomodInstallStep, StableJsonFlags.Unsorted),
        (
            "conditional_file_installs",
            "conditional",
            FomodPattern,
            StableJsonFlags.Unsorted,
        ),
    ]
    module_name: str | None
    eye_candy_attr: dict[str, str]
    module_dependencies: list[FomodFileDependency]
    required: FomodFilesAndFolders
    install_steps_order: FomodOrder
    install_steps: list[FomodInstallStep]
    conditional_file_installs: list[FomodPattern]

    def __init__(self) -> None:
        self.module_name = None
        self.eye_candy_attr = {}
        self.module_dependencies = []
        self.required = FomodFilesAndFolders()
        self.install_steps_order = FomodOrder.Ascending
        self.install_steps = []
        self.conditional_file_installs = []

    @classmethod
    def for_summon_stable_json_load(cls) -> "FomodModuleConfig":
        out = cls()
        out.module_name = ""
        return out


### done with FomodModuleConfig


class FomodArInstallerData:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("fomod_root", "root", ""),
        ("selections", "sel", FomodInstallerSelection, StableJsonFlags.Unsorted),
    ]
    fomod_root: str
    selections: list[FomodInstallerSelection]

    def __init__(
        self, fomodroot: str, selections: list[FomodInstallerSelection]
    ) -> None:
        self.fomod_root = fomodroot
        self.selections = selections


class FomodArInstaller(ArInstaller):
    fomod_root: str
    files: FomodFilesAndFolders
    # selections: list[tuple[FomodInstallerSelection, FomodFilesAndFolders]]
    selections: list[FomodInstallerSelection]

    def __init__(
        self,
        archive: Archive,
        fomodroot: str,
        files: FomodFilesAndFolders,
        selections: list[FomodInstallerSelection],
    ) -> None:
        super().__init__(archive)
        self.fomod_root = fomodroot
        # self.required = required
        self.selections = selections
        self.files = files

    def name(self) -> str:
        return "FOMOD"

    def all_desired_files(self) -> Iterable[tuple[str, FileInArchive]]:
        ar4 = ArchiveForFomodFilesAndFolders(self.archive)
        out: dict[str, tuple[int, FileInArchive]] = {}
        self._to_out(out, ar4, self.files)
        # for _, ff in self.selections:
        #    self._to_out(out, ff)
        return [(k, v[1]) for k, v in out.items()]

    def install_params(self) -> Any:
        return FomodArInstallerData(self.fomod_root, self.selections)

    def _to_out(
        self,
        out: dict[str, tuple[int, FileInArchive]],
        ar4: ArchiveForFomodFilesAndFolders,
        ff: FomodFilesAndFolders,
    ) -> None:
        for f, p, fia in ff.all_files(self.fomod_root, ar4):
            assert not f in out
            """
            if f in out:
                pold, fiaold = out[f]
                if p > pold:
                    out[f] = p, fia
                elif p == pold:
                    if fiaold.file_hash != fia.file_hash:
                        warn('Ambiguous overwriting of a file {} in FomodArInstaller'.format(f))
            else:
            """
            out[f] = p, fia


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
