# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
pickled_cache is a generic cache of already-calculated data (kind of memoization)

Provides pickled_cache() function
"""

from summonmm.common import *


def pickled_cache(
    cachedir: str,
    cachedata: ConfigData,
    prefix: str,
    origfiles: list[str],
    calc: Callable[[Any], Any],
    params: Any = None,
) -> tuple[Any, ConfigData]:

    assert isinstance(origfiles, list)
    rpaths0 = cachedata.get(prefix + ".files")
    readpaths: list[tuple[str, int, float]] = []
    if rpaths0 is not None:
        assert isinstance(rpaths0, list)
        rpaths1: list[Any] = rpaths0
        for rp in rpaths1:
            assert isinstance(rp, list)
            rp1: list[Any] = rp
            assert len(rp1) == 3
            assert isinstance(rp1[0], str)
            assert isinstance(rp1[1], int)
            assert isinstance(rp1[2], float)
            readpaths.append((rp1[0], rp1[1], rp1[2]))

    sameparams: bool = False
    if params is not None:
        # comparing as JSONs is important
        readparams = as_json(cachedata.get(prefix + ".params"))
        jparams = as_json(params)
        sameparams = readparams == jparams
    else:
        sameparams = True

    samefiles = len(readpaths) == len(origfiles)
    if sameparams and samefiles:
        readpaths = sorted(readpaths)
        origfiles = sorted(origfiles)
        for i in range(len(readpaths)):
            rd = readpaths[i]
            st = os.lstat(origfiles[i])
            of = (origfiles[i], st.st_size, st.st_mtime)
            assert isinstance(rd, tuple)
            assert is_normalized_file_path(rd[0])
            assert is_normalized_file_path(of[0])

            jrd = as_json(rd)
            jof = as_json(of)

            if jrd != jof:  # lists are sorted, there should be exact match here
                samefiles = False
                break

    pfname = cachedir + prefix + ".pickle"
    if sameparams and samefiles and os.path.isfile(pfname):
        info("pickledCache(): Yahoo! Can use cache for " + prefix)
        with open(pfname, "rb") as rf:
            return pickle.load(rf), {}

    cachedataoverwrites: ConfigData = {}
    files: list[tuple[str, int, float]] = []
    for of in origfiles:
        st = os.lstat(of)
        files.append((of, st.st_size, st.st_mtime))
    assert len(files) == len(origfiles)

    out = calc(params)

    for f in files:
        st = os.lstat(f[0])
        raise_if_not(
            f[1] == st.st_size and f[2] == st.st_mtime
        )  # if any of the files we depend on, has changed while calc() was calculated - something is really weird is going on here

    with open(cachedir + prefix + ".pickle", "wb") as wf:
        # noinspection PyTypeChecker
        pickle.dump(out, wf)
    cachedataoverwrites[prefix + ".files"] = files
    if params is not None:
        cachedataoverwrites[prefix + ".params"] = params
    return out, cachedataoverwrites


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
