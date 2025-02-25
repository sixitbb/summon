# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
install_checks is a part of summonmm.install, and as such is not allowed to use anything which is not a part of 
  default Python install (i.e. it is not allowed to use anything which requires pip modules)

install_checks' main public function is check_summonmm_prerequisites()
"""

import importlib
import re
import subprocess
import sys

from summonmm.install.install_common import *

REQUIRED_PIP_MODULES: list[str] = [
    "json5",
    "bethesda-structs",
    "pywin32",
    "certifi",
    "pyinstaller",
    "chardet",
]

PIP2PYTHON_MODULE_NAME_REMAPPING: dict[str, str | list[str]] = {
    "bethesda-structs": "bethesda_structs",
    "pywin32": ["win32api", "win32file"],
    "pyinstaller": [],
}


def _is_module_installed(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def _not_installed(msg: str) -> None:
    critical(msg)
    critical("Aborting. Please make sure to run summon-install-dependencies.py")
    # noinspection PyProtectedMember, PyUnresolvedReferences
    os._exit(1)


def _check_module(m: str) -> None:
    if not _is_module_installed(m):
        _not_installed("Module {} is not installed.".format(m))


def safe_call(cmd: list[str], shell: bool = False, cwd: str | None = None) -> bool:
    try:
        ret = subprocess.call(cmd, shell=shell, cwd=cwd)
        return ret == 0
    except OSError:
        return False


def find_command_and_add_to_path(cmd: list[str], shell: bool = False) -> bool:
    """
    adjusts PATH environment variable to include a command if necessary
    it will be inherited by child processes too
    :return: success
    """
    if safe_call(cmd, shell=shell):
        return True

    warn(
        "Cannot run {} using current PATH, will try looking for PATH in registry...".format(
            cmd[0]
        )
    )
    out = subprocess.check_output(
        [
            "reg",
            "query",
            "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
            "/v",
            "PATH",
        ]
    )
    out = out.decode("ascii")
    # print('out:'+out+'\n')
    m = re.search(r"\s*PATH\s*REG_EXPAND_SZ\s*(.*)", out)
    if m and len(m.group(1)) > len(os.environ["PATH"]):
        info("registry PATH was recently changed, trying with registry PATH")
        os.environ["PATH"] = m.group(1)
        info("new PATH=".format(os.environ["PATH"]))
        if safe_call(cmd, shell=shell):
            info("registry PATH did the trick")
            return True

    # last resort: direct search in Program Files
    warn(
        "Cannot run {} using registry PATH, will try looking for executable in Program Files...".format(
            cmd[0]
        )
    )
    for pf in [os.environ["ProgramFiles"], os.environ["ProgramFiles(x86)"]]:
        for curdir, _, files in os.walk(pf):
            for f in files:
                fname, fext = os.path.splitext(f)
                if fname == cmd[0] and (fext == ".exe" or fext == ".bat"):
                    info("found {} in {}, prepending it to PATH...".format(cmd[0], pf))
                    os.environ["PATH"] = curdir + ";" + os.environ["PATH"]
                    info("new PATH=".format(os.environ["PATH"]))
                    if safe_call(cmd, shell=shell):
                        info("Adding {} to PATH did the trick".format(curdir))
                        return True
    warn("My heuristics exhausted, cannot find {} to run".format(cmd[0]))
    return False


def report_hostile_programs(ui: LinearUI) -> None:
    try:
        tasklist = subprocess.check_output(["tasklist"])
        tasklist = tasklist.decode("ascii")
    except OSError:
        alert("Cannot run tasklist: hostile program detection may not work")
        tasklist = None

    if tasklist:
        norton = re.search("nortonsecurity.exe", tasklist, re.IGNORECASE)
        if norton:
            critical(
                "It seems that you have Norton antivirus running. It was reported to cause severe problems with modding."
            )
            critical(
                "It is STRONGLY suggested to quit, uninstall Norton antivirus, reboot, and re-launch {}.".format(
                    sys.argv[0]
                )
            )
            alert(
                "After removing Norton antivirus, you may want to enable Windows Defender."
            )
            choice = ui.message_box(
                "Are you ok with this suggestion?",
                ["Yes", "no"],
                level=LinearUIImportance.VeryImportant,
            )
            if choice != "no":
                alert(
                    "Exiting. Please uninstall Norton antivirus, reboot, optionally enable Windows Defender, and re-launch {}.".format(
                        sys.argv[0]
                    )
                )
                sys.exit(1)


def check_summonmm_prerequisites(ui: LinearUI, frominstall: bool = False) -> None:
    if not sys.version_info >= (3, 10):
        critical("Sorry, S.U.M.M.O.N. needs at least Python 3.10")
        sys.exit(1)

    thirdpartyfolder = (
        os.path.abspath(os.path.split(__file__)[0] + "\\..\\..\\3rdparty-exes") + "\\"
    )
    if not os.path.isfile(thirdpartyfolder + "7zr.exe"):
        _not_installed("3rdparty-exes\\7zr.exe not found")
    if not os.path.isfile(thirdpartyfolder + "UnRAR.exe"):
        _not_installed("3rdparty-exes\\UnRAR.exe not found")

    # we don't really need to check for MSVC already installed, as without it some of the pip modules won't be available

    for m in REQUIRED_PIP_MODULES:
        if m in PIP2PYTHON_MODULE_NAME_REMAPPING:
            val = PIP2PYTHON_MODULE_NAME_REMAPPING[m]
            if isinstance(val, list):
                for v in val:
                    _check_module(v)
            else:
                _check_module(val)
        else:
            _check_module(m)

    gitok = find_command_and_add_to_path(["git", "--version"])
    if not gitok:
        critical("git is not found in PATH.")
        critical(
            '{}Please make sure to install "Git for Windows" and include folder with git.exe into PATH.'.format(
                "Aborting. " if frominstall else ""
            )
        )
        # noinspection PyProtectedMember, PyUnresolvedReferences
        os._exit(1)

    report_hostile_programs(ui)

    info("All S.U.M.M.O.N. prerequisites are ok.")


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
