# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import os
import re
import subprocess
import sys
import traceback

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from summonmm.install.install_common import *
from summonmm.install.install_helpers import run_installer, find_command_and_add_to_path
from summonmm.install.install_github import (
    github_project_exists,
    clone_github_project,
    GithubFolder,
)
from summonmm.install.simple_download import pattern_from_html, download_temp
from summonmm.install.install_checks import report_hostile_programs, safe_call
from summonmm.install.install_ui import InstallUI

__version__ = "0.1.3c"
# TODO: eat pre-prompt input using msvcrt.kbhit()
# TODO: progress or at least "I'm alive" pseudo-progress while downloading/installing
# TODO: consider [optional] install of GitHub Desktop (to install-dependencies.py?)
# TODO: icacls replacement (apparently, icacls is not always available); try https://stackoverflow.com/a/27500472/28537706

_SIXIT = "sixitbb"
_SUMMONMM = "summon"

_GHFOLDER = GithubFolder(_SIXIT + "/" + _SUMMONMM)

ui = InstallUI()
try:
    start_file_logging(os.path.splitext(sys.argv[0])[0] + ".log.html")

    safe_call(
        ["echo", "Starting"] + sys.argv + ["..."], shell=True
    )  # for a mystical reason, launching an external process which prints something to the screen, solves console color issues

    info("S.U.M.M.O.N. bootstrapper version {}...".format(__version__))
    info("Bootstrapper .exe bundled Python version: {}".format(sys.version))

    report_hostile_programs(ui)

    for arg in sys.argv[1:]:
        if arg.lower() == "/silent":
            ui.set_silent_mode()
            info("Silent mode enabled")

    alert(
        "This will install S.U.M.M.O.N. from scratch, including, if necessary, installing python and/or git."
    )
    choice = ui.message_box("Do you want to proceed?", ["Yes", "no"])
    if choice == "no":
        alert("Exiting.")
        sys.exit()

    ### download and install python
    pyok = find_command_and_add_to_path(["py", "--version"], shell=True)
    if pyok:
        info("py found, no need to download and install python")
    else:
        info("py not found, will try to download and install python")
        dlurl = pattern_from_html(
            "https://python.org/downloads/",
            r"(https://www\.python\.org/ftp/python/3\.[0-9.]*/python-3\.[0-9.]*-amd64.exe)",
        )
        raise_if_not(len(dlurl) == 1)
        info("Downloading {}...".format(dlurl[0]))
        pyinstallexe = download_temp(dlurl[0], ui.network_error_handler(2))
        run_installer(
            ui,
            [pyinstallexe, "/quiet", "InstallAllUsers=1", "PrependPath=1"],
            "python.org",
            "Installing python... Installer runs in silent mode and may take up to 5 minutes.",
        )
        info("Python installer finished.")

        pyok = find_command_and_add_to_path(["py", "--version"], shell=True)
        raise_if_not(pyok)
        info("Python is available now.")

    gitok = find_command_and_add_to_path(["git", "--version"])
    if gitok:
        info("git found, no need to download and install it")
    else:
        info("git not found, will try to download and install it")
        tags = pattern_from_html(
            "https://gitforwindows.org/",
            r'https://github.com/git-for-windows/git/releases/tag/([a-zA-Z0-9.]*)"',
        )
        raise_if_not(len(tags) == 1)
        tag = tags[0]
        m = re.match(r"v([0-9.]*)\.windows\.[0-9]*", tag)
        raise_if_not(bool(m))
        assert m is not None
        ver = m.group(1)
        url = "https://github.com/git-for-windows/git/releases/download/{}/Git-{}-64-bit.exe".format(
            tag, ver
        )
        info("Downloading {}...".format(url))
        gitinstallexe = download_temp(url, ui.network_error_handler(2))
        run_installer(
            ui,
            [gitinstallexe, "/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            "github.com",
            "Installing git... Installer runs in silent mode and may take up to 5 minutes.",
        )
        info("Git installer finished.")
        gitok = find_command_and_add_to_path(["git", "--version"], shell=True)
        raise_if_not(gitok)
        info("Git is available now.")

    skiprepo = False
    while True:
        githubdir = ui.input_box(
            "Where do you want to keep your Github projects (including S.U.M.M.O.N.)?",
            "C:\\Modding\\GitHub",
            level=LinearUIImportance.Important,
        )
        if os.path.isdir(githubdir):
            ok = github_project_exists(githubdir, _GHFOLDER)
            if ok == 1:
                info(
                    "It seems that you already have {} cloned. Will proceed without cloning {}.".format(
                        _SUMMONMM, _SUMMONMM
                    )
                )
                skiprepo = True
                break
            if ok == -1:
                alert(
                    "Folder {}\\{}\\{} already exists. Please choose another folder for GitHub projects.".format(
                        githubdir, _GHFOLDER.author, _GHFOLDER.project
                    )
                )
            else:
                assert ok == 0
                break
        else:
            break

    if not skiprepo:
        clone_github_project(
            githubdir, _GHFOLDER, ui.network_error_handler(2), adjustpermissions=True
        )

    summondir = _GHFOLDER.folder(githubdir)
    info(
        "Bootstrapping completed. Now you do not need {} anymore, and should use scripts in {} instead.".format(
            sys.argv[0], summondir
        )
    )
    info("You still need to run {}\\summon-install-dependencies.py".format(summondir))
    choice = ui.message_box(
        "Do you want to run it now?", ["Yes", "no"], level=LinearUIImportance.Important
    )
    if choice == "no":
        info(
            "{}\\summon-install-dependencies.py was not run, make sure to run it before using S.U.M.M.O.N.".format(
                summondir
            )
        )
    else:
        cmd = "{}\\summon-install-dependencies.py".format(summondir)
        info("Running {}...".format(cmd))
        ok = subprocess.check_call(
            ["py", cmd] + sys.argv[1:]
        )  # should not use shell=True here, seems to cause trouble on the very first run
except Exception as e:
    critical("Exception: {}".format(e))
    alert(traceback.format_exc())
    ui.confirm_box(
        "Press any key to exit {}".format(sys.argv[0]),
        level=LinearUIImportance.VeryImportant,
    )

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
