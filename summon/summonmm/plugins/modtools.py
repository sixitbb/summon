# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
Loader for modtool plugins
"""

from summonmm.common import *
from summonmm.plugins.arinstallers import ArInstaller, ArInstallerDetails
from summonmm.helpers.file_retriever import ArchiveFileRetriever
from summonmm.plugins import load_plugins


class ModToolGuessParam:
    install_from: list[tuple[ArInstaller, ArInstallerDetails]]
    remaining_after_install_from: dict[str, list[ArchiveFileRetriever]]


class ModToolGuessDiff:
    moved: list[tuple[str, str]]

    def __init__(self):
        self.moved = []


class ModToolPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def supported_games(self) -> list[str]:
        pass

    @abstractmethod
    def guess_applied(
        self, param: ModToolGuessParam
    ) -> None | tuple[Any, ModToolGuessDiff]:
        pass


_mod_tool_plugins: list[ModToolPluginBase] = []


def _found_mod_tool_plugin(plugin: ModToolPluginBase) -> None:
    global _mod_tool_plugins
    if __debug__:
        for universe in plugin.supported_games():
            assert universe.isupper()
    _mod_tool_plugins.append(plugin)


load_plugins(
    "plugins/modtool/", ModToolPluginBase, lambda plugin: _found_mod_tool_plugin(plugin)
)


def all_mod_tool_plugins(gameuniverse: str) -> list[ModToolPluginBase]:
    global _mod_tool_plugins
    return [t for t in _mod_tool_plugins if gameuniverse.upper() in t.supported_games()]


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
