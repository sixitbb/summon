# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import logging
import re
import traceback

from summonmm.cache.available_files import AvailableFiles
from summonmm.cache.folder_cache import FolderCache
from summonmm.cache.omni_cache import OmniCache
from summonmm.common import *
from summonmm.gitdata.project_json import (
    ProjectJson,
    ProjectMod,
    ProjectInstaller,
    ProjectExtraArchive,
    ProjectExtraArchiveFile,
    ProjectModTool,
    ProjectModPatch,
)
from summonmm.gitdata.stable_json import to_stable_json, write_stable_json
from summonmm.plugins.archives import Archive, FileInArchive, archive_plugin_for
from summonmm.plugins.arinstallers import (
    ArInstaller,
    ArInstallerDetails,
    all_arinstaller_plugins,
)
from summonmm.helpers.file_retriever import (
    FileRetriever,
    ArchiveFileRetriever,
    GithubFileRetriever,
    ZeroFileRetriever,
)
from summonmm.plugins.globaltools import (
    GlobalToolPluginBase,
    all_global_tool_plugins,
    CouldBeProducedByGlobalTool,
)
from summonmm.plugins.modtools import (
    all_mod_tool_plugins,
    ModToolGuessParam,
    ModToolGuessDiff,
)
from summonmm.plugins.patches import patch_plugins_for
from summonmm.helpers.project_config import LocalProjectConfig
from summonmm.helpers.tmp_path import TmpPath


def _log_stats(stats: dict[str, int], level: int, title: str, max_lines: int) -> None:
    log_with_level(level, title)
    total = 0
    i = 0
    maxreached = False
    for zext, zn in sorted(stats.items(), key=lambda x: -x[1]):
        if i >= max_lines:
            maxreached = True
            break
        i += 1
        log_with_level(level, "-> {} -> {}".format(zext, zn))
        total += zn
    if maxreached:
        log_with_level(level, "-> ...")
    log_with_level(level, "-> TOTAL: {}".format(total))


class _ExtStats:
    stats: dict[str, int]

    def __init__(self):
        self.stats = {}

    def add(self, fpath: str) -> None:
        ext = os.path.splitext(fpath)[1]
        if len(ext) > 6:
            ext = ".LONGER"
        if ext not in self.stats:
            self.stats[ext] = 1
        else:
            self.stats[ext] += 1

    def log_me(self, title: str, level: int) -> None:
        _log_stats(self.stats, level, title, max_lines=1000)


class _PerModStats:
    stats: dict[str, int]

    def __init__(self):
        self.stats = {}

    def add(self, modname: str, n: int) -> None:
        if n == 0:
            return
        if modname not in self.stats:
            self.stats[modname] = n
        else:
            self.stats[modname] += n

    def log_me(self, title: str, level: int, max_lines: int = 1000) -> None:
        _log_stats(self.stats, level, title, max_lines)


class _IgnoredTargetFiles:
    ignored_file_patterns: list[re.Pattern[str]]

    def __init__(self, cfg: LocalProjectConfig) -> None:
        self.ignored_file_patterns = [
            re.compile(p) for p in cfg.root_modpack_config().ignored_file_patterns
        ]

    def ignored(self, fpath: str) -> bool:
        for p in self.ignored_file_patterns:
            if p.match(fpath):
                return True
        return False


