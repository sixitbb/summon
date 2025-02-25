# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


import os
import sys
import traceback

from summonmm.install.install_common import LinearUIImportance

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from summonmm.install.install_helpers import install_summonmm_prerequisites
from summonmm.install.install_ui import InstallUI
from summonmm.install.install_logging import info, critical, alert, start_file_logging

__version__ = "0.1.1"

ui = InstallUI()
try:
    start_file_logging(os.path.splitext(sys.argv[0])[0] + ".log.html")

    info("summon-install-dependencies.py version {}...".format(__version__))

    for arg in sys.argv[1:]:
        if arg.lower() == "/silent":
            ui.set_silent_mode()
            info("Silent mode enabled")

    install_summonmm_prerequisites(ui)

    info("Dependencies installed successfully, you are ready to run S.U.M.M.O.N.")
    ui.confirm_box("Press any key to exit {}".format(sys.argv[0]))
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
