# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
install_helpers is a part of summonmm.install, and as such is not allowed to use anything which is not a part of 
  default Python install (i.e. it is not allowed to use anything which requires pip modules)

install_helpers provides run_installer() and most importantly, install_summonmm_prerequisites(). 
"""

import re
import subprocess
import sys
import shutil

from summonmm.install.install_checks import (
    REQUIRED_PIP_MODULES,
    find_command_and_add_to_path,
)
from summonmm.install.install_common import *
from summonmm.install.simple_download import adjust_url


def _install_pip_module(module: str) -> None:
    subprocess.check_call(["py", "-m", "pip", "install", module])


### install


def run_installer(
    ui: LinearUI, cmd: list[str], sitefrom: str, msg: str, cwd: str | None = None
) -> None:
    alert("We're about to run the following installer: {}".format(cmd[0]))
    info("It was downloaded from {}".format(sitefrom))
    info("Feel free to run it through your favorite virus checker,")
    info(
        "     but when, after entering 'Y' below, Windows will ask you stupid questions,"
    )
    alert("     please make sure to tell Windows that you're ok with it")

    choice = ui.message_box("Do you want to proceed?", ["Yes", "no"])
    if choice == "no":
        critical("Aborting installation. S.U.M.M.O.N. is likely to be unusable")
        # noinspection PyProtectedMember, PyUnresolvedReferences
        os._exit(1)

    if msg:
        alert(msg)

    subprocess.check_call(cmd, shell=True, cwd=cwd)


### specific installers


def _install_3rdparty_exes(ui: LinearUI) -> None:
    # importing only here, not at the beginning, to ensure that we already have certifi installed
    import summonmm.install.simple_download as simple_download

    thirdpartyfolder = (
        os.path.abspath(os.path.split(__file__)[0] + "\\..\\..\\3rdparty-exes") + "\\"
    )

    if not os.path.isfile(thirdpartyfolder + "7zr.exe"):
        alert("We need to download and install 7zr.exe from 7-zip.org")
        choice = ui.message_box("Do you want to proceed?", ["Yes", "no"])
        if choice == "no":
            alert("Exiting.")
            sys.exit()

        url0 = "https://www.7-zip.org/download.html"
        urls = simple_download.pattern_from_html(
            url0,
            r'href="(.*/7zr.exe)"',
        )
        raise_if_not(len(urls) >= 1)
        # reverse chronological order, so taking the first one if more than one
        url = adjust_url(url0, urls[0])
        info("Downloading {}...".format(url))
        exe = simple_download.download_temp(url, ui.network_error_handler(2))
        info("Download complete.")
        shutil.copyfile(exe, thirdpartyfolder + "7zr.exe")

    if not os.path.isfile(thirdpartyfolder + "UnRAR.exe"):
        alert("We need to download and install UnRAR.exe from rarlab.com")
        choice = ui.message_box("Do you want to proceed?", ["Yes", "no"])
        if choice == "no":
            alert("Exiting.")
            sys.exit()

        url = "https://www.rarlab.com/rar/unrarw64.exe"
        info("Downloading {}...".format(url))
        exe = simple_download.download_temp(url, ui.network_error_handler(2))
        info("Download complete.")
        run_installer(ui, [exe, "-s"], "rarlab.com", "", cwd=thirdpartyfolder)
        raise_if_not(os.path.isfile(thirdpartyfolder + "UnRAR.exe"))


def _install_vs_build_tools(ui: LinearUI) -> None:
    # importing only here, not at the beginning, to ensure that we already have certifi installed
    import summonmm.install.simple_download as simple_download

    # trying to find one
    programfiles = os.environ["ProgramFiles(x86)"]
    vswhere = os.path.join(
        programfiles, "Microsoft Visual Studio\\Installer\\vswhere.exe"
    )
    if os.path.exists(vswhere):
        out = subprocess.run(
            [
                vswhere,
                "-products",
                "Microsoft.VisualStudio.Product.BuildTools",
                "Microsoft.VisualStudio.Product.Community",
                "Microsoft.VisualStudio.Product.Professional",
                "Microsoft.VisualStudio.Product.Enterprise",
            ],
            text=True,
            capture_output=True,
        )

        if out.returncode == 0:
            outstr = out.stdout
            # _print_yellow(outstr)
            m = re.search(
                r"productId\s*:\s*(Microsoft.VisualStudio.Product.[a-zA-Z0-9]*)", outstr
            )
            if m:
                info(
                    "{} found, no need to download/install Visual Studio".format(
                        m.group(1)
                    )
                )
                return

    urls = simple_download.pattern_from_html(
        "https://visualstudio.microsoft.com/visual-cpp-build-tools/",
        r'href="(https://aka.ms/vs/.*/release/vs_BuildTools.exe)"',
    )
    raise_if_not(len(urls) == 1)
    url = urls[0]
    info("Downloading {}...".format(url))
    exe = simple_download.download_temp(url, ui.network_error_handler(2))
    info("Download complete.")
    run_installer(
        ui, [exe], url, 'Make sure to check "Desktop Development with C++" checkbox.'
    )
    info("Visual C++ build tools install started.")
    alert(
        "Please proceed with VC++ install and restart {} afterwards.".format(
            sys.argv[0]
        )
    )
    ui.confirm_box("Press any key to exit {} now.".format(sys.argv[0]))
    # noinspection PyProtectedMember, PyUnresolvedReferences
    os._exit(0)


def install_summonmm_prerequisites(ui: LinearUI) -> None:
    gitok = find_command_and_add_to_path(["git", "--version"])
    raise_if_not(gitok)

    info("Installing certifi...")
    _install_pip_module(
        "certifi"
    )  # needed to use simple_download within _install_3rdparty_exes() and _install_vs_build_tools()
    info("certifi installed.")

    _install_3rdparty_exes(ui)
    _install_vs_build_tools(ui)  # should run before installing pip modules

    for m in REQUIRED_PIP_MODULES:
        _install_pip_module(m)
        info("pip module {} successfully installed.".format(m))

    # check_summonmm_prerequisites(True) - we should not call check_summonmm_prerequisites() here, seems to fail if called right after install


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