class _ModInProgress:
    name: str
    # all *_files members use intramod as 1st parameter
    unknown_files: set[str]
    zero_files: set[str]
    github_files: dict[str, list[GithubFileRetriever]]
    archive_files: dict[str, list[ArchiveFileRetriever]]

    # files: dict[str, list[FileRetriever]]  # intramod -> list of retrievers
    known_archives: dict[bytes, tuple[Archive, int]]
    required_archives: dict[bytes, tuple[Archive, int]] | None
    install_from: list[tuple[ArInstaller, ArInstallerDetails]] | None
    remaining_after_install_from: dict[str, list[ArchiveFileRetriever]] | None
    unknown_files_could_be_produced_by_tools: (
        dict[str, tuple[str, CouldBeProducedByGlobalTool]] | None
    )
    mod_tools: list[tuple[str, Any]]
    patched: dict[str, tuple[str, Any]]

    def __init__(self, name: str) -> None:
        self.name = name
        # self.files = {}
        self.unknown_files = set()
        self.zero_files = set()
        self.github_files = {}
        self.archive_files = {}

        self.known_archives = {}
        self.required_archives = None

        self.install_from = None
        # self.install_from_root = None
        self.remaining_after_install_from = None
        # self.modified_from_install = None
        # self.skip_from_install = None
        self.unknown_files_could_be_produced_by_tools = None

        self.mod_tools = []
        self.patched = {}

    def add_file(
        self, available: AvailableFiles, intramod: str, retrievers: list[FileRetriever]
    ) -> None:
        assert intramod not in self.unknown_files
        assert intramod not in self.zero_files
        assert intramod not in self.github_files
        assert intramod not in self.archive_files

        if len(retrievers) == 0:
            self.unknown_files.add(intramod)
        else:
            r0 = retrievers[0]
            if isinstance(r0, ZeroFileRetriever):
                assert len(retrievers) == 1
                self.zero_files.add(intramod)
            elif isinstance(r0, GithubFileRetriever):
                if __debug__:
                    for r in retrievers:
                        assert r.file_hash == r0.file_hash
                        assert isinstance(r, GithubFileRetriever)
                self.github_files[intramod] = coerce_list(
                    retrievers, GithubFileRetriever
                )
            else:
                assert isinstance(r0, ArchiveFileRetriever)
                for r in retrievers:
                    assert r.file_hash == r0.file_hash
                    assert isinstance(r, ArchiveFileRetriever)
                    arh = r.archive_hash()
                    if arh not in self.known_archives:
                        ar = available.archive_by_hash(arh)
                        assert ar is not None
                        self.known_archives[arh] = (ar, 1)
                    self.known_archives[arh] = (
                        self.known_archives[arh][0],
                        self.known_archives[arh][1] + 1,
                    )
                self.archive_files[intramod] = coerce_list(
                    retrievers, ArchiveFileRetriever
                )

    def total_files(self) -> int:
        return (
            len(self.unknown_files)
            + len(self.zero_files)
            + len(self.github_files)
            + len(self.archive_files)
        )

    def modified_since_install(self) -> Iterable[str]:
        out: list[str] = []
        assert self.install_from is not None
        for _, arext in self.install_from:
            out += arext.modified_since_install
        return out

    def collect_extension_stats(
        self,
        unknownstats: _ExtStats,
        archivestats: _ExtStats,
        modifiedsincestats: _ExtStats,
    ) -> None:
        assert self.install_from is not None
        for infr in self.install_from:
            aic: ArInstallerDetails = infr[1]
            for f in aic.files:
                archivestats.add(f)
            for msi in aic.modified_since_install:
                modifiedsincestats.add(msi)
        for uf in self.unknown_files:
            unknownstats.add(uf)

    def collect_mod_stats(
        self,
        unknownstats: _PerModStats,
        archivestats: _PerModStats,
        modifiedsincestats: _PerModStats,
    ) -> None:
        assert self.install_from is not None
        for infr in self.install_from:
            aic: ArInstallerDetails = infr[1]
            archivestats.add(self.name, len(aic.files))
            modifiedsincestats.add(self.name, len(aic.modified_since_install))
        unknownstats.add(self.name, len(self.unknown_files))

    def _process_aic_clearing_remaining_after(
        self, cfg: LocalProjectConfig, srccache: FolderCache, aic: ArInstallerDetails
    ):
        assert self.remaining_after_install_from is not None
        for f in aic.files:
            mf = ModFile(self.name, f)
            if __debug__:
                src = cfg.modfile_to_source_vfs(mf)
                srcfile = srccache.file_by_path(src)
                assert srcfile is not None
                if aic.files[f].file_hash != truncate_file_hash(srcfile.file_hash):
                    pass
            if (
                f in self.remaining_after_install_from
            ):  # might have already been deleted if identical file is present in multiple archives
                del self.remaining_after_install_from[f]

    def _inter_dependency(
        self,
        cfg: LocalProjectConfig,
        srccache: FolderCache,
        ar0: tuple[ArInstaller, ArInstallerDetails],
        ar1: tuple[ArInstaller, ArInstallerDetails],
    ) -> tuple[int, int]:
        aoverb = 0
        bovera = 0
        files0: dict[str, FileInArchive] = ar0[1].files
        files1: dict[str, FileInArchive] = ar1[1].files
        commonfiles: set[str] = set(files0).intersection(set(files1))
        for cf in commonfiles:
            if files0[cf].file_hash == files1[cf].file_hash:
                continue
            mf = ModFile(self.name, cf)
            src = cfg.modfile_to_source_vfs(mf)
            srcfile = srccache.file_by_path(src)
            assert srcfile is not None
            if files0[cf].file_hash == truncate_file_hash(srcfile.file_hash):
                aoverb += 1
            elif files1[cf].file_hash == truncate_file_hash(srcfile.file_hash):
                bovera += 1
        return aoverb, bovera

    def resolve_unique(
        self, cfg: LocalProjectConfig, itf: _IgnoredTargetFiles, srccache: FolderCache
    ) -> None:
        assert self.required_archives is None
        assert self.install_from is None
        assert self.remaining_after_install_from is None
        assert self.unknown_files_could_be_produced_by_tools is None
        self.required_archives = {}

        for rlist in self.archive_files.values():
            assert len(rlist) > 0
            if len(rlist) == 1:
                r0: ArchiveFileRetriever = rlist[0]
                arh = r0.archive_hash()
                assert arh in self.known_archives
                self.required_archives[arh] = self.known_archives[arh]

        self.install_from = []
        for rav in self.required_archives.values():
            ra: Archive = rav[0]
            for plugin in all_arinstaller_plugins():
                guess = plugin.guess_arinstaller_from_vfs(
                    ra, self.name, self.archive_files
                )
                if guess is not None:
                    # if isinstance(guess, SimpleArInstaller) and guess.install_from_root != '':
                    #    pass
                    aic = ArInstallerDetails()
                    self.install_from.append((guess, aic))
                    for f, fia in guess.all_desired_files():
                        mf = ModFile(self.name, f)
                        target = cfg.modfile_to_target_vfs(mf)
                        if itf.ignored(target):
                            aic.ignored.add(f)
                        elif not f in self.archive_files:
                            src = cfg.modfile_to_source_vfs(mf)
                            srcfile = srccache.file_by_path(src)
                            if srcfile is None:
                                assert f not in aic.skip
                                aic.skip.add(f)
                            else:
                                if fia.file_hash == truncate_file_hash(
                                    srcfile.file_hash
                                ):
                                    assert fia.file_hash == truncate_file_hash(
                                        ZeroFileRetriever.ZEROHASH
                                    )
                                    # we prefer intra-archive zero-length file
                                    assert f in self.zero_files
                                    self.zero_files.remove(f)
                                else:
                                    assert f not in aic.skip
                                    aic.skip.add(f)
                                    assert f not in aic.modified_since_install
                                    aic.modified_since_install[f] = fia
                        else:
                            src = cfg.modfile_to_source_vfs(mf)
                            srcfile = srccache.file_by_path(src)
                            assert srcfile is not None
                            if fia.file_hash == truncate_file_hash(srcfile.file_hash):
                                assert f not in aic.files
                                aic.files[f] = fia
                            else:
                                assert f not in aic.skip
                                aic.skip.add(f)
                                assert f not in aic.modified_since_install
                                aic.modified_since_install[f] = fia
                    break

        assert self.remaining_after_install_from is None
        self.remaining_after_install_from = self.archive_files.copy()
        if len(self.install_from) == 1:
            ar0: tuple[ArInstaller, ArInstallerDetails] = self.install_from[0]
            _, aic = ar0
            self._process_aic_clearing_remaining_after(cfg, srccache, aic)
        elif len(self.install_from) > 1:
            dependencies: set[tuple[int, int]] = set()
            for i in range(len(self.install_from)):
                for j in range(i + 1, len(self.install_from)):
                    assert j != i
                    ioverj, joveri = self._inter_dependency(
                        cfg, srccache, self.install_from[i], self.install_from[j]
                    )
                    if ioverj:
                        dependencies.add((i, j))
                    if joveri:
                        dependencies.add((j, i))

            ordered: list[int] = []
            while len(ordered) < len(self.install_from):
                # looking for non-dependent one
                roundok = False
                for i in range(len(self.install_from)):
                    if i in ordered:
                        continue
                    iok = True
                    for j in range(len(self.install_from)):
                        if j not in ordered and (i, j) in dependencies:
                            iok = False
                            break  # for j
                    if iok:
                        ordered.append(i)
                        roundok = True
                        break  # for i
                raise_if_not(roundok)  # circular dependency, TODO: handle it

            assert len(ordered) == len(self.install_from)
            assert len(ordered) == len(set(ordered))
            newsif = [self.install_from[i] for i in ordered]
            assert len(newsif) == len(self.install_from)
            self.install_from = newsif

            for _, arx in self.install_from:
                self._process_aic_clearing_remaining_after(cfg, srccache, arx)

        if __debug__:
            fromarch: set[str] = set(self.remaining_after_install_from.keys())
            for _, arinstx0 in self.install_from:
                arinstx: ArInstallerDetails = arinstx0

                for f in arinstx.files:
                    if f not in arinstx.modified_since_install:
                        fromarch.add(f)

            if __debug__ and len(fromarch) != len(self.archive_files):
                assert False
            assert len(fromarch.intersection(self.archive_files)) == len(fromarch)

    def _num_skips(self) -> int:
        out = 0
        assert self.install_from is not None
        for _, arext in self.install_from:
            out += len(arext.skip)
        return out

    def is_fully_github(self) -> bool:
        return len(self.archive_files) == 0

    def is_cleanly_installed(self) -> bool:
        assert self.remaining_after_install_from is not None
        return (
            len(self.unknown_files) == 0
            and len(self.remaining_after_install_from) == 0
            and self._num_skips() == 0
        )

    def is_healable_to_clean_install(self) -> bool:
        assert self.unknown_files_could_be_produced_by_tools is not None
        assert self.remaining_after_install_from is not None
        assert len(self.unknown_files_could_be_produced_by_tools) <= self._num_skips()
        if (
            len(self.remaining_after_install_from) != 0
            or len(self.unknown_files_could_be_produced_by_tools) != self._num_skips()
        ):
            return False
        for f in self.unknown_files:
            if f not in self.unknown_files_could_be_produced_by_tools:
                return False
        return True


