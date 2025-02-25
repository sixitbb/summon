# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import re
import hashlib

from summonmm.common import *
from summonmm.gitdata.stable_json import (
    StableJsonJsonSomething,
    StableJsonTypeDescriptor,
    from_stable_json,
    to_stable_json,
)
from summonmm.plugins.fileorigins import (
    FileOrigin,
    FileOriginPluginBase,
    MetaFileParser,
)


### FileOrigin


class _NexusGameUniverse:
    game_ids: list[int]

    def __init__(self, gameids: list[int]) -> None:
        self.game_ids = gameids

    def is_nexus_gameid_ok(self, nexusgameid: int) -> bool:
        return nexusgameid in self.game_ids


class NexusFileOrigin(FileOrigin):
    gameid: int  # nexus game #
    modid: int
    fileid: int

    # md5: bytes

    def __init__(self, gameid: int, modid: int, fileid: int):
        super().__init__()
        self.gameid = gameid
        self.modid = modid
        self.fileid = fileid

    def eq(self, b: object) -> bool:
        assert isinstance(b, NexusFileOrigin)
        return (
            self.fileid == b.fileid
            and self.modid == b.modid
            and self.gameid == b.gameid
        )


### known-nexus-data.json


class _NexusGitPackedMod:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("files", "f", (int, bytes)),
    ]
    files: dict[int, bytes]

    def __init__(self) -> None:
        self.files = {}


class _NexusGitPackedGame:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("mods", "m", (int, _NexusGitPackedMod)),
    ]
    mods: dict[int, _NexusGitPackedMod]

    def __init__(self) -> None:
        self.mods = {}


class _NexusGitData:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("hash_to_md5", "h2md5", (bytes, bytes)),
        ("games", "games", (int, _NexusGitPackedGame)),
    ]
    hash_to_md5: dict[bytes, bytes]
    games: dict[int, _NexusGitPackedGame]

    def __init__(self) -> None:
        self.hash_to_md5 = {}
        self.games = {}

    def from_plugin(
        self,
        nexus_hash_mapping: dict[bytes, bytes],
        nexus_file_origins: dict[bytes, list[NexusFileOrigin]],
    ) -> None:
        assert len(self.hash_to_md5) == 0
        assert len(self.games) == 0
        self.hash_to_md5 = nexus_hash_mapping.copy()  # just in case
        for h, ol in nexus_file_origins.items():
            for o in ol:
                if o.gameid not in self.games:
                    self.games[o.gameid] = _NexusGitPackedGame()
                g = self.games[o.gameid]
                if o.modid not in g.mods:
                    g.mods[o.modid] = _NexusGitPackedMod()
                m = g.mods[o.modid]
                assert o.fileid not in m.files
                m.files[o.fileid] = h

    def to_plugin(
        self,
    ) -> tuple[dict[bytes, bytes], dict[bytes, list[NexusFileOrigin]]]:
        out1: dict[bytes, bytes] = self.hash_to_md5.copy()  # just in case
        out2: dict[bytes, list[NexusFileOrigin]] = {}
        for g, mods in self.games.items():
            for m, files in mods.mods.items():
                for f, h in files.files.items():
                    if h not in out2:
                        out2[h] = []
                    out2[h].append(NexusFileOrigin(g, m, f))
        return out1, out2


### MetaFileParser


