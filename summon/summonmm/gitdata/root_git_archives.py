# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
Support for known-archives.json

TODO: rewrite to use stable_json
"""

from summonmm.common import *
from summonmm.gitdata.stable_json import StableJsonTypeDescriptor
from summonmm.plugins.archives import Archive, FileInArchive


class _KnownArchivesFile:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("file_hash", "h"),
        ("file_size", "s"),
    ]
    file_hash: bytes
    file_size: int

    def __init__(self, h: bytes, sz: int) -> None:
        self.file_hash = h
        self.file_size = sz

    @classmethod
    def for_summon_stable_json_load(cls) -> "_KnownArchivesFile":
        return cls(b"", -1)


class _KnownNestedArchiveStub:  # merely to avoid circular dependency in SUMMON_JSON
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [("nested_archive", None)]

    nested_archive: "_KnownArchive"

    def __init__(self, a: "_KnownArchive") -> None:
        self.nested_archive = a

    @classmethod
    def for_summon_stable_json_load(cls) -> "_KnownNestedArchiveStub":
        return cls(_create_known_archive_for_stable_json())


class _KnownArchive:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("archive_size", "x"),
        ("by", "b", ""),
        ("files", "f", (str, _KnownArchivesFile)),
        ("archives", "a", (str, _KnownNestedArchiveStub)),
    ]
    archive_size: int
    files: dict[str, _KnownArchivesFile]
    archives: dict[str, _KnownNestedArchiveStub]
    by: str

    def __init__(self, asz: int) -> None:
        self.archive_size = asz
        self.files = {}
        self.archives = {}
        self.by = ""

    @classmethod
    def for_summon_stable_json_load(cls) -> "_KnownArchive":
        return cls(-1)


def _create_known_archive_for_stable_json() -> _KnownArchive:
    return _KnownArchive.for_summon_stable_json_load()


class KnownArchives:
    SUMMON_JSON: list[StableJsonTypeDescriptor] = [
        ("archives", "archives", (bytes, _KnownArchive)),
    ]
    archives: dict[bytes, _KnownArchive]

    def __init__(self) -> None:
        self.archives = {}

    def from_archives(self, archives: Iterable[Archive]) -> None:
        for ar in archives:
            assert ar.archive_hash not in self.archives
            kar = _KnownArchive(ar.archive_size)
            kar.by = ar.by
            self.archives[ar.archive_hash] = kar
            for f in ar.files:
                ip = f.intra_path
                assert isinstance(ip, str)
                assert ip not in kar.files
                kar.files[ip] = _KnownArchivesFile(f.file_hash, f.file_size)

    def to_archives(self) -> list[Archive]:
        out: list[Archive] = []
        for arh, kar in self.archives.items():
            ar = Archive(arh, kar.archive_size, kar.by)
            for ip, f in kar.files.items():
                ar.files.append(FileInArchive(f.file_hash, f.file_size, ip))
            out.append(ar)
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