class _ModsInProgress:
    _cfg: LocalProjectConfig
    _available: AvailableFiles
    mods: dict[str, _ModInProgress]
    _all_retrievers: dict[bytes, list[FileRetriever]]

    def __init__(self, cfg: LocalProjectConfig, available: AvailableFiles) -> None:
        self.mods = {}
        self._cfg = cfg
        self._available = available
        self._all_retrievers = {}

    def has_retrievers_for(self, h: bytes) -> bool:
        return h in self._all_retrievers

    def add_new_file(self, mf: ModFile, retrievers: list[FileRetriever]) -> None:
        assert mf.mod is not None
        if len(retrievers) > 0:
            h0 = retrievers[0].file_hash
            assert not self.has_retrievers_for(h0)
            if __debug__:
                for r in retrievers:
                    assert r.file_hash == h0

            if h0 not in self._all_retrievers:
                self._all_retrievers[h0] = retrievers

        if mf.mod not in self.mods:
            self.mods[mf.mod] = _ModInProgress(mf.mod)
        self.mods[mf.mod].add_file(self._available, mf.intramod, retrievers)

    def add_dup_file(self, mf: ModFile, h: bytes) -> None:
        assert mf.mod is not None
        assert self.has_retrievers_for(h)
        if mf.mod not in self.mods:
            self.mods[mf.mod] = _ModInProgress(mf.mod)
        self.mods[mf.mod].add_file(
            self._available, mf.intramod, self._all_retrievers[h]
        )

    def all_retrievers(self) -> Iterable[tuple[bytes, list[FileRetriever]]]:
        return self._all_retrievers.items()

    def resolve_unique(self, srccache: FolderCache) -> None:
        itf = _IgnoredTargetFiles(self._cfg)
        for mod in self.mods:
            self.mods[mod].resolve_unique(self._cfg, itf, srccache)


