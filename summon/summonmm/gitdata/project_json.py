# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
Everything related to project's summon.json, all the way up to class ProjectJson.
"""

from summonmm.common import *
from summonmm.gitdata.stable_json import StableJsonFlags, StableJsonTypeDescriptor
from summonmm.helpers.file_retriever import GithubFileRetriever


class ProjectExtraArchiveFile:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("target_file_name", "t"),
        ("intra_path", "s", ""),
        ("intra_paths", "sl", str),
    ]
    target_file_name: str
    intra_path: str
    intra_paths: list[str]

    def __init__(self, targetfname: str, intra: list[str]) -> None:
        self.target_file_name = targetfname
        if len(intra) == 1:
            self.intra_path = intra[0]
            self.intra_paths = []
        else:
            self.intra_paths = intra
            self.intra_path = ""

    @classmethod
    def for_summon_stable_json_load(cls) -> "ProjectExtraArchiveFile":
        return cls("", [""])


class ProjectExtraArchive:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("archive_hash", "arh"),
        ("archive_idx", "ar"),
        ("extra_files", "files", ProjectExtraArchiveFile),
    ]
    archive_hash: bytes | None
    archive_idx: int | None
    extra_files: list[ProjectExtraArchiveFile]

    def __init__(self, aid: bytes | int) -> None:
        if isinstance(aid, bytes):
            self.archive_hash = aid
            self.archive_idx = None
        else:
            assert isinstance(aid, int)
            self.archive_hash = None
            self.archive_idx = aid
        self.extra_files = []

    @classmethod
    def for_summon_stable_json_load(cls) -> "ProjectExtraArchive":
        out = cls(0)
        out.archive_idx = 0
        out.archive_hash = b""
        return out


class ProjectInstaller:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("archive_hash", "h"),
        ("installer_type", "type"),
        ("installer_params", "params"),
        ("skip", "skip", str),
    ]
    archive_hash: bytes
    installer_type: str
    installer_params: Any
    skip: list[str]

    def __init__(
        self, arhash: bytes, insttype: str, instparams: Any, skip: list[str]
    ) -> None:
        self.archive_hash = arhash
        self.installer_type = insttype
        self.installer_params = instparams
        self.skip = skip

    @classmethod
    def for_summon_stable_json_load(cls) -> "ProjectInstaller":
        return cls(b"", "", {}, [])


class ProjectModTool:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("name", "name"), ("param", "param")]
    name: str
    param: Any

    def __init__(self, name: str, param: Any) -> None:
        self.name = name
        self.param = param

    @classmethod
    def for_summon_stable_json_load(cls) -> "ProjectModTool":
        return cls("", "")


class ProjectModPatch:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("file", "f"),
        ("type", "t"),
        ("param", "p"),
    ]
    file: str
    type: str
    param: Any

    def __init__(self, file: str, typ: str, param: Any) -> None:
        self.file = file
        self.type = typ
        self.param = param

    @classmethod
    def for_summon_stable_json_load(cls) -> "ProjectModPatch":
        return cls("", "", None)


class ProjectMod:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("mod_name", "name"),
        ("zero_files", "zero", str),
        ("github_files", "github", (str, GithubFileRetriever)),
        ("installers", "installers", ProjectInstaller, StableJsonFlags.Unsorted),
        ("remaining_archives", "xarchives", ProjectExtraArchive),
        ("unknown_files_by_tools", "unknownbytools", str),
        ("unknown_files", "unknown", str),
        ("mod_tools", "modtools", ProjectModTool),
        ("patches", "patches", ProjectModPatch),
    ]
    mod_name: str | None
    zero_files: list[str] | None
    github_files: dict[str, GithubFileRetriever] | None
    installers: list[ProjectInstaller] | None
    remaining_archives: list[ProjectExtraArchive] | None
    unknown_files: list[str] | None
    unknown_files_by_tools: list[str] | None
    mod_tools: list[ProjectModTool] | None
    patches: list[ProjectModPatch] | None

    def __init__(self) -> None:
        self.mod_name = None
        self.zero_files = None
        self.github_files = None
        self.installers = None
        self.remaining_archives = None
        self.unknown_files = None
        self.unknown_files_by_tools = None
        self.mod_tools = None
        self.patches = None

    @classmethod
    def for_summon_stable_json_load(cls) -> "ProjectMod":
        out = cls()
        out.mod_name = ""
        out.zero_files = []
        out.github_files = {}
        out.installers = []
        out.remaining_archives = []
        out.unknown_files = []
        out.unknown_files_by_tools = []
        out.patches = []
        return out


class ProjectJson:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("mods", "mods", ProjectMod)]
    # intermediate_archives: list[bytes] | None
    mods: list[ProjectMod] | None

    def __init__(self) -> None:
        # self.intermediate_archives = None
        self.mods = None


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
