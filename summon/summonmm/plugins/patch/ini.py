# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import configparser

from summonmm.common import *
from summonmm.plugins.patches import PatchPluginBase
from summonmm.gitdata.stable_json import StableJsonTypeDescriptor


class _IniPatchPluginOverwrite:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("section", "sect"),
        ("name", "name"),
        ("value", "value"),
    ]
    section: str
    name: str
    value: str

    def __init__(self, section: str, name: str, val: str):
        self.section = section
        self.name = name
        self.value = val

    @classmethod
    def for_summon_stable_json_load(cls) -> "_IniPatchPluginOverwrite":
        return cls("", "", "")


class _IniPatchPluginDel:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("section", "sect"),
        ("name", "name"),
    ]
    section: str
    name: str

    def __init__(self, section: str, name: str):
        self.section = section
        self.name = name

    @classmethod
    def for_summon_stable_json_load(cls) -> "_IniPatchPluginDel":
        return cls("", "")


class _IniPluginPatch:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("overwrites", "over", _IniPatchPluginOverwrite),
        ("deletes", "del", _IniPatchPluginDel),
    ]
    overwrites: list[_IniPatchPluginOverwrite]
    deletes: list[_IniPatchPluginDel]

    def __init__(self):
        self.overwrites = []
        self.deletes = []

    def add_overwrite(self, section: str, name: str, value: str) -> None:
        self.overwrites.append(_IniPatchPluginOverwrite(section, name, value))

    def add_delete(self, section: str, name: str) -> None:
        self.deletes.append(_IniPatchPluginDel(section, name))


class IniPatchPlugin(PatchPluginBase):
    def name(self) -> str:
        return "INI"

    def extensions(self) -> list[str]:
        return [".ini"]

    def patch(self, srcfile: str, dstfile: str) -> Any:
        srcini = configparser.ConfigParser(allow_unnamed_section=True)
        srcini.optionxform = str  # type: ignore ; making key names case-sensitive
        with open_3rdparty_txt_file_autodetect(srcfile) as fp:
            srcini.read_file(fp)
        dstini = configparser.ConfigParser(allow_unnamed_section=True)
        dstini.optionxform = str  # type: ignore ; making key names case-sensitive
        with open_3rdparty_txt_file_autodetect(dstfile) as fp:
            dstini.read_file(fp)

        nmatch = 0
        out = _IniPluginPatch()
        for section in dstini.sections():
            for name, value in dstini[section].items():
                assert isinstance(name, str)
                assert isinstance(value, str)
                override = True
                if section in srcini.sections():
                    if name in srcini[section]:
                        if srcini[section][name] == value:
                            override = False
                            nmatch += 1
                if override:
                    sec = (
                        "__@#$SUMMON_UNNAMED_SECTION$#@__"
                        if section == configparser.UNNAMED_SECTION
                        else section
                    )
                    out.add_overwrite(sec, name, value)

        for section in srcini.sections():
            for name, value in srcini[section].items():
                assert isinstance(name, str)
                assert isinstance(value, str)
                if section not in dstini.sections() or name not in dstini[section]:
                    out.add_delete(section, name)

        if nmatch == 0:
            return None
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
