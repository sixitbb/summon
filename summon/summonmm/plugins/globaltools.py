# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
Loader for globaltool plugins
"""

from summonmm.common import *
from summonmm.plugins import load_plugins
from summonmm.helpers.project_config import LocalProjectConfig


class CouldBeProducedByGlobalTool(IntEnum):
    NotFound = 0
    Maybe = 1
    WithKnownConfig = 2
    WithOldConfig = 3
    WithCurrentConfig = 4

    def is_greater_or_eq(self, cbp: "CouldBeProducedByGlobalTool") -> bool:
        return int(self) >= int(cbp)


class GlobalToolPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def supported_games(self) -> list[str]:
        pass

    @abstractmethod
    def extensions(self) -> list[str]:
        pass

    @abstractmethod
    def create_context(self, cfg: LocalProjectConfig, resolvedvfs: ResolvedVFS) -> Any:
        pass

    @abstractmethod
    def could_be_produced(
        self, context: Any, srcpath: str, targetpath: str
    ) -> CouldBeProducedByGlobalTool:
        pass


_global_tool_plugins: list[GlobalToolPluginBase] = []


def _found_global_tool_plugin(plugin: GlobalToolPluginBase) -> None:
    global _global_tool_plugins
    if __debug__:
        for universe in plugin.supported_games():
            assert universe.isupper()
    _global_tool_plugins.append(plugin)


load_plugins(
    "plugins/globaltool/",
    GlobalToolPluginBase,
    lambda plugin: _found_global_tool_plugin(plugin),
)


def all_global_tool_plugins(gameuniverse: str) -> list[GlobalToolPluginBase]:
    global _global_tool_plugins
    return [
        t for t in _global_tool_plugins if gameuniverse.upper() in t.supported_games()
    ]


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
