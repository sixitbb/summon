# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import logging
import typing
from types import NoneType
import time
from multiprocessing import SimpleQueue
from threading import Thread

from summonmm.install.install_logging import (
    log_record,
    log_record_skip_console,
    make_log_record,
)
from summonmm.tasks._tasks_common import current_proc_num

type _LogRecReturn = tuple[int, float, logging.LogRecord]
type _LogQItem = _LogRecReturn | None | StopSkipping | EndOfRegularLog
type LogQueue = SimpleQueue[_LogQItem]
type OutLogQueue = SimpleQueue[NoneType]


def create_logging_thread(logq: LogQueue, outlogq: OutLogQueue) -> Thread:
    return Thread(target=_logging_thread_func, args=(logq, outlogq))


class ChildProcessLogHandler(logging.StreamHandler[typing.TextIO]):
    logq: LogQueue

    def __init__(self, logq: LogQueue) -> None:
        super().__init__()
        self.logq = logq

    def emit(self, record: logging.LogRecord) -> None:
        assert current_proc_num() >= 0
        self.logq.put((current_proc_num(), time.perf_counter(), record))
        # print(record.getMessage())


_log_elapsed: float | None = None
_log_waited: float = 0.0


def log_elapsed() -> float | None:
    global _log_elapsed
    return _log_elapsed


def log_waited() -> float:
    global _log_waited
    return _log_waited


class StopSkipping:
    pass


class EndOfRegularLog:
    pass


### Implementation

_CONSOLE_LOG_QUEUE_THRESHOLD: int = 10
_CONSOLE_LOG_SKIPPING_UP_TO_LEVEL: int = logging.INFO


class _LoggingThreadState:
    _state: int
    _log_started: float
    _log_waited: float
    _log_outq: OutLogQueue
    _last_n_without_wait: int
    _last_n_with_spurious_wait: int

    def __init__(self, outlogq: OutLogQueue) -> None:
        self._state = 0
        self._log_started = time.perf_counter()
        self._log_waited = 0.0
        self._log_outq = outlogq
        self._last_n_without_wait = 0
        self._last_n_with_spurious_wait = 0

    def read_log_rec(self, logq: LogQueue) -> _LogRecReturn | bool | None:
        assert self._state == 0 or self._state == 1

        wt0 = time.perf_counter()
        record = logq.get()
        dwt = time.perf_counter() - wt0
        self._log_waited += dwt
        # print(dwt)
        if dwt < 3e-4:  # 300us
            self._last_n_without_wait += 1
            self._last_n_with_spurious_wait = 0
        else:
            if dwt > 0.01:  # certainly not spurious, we are no longer overloaded
                self._last_n_without_wait = 0
            else:
                self._last_n_with_spurious_wait += 1
                if self._last_n_with_spurious_wait > 1:
                    self._last_n_without_wait = 0

        if record is None:
            self._state = 2
            global _log_elapsed
            global _log_waited
            _log_elapsed = time.perf_counter() - self._log_started
            _log_waited = self._log_waited
            return None

        if isinstance(record, EndOfRegularLog):
            self._state = 1
            self._log_outq.put(None)
            return False
        if isinstance(record, StopSkipping):
            return True
        assert isinstance(record, tuple)

        (procnum, t, rec) = record
        rec.summonmm_when = t
        if procnum >= 0:
            rec.summonmm_prefix = "Process #{}: ".format(procnum + 1)

        # rec.summonmm_prefix = '@{}:'.format(self._state) + (rec.summonmm_prefix if hasattr(rec,'summonmm_prefix') and rec.summonmm_prefix is not None else '')
        # rec.msg = 'LOGTHREAD:' + rec.msg  # TODO: remove

        return record

    def is_overloaded(self, threshold: int) -> bool:
        return self._last_n_without_wait >= threshold


def _log_skipped(skipped: dict[int, int]) -> None:
    for levelno in skipped:
        rec = make_log_record(
            levelno,
            "tasks.log: logging thread overloaded, skipped {} [{}] entries in console, see log file for full details".format(
                skipped[levelno], logging.getLevelName(levelno)
            ),
        )
        log_record(rec)


def _logging_thread_func(logq: LogQueue, outlogq: OutLogQueue) -> None:
    assert current_proc_num() == -1
    lstate = _LoggingThreadState(outlogq)
    stopskipping = False
    while True:
        assert current_proc_num() == -1

        """
        skipped = {}
        while lstate.is_overloaded(_FILE_LOG_QUEUE_THRESHOLD):
            record = lstate.read_log_rec(logq)
            if record is None:
                return
            if record is False:
                continue
            (procnum, t, rec) = record
            levelno = rec.levelno
            if levelno <= _FILE_LOG_SKIPPING_UP_TO_LEVEL:
                if levelno in skipped:
                    skipped[levelno] += 1
                else:
                    skipped[levelno] = 1
            else:
                log_record(rec)

        for levelno in skipped:
            rec = make_log_record(levelno,
                                  'tasks.log: logging thread overloaded, skipped {} [{}] entries, which are lost forever'.format(
                                      skipped[levelno], log_level_name(levelno)))
            log_record(rec)
        """

        skipped: dict[int, int] = {}
        while lstate.is_overloaded(_CONSOLE_LOG_QUEUE_THRESHOLD) and not stopskipping:
            record = lstate.read_log_rec(logq)
            if record is None:
                _log_skipped(skipped)
                return
            if record is False:
                continue
            if record is True:
                stopskipping = True
                continue
            (_, _1, rec) = record
            levelno = rec.levelno
            if levelno <= _CONSOLE_LOG_SKIPPING_UP_TO_LEVEL:
                if levelno in skipped:
                    skipped[levelno] += 1
                else:
                    skipped[levelno] = 1
                log_record_skip_console(rec)
            else:
                log_record(rec)

        _log_skipped(skipped)

        record = lstate.read_log_rec(logq)
        if record is None:
            return

        if record is False:
            continue
        if record is True:
            stopskipping = True
            continue
        (_, _, rec) = record
        log_record(rec)


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
