# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
simple_download is a part of summonmm.install, and as such is not allowed to use anything which is not a part of 
  default Python install (i.e. it is not allowed to use anything which requires pip modules)
  
  !! ONE EXCEPTION HERE IS certifi (on some boxes SSL doesn't work without certifi), so it is a responsibility of the caller 
     to ensure that certifi is already installed (but certifi CAN be installed simply by running pip, without any other 
     dependencies)

Provides helper functions to build very simple installers (such as "get download link to most recent Python from 
  https://python.org/ and download Python from there"): most importantly, pattern_from_html() and download_temp(). 
"""

import gzip
import re
import shutil
import ssl
import tempfile
import urllib.request

import certifi  # some boxes won't work without it :(

from summonmm.install.install_common import *

_MAX_PAGE_SIZE = 1000000


def get_html(url: str) -> Any:
    """
    Gets data from url; do NOT try to download huge files, it is intended to work with small data files such as HTML.
    """
    rq = urllib.request.Request(url)
    ctx = ssl.create_default_context(cafile=certifi.where())
    return urllib.request.urlopen(rq, context=ctx)


def pattern_from_html(url: str, pattern: str, encoding: str = "utf-8") -> list[str]:
    """
    Gets HTML and tries to find the pattern in it
    """
    with get_html(url) as f:
        b: bytes = f.read(_MAX_PAGE_SIZE)
        assert len(b) < _MAX_PAGE_SIZE
        if f.getheader("content-encoding") == "gzip":
            b = gzip.decompress(b)
        html: str = b.decode(encoding)
        return re.findall(pattern, html, re.IGNORECASE)


def adjust_url(baseurl: str, url: str) -> str:
    """
    Adjusts relative url if necessary
    """
    if url.startswith("http://") or url.startswith("https://"):
        return url

    # url is relative
    lastslash = baseurl.rfind("/")
    raise_if_not(lastslash >= 0)
    return baseurl[: lastslash + 1] + url


def _download_temp(url: str, errhandler: SummonBaseNetworkErrorHandler | None) -> str:
    wf: int
    wf, tfname = tempfile.mkstemp()
    assert isinstance(wf, int)
    while True:
        try:
            with get_html(url) as rf:
                while True:
                    b: Any = rf.read(1048576)
                    assert isinstance(b, bytes)
                    if not b:
                        break
                    os.write(wf, b)
            os.close(wf)
            return tfname
        except OSError as e:
            alert("Exception {} while downloading {}".format(e, url))
            os.close(wf)
            assert e.errno is not None

            if errhandler is not None and errhandler.handle_error(
                "Downloading {}".format(url), e.errno
            ):
                wf = os.open(tfname, os.O_WRONLY | os.O_CREAT)
                continue

            raise e


def download_temp(url: str, errhandler: SummonBaseNetworkErrorHandler | None) -> str:
    """
    Downloads file from url, trying to preserve file name
    """
    tfname = _download_temp(url, errhandler)
    assert os.path.isfile(tfname)
    desired_fname = url.split("/")[-1]
    for i in range(9):
        new_fname = os.path.split(tfname)[0] + "\\" + desired_fname
        if i > 0:
            new_fname += " (" + str(i) + ")"
        if os.path.exists(new_fname):
            continue
        try:
            shutil.move(tfname, new_fname)
            if os.path.isfile(new_fname):
                return new_fname
        except OSError:
            continue

        raise_if_not(os.path.isfile(tfname))
    raise_if_not(False)
    assert False


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
