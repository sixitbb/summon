# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
Home of class RootGitData
"""

from summonmm.gitdata.stable_json import (
    StableJsonJsonSomething,
    from_stable_json,
    to_stable_json,
    write_stable_json_opened,
)
import summonmm.tasks as tasks
from summonmm.cache.pickled_cache import pickled_cache
from summonmm.common import *
from summonmm.plugins.fileorigins import (
    FileOrigin,
    GitTentativeArchiveNames,
    file_origin_plugins,
    file_origin_plugin_by_name,
    FileOriginPluginBase,
)
from summonmm.gitdata.root_git_archives import KnownArchives
from summonmm.plugins.archives import (
    Archive,
    FileInArchive,
    normalize_archive_intra_path,
)
from summonmm.plugins.archives import (
    ArchivePluginBase,
    all_archive_plugins_extensions,
    archive_plugin_for,
)
from summonmm.plugins.arinstallers import (
    all_arinstaller_plugins,
    arinstaller_plugin_by_name,
    ExtraArchiveDataFactory,
    arinstaller_plugin_add_extra_data,
)
from summonmm.helpers.tmp_path import TmpPath

### RootGitData Helpers

_KNOWN_ARCHIVES_FNAME = "known-archives.json"
_KNOWN_TENTATIVE_ARCHIVE_NAMES_FNAME = "known-tentative-archive-names.json"


def _known_fo_plugin_fname(name: str) -> str:
    return "known-fileorigin-{}-data.json".format(name)


def _known_arinst_plugin_fname(name: str) -> str:
    return "known-arinstaller-{}-data.json".format(name)


"""
def _processing_archive_time_estimate(fsize: int):
    return float(fsize) / 1048576.0 / 10.0  # 10 MByte/s