class NexusMetaFileParser(MetaFileParser):
    MOD_ID_PATTERN = re.compile(r"^modID\s*=\s*([0-9]+)\s*$", re.IGNORECASE)
    FILE_ID_PATTERN = re.compile(r"^fileID\s*=\s*([0-9]+)\s*$", re.IGNORECASE)
    URL_PATTERN = re.compile(r'^url\s*=\s*"([^"]*)"\s*$', re.IGNORECASE)
    HTTPS_PATTERN = re.compile(
        r"^https://.*\.nexus.*\.com.*/([0-9]*)/([0-9]*)/([^?]*).*[?&]md5=([^&]*)&.*",
        re.IGNORECASE,
    )

    game_id: int | None
    mod_id: int | None
    file_id: int | None
    url: str | None
    file_name: str
    _universe: _NexusGameUniverse

    def __init__(self, universe: _NexusGameUniverse, meta_file_path: str) -> None:
        super().__init__(meta_file_path)
        self.game_id = None
        self.mod_id = None
        self.file_id = None
        self.url = None
        self.file_name = os.path.split(meta_file_path)[1]
        self._universe = universe

    def take_ln(self, ln: str) -> None:
        m = NexusMetaFileParser.MOD_ID_PATTERN.match(ln)
        if m:
            self.mod_id = int(m.group(1))
        m = NexusMetaFileParser.FILE_ID_PATTERN.match(ln)
        if m:
            self.file_id = int(m.group(1))
        m = NexusMetaFileParser.URL_PATTERN.match(ln)
        if m:
            self.url = m.group(1)
            assert self.url is not None
            urls = self.url.split(";")
            filename_from_url = None
            md5 = None
            for u in urls:
                m2 = NexusMetaFileParser.HTTPS_PATTERN.match(u)
                if not m2:
                    warn(
                        "meta/nexus: unrecognized url {} in {}".format(
                            u, self.meta_file_path
                        )
                    )
                    continue
                urlgameid = int(m2.group(1))
                urlmodid = int(m2.group(2))
                urlfname = m2.group(3)
                urlmd5 = m2.group(4)
                if self._universe.is_nexus_gameid_ok(urlgameid):
                    if self.game_id is None:
                        self.game_id = urlgameid
                    elif self.game_id != urlgameid:
                        warn(
                            "meta/nexus: mismatching game id {} in {}".format(
                                urlgameid, self.meta_file_path
                            )
                        )
                else:
                    warn(
                        "meta/nexus: unexpected gameid {} in {}".format(
                            urlgameid, self.meta_file_path
                        )
                    )
                if urlmodid != self.mod_id:
                    warn(
                        "meta/nexus: unmatching url modid {} in {}".format(
                            urlmodid, self.meta_file_path
                        )
                    )
                if filename_from_url is None:
                    filename_from_url = urlfname
                elif urlfname != filename_from_url:
                    warn(
                        "meta/nexus: unmatching url filename {} in {}".format(
                            urlfname, self.meta_file_path
                        )
                    )
                if md5 is None:
                    md5 = urlmd5
                elif urlmd5 != md5:
                    warn(
                        "meta/nexus: unmatching url md5 {} in {}".format(
                            urlmd5, self.meta_file_path
                        )
                    )
            if filename_from_url is not None:
                self.file_name = filename_from_url

    def make_file_origin(self) -> FileOrigin | None:
        # warn(str(modid))
        # warn(str(fileid))
        # warn(url)
        if (
            self.game_id is not None
            and self.mod_id is not None
            and self.file_id is not None
            and self.url is not None
        ):
            return NexusFileOrigin(self.game_id, self.mod_id, self.file_id)
        elif (
            self.game_id is None
            and self.mod_id is None
            and self.file_id is None
            and self.url is None
        ):
            return None
        elif (
            self.game_id is not None
            and self.mod_id is not None
            and self.file_id is not None
            and self.url is None
        ):
            warn(
                "meta/nexus: missing url in {}, will do without".format(
                    self.meta_file_path
                )
            )
            return NexusFileOrigin(self.game_id, self.mod_id, self.file_id)
        else:
            warn(
                "meta/nexus: incomplete modid+fileid+url in {}".format(
                    self.meta_file_path
                )
            )
            return None


### Plugin


class NexusMd5Hash(ExtraHash):
    _md5: Any

    def __init__(self):
        super().__init__()
        self._md5 = hashlib.md5(usedforsecurity=False)

    def update(self, data: bytes) -> None:
        self._md5.update(data)

    def digest(self) -> bytes:
        return self._md5.digest()


def _nexus_md5_factory() -> NexusMd5Hash:
    return NexusMd5Hash()


class NexusFileOriginPlugin(FileOriginPluginBase):
    game_ids: list[int]
    nexus_hash_mapping: dict[bytes, bytes]
    nexus_file_origins: dict[bytes, list[NexusFileOrigin]]

    def __init__(self) -> None:
        super().__init__()
        self.nexus_hash_mapping = {}
        self.nexus_file_origins = {}

    def name(self) -> str:
        return "NEXUS"

    def config(self, cfg: ConfigData) -> None:
        unused_config_warning("origins.nexus", cfg, ["gameids"])
        if "gameids" in cfg:
            gameids: Any = cfg["gameids"]
            if isinstance(gameids, int):
                gameids = [gameids]
            raise_if_not(isinstance(gameids, list))
            for gid in gameids:
                raise_if_not(isinstance(gid, int))
            self.game_ids = gameids
        else:
            self.game_ids = []

    def meta_file_parser(self, metafilepath: str) -> MetaFileParser:
        return NexusMetaFileParser(_NexusGameUniverse(self.game_ids), metafilepath)

    def add_file_origin(self, h: bytes, fo: FileOrigin) -> bool:
        assert isinstance(fo, NexusFileOrigin)
        if h in self.nexus_file_origins:
            for fo2 in self.nexus_file_origins[h]:
                assert isinstance(fo2, NexusFileOrigin)
                if fo2.eq(fo):
                    return False
            self.nexus_file_origins[h].append(fo)
            return True
        else:
            self.nexus_file_origins[h] = [fo]
            return True

    def extra_hash_factory(self) -> ExtraHashFactory:
        return _nexus_md5_factory

    def add_hash_mapping(self, h: bytes, xh: bytes) -> bool:
        if h not in self.nexus_hash_mapping:
            self.nexus_hash_mapping[h] = xh
            return True
        else:
            assert self.nexus_hash_mapping[h] == xh
            return False

    def data_for_save_json(self) -> StableJsonJsonSomething:
        out = _NexusGitData()
        out.from_plugin(self.nexus_hash_mapping, self.nexus_file_origins)
        return to_stable_json(out)

    def init_from_load_json_data(self, data: StableJsonJsonSomething) -> None:
        assert (len(self.nexus_file_origins)) == 0
        assert (len(self.nexus_hash_mapping)) == 0
        gdata = _NexusGitData()
        from_stable_json(gdata, data)
        self.nexus_hash_mapping, self.nexus_file_origins = gdata.to_plugin()


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
