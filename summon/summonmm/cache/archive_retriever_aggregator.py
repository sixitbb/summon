# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


import os.path

from summonmm.common import *
from summonmm.plugins.archives import archive_plugin_for
from summonmm.helpers.file_retriever import FileRetriever, ArchiveFileRetriever


class ArchiveRetrieverAggregator:
    archives: dict[
        bytes, list[ArchiveFileRetriever]
    ]  # all items in the list must have the same archive_hash()

    def __init__(self) -> None:
        self.archives = {}

    @staticmethod
    def is_my_retriever(fr: FileRetriever) -> bool:
        return isinstance(fr, ArchiveFileRetriever)

    def add_retriever(self, fr: ArchiveFileRetriever):
        assert ArchiveRetrieverAggregator.is_my_retriever(fr)
        arh = fr.archive_hash()
        if arh not in self.archives:
            self.archives[arh] = []
        self.archives[arh].append(fr)

    def is_empty(self) -> bool:
        return len(self.archives) == 0

    def all_archives_needed(self) -> list[bytes]:
        return list(self.archives.keys())

    def extract_all_from_one_archive(
        self, tmpdir: str, arh: bytes, arpath: str
    ) -> dict[bytes, str]:
        # returning file_hash -> temp_path
        assert is_normalized_dir_path(tmpdir)
        assert is_normalized_file_path(arpath)
        assert arh in self.archives

        tmpdir0 = tmpdir + "0\\"
        plugin = archive_plugin_for(arpath)
        assert plugin is not None
        flist: list[str] = [
            aretr.single_archive_retrievers[0].file_in_archive.intra_path
            for aretr in self.archives[arh]
        ]
        plugin.extract(arpath, flist, tmpdir0)

        out: dict[bytes, str] = {}
        nextagg = ArchiveRetrieverAggregator()
        existingars: dict[bytes, str] = {}
        for aretr in self.archives[arh]:
            a0 = aretr.single_archive_retrievers[0]
            ipath = a0.file_in_archive.intra_path
            fpath = tmpdir0 + ipath
            assert os.path.isfile(fpath)
            if len(aretr.single_archive_retrievers) == 1:  # final one
                assert a0.file_hash not in out
                out[a0.file_hash] = fpath
            else:  # nested
                nextagg.add_retriever(
                    ArchiveFileRetriever(
                        (a0.file_hash, a0.file_size),
                        aretr.constructor_parameter_removing_parent(),
                    )
                )
                assert a0.file_hash not in existingars
                existingars[a0.file_hash] = fpath

        assert len(existingars) == len(nextagg.archives)
        if not nextagg.is_empty():
            tmpi = 1
            for arh1 in nextagg.all_archives_needed():
                assert arh1 in existingars
                arpath = existingars[arh1]
                tmpdir1 = tmpdir + str(tmpi) + "\\"
                tmpi += 1
                out |= nextagg.extract_all_from_one_archive(tmpdir1, arh1, arpath)

        assert len(out) == len(self.archives)
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
