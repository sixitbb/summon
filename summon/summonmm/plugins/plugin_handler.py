# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import glob
import importlib
import inspect

from summonmm.common import *


def load_plugins(plugindir: str, basecls: Any, found: Callable[[Any], None]) -> None:
    # plugindir is relative to the path of this very file
    thisdir = os.path.split(os.path.abspath(__file__))[0] + "\\..\\"
    # print(thisdir)
    sortedpys = sorted([py for py in glob.glob(thisdir + plugindir + "*.py")])
    for py in sortedpys:
        # print(py)
        modulename = os.path.splitext(os.path.split(py)[1])[0]
        if modulename == "__init__" or modulename.startswith("_"):
            continue
        # print(modulename)
        module = importlib.import_module(
            "summonmm." + plugindir.replace("/", ".") + modulename
        )
        ok = False
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                cls = obj
                mro = inspect.getmro(cls)
                if len(mro) >= 2:
                    parent = mro[1]
                    if parent is basecls:
                        plugin = cls()
                        found(plugin)
                        ok = True
        if not ok:
            warn("no class derived from " + str(basecls) + " found in " + py)


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
