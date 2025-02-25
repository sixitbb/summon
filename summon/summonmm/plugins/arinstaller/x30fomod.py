# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
FOMOD installer. Bread and butter of modern modding.

Guessing is really complicated, trying to replay all possible install scenarios a.k.a. forks
  (though separating independent selections from forking to keep replaying times within reason)
"""

# noinspection PyUnresolvedReferences
import xml.etree.ElementTree as ElementTree

from summonmm.common import *
from summonmm.gitdata.stable_json import (
    StableJsonJsonSomething,
    from_stable_json,
    to_stable_json,
    StableJsonTypeDescriptor,
    write_stable_json_opened,
)
from summonmm.plugins.archives import Archive
from summonmm.plugins.arinstallers import (
    ArInstallerPluginBase,
    ArInstaller,
    ExtraArchiveDataFactory,
)
from summonmm.helpers.file_retriever import ArchiveFileRetriever

# noinspection PyProtectedMember
from summonmm.plugins.arinstaller._fomod.fomod_common import FomodModuleConfig

# noinspection PyProtectedMember
from summonmm.plugins.arinstaller._fomod.fomod_guess import fomod_guess

# noinspection PyProtectedMember
from summonmm.plugins.arinstaller._fomod.fomod_parser import parse_fomod_moduleconfig


class _FomodArInstallerPluginExtraData:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("module_configs", None, (str, FomodModuleConfig))
    ]
    module_configs: dict[str, FomodModuleConfig]

    def __init__(self, mconfigs: dict[str, FomodModuleConfig]) -> None:
        self.module_configs = mconfigs

    @classmethod
    def for_summon_stable_json_load(cls) -> "_FomodArInstallerPluginExtraData":
        return cls({})


class FomodExtraArchiveDataFactory(ExtraArchiveDataFactory):
    def name(self) -> str:
        return "FOMOD"

    def extra_data(
        self, fullarchivedir: str
    ) -> _FomodArInstallerPluginExtraData | None:  # returns stable_json data
        assert is_normalized_dir_path(fullarchivedir)
        fomod_paths: list[str] = []
        for dirpath, _, filenames in os.walk(fullarchivedir):
            d = dirpath.lower()
            if d.endswith("\\fomod"):
                for f in filenames:
                    if f.lower() == "moduleconfig.xml":
                        assert d.startswith(fullarchivedir)
                        drel = d[len(fullarchivedir) :]
                        if drel == "fomod":
                            fomod_paths.append("")
                        else:
                            assert drel.endswith("\\fomod")
                            drel = drel[: -len("\\fomod")]
                            fomod_paths.append(drel)

        if len(fomod_paths) == 0:
            return None

        fomod_configs: list[FomodModuleConfig] = []
        for fomodroot in fomod_paths:
            fname = fullarchivedir + fomodroot + "\\fomod\\moduleconfig.xml"
            assert os.path.isfile(fname)
            with open_3rdparty_txt_file_autodetect(fname) as f:
                xml = ""
                for ln in f:
                    xml += ln
                root = ElementTree.fromstring(xml)
                modulecfg = parse_fomod_moduleconfig(root)
                fomod_configs.append(modulecfg)

        assert len(fomod_configs) == len(fomod_paths)
        return _FomodArInstallerPluginExtraData(
            {fomod_paths[i]: fomod_configs[i] for i in range(len(fomod_configs))}
        )


class _FomodArInstallerPluginInstallData:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("extra_data", "data", (bytes, _FomodArInstallerPluginExtraData)),
        ("no_extra_data", "empty", bytes),
        ("exceptions", "exceptions", (bytes, str)),
    ]
    extra_data: dict[bytes, _FomodArInstallerPluginExtraData]
    no_extra_data: list[bytes]
    exceptions: dict[bytes, str]

    def __init__(
        self,
        extradata: dict[bytes, _FomodArInstallerPluginExtraData],
        noextradata: list[bytes],
        exceptions: dict[bytes, str],
    ) -> None:
        self.extra_data = extradata
        self.no_extra_data = noextradata
        self.exceptions = exceptions

    @classmethod
    def for_summon_stable_json_load(cls) -> "_FomodArInstallerPluginInstallData":
        return cls({}, [], {})


class FomodArInstallerPlugin(ArInstallerPluginBase):
    extra_data: dict[bytes, _FomodArInstallerPluginExtraData] | None
    no_extra_data: list[bytes]
    exceptions: dict[bytes, str]

    def __init__(self):
        super().__init__()
        self.extra_data = None
        self.no_extra_data = []
        self.exceptions = {}

    def name(self) -> str:
        return "FOMOD"

    def guess_arinstaller_from_vfs(
        self,
        archive: Archive,
        modname: str,
        modfiles: dict[str, list[ArchiveFileRetriever]],
    ) -> ArInstaller | None:
        assert self.extra_data is not None
        if archive.archive_hash not in self.extra_data:
            return None
        instdata: _FomodArInstallerPluginExtraData = self.extra_data[
            archive.archive_hash
        ]
        assert len(instdata.module_configs) > 0
        bestguess = None
        bestn = None
        for root, modulecfg in instdata.module_configs.items():
            guess0 = fomod_guess(root, modulecfg, archive, modfiles)
            if guess0 is not None:
                guess, n = guess0
                if bestguess is None or bestn is None or n > bestn:
                    bestguess = guess
                    bestn = n
        return bestguess

    def init_from_load_json_data(self, data: StableJsonJsonSomething) -> None:
        target = _FomodArInstallerPluginInstallData.for_summon_stable_json_load()
        from_stable_json(target, data)
        self.extra_data = target.extra_data
        self.no_extra_data = target.no_extra_data
        self.exceptions = target.exceptions

    def data_for_save_json(self) -> StableJsonJsonSomething:
        assert self.extra_data is not None
        return to_stable_json(
            _FomodArInstallerPluginInstallData(
                self.extra_data, self.no_extra_data, self.exceptions
            )
        )

    def extra_data_factory(self) -> ExtraArchiveDataFactory | None:
        return FomodExtraArchiveDataFactory()

    def add_extra_data(
        self, arh: bytes, data: _FomodArInstallerPluginExtraData | None | Exception
    ) -> None:
        assert self.extra_data is not None
        if data is None:
            self.no_extra_data.append(truncate_file_hash(arh))
            return
        if isinstance(data, Exception):
            self.exceptions[arh] = repr(data)
            return
        assert isinstance(data, _FomodArInstallerPluginExtraData)
        if __debug__:
            if arh in self.extra_data:
                sjdata = to_stable_json(data)
                sjdatas = json.dumps(sjdata)
                sxtradata = to_stable_json(self.extra_data[arh])
                sxtradatas = json.dumps(sxtradata)
                assert sjdatas == sxtradatas
        self.extra_data[arh] = data


if __name__ == "__main__":
    import sys
    import xml.etree.ElementTree as ElementTree

    argv = sys.argv[1:]
    if len(sys.argv) == 2 and sys.argv[1] == "test":
        """
        tfname = os.path.split(os.path.abspath(__file__))[0] + '\\ModuleConfig.xml'
        tree = ElementTree.parse(tfname)
        modulecfg = parse_fomod_moduleconfig(tree.getroot())
        asjson = as_json(modulecfg)
        info(asjson)
        """
        tfname = (
            os.path.split(os.path.abspath(__file__))[0]
            + "\\..\\..\\..\\..\\summon-skyrim-root\\known-arinstaller-fomod-data.json"
        )

        xdata = _FomodArInstallerPluginInstallData.for_summon_stable_json_load()

        with open(tfname, "rt") as tf:
            known_json = json.load(tf)
            from_stable_json(xdata, known_json)

        new_json = to_stable_json(xdata)
        with open(tfname, "wt") as tf:
            # noinspection PyTypeChecker
            write_stable_json_opened(tf, new_json)

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
