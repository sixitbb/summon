# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
class TmpPath
"""

import shutil
import time

from summonmm.common import *


class TmpPath:  # as we're playing with rmtree() here, we need to be super-careful not to delete too much
    tmpdir: str
    ADDED_FOLDER: str = "jbsltet9"  # seriously unique
    MAX_RMTREE_RETRIES: int = 3
    MAX_RESERVE_FOLDERS: int = 10

    def __init__(self, basetmpdir: str) -> None:
        assert basetmpdir.endswith("\\")
        self.tmpdir = basetmpdir + TmpPath.ADDED_FOLDER + "\\"

    def __enter__(self) -> "TmpPath":
        if os.path.isdir(self.tmpdir):
            try:
                shutil.rmtree(
                    self.tmpdir
                )  # safe not to remove too much as we're removing a folder with a UUID-based name
            except Exception as e:
                warn("Error removing {}: {}".format(self.tmpdir, e))
                # we cannot remove whole tmpdir, but maybe we'll have luck with one of 'reserve' subfolders?
                ok = False
                for i in range(self.MAX_RESERVE_FOLDERS):
                    reservefolder = self.tmpdir + "_" + str(i) + "\\"
                    if not os.path.isdir(reservefolder):
                        self.tmpdir = reservefolder
                        ok = True
                        break  # for i
                    try:
                        shutil.rmtree(reservefolder)
                        self.tmpdir = reservefolder
                        ok = True
                        break  # for i
                    except Exception as e2:
                        warn("Error removing {}: {}".format(reservefolder, e2))

                raise_if_not(ok)
                info("Will use {} as tmpdir".format(self.tmpdir))

        os.makedirs(self.tmpdir)
        return self

    def tmp_dir(self) -> str:
        return self.tmpdir

    @staticmethod
    def tmp_in_tmp(tmpbase: str, prefix: str, num: int) -> str:
        assert tmpbase.endswith("\\")
        if "\\" + TmpPath.ADDED_FOLDER + "\\" not in tmpbase:
            assert False
        return tmpbase + prefix + str(num) + "\\"

    def __exit__(self, _, exc_val: BaseException | None, exc_tb: TracebackType) -> None:
        TmpPath.rm_tmp_tree(self.tmpdir)
        if exc_val is not None:
            raise exc_val

    @staticmethod
    def rm_tmp_tree(
        tmppath: str,
    ) -> (
        None
    ):  # Sometimes, removing tmp tree doesn't work right after work with archive is done.
        # I suspect f...ing indexing service, but have not much choice rather than retrying.
        assert "\\" + TmpPath.ADDED_FOLDER + "\\" in tmppath
        nretries = TmpPath.MAX_RMTREE_RETRIES
        while True:
            nretries -= 1
            try:
                shutil.rmtree(tmppath)
                return
            except OSError as e:
                if nretries <= 0:
                    warn(
                        "Error trying to remove temp tree {}: {}. Will not retry, should be removed on restart".format(
                            tmppath, e
                        )
                    )
                    return
                warn(
                    "Error trying to remove temp tree {}: {}. Will retry in 1 sec, {} retries left".format(
                        tmppath, e, nretries
                    )
                )
                time.sleep(1.0)


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
