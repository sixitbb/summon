# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
Home of class FolderCache
"""

import os.path
import stat
import time

import summonmm.tasks as tasks
from summonmm.common import *


class _FastSearchOverFolderListToCache:
    _srch: FastSearchOverPartialStrings

    # _dbg_orig: FolderListToCache

    def __init__(self, src: FolderListToCache) -> None:
        initlst: list[tuple[str, bool]] = []
        for f in src.folders:
            initlst.append((f.folder, True))
            for x in f.exdirs:
                assert x.startswith(f.folder)
                initlst.append((x, False))
        self.srch = FastSearchOverPartialStrings(initlst)
        # self._dbg_orig = src

    def is_file_path_included(self, fpath: str) -> bool:
        assert is_normalized_file_path(fpath)
        found = self.srch.find_val_for_str(fpath)
        if found is None:
            # if self._dbg_orig.is_file_path_included(fpath) is not False:
            #    assert False
            return False
        # if self._dbg_orig.is_file_path_included(fpath) != found[1]:
        #    assert False
        return found[1]


### helpers

"""
def _get_file_timestamp(fname: str) -> float:
    return os.lstat(fname).st_mtime
"""


def _get_file_timestamp_from_st(st: os.stat_result) -> float:
    return st.st_mtime


def _read_dict_of_files(dirpath: str, name: str) -> dict[str, FileOnDisk]:
    assert is_normalized_dir_path(dirpath)
    fpath = dirpath + "foldercache." + name + ".pickle"
    return read_dict_from_pickled_file(fpath)


def _write_dict_of_files(
    dirpath: str,
    name: str,
    const_filesbypath: dict[str, FileOnDisk],
    filteredfiles: list[FileOnDisk],
) -> None:
    assert is_normalized_dir_path(dirpath)
    fpath = dirpath + "foldercache." + name + ".pickle"
    outfiles: dict[str, FileOnDisk] = const_filesbypath.copy()
    for f in filteredfiles:
        assert f.file_path not in outfiles
        outfiles[f.file_path] = f
    with open(fpath, "wb") as wf:
        # noinspection PyTypeChecker
        pickle.dump(outfiles, wf)

    if __debug__:
        fpath2 = dirpath + "foldercache." + name + ".njson"
        with open_3rdparty_txt_file_w(fpath2) as wf2:
            srt: list[tuple[str, FileOnDisk]] = sorted(outfiles.items())
            for item in srt:
                wf2.write(as_json(item[1]) + "\n")


def _read_all_scan_stats(dirpath: str, name: str) -> dict[str, dict[str, int]]:
    assert is_normalized_dir_path(dirpath)
    fpath = dirpath + "foldercache." + name + ".scan-stats.pickle"
    return read_dict_from_pickled_file(fpath)


def _write_all_scan_stats(
    dirpath: str, name: str, all_scan_stats: dict[str, dict[str, int]]
) -> None:
    assert is_normalized_dir_path(dirpath)
    all_scan_stats_for_save = dict(sorted(all_scan_stats.items()))
    for k, v in all_scan_stats_for_save.items():
        all_scan_stats_for_save[k] = dict(sorted(v.items()))
    fpath = dirpath + "foldercache." + name + ".scan-stats.pickle"
    with open(fpath, "wb") as wf:
        # noinspection PyTypeChecker
        pickle.dump(all_scan_stats_for_save, wf)

    if __debug__:
        fpath2 = dirpath + "foldercache." + name + ".scan-stats.json"
        with open_3rdparty_txt_file_w(fpath2) as wf2:
            # noinspection PyTypeChecker
            json.dump(all_scan_stats_for_save, wf2, indent=2)


class _FolderScanStats:
    nmodified: int
    nscanned: int
    ndel: int

    def __init__(self) -> None:
        self.nmodified = 0
        self.nscanned = 0
        self.ndel = 0

    def add(self, stats2: "_FolderScanStats") -> None:
        self.nmodified += stats2.nmodified
        self.nscanned += stats2.nscanned


class _FolderScanDirOut:
    root: str
    scanned_files: dict[str, FileOnDisk]
    requested_dirs: list[str]
    requested_files: list[tuple[str, float, int]]
    scan_stats: dict[str, int]  # fpath -> nfiles

    def __init__(self, root: str) -> None:
        self.root = root
        self.scanned_files = {}
        self.requested_dirs = []
        self.requested_files = []
        self.scan_stats = {}


# heuristics to enable splitting tasks


def _time_to_split_task(t: float) -> bool:
    return t > 0.5


def _scan_task_nf_threshold_heuristics() -> int:
    sec_threshold = 0.3
    return int(sec_threshold * 20000)  # scans per second


def _scan_task_time_estimate(nf: int) -> float:
    return float(nf) / 20000.0


def _hashing_file_time_estimate(fsize: int) -> float:
    return float(fsize) / 1048576.0 / 30.0


### Tasks


def _load_files_task_func(
    param: tuple[str, str, FolderListToCache]
) -> tuple[dict[str, FileOnDisk], list[FileOnDisk]]:
    (cachedir, name, folder_list) = param
    filesbypath: dict[str, FileOnDisk] = _read_dict_of_files(cachedir, name)
    files_by_path: dict[str, FileOnDisk] = {}
    filtered_files: list[FileOnDisk] = []
    srch = _FastSearchOverFolderListToCache(folder_list)
    for p, f in filesbypath.items():
        assert p == f.file_path
        # incl = self._folder_list.is_file_path_included(p)
        incl2 = srch.is_file_path_included(p)
        # raise_if_not(incl == incl2)
        if incl2:
            files_by_path[p] = f
        else:
            filtered_files.append(f)

    return files_by_path, filtered_files


def _scan_folder_task_func(
    param: tuple[FolderToCache, str], fromownload: tuple[tasks.SharedPubParam]
) -> tuple[FolderToCache, _FolderScanStats, _FolderScanDirOut]:
    (tocache, name) = param
    (pubfilesbypath,) = fromownload
    sdout = _FolderScanDirOut(tocache.folder)
    stats = _FolderScanStats()
    filesbypath = tasks.from_publication(pubfilesbypath)
    # debug('FolderCache._scan_folder_task_func({}): {} pubfilesbypath'.format(name, len(filesbypath)))
    started = time.perf_counter()
    lfilesbypath = len(filesbypath)
    FolderCache.scan_dir(
        started,
        sdout,
        stats,
        tocache,
        tocache.folder,
        filesbypath,
        pubfilesbypath,
        name,
    )
    debug(
        "FolderCache._scan_folder_task_func({}): requested_files/requested_dirs/scanned_files={}/{}/{}".format(
            name,
            len(sdout.requested_files),
            len(sdout.requested_dirs),
            len(sdout.scanned_files),
        )
    )
    assert len(filesbypath) == lfilesbypath
    return tocache, stats, sdout


def _calc_hash_task_func(
    param: tuple[str, float, int, list[ExtraHashFactory]]
) -> tuple[FileOnDisk, list[bytes]]:
    (fpath, tstamp, fsize, extrahashes) = param
    s, h, xtra = calculate_file_hash_ex(fpath, extrahashes)
    assert s == fsize
    return FileOnDisk(h, tstamp, fpath, fsize), xtra


def _save_files_task_func(
    param: tuple[
        str, str, dict[str, FileOnDisk], list[FileOnDisk], dict[str, dict[str, int]]
    ]
) -> None:
    (cachedir, name, filesbypath, filteredfiles, scan_stats) = param
    lfilesbypath = len(filesbypath)
    _write_dict_of_files(cachedir, name, filesbypath, filteredfiles)
    _write_all_scan_stats(cachedir, name, scan_stats)
    assert len(filesbypath) == lfilesbypath


class _ScanStatsNode:
    parent: "_ScanStatsNode|None"
    path: str
    own_nf: int
    children: list["_ScanStatsNode"]

    def __init__(self, parent: "_ScanStatsNode|None", path: str, nf: int) -> None:
        self.parent = parent
        self.path = path
        self.own_nf = nf
        self.children = []
        if parent is not None:
            parent.children.append(self)

    @staticmethod
    def _read_tree_from_stats(scan_stats: dict[str, int]) -> "_ScanStatsNode":
        rootstatnode: _ScanStatsNode | None = None
        curstatnode: _ScanStatsNode | None = None
        for fpath, nf in sorted(scan_stats.items()):
            assert is_normalized_dir_path(fpath)
            if curstatnode is None:
                assert rootstatnode is None
                rootstatnode = _ScanStatsNode(None, fpath, nf)
                curstatnode = rootstatnode
                continue

            assert rootstatnode is not None
            if fpath.startswith(curstatnode.path):
                curstatnode = _ScanStatsNode(curstatnode, fpath, nf)
            else:
                ok = False
                while curstatnode.parent is not None:
                    curstatnode = curstatnode.parent
                    if fpath.startswith(curstatnode.path):
                        curstatnode = _ScanStatsNode(curstatnode, fpath, nf)
                        ok = True
                        break  # while
                assert ok
        assert rootstatnode is not None
        return rootstatnode

    @staticmethod
    def _append_task(
        alltasks: list[tuple[FolderToCache, int]],
        path: str,
        nf: int,
        exdirs: list[str],
        extexdirs: list[str],
    ) -> None:
        assert len(FolderToCache.filter_ex_dirs(exdirs, path)) == len(exdirs)
        mergedexdirs = exdirs + FolderToCache.filter_ex_dirs(extexdirs, path)
        alltasks.append((FolderToCache(path, mergedexdirs), nf))

    def _is_filtered_out(self, exdirs: list[str]) -> bool:
        for exdir in exdirs:
            if self.path.startswith(exdir):
                return True
        return False

    @staticmethod
    def make_tree(scan_stats: dict[str, int] | None, rootfolder: str):
        if scan_stats is None:
            rootstatnode = _ScanStatsNode(None, rootfolder, 10000)  # a LOT
        else:
            rootstatnode = _ScanStatsNode._read_tree_from_stats(scan_stats)
            assert rootstatnode.path == rootfolder
        return rootstatnode

    def fill_tasks(
        self, alltasks: list[tuple[FolderToCache, int]], root: str, extexdirs: list[str]
    ) -> tuple[int, list[str]] | None:  # recursive
        nf = self.own_nf
        chex: list[list[str]] = []
        chexmerged: list[str] = []
        chnfs: list[int] = []
        for ch in self.children:
            chfil = ch.fill_tasks(alltasks, root, extexdirs)
            assert chfil is not None
            chnf, exdirs = chfil
            nf += chnf
            chnfs.append(chnf)
            chex.append(exdirs)
            chexmerged += exdirs
        if self.parent is None:
            _ScanStatsNode._append_task(alltasks, self.path, nf, chexmerged, extexdirs)
            return None
        if nf < _scan_task_nf_threshold_heuristics():
            return nf, chexmerged
        else:
            assert len(chex) == len(self.children)
            assert len(chnfs) == len(self.children)
            outexdirs: list[str] = []
            for i in range(len(self.children)):
                ch = self.children[i]
                _ScanStatsNode._append_task(
                    alltasks, ch.path, chnfs[i], chex[i], extexdirs
                )
                outexdirs.append(ch.path)
            return self.own_nf, outexdirs


class FolderCache:
    """
    Can handle multiple folders, each folder with its own set of exclusions
    As a result, can be used to handle ANY folder structure
      (re-including after inclusion can be represented by adding re-included folder to the root forest)
    """

    _cache_dir: str
    name: str
    _folder_list: FolderListToCache
    _files_by_path: dict[str, FileOnDisk] | None
    _files_by_hash: dict[bytes, list[FileOnDisk]] | None
    _filtered_files: list[FileOnDisk]
    _all_scan_stats: dict[str, dict[str, int]]  # rootfolder -> {fpath -> nfiles}
    _new_all_scan_stats: dict[str, dict[str, int]] | None
    _state: int  # bitmask: 0x1 - load completed, 0x2 - reconcile completed
    _extra_hash_factories: list[ExtraHashFactory]
    extra_hashes: dict[bytes, list[bytes]]

    def __init__(
        self,
        cachedir: str,
        name: str,
        folderlist: FolderListToCache,
        extrahashfactories: list[ExtraHashFactory] | None = None,
    ) -> None:
        assert not FolderCache._folder_list_self_overlaps(folderlist)
        self._cache_dir = cachedir
        self.name = name
        self._folder_list = folderlist
        self._files_by_path = None
        self._files_by_hash = None
        self._filtered_files = []
        self._all_scan_stats = _read_all_scan_stats(cachedir, name)
        self._new_all_scan_stats = {}
        self._state = 0
        self._extra_hash_factories = (
            extrahashfactories if extrahashfactories is not None else []
        )
        self.extra_hashes = {}

    def start_tasks(self, parallel: tasks.Parallel) -> None:
        return self._start_tasks(parallel)

    def ready_task_name(self) -> str:
        return self._reconcile_own_task_name()

    def all_files(self) -> Iterable[FileOnDisk]:
        assert (self._state & 0x3) == 0x3
        assert self._files_by_path is not None
        return self._files_by_path.values()

    def file_by_path(self, fpath: str) -> FileOnDisk | None:
        assert self._files_by_path is not None
        return self._files_by_path.get(fpath)

    def file_by_hash(self, h: bytes) -> list[FileOnDisk] | None:
        assert self._files_by_hash is not None
        return self._files_by_hash.get(h)

    # private functions

    @staticmethod
    def _two_folders_overlap(a: str, aex: list[str], b: str, bex: list[str]) -> bool:
        if a == b:
            return True
        ok = True
        if a.startswith(b):  # b contains a
            ok = False
            for x in bex:
                if a.startswith(x):
                    ok = True
                    break
        elif b.startswith(a):  # a contains b
            ok = False
            for x in aex:
                if b.startswith(x):
                    ok = True
                    break
        return not ok

    @staticmethod
    def _folder_list_self_overlaps(l: FolderListToCache) -> bool:
        for aidx in range(len(l)):
            for bidx in range(len(l)):
                if aidx == bidx:
                    continue
                if FolderCache._two_folders_overlap(
                    l[aidx].folder, l[aidx].exdirs, l[bidx].folder, l[bidx].exdirs
                ):
                    debug(
                        "FolderCache: {} overlaps {}".format(
                            l[aidx].folder, l[bidx].folder
                        )
                    )
                    return True
        return False

    @staticmethod
    def folder_lists_overlap(al: FolderListToCache, bl: FolderListToCache) -> bool:
        for a in al:
            for b in bl:
                if FolderCache._two_folders_overlap(
                    a.folder, a.exdirs, b.folder, b.exdirs
                ):
                    return True
        return False

    def _load_own_task_name(self) -> str:
        return "summon.foldercache." + self.name + ".ownload"

    def _start_tasks(self, parallel: tasks.Parallel) -> None:
        # building tree of known scans
        allscantasks: list[tuple[FolderToCache, int]] = []  # [(tocache,nf)]

        for i in range(len(self._folder_list)):
            folderplus = self._folder_list[i]
            # for folderplus in self._folder_list: - for whatever reason, causes out of range exception under VS Code
            scan_stats = self._all_scan_stats.get(folderplus.folder)
            rootstatnode = _ScanStatsNode.make_tree(scan_stats, folderplus.folder)
            tmptasks: list[tuple[FolderToCache, int]] = []
            rootstatnode.fill_tasks(tmptasks, folderplus.folder, folderplus.exdirs)
            # filtering
            newtmptasks: list[tuple[FolderToCache, int]] = []
            for t in tmptasks:
                (fp, nf) = t
                filtered: list[FolderToCache] = (
                    FolderCache._intersect_folder_with_folder(fp, folderplus)
                )
                newnf = int(nf / len(filtered))  # ugly guess
                newtmptasks += [(f, newnf) for f in filtered]
            allscantasks += newtmptasks

        # finding missing tasks
        for i in range(len(self._folder_list)):
            folderplus = self._folder_list[i]
            # for folderplus in self._folder_list: - for whatever reason, causes out of range exception under VS Code
            remainder = [folderplus]

            for t in allscantasks:
                remainder = FolderCache._subtract_folder_from_list(remainder, t[0])

            for r in remainder:
                allscantasks.append((r, 10000))

        if __debug__:
            for t in allscantasks:
                for tt in allscantasks:
                    if t != tt:
                        assert not FolderCache._two_folders_overlap(
                            t[0].folder, t[0].exdirs, tt[0].folder, tt[0].exdirs
                        )

        # ready to start tasks
        scannedfiles: dict[str, FileOnDisk] = {}
        stats = _FolderScanStats()

        loadtaskname = "summon.foldercache." + self.name + ".load"
        loadtask = tasks.Task(
            loadtaskname,
            _load_files_task_func,
            (self._cache_dir, self.name, self._folder_list),
            [],
        )
        parallel.add_task(loadtask)

        loadowntaskname = self._load_own_task_name()
        loadowntask = tasks.OwnTask(
            loadowntaskname,
            lambda _, out: self._load_files_own_task_func(out, parallel),
            None,
            [loadtaskname],
            datadeps=self._loadowntask_datadeps(),
        )
        parallel.add_task(loadowntask)

        for tt in allscantasks:
            (tocache, nf) = tt
            assert is_normalized_dir_path(tocache.folder)
            taskname = self._scanned_task_name(tocache.folder)
            task = tasks.Task(
                taskname,
                _scan_folder_task_func,
                (tocache, self.name),
                [loadowntaskname],
                _scan_task_time_estimate(nf),
            )
            owntaskname = self._scanned_own_task_name(tocache.folder)
            owntask = tasks.OwnTask(
                owntaskname,
                lambda _, out: self._scan_folder_own_task_func(
                    out, parallel, scannedfiles, stats
                ),
                None,
                [taskname],
            )

            parallel.add_tasks([task, owntask])

        scanningdeps = self._scanned_own_wildcard_task_name()
        hashingdeps = self._hashing_own_wildcard_task_name()
        reconciletask = tasks.OwnTask(
            self._reconcile_own_task_name(),
            lambda _, _1: self._own_reconcile_task_func(parallel, scannedfiles),
            None,
            [loadowntaskname] + [scanningdeps] + [hashingdeps],
            datadeps=self._ownreconciletask_datadeps(),
        )
        parallel.add_task(reconciletask)

    @staticmethod
    def _ex_subtract(bex: list[str], a: FolderToCache) -> list[FolderToCache]:
        for bx in bex:
            if a.folder.startswith(bx):  # bx contains a.folder
                return [a]
        return []

    @staticmethod
    def _subtract_folder_from_folder(
        a: FolderToCache, b: FolderToCache
    ) -> list[FolderToCache]:
        if a.folder.startswith(b.folder):
            if a.folder == b.folder:
                return FolderCache._ex_subtract(b.exdirs, a)
            else:  # b contains a
                # a.folder gets fully excluded
                # newex = a.exdirs + [b.folder]
                assert not FolderToCache.ok_to_construct(a.folder, [b.folder])
                #    return [FolderToCache(a.folder, newex)] + FolderCache._ex_subtract(b.exdirs, a)
                return FolderCache._ex_subtract(b.exdirs, a)
        elif b.folder.startswith(a.folder):  # a contains b
            # b gets excluded
            newex = a.exdirs + [b.folder]
            assert FolderToCache.ok_to_construct(a.folder, newex)
            return [FolderToCache(a.folder, newex)] + FolderCache._ex_subtract(
                b.exdirs, a
            )
        else:  # a and b are unrelated
            return [a]

    @staticmethod
    def _subtract_folder_from_list(
        remainder: list[FolderToCache], f: FolderToCache
    ) -> list[FolderToCache]:
        out: list[FolderToCache] = []
        for ff in remainder:
            diff = FolderCache._subtract_folder_from_folder(ff, f)
            out += diff
        return out

    @staticmethod
    def _intersect_folder_with_folder(
        a: FolderToCache, b: FolderToCache
    ) -> list[FolderToCache]:
        if a.folder.startswith(b.folder):
            if a.folder == b.folder:
                return [FolderToCache(a.folder, list(set(a.exdirs + b.exdirs)))]
            else:
                return [
                    FolderToCache(
                        a.folder,
                        FolderToCache.filter_ex_dirs(
                            list(set(a.exdirs + b.exdirs)), a.folder
                        ),
                    )
                ]
        elif b.folder.startswith(a.folder):
            return [
                FolderToCache(
                    b.folder,
                    FolderToCache.filter_ex_dirs(
                        list(set(a.exdirs + b.exdirs)), b.folder
                    ),
                )
            ]
        else:  # a and b are unrelated
            return []

    @staticmethod
    def scan_dir(
        started: float,
        sdout: _FolderScanDirOut,
        stats: _FolderScanStats,
        const_tocache: FolderToCache,
        dirpath: str,
        const_filesbypath: dict[str, FileOnDisk],
        pubfilesbypath: tasks.SharedPubParam,
        name: str,
    ) -> None:  # recursive over dir
        assert is_normalized_dir_path(dirpath)
        # recursive implementation: able to skip subtrees, but more calls (lots of os.listdir() instead of single os.walk())
        # still, after recent performance fix seems to win like 1.5x over os.walk-based one
        nf = 0
        for f in os.listdir(dirpath):
            fpath = dirpath + normalize_file_name(f)
            st = os.lstat(fpath)
            fmode = st.st_mode
            if stat.S_ISREG(fmode):
                assert not stat.S_ISLNK(fmode)
                assert is_normalized_file_path(fpath)

                assert const_tocache.is_file_path_included(fpath)

                stats.nscanned += 1
                nf += 1
                tstamp = _get_file_timestamp_from_st(st)
                found: FileOnDisk | None = const_filesbypath.get(fpath)
                matched = False
                if found is not None:
                    # debug('FolderCache: found {}'.format(fpath))
                    sdout.scanned_files[fpath] = found
                    assert found.file_hash is not None
                    tstamp2 = found.file_modified
                    if tstamp == tstamp2:
                        matched = True
                        if found.file_size != st.st_size:
                            warn(
                                "FolderCache: file size changed while timestamp did not for file {}, re-hashing it".format(
                                    fpath
                                )
                            )
                            matched = False
                else:
                    debug("FolderCache: not found {}".format(fpath))
                if not matched:
                    sdout.requested_files.append((fpath, tstamp, st.st_size))
            elif stat.S_ISDIR(fmode):
                newdir = fpath + "\\"
                assert is_normalized_dir_path(newdir)
                if newdir in const_tocache.exdirs:
                    continue
                elapsed = time.perf_counter() - started
                if _time_to_split_task(elapsed):  # an ad-hoc split
                    sdout.requested_dirs.append(newdir)
                else:
                    newtocache = FolderToCache(
                        const_tocache.folder,
                        FolderToCache.filter_ex_dirs(const_tocache.exdirs, newdir),
                    )
                    FolderCache.scan_dir(
                        started,
                        sdout,
                        stats,
                        newtocache,
                        newdir,
                        const_filesbypath,
                        pubfilesbypath,
                        name,
                    )
            else:
                critical(
                    "FolderCache: {} is neither dir or file, aborting".format(fpath)
                )
                raise_if_not(False)
        assert dirpath not in sdout.scan_stats
        sdout.scan_stats[dirpath] = nf

    # Task Names
    def _scanned_task_name(self, dirpath: str) -> str:
        assert is_normalized_dir_path(dirpath)
        return "summon.foldercache." + self.name + ".scan." + dirpath

    def _scanned_own_task_name(self, dirpath: str) -> str:
        assert is_normalized_dir_path(dirpath)
        return "summon.foldercache." + self.name + ".ownscan." + dirpath

    def _scanned_own_wildcard_task_name(self) -> str:
        return "summon.foldercache." + self.name + ".ownscan." + "*"

    def _reconcile_own_task_name(self) -> str:
        return "summon.foldercache." + self.name + ".reconcile"

    def _hashing_task_name(self, fpath: str) -> str:
        assert is_normalized_file_path(fpath)
        return "summon.foldercache." + self.name + ".hash." + fpath

    def _hashing_own_task_name(self, fpath: str) -> str:
        assert is_normalized_file_path(fpath)
        return "summon.foldercache." + self.name + ".ownhash." + fpath

    def _hashing_own_wildcard_task_name(self) -> str:
        return "summon.foldercache." + self.name + ".ownhash." + "*"

    def stats_of_interest(self) -> list[str]:
        return [
            "summon.foldercache." + self.name + ".scan.",
            "summon.foldercache." + self.name + ".ownscan.",
            "summon.foldercache." + self.name + ".hash.",
            "summon.foldercache." + self.name + ".ownhash.",
            "summon.foldercache." + self.name + ".reconcile",
            "summon.foldercache." + self.name + ".load",
            "summon.foldercache." + self.name + ".ownload",
            "summon.foldercache." + self.name + ".save",
            "summon.foldercache." + self.name,
        ]

    ### Own Task Funcs

    def _loadowntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            [],
            ["summon.foldercache." + self.name + ".reconciled()"],
            [
                "summon.foldercache." + self.name + "._files_by_path",
                "summon.foldercache." + self.name + "._filtered_files",
                "summon.foldercache." + self.name + ".pub_files_by_path",
            ],
        )

    def _load_files_own_task_func(
        self,
        out: tuple[dict[str, FileOnDisk], list[FileOnDisk]],
        parallel: tasks.Parallel,
    ) -> tuple[tasks.SharedPubParam]:
        assert (self._state & 0x1) == 0
        self._state |= 0x1
        debug("FolderCache.{}: started processing loading files".format(self.name))
        (filesbypath, filteredfiles) = out
        assert self._files_by_path is None
        assert self._filtered_files == []
        self._files_by_path = filesbypath
        assert self._files_by_hash is None
        self._files_by_hash = {}
        for f in filesbypath.values():
            if f.file_hash not in self._files_by_hash:
                self._files_by_hash[f.file_hash] = []
            self._files_by_hash[f.file_hash].append(f)
        self._filtered_files = filteredfiles

        debug(
            "FolderCache.{}: _load_files_own_task_func(): {} _files_by_path".format(
                self.name, len(self._files_by_path)
            )
        )

        debug(
            "FolderCache.{}: almost processed loading files, preparing SharedPublication".format(
                self.name
            )
        )
        self.pub_files_by_path = tasks.SharedPublication(parallel, self._files_by_path)
        pubparam = tasks.make_shared_publication_param(self.pub_files_by_path)
        debug("FolderCache.{}: done processing loading files".format(self.name))
        return (pubparam,)

    def _owncalchashtask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ["summon.foldercache." + self.name + "._files_by_path"],
            ["summon.foldercache." + self.name + ".reconciled()"],
            [],
        )

    def _own_calc_hash_task_func(
        self, out: tuple[FileOnDisk, list[bytes]], scannedfiles: dict[str, FileOnDisk]
    ) -> None:
        assert (self._state & 0x3) == 0x1
        assert self._files_by_path is not None
        (f, xtra) = out
        scannedfiles[f.file_path] = f
        self._files_by_path[f.file_path] = f
        debug(
            "FolderCache.{}: _own_calc_hash_task_func(): {} _files_by_path".format(
                self.name, len(self._files_by_path)
            )
        )
        assert len(xtra) == len(self._extra_hash_factories)
        if __debug__:
            if f.file_hash in self.extra_hashes:
                oldxtra = self.extra_hashes[f.file_hash]
                assert len(xtra) == len(oldxtra)
                for i in range(len(xtra)):
                    assert xtra[i] == oldxtra[i]
        self.extra_hashes[f.file_hash] = xtra

    def _ownreconciletask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ["summon.foldercache." + self.name + "._files_by_path"],
            [],
            [
                "summon.foldercache." + self.name + ".reconciled()",
                "summon.foldercache." + self.name + ".ready()",
            ],
        )

    def _own_reconcile_task_func(
        self, parallel: tasks.Parallel, scannedfiles: dict[str, FileOnDisk]
    ) -> None:
        assert (self._state & 0x3) == 0x1
        assert self._new_all_scan_stats is not None
        self._state |= 0x2
        assert self._files_by_path is not None

        info("FolderCache({}):{} files scanned".format(self.name, len(scannedfiles)))
        ndel = 0
        newfbypath: dict[str, FileOnDisk] = {}
        for file in self._files_by_path.values():
            fpath = file.file_path
            assert is_normalized_file_path(fpath)
            if scannedfiles.get(fpath) is None:
                # inhere = self._files_by_path.get(fpath)
                # if inhere is not None and inhere.file_hash is None:  # special record is already present
                #    continue
                info("FolderCache: {} was deleted".format(fpath))
                # self._files_by_path[fpath] = FileOnDisk(None, None, fpath, None)
                # not adding to newfbypath
                ndel += 1
            else:
                newfbypath[fpath] = file
        info("FolderCache reconcile: {} files were deleted".format(ndel))
        assert len(newfbypath) + ndel == len(self._files_by_path)
        self._files_by_path = newfbypath

        self._all_scan_stats = self._new_all_scan_stats
        self._new_all_scan_stats = None

        debug(
            "FolderCache.{}: _own_reconcile_task_func(): {} _files_by_path".format(
                self.name, len(self._files_by_path)
            )
        )

        savetaskname = "summon.foldercache." + self.name + ".save"
        savetask = tasks.Task(
            savetaskname,
            _save_files_task_func,
            (
                self._cache_dir,
                self.name,
                self._files_by_path,
                self._filtered_files,
                self._all_scan_stats,
            ),
            [],
        )
        parallel.add_task(
            savetask
        )  # we won't explicitly wait for savetask, it will be waited for in Parallel.__exit__

    def _ownscantask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            [], ["summon.foldercache." + self.name + ".reconciled()"], []
        )

    def _scan_folder_own_task_func(
        self,
        out: tuple[FolderToCache, _FolderScanStats, _FolderScanDirOut],
        parallel: tasks.Parallel,
        scannedfiles: dict[str, FileOnDisk],
        stats: _FolderScanStats,
    ) -> None:
        assert (self._state & 0x3) == 0x1
        assert self._new_all_scan_stats is not None
        (tocache, gotstats, sdout) = out
        stats.add(gotstats)
        assert len(scannedfiles.keys() & sdout.scanned_files.keys()) == 0
        scannedfiles |= sdout.scanned_files
        if sdout.root in self._new_all_scan_stats:
            assert (
                len(
                    self._new_all_scan_stats[sdout.root].keys()
                    & sdout.scan_stats.keys()
                )
                == 0
            )
            self._new_all_scan_stats[sdout.root] |= sdout.scan_stats
        else:
            self._new_all_scan_stats[sdout.root] = sdout.scan_stats

        assert self._files_by_path is not None
        debug(
            "FolderCache.{}: _scan_folder_own_task_func(): {} _files_by_path".format(
                self.name, len(self._files_by_path)
            )
        )

        # new hashing tasks
        for f in sdout.requested_files:
            (fpath, tstamp, fsize) = f
            # debug(fpath)  # RM
            htaskname = self._hashing_task_name(fpath)
            htask = tasks.Task(
                htaskname,
                _calc_hash_task_func,
                (fpath, tstamp, fsize, self._extra_hash_factories),
                [],
                _hashing_file_time_estimate(fsize),
            )
            howntaskname = self._hashing_own_task_name(fpath)
            howntask = tasks.OwnTask(
                howntaskname,
                lambda _, o: self._own_calc_hash_task_func(o, scannedfiles),
                None,
                [htaskname],
                0.001,
                datadeps=self._owncalchashtask_datadeps(),
            )  # expected to take negligible time
            parallel.add_tasks([htask, howntask])

        # new scanning tasks
        for dpath in sdout.requested_dirs:
            assert is_normalized_dir_path(dpath)
            taskname = self._scanned_task_name(dpath)
            task = tasks.Task(
                taskname,
                _scan_folder_task_func,
                (
                    FolderToCache(
                        dpath, FolderToCache.filter_ex_dirs(tocache.exdirs, dpath)
                    ),
                    self.name,
                ),
                [self._load_own_task_name()],
                1.0,
            )  # this is an ad-hoc split, we don't want tasks to cache w, and we have no idea
            owntaskname = self._scanned_own_task_name(dpath)
            owntask = tasks.OwnTask(
                owntaskname,
                lambda _, o: self._scan_folder_own_task_func(
                    o, parallel, scannedfiles, stats
                ),
                None,
                [taskname],
                0.01,
            )  # should not take too long
            parallel.add_tasks([task, owntask])


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        tfoldercache = FolderCache(
            normalize_dir_path("..\\..\\summon.cache\\"),
            "downloads",
            FolderListToCache(
                [FolderToCache(normalize_dir_path("..\\..\\..\\mo2\\downloads"), [])]
            ),
        )
        with tasks.Parallel(None) as tparallel:
            tfoldercache.start_tasks(tparallel)
            tparallel.run(
                []
            )  # all necessary tasks were already added in acache.start_tasks()

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
