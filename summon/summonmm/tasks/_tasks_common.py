# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

from summonmm.common import *

_proc_num: int = -1  # number of child process
_parallel_count: int = 0


def current_proc_num() -> int:
    global _proc_num
    return _proc_num


def set_current_proc_num(proc_num: int) -> None:
    global _proc_num
    _proc_num = proc_num


def increment_parallel_count() -> None:
    global _parallel_count
    _parallel_count += 1


def decrement_parallel_count() -> None:
    global _parallel_count
    _parallel_count -= 1


def _abort_if_parallel_running() -> None:
    global _parallel_count
    raise_if_not(_parallel_count == 0)


def is_lambda(func: Any) -> bool:
    return callable(func) and func.__name__ == "<lambda>"


class LambdaReplacement:
    f: Callable[[Any, Any], Any]
    capture: Any

    def __init__(self, f: Callable[[Any, Any], Any], capture: Any) -> None:
        self.f = f
        self.capture = capture

    def call(self, param: Any) -> Any:
        return self.f(self.capture, param)


_global_process_initializers: list[LambdaReplacement] = []


def add_global_process_initializer(init: LambdaReplacement) -> None:
    _abort_if_parallel_running()
    _global_process_initializers.append(init)


def get_global_process_initializers() -> list[LambdaReplacement]:
    return _global_process_initializers


def run_global_process_initializers(inits: list[LambdaReplacement]) -> None:
    for init in inits:
        init.call(None)


class TaskDataDependencies:
    required_tags: list[str]
    required_not_tags: list[str]
    provided_tags: list[str]

    def __init__(
        self, reqtags: list[str], reqnottags: list[str], provtags: list[str]
    ) -> None:
        self.required_tags = reqtags
        self.required_not_tags = reqnottags
        self.provided_tags = provtags


type _TaskF = Callable[[], Any] | Callable[[Any], Any] | Callable[
    [Any, Any], Any
] | Callable[[Any, Any, Any], Any] | Callable[[Any, Any, Any, Any], Any]


class Task:
    name: str
    f: (
        _TaskF | None
    )  # variable # of params depending on len(dependencies); None is for TaskPlaceholder below
    param: Any
    dependencies: list[str]
    w: float | None
    data_dependencies: TaskDataDependencies | None

    def __init__(
        self,
        name: str,
        f: _TaskF,
        param: Any,
        dependencies: list[str],
        w: float | None = None,
        datadeps: TaskDataDependencies | None = None,
    ) -> None:
        self.name = name
        self.f = f
        self.param = param
        self.dependencies = dependencies
        self.w = w
        self.data_dependencies = datadeps


class OwnTask(Task):
    pass


class TaskPlaceholder(Task):
    def __init__(self, name: str) -> None:
        super().__init__(name, lambda: None, None, [])


type TaskStatsOfInterest = list[str]


class ProcessStarted:
    def __init__(self, proc_num: int) -> None:
        self.proc_num = proc_num


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