class _ToolFinder:
    tools_by_ext: dict[str, list[tuple[GlobalToolPluginBase, Any]]]

    def __init__(self, cfg: LocalProjectConfig, resolvedvfs: ResolvedVFS) -> None:
        self.tools_by_ext = {}
        gameu = cfg.root_modpack_config().game_universe
        assert gameu is not None
        for plugin in all_global_tool_plugins(gameu):
            info("Preparing context for {} tool...".format(plugin.name()))
            pluginex = (plugin, plugin.create_context(cfg, resolvedvfs))
            exts = plugin.extensions()
            assert len(exts) > 0
            for ext in exts:
                if ext not in self.tools_by_ext:
                    self.tools_by_ext[ext] = []
                self.tools_by_ext[ext].append(pluginex)

    def could_be_produced(
        self, srcfile: str, targetpath: str
    ) -> tuple[CouldBeProducedByGlobalTool, str | None]:
        ext = os.path.splitext(srcfile)[1]
        assert ext == os.path.splitext(targetpath)[1]
        if ext in self.tools_by_ext:
            plugins = self.tools_by_ext[ext]
            besttool = None
            maxcbp = CouldBeProducedByGlobalTool.NotFound
            for plugin, ctx in plugins:
                cbp = plugin.could_be_produced(ctx, srcfile, targetpath)
                if cbp.is_greater_or_eq(maxcbp):
                    maxcbp = cbp
                    besttool = plugin.name()
            return maxcbp, besttool
        return CouldBeProducedByGlobalTool.NotFound, None


