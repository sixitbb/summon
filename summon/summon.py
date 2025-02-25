# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import os
import sys
import time
import traceback

from summonmm.helpers.tmp_path import TmpPath

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from summonmm.common import *
from summonmm.install.install_checks import check_summonmm_prerequisites
from summonmm.install.install_ui import InstallUI
from summonmm.helpers.project_config import (
    LocalProjectConfig,
    install_github_project_with_dependencies,
    GithubModpackConfig,
)
import summonmm.tasks as tasks
from summonmm.cache.omni_cache import OmniCache
from summonmm.commands.run_guess import run_guess


def _usage() -> None:
    thisscriptcall = os.path.split(sys.argv[0])[0]
    info("usage:")
    info("-> {} <ProjectConfig.json5>".format(thisscriptcall))


if __name__ == "__main__":
    argv = sys.argv[1:]
    if len(sys.argv) == 2 and sys.argv[1] == "test":
        argv = ["../../../local-summon-project.json5"]

    if len(argv) != 1:
        _usage()
        sys.exit(1)

    ui = InstallUI()
    check_summonmm_prerequisites(ui)

    cfgfname = argv[0]
    raise_if_not(os.path.isfile(cfgfname))
    cfgfname = normalize_file_path(cfgfname)
    cfg = LocalProjectConfig(ui, cfgfname)
    start_file_logging(cfg.tmp_dir + "summon.log.html")
    enable_extended_logging()

    with TmpPath(cfg.tmp_dir) as tmp:
        wcache = OmniCache(cfg, tmp)
        with tasks.Parallel(
            None, taskstatsofinterest=wcache.stats_of_interest(), dbg_serialize=False
        ) as tparallel:
            t0 = time.perf_counter()
            wcache.start_tasks(tparallel)
            tparallel.run([])
        wcache.done()

    while True:
        cmd = ui.input_box("Enter Command:", "")
        try:
            info(cmd)
            command: list[str] = cmd.split(" ")
            if len(command) == 0:
                command = ["h"]
            match command[0]:
                case "x" | "exit":
                    info("Exiting...")
                    sys.exit(0)

                case "github.install":
                    if len(command) < 2:
                        alert("wrong number of parameters, use help to ask for syntax")
                    else:
                        allmodpackconfigs: dict[str, GithubModpackConfig] = (
                            {}
                        )  # have to use temporary one to avoid changing our main cfg
                        rootmodpack = install_github_project_with_dependencies(
                            ui, command[1], cfg.github_root_dir, allmodpackconfigs
                        )
                        info("{} installed, root={}".format(command[1], rootmodpack))

                case "guess":
                    run_guess(cfg, wcache)

                case "h" | "help" | "" | _:
                    info("commands:")
                    info("-> h|help")
                    info("-> x|exit")
                    info("-> github.install <author> <project>")
                    info("-> guess")

        except Exception as e:
            alert("Exception {}: {!r}".format(type(e), e.args))
            warn(traceback.format_exc())
            pass

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
