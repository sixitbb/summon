# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

from summonmm.common import *
from summonmm.gitdata.stable_json import StableJsonFlags
from summonmm.plugins.patches import PatchPluginBase
from summonmm.gitdata.stable_json import StableJsonTypeDescriptor


class _JsonPluginPatchPath:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("path", None, str, StableJsonFlags.Unsorted)
    ]
    path: list[str]

    def __init__(self, path: list[str]):
        self.path = path

    @classmethod
    def for_summon_stable_json_load(cls) -> "_JsonPluginPatchPath":
        return cls([])


class _JsonPluginStringOverwrite:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("path", "path"), ("value", "s")]
    path: _JsonPluginPatchPath
    value: str

    def __init__(self, path: list[str], val: str):
        self.path = _JsonPluginPatchPath(path)
        self.value = val

    @classmethod
    def for_summon_stable_json_load(cls) -> "_JsonPluginStringOverwrite":
        return cls([], "")


class _JsonPluginNumberOverwrite:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("path", "path"), ("value", "n")]
    path: _JsonPluginPatchPath
    value: float

    def __init__(self, path: list[str], val: float):
        self.path = _JsonPluginPatchPath(path)
        self.value = val

    @classmethod
    def for_summon_stable_json_load(cls) -> "_JsonPluginNumberOverwrite":
        return cls([], 0.0)


class _JsonPluginPatch:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("string_overwrites", "str", _JsonPluginStringOverwrite),
        ("number_overwrites", "float", _JsonPluginNumberOverwrite),
        ("deletes", "del", _JsonPluginPatchPath),
    ]
    string_overwrites: list[_JsonPluginStringOverwrite]
    number_overwrites: list[_JsonPluginNumberOverwrite]
    deletes: list[_JsonPluginPatchPath]

    def __init__(self):
        self.string_overwrites = []
        self.number_overwrites = []
        self.deletes = []

    def add_string_overwrite(self, path: list[str], value: str) -> None:
        self.string_overwrites.append(_JsonPluginStringOverwrite(path, value))

    def add_number_overwrite(self, path: list[str], value: float) -> None:
        self.number_overwrites.append(_JsonPluginNumberOverwrite(path, value))

    def add_delete(self, path: list[str]) -> None:
        self.deletes.append(_JsonPluginPatchPath(path))


class JsonPatchPlugin(PatchPluginBase):
    def name(self) -> str:
        return "SORTEDJSON"

    def extensions(self) -> list[str]:
        return [".json"]

    def patch(self, srcfile: str, dstfile: str) -> Any:
        with open_3rdparty_txt_file_autodetect(srcfile) as fp:
            srcjson = json.load(fp)
        with open_3rdparty_txt_file_autodetect(dstfile) as fp:
            dstjson = json.load(fp)
        out = _JsonPluginPatch()
        nmatch = Val(0)
        JsonPatchPlugin._patch_json_object(nmatch, out, [], srcjson, dstjson)
        if nmatch.val == 0:
            return None
        return out

    @staticmethod
    def _patch_json_object(
        nmatch: Val, out: _JsonPluginPatch, path: list[str], src: Any, dst: Any
    ) -> None:
        if isinstance(src, str):
            raise_if_not(isinstance(dst, str))
            if dst == src:
                nmatch.val += 1
                pass
            out.add_string_overwrite(path, dst)
        elif isinstance(src, (int, float)):
            raise_if_not(isinstance(dst, (int, float)))
            if dst == src:
                nmatch.val += 1
                pass
            out.add_number_overwrite(path, dst)
        elif isinstance(src, dict):
            raise_if_not(isinstance(dst, dict))
            src1: dict[str, Any] = src
            JsonPatchPlugin._patch_json_dict(nmatch, out, path, src1, dst)
        else:
            raise_if_not(False)

    @staticmethod
    def _patch_json_dict(
        nmatch: Val,
        out: _JsonPluginPatch,
        path: list[str],
        src: dict[str, Any],
        dst: dict[str, Any],
    ) -> None:
        assert isinstance(src, dict)
        assert isinstance(dst, dict)
        for key in dst.keys():
            assert isinstance(key, str)
            path1 = path + [key]
            if key in src:
                JsonPatchPlugin._patch_json_object(
                    nmatch, out, path1, src[key], dst[key]
                )
            else:
                JsonPatchPlugin._add_json_object(out, path1, dst[key])

        for key in src:
            assert isinstance(key, str)
            if not key in dst:
                path1 = path + [key]
                out.add_delete(path1)

    @staticmethod
    def _add_json_object(
        out: _JsonPluginPatch, path: list[str], dst: dict[str, Any]
    ) -> None:
        if isinstance(dst, str):
            out.add_string_overwrite(path, dst)
        elif isinstance(dst, (int, float)):
            out.add_number_overwrite(path, dst)
        else:
            raise_if_not(
                isinstance(
                    dst, dict
                )  # pyright: ignore (it is actually a runtime check)
            )
            for key, value in dst.items():
                assert isinstance(key, str)
                path1 = path + [key]
                JsonPatchPlugin._add_json_object(out, path1, value)
        # else:
        #    raise_if_not(False)


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