def run_guess(cfg: LocalProjectConfig, ocache: OmniCache) -> None:
    toolsfinder: _ToolFinder = _ToolFinder(cfg, ocache.resolved_vfs())

    info("Stage 0: collecting retrievers")
    mip = _ModsInProgress(cfg, ocache.available)
    nzero = 0
    nzerostats = _ExtStats()
    ndup = 0
    toolstats: dict[str, _ExtStats] = {}
    nignored = 0
    itf = _IgnoredTargetFiles(cfg)
    for f in ocache.all_source_vfs_files():
        mf = cfg.parse_source_vfs(f.file_path)

        target = cfg.mod_manager_config.modfile_to_target_vfs(mf)
        ignored = itf.ignored(target)

        if ignored:
            nignored += 1
            continue

        if mip.has_retrievers_for(f.file_hash):
            ndup += 1
            mip.add_dup_file(mf, f.file_hash)
        else:
            retr0: list[FileRetriever] = ocache.file_retrievers_by_hash(f.file_hash)
            if len(retr0) > 0:
                for r in retr0:
                    if isinstance(r, (ZeroFileRetriever, GithubFileRetriever)):
                        retr0 = [r]
                        break
            if len(retr0) == 0:
                nzero += 1
                nzerostats.add(f.file_path)
                mip.add_new_file(mf, [])
            else:
                mip.add_new_file(mf, retr0)

    info("{} files ignored, found {} duplicate files".format(nignored, ndup))
    for tool in toolstats:
        toolstats[tool].log_me("tool {}:".format(tool), logging.INFO)
    if nzero > 0:
        nzerostats.log_me(
            "did not find retrievers for {} files".format(nzero), logging.WARNING
        )

    info("stats (nretrievers->ntimes):")
    stats: dict[int, int] = {}
    for _, rlist in mip.all_retrievers():
        n = len(rlist)
        if n not in stats:
            stats[n] = 1
        else:
            stats[n] += 1
    srt = sorted(stats.keys())
    srtfirst = srt[: min(len(srt), 5)]
    for ss in srtfirst:
        info("-> {} -> {}".format(ss, stats[ss]))
    info("-> ...")
    srtlast = srt[-min(len(srt), 5) :]
    for ss in srtlast:
        info("{} -> {}".format(ss, stats[ss]))

    ### processing unique retrievers, resolving per-mod install files, etc.
    info("Stage 1: resolve_unique()...")
    mip.resolve_unique(ocache.source_vfs_cache)

    info("Stage 2: using already-required archives...")
    required_archives: dict[bytes, list[str]] = {}
    nresolvedinmods = 0
    for mod in mip.mods.values():
        assert mod.install_from is not None
        for infr in mod.install_from:
            arh = infr[0].archive.archive_hash
            if arh in required_archives:
                required_archives[arh].append(mod.name)
            else:
                required_archives[arh] = [mod.name]
        # at this point, we're looking ONLY for this-mod archives; required_archives are not fully known yet
        overwrite: dict[str, list[ArchiveFileRetriever]] = {}
        assert mod.remaining_after_install_from is not None
        retr: list[ArchiveFileRetriever]
        for f, retr in mod.remaining_after_install_from.items():
            if len(retr) > 1:
                found = None
                for r in retr:
                    assert isinstance(r, ArchiveFileRetriever)
                    arh = r.archive_hash()
                    if arh in required_archives:
                        if required_archives[arh][-1] == mod.name:
                            found = r
                            break
                if found is not None:
                    nresolvedinmods += 1
                    overwrite[f] = [found]

        mod.remaining_after_install_from |= overwrite

    # now, re-using ALL the required_archives...
    nresolvedoutofmods = 0
    for mod in mip.mods.values():
        assert mod.remaining_after_install_from is not None
        overwrite: dict[str, list[ArchiveFileRetriever]] = {}
        for f, retr in mod.remaining_after_install_from.items():
            if len(retr) > 1:
                found = None
                for r in retr:
                    assert isinstance(r, ArchiveFileRetriever)
                    arh = r.archive_hash()
                    if arh in required_archives:
                        found = r
                assert found is not None  # TODO: handle not-required-archives
                overwrite[f] = [found]
                nresolvedoutofmods += 1
        mod.remaining_after_install_from |= overwrite
    info(
        "Resolved {} ambiguous files within mod archives, {} from other mod archives".format(
            nresolvedinmods, nresolvedoutofmods
        )
    )

    info("Trying to apply mod tools...")
    gameu = cfg.root_modpack_config().game_universe
    assert gameu is not None
    modtools = all_mod_tool_plugins(gameu)
    for mod in mip.mods.values():
        for t in modtools:
            param = ModToolGuessParam()
            assert mod.install_from is not None
            assert mod.remaining_after_install_from is not None
            param.install_from = mod.install_from
            param.remaining_after_install_from = mod.remaining_after_install_from
            guess = t.guess_applied(param)
            if guess is not None:
                guessdescr, guessdiff = guess
                assert isinstance(guessdiff, ModToolGuessDiff)
                for src, dst in guessdiff.moved:
                    foundar = None
                    for ar in mod.install_from:
                        if src in ar[1].skip:
                            foundar = ar
                            break

                    assert foundar is not None
                    assert src in foundar[1].skip
                    assert dst in mod.remaining_after_install_from
                    retr = mod.remaining_after_install_from[dst]
                    fh = truncate_file_hash(retr[0].file_hash)
                    fh0 = None
                    for f, fia in foundar[0].all_desired_files():
                        if f == src:
                            fh0 = fia.file_hash
                            break
                    assert fh0 is not None
                    assert fh == fh0

                    foundar[1].skip.remove(src)
                    del mod.remaining_after_install_from[dst]
                mod.mod_tools.append((t.name(), guessdescr))

    info("Guesswork with global tools...")
    ntools = 0
    for mod in mip.mods.values():
        assert mod.unknown_files_could_be_produced_by_tools is None
        mod.unknown_files_could_be_produced_by_tools = {}
        for ff in mod.modified_since_install():
            if not ff in mod.unknown_files:
                continue  # TODO: double-check that we don't want to do anything about such strange (usually spurious) files

            mf = ModFile(mod.name, ff)
            targetpath = cfg.modfile_to_target_vfs(mf)
            assert targetpath is not None
            srcf = cfg.mod_manager_config.modfile_to_source_vfs(mf)
            cbp, tool = toolsfinder.could_be_produced(srcf, targetpath)
            if cbp.is_greater_or_eq(CouldBeProducedByGlobalTool.Maybe):
                ntools += 1
                assert tool is not None
                mod.unknown_files_could_be_produced_by_tools[ff] = (tool, cbp)
                mod.unknown_files.remove(ff)

                if tool not in toolstats:
                    toolstats[tool] = _ExtStats()
                toolstats[tool].add(srcf)
    info("{} unknown mod files could have been produced by tools".format(ntools))

    info("Trying to find possible patches...")
    with TmpPath(cfg.tmp_dir) as tmp:
        for mod in mip.mods.values():
            assert mod.install_from is not None
            for arinst, aic in mod.install_from:
                for ff in list(aic.modified_since_install.keys()):
                    if not ff in mod.unknown_files:
                        continue  # TODO: double-check that we don't want to do anything about such strange (usually spurious) files

                    modified: FileInArchive = aic.modified_since_install[ff]
                    inarpath = modified.intra_path

                    patchplugins = patch_plugins_for(ff)
                    if patchplugins is None:
                        continue

                    mf = ModFile(mod.name, ff)
                    realpath = cfg.modfile_to_source_vfs(mf)
                    assert realpath is not None

                    arh = arinst.archive.archive_hash
                    ar = ocache.available.archive_by_hash(arh)
                    if ar is not None:
                        assert ar.archive_hash == arh
                        arfiles: list[FileOnDisk] | None = (
                            ocache.available.downloaded_file_by_hash(arh)
                        )
                        if arfiles is None:
                            continue
                        arfile = arfiles[0]  # if there is more than one, any will do
                        arplg = archive_plugin_for(arfile.file_path)
                        assert arplg is not None
                        extracted = arplg.extract(
                            arfile.file_path, [inarpath], tmp.tmpdir
                        )
                        assert len(extracted) == 1
                        if extracted[0] is not None:
                            extracted = extracted[0]
                            for pplg in patchplugins:
                                try:
                                    patch = pplg.patch(extracted, realpath)
                                    if patch is not None:
                                        info("Patch found for {}".format(ff))
                                        assert ff in aic.modified_since_install
                                        del aic.modified_since_install[ff]
                                        assert ff in aic.skip
                                        aic.skip.remove(ff)
                                        mod.unknown_files.remove(ff)
                                        mod.patched[ff] = (pplg.name(), patch)
                                        break
                                except Exception as e:
                                    warn(
                                        "Exception while patching {}: {}".format(ff, e)
                                    )
                                    warn(traceback.format_exc())

    ninstallfrom = 0
    # info('per-mod stats:')
    cleanlyinstalledmods: list[tuple[str, _ModInProgress]] = []
    healabletocleanmods: list[tuple[str, _ModInProgress]] = []
    fullygithubmods: list[tuple[str, _ModInProgress]] = []
    othermods: list[tuple[str, _ModInProgress]] = []
    for modname, mod in mip.mods.items():
        assert mod.install_from is not None
        if mod.is_fully_github():
            fullygithubmods.append((modname, mod))
            continue

        processed = False
        if len(mod.install_from) > 0:
            # names = [wcache.available.tentative_names_for_archive(arinst.archive.archive_hash) for arinst, _ in
            #         mod.install_from]
            # instdata = [arinst.install_data() for arinst, _ in mod.install_from]
            # info("-> {}: install_from {}, install_data='{}'".format(
            #    modname, str(names), str(instdata)))
            ninstallfrom += 1
            if mod.is_cleanly_installed():
                cleanlyinstalledmods.append((modname, mod))
                processed = True
            elif mod.is_healable_to_clean_install():
                healabletocleanmods.append((modname, mod))
                processed = True

        if processed:
            continue

        othermods.append((modname, mod))

    info(
        "found install_from archives for {} mods out of {}, {:.1f}%".format(
            ninstallfrom, len(mip.mods), ninstallfrom / len(mip.mods) * 100.0
        )
    )
    info(
        "{} mod(s) are github-only, {} mod(s) are cleanly installed, {} mod(s) can probably be healed to clean install".format(
            len(fullygithubmods), len(cleanlyinstalledmods), len(healabletocleanmods)
        )
    )
    alert("{} mod(s) remaining".format(len(othermods)))

    unknownextstats = _ExtStats()
    archivefilesextstats = _ExtStats()
    modifiedsinceextstats = _ExtStats()
    unknownmodstats = _PerModStats()
    archivefilesmodstats = _PerModStats()
    modifiedsincemodstats = _PerModStats()
    for mod in mip.mods.values():
        mod.collect_extension_stats(
            unknownextstats, archivefilesextstats, modifiedsinceextstats
        )
        mod.collect_mod_stats(
            unknownmodstats, archivefilesmodstats, modifiedsincemodstats
        )
    unknownextstats.log_me("Unknown files stats:", logging.INFO)
    archivefilesextstats.log_me("Archive files stats:", logging.INFO)
    modifiedsinceextstats.log_me("Modified files stats:", logging.INFO)
    unknownmodstats.log_me("Unknown files stats:", logging.INFO)
    archivefilesmodstats.log_me("Archive files stats:", logging.INFO, 20)
    modifiedsincemodstats.log_me("Modified files stats:", logging.INFO)

    # preparing ProjectJson object
    pj = ProjectJson()
    pj.mods = []
    for mod in mip.mods.values():
        assert mod.install_from is not None
        assert mod.remaining_after_install_from is not None
        assert mod.unknown_files_could_be_produced_by_tools is not None
        pm = ProjectMod()
        pj.mods.append(pm)
        pm.mod_name = mod.name
        pm.zero_files = [z for z in mod.zero_files]
        pm.github_files = {k: v[0] for k, v in mod.github_files.items()}
        pm.installers = []
        for infr in mod.install_from:
            ainst, aex = infr
            skip = [s for s in aex.skip]
            pa = ProjectInstaller(
                ainst.archive.archive_hash, ainst.name(), ainst.install_params(), skip
            )
            pm.installers.append(pa)
        pm.remaining_archives = []
        installerarchives: list[bytes] = [
            x[0].archive.archive_hash for x in mod.install_from
        ]
        extraarchives: dict[bytes, ProjectExtraArchive] = {}
        for f, retr in mod.remaining_after_install_from.items():
            assert len(retr) == 1
            r0 = retr[0]
            assert isinstance(r0, ArchiveFileRetriever)
            arh = r0.archive_hash()
            arid = arh
            if arh in installerarchives:
                arid = installerarchives.index(arh)
            if arh not in extraarchives:
                extraarchives[arh] = ProjectExtraArchive(arid)
            intra_paths = [
                ar.file_in_archive.intra_path for ar in r0.single_archive_retrievers
            ]
            extraarchives[arh].extra_files.append(
                ProjectExtraArchiveFile(f, intra_paths)
            )

        for xa in extraarchives.values():
            pm.remaining_archives.append(xa)

        pm.unknown_files = [u for u in mod.unknown_files]
        pm.unknown_files_by_tools = [
            t for t in mod.unknown_files_could_be_produced_by_tools
        ]
        pm.mod_tools = [
            ProjectModTool(mtname, mtparam) for mtname, mtparam in mod.mod_tools
        ]
        pm.patches = [
            ProjectModPatch(key, val[0], val[1]) for key, val in mod.patched.items()
        ]

    jdata = to_stable_json(pj)
    write_stable_json(cfg.this_modpack_folder() + "project.json", jdata)


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