"""


def _read_git_archives(params: tuple[str]) -> list[Archive]:
    (archivesgitfile,) = params
    assert is_normalized_file_path(archivesgitfile)
    with open_git_data_file_for_reading(archivesgitfile) as rf:
        data = json.load(rf)
        kar = KnownArchives()
        from_stable_json(kar, data)
        archives = kar.to_archives()
    return archives


def _read_cached_git_archives(
    rootgitdir: str, cachedir: str, cachedata: ConfigData
) -> tuple[list[Archive], ConfigData]:
    assert is_normalized_dir_path(rootgitdir)
    rootgitfile = rootgitdir + _KNOWN_ARCHIVES_FNAME
    return pickled_cache(
        cachedir,
        cachedata,
        "known-archives",
        [rootgitfile],
        _read_git_archives,
        (rootgitfile,),
    )


def _write_git_archives(rootgitdir: str, archives: list[Archive]) -> None:
    assert is_normalized_dir_path(rootgitdir)
    fpath = rootgitdir + _KNOWN_ARCHIVES_FNAME
    with open_git_data_file_for_writing(fpath) as wf:
        kar = KnownArchives()
        kar.from_archives(archives)
        data = to_stable_json(kar)
        write_stable_json_opened(wf, data)


def _hash_archive(
    archives: list[Archive],
    extradata: dict[str, dict[bytes, Any]],
    by: str,
    tmppath: str,  # recursive!
    plugin: ArchivePluginBase,
    archivepath: str,
    arhash: bytes,
    arsize: int,
    extrafactories: list[ExtraArchiveDataFactory],
) -> None:
    assert os.path.isdir(tmppath)
    plugin.extract_all(archivepath, tmppath)
    pluginexts = all_archive_plugins_extensions()  # for nested archives
    ar = Archive(arhash, arsize, by)
    archives.append(ar)
    for root, _, files in os.walk(tmppath):
        nf = 0
        for f in files:
            nf += 1
            fpath = os.path.join(root, f)
            s, h = calculate_file_hash(fpath)
            assert fpath.startswith(tmppath)
            ar.files.append(
                FileInArchive(
                    truncate_file_hash(h),
                    s,
                    normalize_archive_intra_path(fpath[len(tmppath) :]),
                )
            )

            ext = os.path.split(fpath)[1].lower()
            if ext in pluginexts:
                nested_plugin = archive_plugin_for(fpath)
                assert nested_plugin is not None
                newtmppath = TmpPath.tmp_in_tmp(
                    tmppath,
                    "T3lIzNDx.",  # tmp is not from root,
                    # so randomly-looking prefix is necessary
                    nf,
                )
                assert not os.path.isdir(newtmppath)
                os.makedirs(newtmppath)
                _hash_archive(
                    archives,
                    extradata,
                    by,
                    newtmppath,
                    nested_plugin,
                    fpath,
                    h,
                    s,
                    extrafactories,
                )
    for xf in extrafactories:
        if xf.name() not in extradata:
            extradata[xf.name()] = {}
        xfbyname = extradata[xf.name()]
        assert arhash not in xfbyname

        try:
            xd = xf.extra_data(tmppath)
            xfbyname[arhash] = xd
        except Exception as e:
            xfbyname[arhash] = e


def _read_git_tentative_names(params: tuple[str]) -> dict[bytes, list[str]]:
    (tafile,) = params
    assert is_normalized_file_path(tafile)
    with open_git_data_file_for_reading(tafile) as rf:
        data = json.load(rf)
        tanames = GitTentativeArchiveNames()
        from_stable_json(tanames, data)
        return tanames.to_plugin()


def _read_cached_git_tentative_names(
    rootgitdir: str, cachedir: str, cachedata: ConfigData
) -> tuple[dict[bytes, list[str]], ConfigData]:
    assert is_normalized_dir_path(rootgitdir)
    rootgitfile = rootgitdir + _KNOWN_TENTATIVE_ARCHIVE_NAMES_FNAME
    return pickled_cache(
        cachedir,
        cachedata,
        "known-tentative-archive-names",
        [rootgitfile],
        _read_git_tentative_names,
        (rootgitfile,),
    )


def _write_git_tentative_names(
    rootgitdir: str, tanames: dict[bytes, list[str]]
) -> None:
    assert is_normalized_dir_path(rootgitdir)
    fpath = rootgitdir + _KNOWN_TENTATIVE_ARCHIVE_NAMES_FNAME
    with open_git_data_file_for_writing(fpath) as wf:
        tan = GitTentativeArchiveNames()
        tan.from_plugin(tanames)
        data = to_stable_json(tan)
        write_stable_json_opened(wf, data)


# plugin data


def _read_some_plugin_data(
    params: tuple[str, str]
) -> tuple[str, StableJsonJsonSomething]:
    (name, rootgitfile) = params
    assert is_normalized_file_path(rootgitfile)
    with open_git_data_file_for_reading(rootgitfile) as rf:
        return name, json.load(rf)


def _read_some_cached_plugin_data(
    rootgitdir: str,
    name: str,
    fname: str,
    cachedir: str,
    cachedata: ConfigData,
) -> tuple[Any, ConfigData]:
    assert is_normalized_dir_path(rootgitdir)
    rootgitfile = rootgitdir + fname.lower()
    pickledprefix = os.path.splitext(fname)[0]
    return pickled_cache(
        cachedir,
        cachedata,
        pickledprefix,
        [rootgitfile],
        _read_some_plugin_data,
        (name, rootgitfile),
    )


def _write_some_plugin_data(
    rootgitdir: str,
    fname: str,
    wrdata: StableJsonJsonSomething,
) -> None:
    assert is_normalized_dir_path(rootgitdir)
    fpath = rootgitdir + fname.lower()
    assert is_normalized_file_path(fpath)
    with open_git_data_file_for_writing(fpath) as wf:
        write_stable_json_opened(wf, wrdata)


### RootGitData Tasks

type _ArFileList = list[tuple[Archive, FileInArchive]]


def _append_archive(
    archives_by_hash: dict[bytes, Archive],
    archived_files_by_hash: dict[bytes, _ArFileList],
    archived_files_by_name: dict[str, _ArFileList],
    ar: Archive,
) -> None:
    # warn(str(len(ar.files)))
    assert ar.archive_hash not in archives_by_hash
    archives_by_hash[ar.archive_hash] = ar
    for fi in ar.files:
        if fi.file_hash not in archived_files_by_hash:
            archived_files_by_hash[fi.file_hash] = []
        archived_files_by_hash[fi.file_hash].append((ar, fi))

        fname = os.path.split(fi.intra_path)[1]
        if fname not in archived_files_by_name:
            archived_files_by_name[fname] = []
        archived_files_by_name[fname].append((ar, fi))


def _load_archives_task_func(param: tuple[str, str, dict[str, Any]]) -> tuple[
    dict[bytes, Archive],
    dict[bytes, _ArFileList],
    dict[str, _ArFileList],
    dict[str, Any],
]:
    (rootgitdir, cachedir, cachedata) = param
    (archives, cacheoverrides) = _read_cached_git_archives(
        rootgitdir, cachedir, cachedata
    )
    archives_by_hash: dict[bytes, Archive] = {}
    archived_files_by_hash: dict[bytes, _ArFileList] = {}
    archived_files_by_name: dict[str, _ArFileList] = {}
    for ar in archives:
        _append_archive(
            archives_by_hash, archived_files_by_hash, archived_files_by_name, ar
        )
    return (
        archives_by_hash,
        archived_files_by_hash,
        archived_files_by_name,
        cacheoverrides,
    )


def _archive_hashing_task_func(
    param: tuple[str, str, bytes, int, str, list[ExtraArchiveDataFactory]]
) -> tuple[list[Archive], dict[str, dict[bytes, Any]]]:
    (by, arpath, arhash, arsize, tmppath, extrafactories) = param
    assert not os.path.isdir(tmppath)
    os.makedirs(tmppath)
    plugin = archive_plugin_for(arpath)
    assert plugin is not None
    archives: list[Archive] = []
    extradata: dict[str, dict[bytes, Any]] = {}
    _hash_archive(
        archives, extradata, by, tmppath, plugin, arpath, arhash, arsize, extrafactories
    )
    debug("RootGitData: about to remove temporary tree {}".format(tmppath))
    TmpPath.rm_tmp_tree(tmppath)
    return archives, extradata


"""
def _debug_assert_eq_list(saved_loaded: list[Any], sorted_data: list[Any]) -> None:
    assert len(saved_loaded) == len(sorted_data)
    for i in range(len(sorted_data)):
        olda: str = as_json(sorted_data[i])
        newa: str = as_json(saved_loaded[i])
        if olda != newa:
            warn(olda)
            warn(newa)
            warn(os.path.commonprefix([olda, newa]))
            assert False
