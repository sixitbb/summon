# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
install_logging is a part of summonmm.install, and as such is not allowed to use anything which is not a part of 
  default Python install (i.e. it is not allowed to use anything which requires pip modules)

install_logging provides support for summonmm logging, including 
  colorized console, HTML log file, and functions which are used by summonmm.tasks for multiprocess logging. 
"""

import logging
import time
import typing
from collections.abc import Callable


def _summon_patch_record(record: logging.LogRecord) -> None:
    if not hasattr(record, "summonmm_when"):
        record.summonmm_when = time.perf_counter()
    if not hasattr(record, "summonmm_prefix"):
        record.summonmm_prefix = ""
    when: float = record.summonmm_when  # type: ignore ; we hope we know what we're doing here
    record.summonmm_from_start = when - logging_started()


_PERFWARN_LEVEL_NUM = 25

_FORMAT: str = "%(message)s"
_FORMAT_EX: str = (
    "[%(levelname)s@%(summonmm_from_start).2f]:%(summonmm_prefix)s %(message)s (%(filename)s:%(lineno)d)"
)


class _SummonFormatter(logging.Formatter):
    _formats: dict[int, str]

    def __init__(self) -> None:
        super().__init__()
        self._formats = _SummonFormatter._formats_dict(_FORMAT)

    @staticmethod
    def _formats_dict(fmt: str) -> dict[int, str]:
        return {
            logging.DEBUG: "\x1b[90m" + fmt + "\x1b[0m",
            logging.INFO: "\x1b[32m" + fmt + "\x1b[0m",
            _PERFWARN_LEVEL_NUM: "\x1b[34m" + fmt + "\x1b[0m",
            logging.WARNING: "\x1b[33m" + fmt + "\x1b[0m",
            logging.ERROR: "\x1b[93m" + fmt + "\x1b[0m",  # alert()
            logging.CRITICAL: "\x1b[91;1m" + fmt + "\x1b[0m",
        }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self._formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        _summon_patch_record(record)
        return formatter.format(record)

    def enable_ex_logging(self) -> None:
        self._formats = _SummonFormatter._formats_dict(_FORMAT_EX)


class _SummonHtmlFileFormatter(logging.Formatter):
    _formats: dict[int, str]

    def __init__(self) -> None:
        super().__init__()
        self._formats = _SummonHtmlFileFormatter._formats_dict(_FORMAT)

    @staticmethod
    def _formats_dict(fmt: str) -> dict[int, str]:
        return {
            logging.DEBUG: '<div class="debug">' + fmt + "</div>",
            logging.INFO: '<div class="info">' + fmt + "</div>",
            _PERFWARN_LEVEL_NUM: '<div class="perf_warn">' + fmt + "</div>",
            logging.WARNING: '<div class="warn">' + fmt + "</div>",
            logging.ERROR: '<div class="alert">' + fmt + "</div>",
            logging.CRITICAL: '<div class="critical">' + fmt + "</div>",
        }

    def format(self, record: logging.LogRecord) -> str:
        record.msg = record.msg.replace("\n", "<br>")
        log_fmt = self._formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        _summon_patch_record(record)
        return formatter.format(record)

    def enable_ex_logging(self) -> None:
        self._formats = _SummonHtmlFileFormatter._formats_dict(_FORMAT_EX)


logging.addLevelName(_PERFWARN_LEVEL_NUM, "PERFWARN")


def _perfwarn(
    logger: logging.Logger, message: str, *args: typing.Any, **kws: typing.Any
) -> None:
    if logger.isEnabledFor(_PERFWARN_LEVEL_NUM):
        # Yes, logger takes its '*args' as 'args'.
        logger._log(_PERFWARN_LEVEL_NUM, message, args, **kws)


logging.Logger.perf_warn = _perfwarn  # type: ignore (yes, we're making a new member in logging.Logger on the fly)

logging.addLevelName(logging.ERROR, "ALERT")
_logger = logging.getLogger()
_logger.setLevel(logging.DEBUG if __debug__ else logging.INFO)

_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.DEBUG)
_console_handler.setFormatter(_SummonFormatter())

_logger.addHandler(_console_handler)

_logger_file_handler: logging.FileHandler | None = None

_started: float = time.perf_counter()


class _HtmlFileHandler(logging.FileHandler):
    def __init__(self, fpath: str) -> None:
        super().__init__(fpath, "w", encoding="utf-8")
        bodystyle = "body{ background-color:black; white-space:nowrap; font-size:1.2em; font-family:monospace; }\n"
        debugstyle = ".debug{color:#666666;}\n"
        infostyle = ".info{color:#008000;}\n"
        perfwarnstyle = ".perf_warn{color:#0492c2;}\n"
        warnstyle = ".warn{color:#a28a08;}\n"
        alertstyle = ".alert{color:#e5bf00; font-weight:600;}\n"
        criticalstyle = ".critical{color:#ff0000; font-weight:600;}\n"
        self.stream.write(
            "<html><head><style>\n"
            + bodystyle
            + debugstyle
            + infostyle
            + perfwarnstyle
            + warnstyle
            + alertstyle
            + criticalstyle
            + "</style></head>\n"
            + "<body>\n"
        )
        self.stream.write(
            '<div class="info">[STARTING LOGGING]: {}</div>\n'.format(time.asctime())
        )


_ex_logging: bool = False


def start_file_logging(fpath: str) -> None:
    """
    Starts summonmm HTML file logging
    """
    global _logger, _logger_file_handler
    assert _logger_file_handler is None
    try:
        _logger_file_handler = _HtmlFileHandler(fpath)
        _logger_file_handler.setLevel(logging.DEBUG if __debug__ else logging.INFO)
        _logger_file_handler.setFormatter(_SummonHtmlFileFormatter())
        if _ex_logging:
            assert isinstance(_logger_file_handler.formatter, _SummonHtmlFileFormatter)
            _logger_file_handler.formatter.enable_ex_logging()
        _logger.addHandler(_logger_file_handler)
    except OSError as e:
        alert(
            "Exception {} while trying to enable file logging, will continue without file logging".format(
                e
            )
        )
        _logger_file_handler = None


def enable_extended_logging() -> None:
    """
    Enables extended logging (with more info, and more verbose)
    """
    global _console_handler, _logger_file_handler, _ex_logging
    assert isinstance(_console_handler.formatter, _SummonFormatter)
    _console_handler.formatter.enable_ex_logging()
    if _logger_file_handler is not None:
        assert isinstance(_logger_file_handler.formatter, _SummonHtmlFileFormatter)
        _logger_file_handler.formatter.enable_ex_logging()
    _ex_logging = True


def add_logging_handler(handler: logging.StreamHandler[typing.TextIO]) -> None:
    global _logger
    _logger.addHandler(handler)


_logging_hook: Callable[[logging.LogRecord], None] | None = None


def set_logging_hook(
    newhook: Callable[[logging.LogRecord], None] | None
) -> Callable[[logging.LogRecord], None] | None:
    """
    Sets logging hook, intercepting all the calls to the logging functions such as debug()...critical().

    Low-level function, used by summonmm.tasks
    """
    global _logging_hook
    oldhook = _logging_hook
    _logging_hook = newhook
    return oldhook


def log_record(record: logging.LogRecord) -> None:
    """
    Low-level stuff, used by summonmm.tasks
    """
    global _console_handler, _logger_file_handler
    _console_handler.emit(record)
    if _logger_file_handler is None:
        return
    _logger_file_handler.emit(record)


def log_record_skip_console(record: logging.LogRecord) -> None:
    """
    Low-level stuff, used by summonmm.tasks
    """
    global _logger_file_handler
    if _logger_file_handler is None:
        return
    _logger_file_handler.emit(record)


def _make_log_record(level: int, msg: str) -> logging.LogRecord:
    global _logger
    fn, lno, func, sinfo = _logger.findCaller(False, stacklevel=3)
    rec = _logger.makeRecord(
        _logger.name, level, fn, lno, msg, (), None, func, None, sinfo
    )
    rec.summonmm_when = time.perf_counter()
    rec.summonmm_prefix = ""
    return rec


def make_log_record(
    level: int, msg: str
) -> logging.LogRecord:  # different stacklevel than _make_log_record
    """
    Low-level stuff, used by summonmm.tasks
    """
    global _logger
    fn, lno, func, sinfo = _logger.findCaller(False, stacklevel=2)
    rec = _logger.makeRecord(
        _logger.name, level, fn, lno, msg, (), None, func, None, sinfo
    )
    rec.summonmm_when = time.perf_counter()
    rec.summonmm_prefix = ""
    return rec


def logging_started() -> float:
    global _started
    return _started


def log_with_level(level: int, msg: str) -> None:
    """
    As it says on the tin: logs with level.
    """
    if not __debug__ and level <= logging.DEBUG:
        return
    global _logging_hook
    if _logging_hook is not None:
        _logging_hook(_make_log_record(level, msg))
        return
    global _logger
    _logger.log(level, msg, stacklevel=2)


def debug(msg: str) -> None:
    """
    If __debug__ is True, logs DEBUG message (usually grey)
    """
    if not __debug__:
        return
    global _logging_hook
    if _logging_hook is not None:
        _logging_hook(_make_log_record(logging.DEBUG, msg))
        return
    global _logger
    _logger.debug(msg, stacklevel=2)


def info(msg: str) -> None:
    """
    Logs INFO message (usually green)
    """
    global _logger
    global _logging_hook
    if _logging_hook is not None:
        _logging_hook(_make_log_record(logging.INFO, msg))
        return
    _logger.info(msg, stacklevel=2)


def perf_warn(msg: str) -> None:
    """
    Logs PERFWARN message (usually cerulean); PERFWARN is a custom level introduced by summonmm, to show PERFormance WARNings.
    """
    global _logger
    global _logging_hook
    if _logging_hook is not None:
        _logging_hook(_make_log_record(_PERFWARN_LEVEL_NUM, msg))
        return
    # noinspection PyUnresolvedReferences
    _logger.perf_warn(msg, stacklevel=2)  # type: ignore


def warn(msg: str) -> None:
    """
    Logs INFO message (usually yellow)
    """
    global _logging_hook
    if _logging_hook is not None:
        _logging_hook(_make_log_record(logging.WARN, msg))
        return
    global _logger
    _logger.warning(msg, stacklevel=2)


def alert(msg: str) -> None:
    """
    Logs ALERT message (usually amber); it corresponds to Python's logging.Error
    """
    global _logging_hook
    if _logging_hook is not None:
        _logging_hook(_make_log_record(logging.ERROR, msg))
        return
    global _logger
    _logger.error(msg, stacklevel=2)


def critical(msg: str) -> None:
    """
    Logs CRITICAL message (usually bright-red)
    """
    global _logging_hook
    if _logging_hook is not None:
        _logging_hook(_make_log_record(logging.CRITICAL, msg))
        return
    global _logger
    _logger.critical(msg, stacklevel=2)


def info_or_perf_warn(pwarn: bool, msg: str) -> None:
    """
    Logs INFO or PERFWARN message (depending on condition)
    """
    if pwarn:
        perf_warn(msg)
    else:
        info(msg)


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
