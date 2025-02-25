# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
Home of class OmniCache
"""

import summonmm.tasks as tasks
from summonmm.cache.available_files import FileRetriever, AvailableFiles
from summonmm.cache.folder_cache import FolderCache
from summonmm.common import *
from summonmm.common import SummonJsonEncoder
from summonmm.helpers.project_config import LocalProjectConfig, GithubModpack
from summonmm.helpers.tmp_path import TmpPath


class OmniCache:
    """
    Omni, once ready_task_name() is reached, contains whole information about the folders, and available files
      As such, OmniCache is 'omniscient'
      All the information is in-memory, so it can work incredibly fast
    """

    source_vfs_cache: FolderCache
    available: AvailableFiles
    _project_config: LocalProjectConfig
    _cache_data: ConfigData
    _resolved_vfs: ResolvedVFS | None
    _SYNCOWNTASKNAME: str = "summon.omnicache.sync"

    def __init__(self, projectcfg: LocalProjectConfig, tmp: TmpPath) -> None:
        self._project_config = projectcfg
        try:
            with open(self._cache_data_fname(), "r") as f:
                self._cache_data = json.load(f)
        except Exception as e:
            warn(
                "OmniCache: cannot load cachedata from {}: {}".format(
                    self._cache_data_fname, e
                )
            )
            self._cache_data = {}

        assert projectcfg.root_modpack is not None
        rootmodpackdir = GithubModpack(projectcfg.root_modpack).folder(
            projectcfg.github_root_dir
        )
        self.available = AvailableFiles(
            projectcfg.github_username,
            projectcfg.cache_dir,
            tmp.tmpdir,
            projectcfg.github_root_dir,
            rootmodpackdir,
            projectcfg.download_dirs,
            projectcfg.github_folders(),
            self._cache_data,
        )

        folderstocache: FolderListToCache = projectcfg.active_source_vfs_folders()
        self.source_vfs_cache = FolderCache(projectcfg.cache_dir, "vfs", folderstocache)

        self._resolved_vfs = None

    def start_tasks(self, parallel: tasks.Parallel) -> None:
        self.source_vfs_cache.start_tasks(parallel)
        self.available.start_tasks(parallel)

        syncowntask = tasks.OwnTask(
            OmniCache._SYNCOWNTASKNAME,
            lambda _, _1, _2: self._start_sync_own_task_func(),
            None,
            [
                self.source_vfs_cache.ready_task_name(),
                self.available.ready_task_name(),
            ],
        )
        parallel.add_task(syncowntask)

    @staticmethod
    def ready_task_name() -> str:
        return OmniCache._SYNCOWNTASKNAME

    def all_source_vfs_files(self) -> Iterable[FileOnDisk]:
        return self.source_vfs_cache.all_files()

    def file_retrievers_by_hash(
        self, h: bytes
    ) -> list[FileRetriever]:  # resolved as fully as feasible
        return self.available.file_retrievers_by_hash(h)

    def archive_stats(self) -> dict[bytes, tuple[int, int]]:  # hash -> (n,total_size)
        return self.available.archive_stats()

    def resolved_vfs(self) -> ResolvedVFS:
        if self._resolved_vfs is None:
            self._resolved_vfs = self._project_config.mod_manager_config.resolve_vfs(
                self.all_source_vfs_files()
            )
        return self._resolved_vfs

    def stats_of_interest(self) -> list[str]:
        return (
            self.available.stats_of_interest()
            + self.source_vfs_cache.stats_of_interest()
            + ["summon.omnicache."]
        )

    def done(self) -> None:
        with open(self._cache_data_fname(), "w") as f:
            # noinspection PyTypeChecker
            json.dump(self._cache_data, f, indent=2, cls=SummonJsonEncoder)

    ### private functions
    def _sync_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ["summon.available.ready()", "summon.foldercache.vfs.ready()"],
            [],
            ["summon.omnicache.ready()"],
        )

    def _start_sync_own_task_func(self) -> None:
        pass  # do nothing, this task is necessary only to synchronize

    def _cache_data_fname(self) -> str:
        return self._project_config.cache_dir + "omnicache.cachedata.json"


if __name__ == "__main__":
    import sys
    import time
    from summonmm.install.install_github import clone_github_project, GithubFolder
    from summonmm.install.install_ui import InstallUI

    ui = InstallUI()
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        ttmppath = normalize_dir_path("../../../../summon.tmp\\")
        if not os.path.isdir(ttmppath):
            os.makedirs(ttmppath)
        if not os.path.isdir("../../../../author/folder"):
            clone_github_project(
                "../../../../",
                GithubFolder("author/folder"),
                ui.network_error_handler(2),
            )
        start_file_logging(ttmppath + "summon.log.html")
        enable_extended_logging()
        check_summonmm_prerequisites(ui)

        cfgfname = normalize_file_path("../../../../local-summon-project.json5")
        tcfg = LocalProjectConfig(ui, cfgfname)

        with TmpPath(ttmppath) as ttmp:
            wcache = OmniCache(tcfg, ttmp)
            with tasks.Parallel(
                None,
                taskstatsofinterest=wcache.stats_of_interest(),
                dbg_serialize=False,
            ) as tparallel:
                t0 = time.perf_counter()
                wcache.start_tasks(tparallel)
                dt = time.perf_counter() - t0
                info("Whole Cache: starting tasks took {:.2f}s".format(dt))
                tparallel.run([])
            wcache.done()

        info("omni_cache.py test finished ok")

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