"""


def _save_archives_task_func(param: tuple[str, list[Archive]]) -> None:
    (rootgitdir, archives) = param
    _write_git_archives(rootgitdir, archives)
    """
    if __debug__:
        saved_loaded = _read_git_archives((rootgitdir + _KNOWN_ARCHIVES_FNAME,))
        # warn(str(len(archives)))
        # warn(str(len(saved_loaded)))
        sorted_archives = sorted(
            [
                Archive(
                    ar.archive_hash,
                    ar.archive_size,
                    ar.by,
                    sorted([fi for fi in ar.files], key=lambda f: f.intra_path),
                )
                for ar in archives
            ],
            key=lambda a: a.archive_hash,
        )
        _debug_assert_eq_list(saved_loaded, sorted_archives)
    """


def _load_tentative_names_task_func(
    param: tuple[str, str, ConfigData]
) -> tuple[dict[bytes, list[str]], ConfigData]:
    (rootgitdir, cachedir, cachedata) = param
    (tanames, cacheoverrides) = _read_cached_git_tentative_names(
        rootgitdir, cachedir, cachedata
    )
    return tanames, cacheoverrides


def _save_tentative_names_task_func(param: tuple[str, dict[bytes, list[str]]]) -> None:
    (rootgitdir, tanames) = param
    # warn(repr(tanames))
    _write_git_tentative_names(rootgitdir, tanames)

    """
    if __debug__:
        saved_loaded = list(
            _read_git_tentative_names(
                (rootgitdir + _KNOWN_TENTATIVE_ARCHIVE_NAMES_FNAME,)
            ).items()
        )
        # warn(str(len(tanames)))
        # warn(str(len(saved_loaded)))
        sorted_tanames: list[tuple[bytes, list[str]]] = sorted(tanames.items())
        for i in range(len(sorted_tanames)):
            tan = sorted_tanames[i]
            sorted_tanames[i] = (tan[0], sorted(tan[1]))
        _debug_assert_eq_list(saved_loaded, sorted_tanames)
    """


def _load_some_plugin_data_task_func(
    param: tuple[str, str, str, str, ConfigData]
) -> tuple[Any, ConfigData]:
    (rootgitdir, name, fname, cachedir, cachedata) = param
    return _read_some_cached_plugin_data(rootgitdir, name, fname, cachedir, cachedata)


def _save_some_plugin_data_task_func(
    param: tuple[str, str, StableJsonJsonSomething],
) -> None:
    (rootgitdir, fname, wrdata) = param
    _write_some_plugin_data(rootgitdir, fname, wrdata)


### RootGitData itself


class RootGitData:
    """
    Contains constant data which is gathered by community and stored/shared via 'summon-xxx-root' project.
    In particular, what's-contained-in-known-archives, and known-archives-tentative-names is stored/shared.
    """

    _root_git_dir: str
    _cache_dir: str
    _tmp_dir: str
    _cache_data: ConfigData
    _archives_by_hash: dict[bytes, Archive] | None
    _archived_files_by_hash: (
        dict[bytes, list[tuple[Archive, FileInArchive]]] | None
    )  # all (ar,fi) pairs for given hash
    _archived_files_by_name: dict[str, list[tuple[Archive, FileInArchive]]] | None
    _tentative_archive_names: dict[bytes, list[str]] | None
    _nhashes_requested: (
        int  # number of hashes already requested; used to make name of tmp dir
    )
    _new_hashes_by: str | None
    _dirty_ar: bool
    _dirty_fo: bool
    _ar_is_ready: int  # 0 - not ready, 1 - partially ready, 2 - fully ready
    _fo_is_ready: int
    _n_ready_arinst_plugins: int  # counter

    _LOADAROWNTASKNAME = "summon.rootgit.ownloadar"
    _LOADFOOWNTASKNAME = "summon.rootgit.ownloadfo"

    def __init__(
        self,
        new_hashes_by: str | None,
        rootgitdir: str,
        cachedir: str,
        tmpdir: str,
        cache_data: ConfigData,
    ) -> None:
        self._new_hashes_by = new_hashes_by
        self._root_git_dir = rootgitdir
        self._cache_dir = cachedir
        self._tmp_dir = tmpdir
        self._cache_data = cache_data
        self._archives_by_hash = None
        self._archived_files_by_hash = None
        self._archived_files_by_name = None
        self._tentative_archive_names = None
        self._nhashes_requested = 0
        self._dirty_ar = False
        self._dirty_fo = False
        self._ar_is_ready = 0
        self._fo_is_ready = 0
        self._n_ready_arinst_plugins = False

    def start_tasks(self, parallel: tasks.Parallel) -> None:
        load2taskname = "summon.rootgit.loadtan"
        load2task = tasks.Task(
            load2taskname,
            _load_tentative_names_task_func,
            (self._root_git_dir, self._cache_dir, self._cache_data),
            [],
        )
        parallel.add_task(load2task)

        for plugin in file_origin_plugins():
            loadfotaskname = "summon.rootgit.loadfo." + plugin.name()
            loadfotask = tasks.Task(
                loadfotaskname,
                _load_some_plugin_data_task_func,
                (
                    self._root_git_dir,
                    plugin.name(),
                    _known_fo_plugin_fname(plugin.name()),
                    self._cache_dir,
                    self._cache_data,
                ),
                [],
            )
            parallel.add_task(loadfotask)

            loadfoowntaskname = "summon.rootgit.ownloadfo." + plugin.name()
            loadfoowntask = tasks.OwnTask(
                loadfoowntaskname,
                lambda _, out: self._load_own_fo_plugin_data_task_func(out),
                None,
                [loadfotaskname],
            )
            parallel.add_task(loadfoowntask)

        loadarinstowntasknamepattern = "summon.rootgit.loadarinst.*"
        for plugin in all_arinstaller_plugins():
            if plugin.extra_data_factory() is None:
                continue
            loadarinsttaskname = "summon.rootgit.loadarinst." + plugin.name()
            loadarinsttask = tasks.Task(
                loadarinsttaskname,
                _load_some_plugin_data_task_func,
                (
                    self._root_git_dir,
                    plugin.name(),
                    _known_arinst_plugin_fname(plugin.name()),
                    self._cache_dir,
                    self._cache_data,
                ),
                [],
            )
            parallel.add_task(loadarinsttask)

            loadarinstowntaskname = "summon.rootgit.ownloadarinst." + plugin.name()
            loadarinstowntask = tasks.OwnTask(
                loadarinstowntaskname,
                lambda _, out: self._load_own_arinst_plugin_data_task_func(out),
                None,
                [loadarinsttaskname],
            )
            parallel.add_task(loadarinstowntask)

        loadartaskname = "summon.rootgit.loadar"
        loadartask = tasks.Task(
            loadartaskname,
            _load_archives_task_func,
            (self._root_git_dir, self._cache_dir, self._cache_data),
            [],
        )
        parallel.add_task(loadartask)
        loadarowntaskname = RootGitData._LOADAROWNTASKNAME
        loadarowntask = tasks.OwnTask(
            loadarowntaskname,
            lambda _, out: self._load_archives_own_task_func(out),
            None,
            [loadartaskname, loadarinstowntasknamepattern],
            datadeps=self._loadar_owntask_datadeps(),
        )
        parallel.add_task(loadarowntask)

        load2owntaskname = RootGitData._LOADFOOWNTASKNAME
        load2owntask = tasks.OwnTask(
            load2owntaskname,
            lambda _, out: self._load_tentative_names_own_task_func(out),
            None,
            [load2taskname, "summon.rootgit.ownloadfo.*"],
            datadeps=self._loadtan_owntask_datadeps(),
        )
        parallel.add_task(load2owntask)

    @staticmethod
    def ready_to_start_hashing_task_name() -> str:
        return RootGitData._LOADAROWNTASKNAME

    @staticmethod
    def archives_ready_task_name() -> str:
        return RootGitData._LOADAROWNTASKNAME

    @staticmethod
    def ready_to_start_adding_file_origins_task_name() -> str:
        return RootGitData._LOADFOOWNTASKNAME

    def start_hashing_archive(
        self, parallel: tasks.Parallel, arpath: str, arhash: bytes, arsize: int
    ) -> None:
        assert self._ar_is_ready == 1 and self._n_ready_arinst_plugins == sum(
            1 if plg.extra_data_factory() else 0 for plg in all_arinstaller_plugins()
        )
        hashingtaskname = "summon.rootgit.hash." + arpath
        self._nhashes_requested += 1
        tmp_dir = TmpPath.tmp_in_tmp(self._tmp_dir, "ah.", self._nhashes_requested)
        extrafactories0 = [
            plugin.extra_data_factory() for plugin in all_arinstaller_plugins()
        ]
        extrafactories = [xf for xf in extrafactories0 if xf is not None]
        hashingtask = tasks.Task(
            hashingtaskname,
            _archive_hashing_task_func,
            (self._new_hashes_by, arpath, arhash, arsize, tmp_dir, extrafactories),
            [],
        )
        parallel.add_task(hashingtask)
        hashingowntaskname = "summon.rootgit.ownhash." + arpath
        hashingowntask = tasks.OwnTask(
            hashingowntaskname,
            lambda _, out: self._archive_hashing_own_task_func(out),
            None,
            [hashingtaskname],
            datadeps=self._arhashing_owntask_datadeps(),
        )
        parallel.add_task(hashingowntask)

    def add_file_origin(self, h: bytes, fo: FileOrigin) -> None:
        assert self._fo_is_ready == 1
        for plugin in file_origin_plugins():
            if plugin.add_file_origin(h, fo):
                self._dirty_fo = True

    def add_hash_mappings(
        self, h: bytes, plugins: list[FileOriginPluginBase], hashes: list[bytes]
    ) -> None:
        assert len(plugins) == len(hashes)
        assert self._fo_is_ready == 1
        for i in range(len(plugins)):
            if plugins[i].add_hash_mapping(h, hashes[i]):
                self._dirty_fo = True

    def add_tentative_name(self, h: bytes, tentativename: str) -> None:
        tentativename = tentativename.lower()
        assert self._fo_is_ready == 1
        assert self._tentative_archive_names is not None
        if h in self._tentative_archive_names:
            for tn in self._tentative_archive_names[h]:
                if tn == tentativename:
                    return
            self._tentative_archive_names[h].append(tentativename)
            self._dirty_fo = True
        else:
            self._tentative_archive_names[h] = [tentativename]
            self._dirty_fo = True

    def start_done_hashing_task(
        self,  # should be called only after all start_hashing_archive() calls are done
        parallel: tasks.Parallel,
    ) -> str:
        assert self._ar_is_ready == 1
        donehashingowntaskname = "summon.rootgit.donehashing"
        donehashingowntask = tasks.OwnTask(
            donehashingowntaskname,
            lambda _, _1: self._done_hashing_own_task_func(parallel),
            None,
            [RootGitData._LOADAROWNTASKNAME, "summon.rootgit.ownhash.*"],
            datadeps=self._done_hashing_owntask_datadeps(),
        )
        parallel.add_task(donehashingowntask)

        return donehashingowntaskname

    def start_done_adding_file_origins_task(
        self,  # should be called only after all add_file_origin() calls are done
        parallel: tasks.Parallel,
    ) -> None:
        assert self._fo_is_ready == 1
        self._fo_is_ready = 2
        if self._dirty_fo:
            save2taskname = "summon.rootgit.savetan"
            save2task = tasks.Task(
                save2taskname,
                _save_tentative_names_task_func,
                (self._root_git_dir, self._tentative_archive_names),
                [],
            )
            parallel.add_task(save2task)

            for plugin in file_origin_plugins():
                savefotaskname = "summon.rootgit.savefo." + plugin.name()
                savefotask = tasks.Task(
                    savefotaskname,
                    _save_some_plugin_data_task_func,
                    (
                        self._root_git_dir,
                        _known_fo_plugin_fname(plugin.name()),
                        plugin.data_for_save_json(),
                    ),
                    [],
                )
                parallel.add_task(savefotask)

    def archived_file_by_hash(
        self, h: bytes
    ) -> list[tuple[Archive, FileInArchive]] | None:
        assert self._ar_is_ready == 2
        assert self._archived_files_by_hash is not None
        return self._archived_files_by_hash.get(truncate_file_hash(h))

    def archive_by_hash(self, arh: bytes, partialok: bool = False) -> Archive | None:
        assert (self._ar_is_ready >= 1) if partialok else (self._ar_is_ready >= 2)
        assert self._archives_by_hash is not None
        return self._archives_by_hash.get(arh)

    def tentative_names_for_archive(self, h: bytes) -> list[str]:
        assert self._tentative_archive_names is not None
        return self._tentative_archive_names.get(h, [])

    def archive_stats(self) -> dict[bytes, tuple[int, int]]:  # hash -> (n,total_size)
        assert self._ar_is_ready == 2
        assert self._archives_by_hash is not None
        out: dict[bytes, tuple[int, int]] = {}
        for arh, ar in self._archives_by_hash.items():
            assert ar.archive_hash == arh
            assert arh not in out
            out[arh] = (0, 0)
        assert self._archived_files_by_hash is not None
        for arfilist in self._archived_files_by_hash.values():
            for ar, fina in arfilist:
                assert ar.archive_hash in out
                out[ar.archive_hash] = (
                    out[ar.archive_hash][0] + 1,
                    out[ar.archive_hash][1] + fina.file_size,
                )
        for stats in out.values():
            assert stats[0] != 0

        return out

    def stats_of_interest(self) -> list[str]:
        return [
            "summon.rootgit.savear",
            "summon.rootgit.loadar",
            "summon.rootgit.loadtan",
            "summon.rootgit.savetan",
            "summon.rootgit.ownloadar",
            "summon.rootgit.ownloadfo",
            "summon.rootgit.hash.",
            "summon.rootgit.ownhash." "summon.rootgit.donehashing",
            "summon.rootgit.",
        ]

    ### private functions
    # own tasks with helpers

    def _loadar_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            [],
            ["summon.rootgit.done_hashing()"],
            [
                "summon.rootgit._archives_by_hash",
                "summon.rootgit._archived_files_by_hash",
                "summon.rootgit._archived_files_by_name",
            ],
        )

    def _load_archives_own_task_func(
        self,
        out: tuple[
            dict[bytes, Archive],
            dict[bytes, _ArFileList],
            dict[str, _ArFileList],
            dict[str, Any],
        ],
    ) -> None:
        (
            archives_by_hash,
            archived_files_by_hash,
            archived_files_by_name,
            cacheoverrides,
        ) = out
        assert self._archives_by_hash is None
        assert self._archived_files_by_hash is None
        self._archives_by_hash = archives_by_hash
        self._archived_files_by_hash = archived_files_by_hash
        self._archived_files_by_name = archived_files_by_name
        self._cache_data |= cacheoverrides
        assert self._ar_is_ready == 0
        self._ar_is_ready = 1

    def _arhashing_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            [
                "summon.rootgit._archives_by_hash",
                "summon.rootgit._archived_files_by_hash",
                "summon.rootgit._archived_files_by_name",
            ],
            ["summon.rootgit.done_hashing()"],
            [],
        )

    def _archive_hashing_own_task_func(
        self, out: tuple[list[Archive], dict[str, dict[bytes, Any]]]
    ):
        assert self._ar_is_ready == 1
        assert self._archives_by_hash is not None
        assert self._archived_files_by_hash is not None
        assert self._archived_files_by_name is not None
        (archives, extradata) = out
        for ar in archives:
            _append_archive(
                self._archives_by_hash,
                self._archived_files_by_hash,
                self._archived_files_by_name,
                ar,
            )
        for pluginname, data0 in extradata.items():
            for arh, data in data0.items():
                arinstaller_plugin_add_extra_data(pluginname, arh, data)
        self._dirty_ar = True

    def _done_hashing_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            [
                "summon.rootgit._archives_by_hash",
                "summon.rootgit._archived_files_by_hash",
                "summon.rootgit._archived_files_by_name",
            ],
            [],
            ["summon.rootgit.done_hashing()"],
        )

    def _done_hashing_own_task_func(self, parallel: tasks.Parallel) -> None:
        assert self._ar_is_ready == 1
        self._ar_is_ready = 2
        assert self._archives_by_hash is not None
        if self._dirty_ar:
            savetaskname = "summon.rootgit.savear"
            savetask = tasks.Task(
                savetaskname,
                _save_archives_task_func,
                (self._root_git_dir, list(self._archives_by_hash.values())),
                [],
            )
            parallel.add_task(savetask)

            for plugin in all_arinstaller_plugins():
                if plugin.extra_data_factory() is None:
                    continue
                savearinsttaskname = "summon.rootgit.savearinst." + plugin.name()
                savearinsttask = tasks.Task(
                    savearinsttaskname,
                    _save_some_plugin_data_task_func,
                    (
                        self._root_git_dir,
                        _known_arinst_plugin_fname(plugin.name()),
                        plugin.data_for_save_json(),
                    ),
                    [],
                )
                parallel.add_task(savearinsttask)

    def _loadtan_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            [], [], ["summon.rootgit._tentative_archive_names"]
        )

    def _load_tentative_names_own_task_func(
        self, out: tuple[dict[bytes, list[str]], ConfigData]
    ) -> None:
        assert self._fo_is_ready == 0
        self._fo_is_ready = 1
        (tanames, cacheoverrides) = out
        assert self._tentative_archive_names is None
        self._tentative_archive_names = tanames
        self._cache_data |= cacheoverrides

    def _load_own_fo_plugin_data_task_func(
        self, out: tuple[tuple[str, StableJsonJsonSomething], ConfigData]
    ) -> None:
        assert self._fo_is_ready == 0
        (loadret, cacheoverrides) = out
        (name, plugindata) = loadret
        plugin = file_origin_plugin_by_name(name)
        plugin.init_from_load_json_data(plugindata)
        self._cache_data |= cacheoverrides

    def _load_own_arinst_plugin_data_task_func(
        self, out: tuple[tuple[str, StableJsonJsonSomething], ConfigData]
    ) -> None:
        self._n_ready_arinst_plugins += 1
        (loadret, cacheoverrides) = out
        (name, plugindata) = loadret
        plugin = arinstaller_plugin_by_name(name)
        plugin.init_from_load_json_data(plugindata)
        self._cache_data |= cacheoverrides


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
