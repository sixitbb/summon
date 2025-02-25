# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

"""
FOMOD guessing. Really complicated. Replaying all scenarios (a.k.a. forks) from
  (already parsed by fomod_parser) ModuleConfig.xml using _FomodGuessFakeUI, and then replaying
  again using FomodAutoinstallFakeUI
Tries to keep number of forks in check separating independent selections from forks
"""

from summonmm.helpers.file_retriever import ArchiveFileRetriever
from summonmm.plugins.arinstaller._fomod.fomod_common import *
from summonmm.plugins.arinstaller._fomod.fomod_engine import (
    FomodEngine,
    FomodEnginePluginSelector,
    FomodAutoinstallFakeUI,
)

type _FomodReplaySteps = list[tuple[FomodInstallerSelection, bool | None]]
type _FomodGuessPlugins = list[
    tuple[FomodInstallerSelection, FomodFilesAndFolders | None]
]


class _FomodGuessFork:
    start_step: _FomodReplaySteps
    true_or_false_plugins: _FomodGuessPlugins
    one_of_plugins: list[_FomodGuessPlugins]

    def __init__(
        self,
        start: _FomodReplaySteps,
        tof: _FomodGuessPlugins | None = None,
        oof: list[_FomodGuessPlugins] | None = None,
    ) -> None:
        self.start_step = start
        self.true_or_false_plugins = tof if tof is not None else []
        self.one_of_plugins = oof if oof is not None else []

    def copy(self) -> "_FomodGuessFork":
        return _FomodGuessFork(
            self.start_step.copy(),
            self.true_or_false_plugins.copy(),
            self.one_of_plugins.copy(),
        )


class _FomodGuessFakeUI(LinearUI):
    current_fork: _FomodGuessFork
    current_step: _FomodReplaySteps
    requested_forks: list[_FomodGuessFork]

    def __init__(self, startingfork: _FomodGuessFork) -> None:
        self.current_fork = startingfork
        self.current_step = []
        self.requested_forks = []

    def set_silent_mode(self) -> None:
        assert False

    # noinspection PyTypeChecker
    def message_box(
        self,
        prompt: str,
        spec: list[str],
        level: LinearUIImportance = LinearUIImportance.Default,
    ) -> str:
        assert False

    # noinspection PyTypeChecker
    def input_box(
        self,
        prompt: str,
        default: str,
        level: LinearUIImportance = LinearUIImportance.Default,
    ) -> str:
        assert False

    def confirm_box(
        self, prompt: str, level: LinearUIImportance = LinearUIImportance.Default
    ) -> None:
        assert False

    # noinspection PyTypeChecker
    def network_error_handler(self, nretries: int) -> SummonBaseNetworkErrorHandler:
        assert False

    def wizard_page(
        self,
        wizardpage: LinearUIGroup,
        validator: Callable[[LinearUIGroup], str | None] | None = None,
    ) -> None:
        it = FomodEnginePluginSelector(wizardpage)
        for cgrp in wizardpage.controls:
            assert isinstance(cgrp, LinearUIGroup)
            it.set_grp(cgrp)
            for c2idx, c2 in enumerate(cgrp.controls):
                it.set_chkbox(c2)
                if len(self.current_step) < len(self.current_fork.start_step):
                    nxt = self.current_fork.start_step[len(self.current_step)]
                    assert it.istep.name == nxt[0].step_name
                    assert it.grp is not None
                    assert it.plugin is not None
                    assert it.plugin_ctrl is not None
                    if it.grp.name != nxt[0].group_name:
                        assert False
                    if it.plugin.name != nxt[0].plugin_name:
                        assert False

                    self.current_step.append(nxt)
                    if it.plugin_ctrl.disabled:
                        assert it.plugin_ctrl.value == nxt[1]
                    else:
                        it.plugin_ctrl.value = nxt[1]
                    continue
                assert len(self.current_step) >= len(self.current_fork.start_step)
                oldcurlen = len(self.current_step)

                assert it.istep.name is not None
                assert it.grp is not None
                assert it.grp.name is not None
                assert it.plugin is not None
                assert it.plugin.name is not None
                cur = FomodInstallerSelection(
                    it.istep.name, it.grp.name, it.plugin.name
                )
                possible: tuple[NoneType] | tuple[bool] | tuple[bool, bool]
                match it.grp.select:
                    case FomodGroupSelect.SelectAny:
                        possible = (None,)
                    case FomodGroupSelect.SelectAll:
                        possible = (True,)
                    case FomodGroupSelect.SelectExactlyOne:
                        independent = True
                        for plg in it.grp.plugins:
                            if len(plg.condition_flags) > 0:
                                independent = False
                                break

                        if independent:
                            possible = (None,)
                            if c2idx == 0:
                                self.current_fork.one_of_plugins.append(
                                    [
                                        (
                                            FomodInstallerSelection(
                                                cur.step_name,
                                                cur.group_name,
                                                coerce_str_not_none(plg.name),
                                            ),
                                            plg.files,
                                        )
                                        for plg in it.grp.plugins
                                    ]
                                )
                        else:
                            possible = (True, False)
                            for i in range(c2idx):
                                prevstep = self.current_step[-1 - i]
                                assert (
                                    prevstep[0].step_name == it.istep.name
                                    and prevstep[0].group_name == it.grp.name
                                )
                                assert prevstep[1] is False or prevstep[1] is True
                                if prevstep[1] is True:
                                    possible = (False,)
                                    break
                            if len(possible) == 2 and c2idx == len(cgrp.controls) - 1:
                                possible = (True,)
                    case FomodGroupSelect.SelectAtLeastOne:
                        possible = (True, False)
                        found = False
                        for i in range(c2idx):
                            prevstep = self.current_step[-1 - i]
                            assert (
                                prevstep[0].step_name == it.istep.name
                                and prevstep[0].group_name == it.grp.name
                            )
                            assert prevstep[1] is False or prevstep[1] is True

                            if prevstep[1] is True:
                                found = True
                                break
                        if not found and c2idx == len(cgrp.controls) - 1:
                            possible = (True,)
                    case FomodGroupSelect.SelectAtMostOne:
                        possible = (True, False)
                        found = False
                        for i in range(c2idx):
                            prevstep = self.current_step[-1 - i]
                            assert (
                                prevstep[0].step_name == it.istep.name
                                and prevstep[0].group_name == it.grp.name
                            )
                            assert prevstep[1] is False or prevstep[1] is True

                            if prevstep[1] is True:
                                found = True
                                break
                        if found:
                            possible = (False,)
                    case _:
                        assert False

                assert isinstance(possible, tuple)
                assert len(possible) == 1 or len(possible) == 2
                predetermined = len(possible) == 1 and possible[0] is not None
                assert it.plugin_ctrl is not None
                if it.plugin_ctrl.disabled:
                    assert predetermined
                    assert possible[0] == it.plugin_ctrl.value

                willfork = False
                if predetermined:  # no choice, no fork
                    assert len(possible) == 1
                    assert possible[0] is False or possible[0] is True
                    it.plugin_ctrl.value = possible[0]
                    self.current_step.append((cur, possible[0]))
                elif len(it.plugin.condition_flags) > 0:
                    willfork = True
                elif possible[0] is None:
                    self.current_step.append((cur, None))
                    assert it.grp.select in (
                        FomodGroupSelect.SelectExactlyOne,
                        FomodGroupSelect.SelectAny,
                    )
                    if (
                        it.grp.select == FomodGroupSelect.SelectAny
                        and it.plugin.files is not None
                    ):
                        self.current_fork.true_or_false_plugins.append(
                            (cur, it.plugin.files)
                        )
                else:
                    willfork = True

                if (
                    willfork
                ):  # both are possible, will handle True in this run, will request fork with False
                    assert possible[0] is None or (
                        len(possible) == 2
                        and possible[0] is True
                        and possible[1] is False
                    )
                    # (None,) is treated the same as (True,False) here
                    forked = self.current_fork.copy()
                    forked.start_step = self.current_step.copy()
                    forked.start_step.append((cur, False))
                    self.requested_forks.append(forked)
                    self.current_step.append((cur, True))
                    # self.current_fork.flags |= {dep.name: dep.value for dep in it.plugin.condition_flags}
                    assert not it.plugin_ctrl.disabled
                    it.plugin_ctrl.value = True
                    # if it.plugin.files is not None:
                    #    self.current_fork.selected_plugins.append((cur, it.plugin.files))

                assert len(self.current_step) == oldcurlen + 1


def _add_folder_to_xofs(
    xofs: dict[str, list[tuple[FomodInstallerSelection, FileInArchive]]],
    fdst: str,
    instsel: FomodInstallerSelection,
    remainder: str,
    af: FileInArchive,
) -> None:
    filedst = fdst + remainder
    if filedst not in xofs:
        xofs[filedst] = []
    xofs[filedst].append((instsel, af))


def _find_required_xofs(
    ar4: ArchiveForFomodFilesAndFolders,
    fomodroot: str,
    modfiles: dict[str, list[ArchiveFileRetriever]],
    true_or_false_plugins: _FomodGuessPlugins,
    one_of_plugins: list[_FomodGuessPlugins],
) -> list[FomodInstallerSelection]:
    if len(true_or_false_plugins) == 0 and len(one_of_plugins) == 0:
        return []
    assert not fomodroot.endswith("\\")
    fomodroot1 = "" if fomodroot == "" else fomodroot + "\\"

    xofs: dict[str, list[tuple[FomodInstallerSelection, FileInArchive]]] = {}
    allcandidates: _FomodGuessPlugins = true_or_false_plugins
    for oof in one_of_plugins:
        allcandidates += oof
    for instsel, ff in allcandidates:
        if ff is not None:
            for f in ff.files:
                assert f.src is not None
                assert f.dst is not None
                fsrc = FomodFilesAndFolders.normalize_file_path(fomodroot1 + f.src)
                fdst = FomodFilesAndFolders.normalize_file_path(f.dst)
                if fsrc not in ar4.arfiles:
                    assert False
                if fdst not in xofs:
                    xofs[fdst] = []
                xofs[fdst].append((instsel, ar4.arfiles[fsrc]))
            for f in ff.folders:
                assert f.src is not None
                assert f.dst is not None
                fsrc = FomodFilesAndFolders.normalize_folder_path(fomodroot1 + f.src)
                fdst = FomodFilesAndFolders.normalize_folder_path(f.dst)
                ar4.for_all_starting_with(
                    fsrc,
                    lambda remainder, af: _add_folder_to_xofs(
                        xofs, fdst, instsel, remainder, af
                    ),
                )

    required_xofs: set[FomodInstallerSelection] = set()
    for modfile, rlist in modfiles.items():
        r0: ArchiveFileRetriever = rlist[0]
        fh = truncate_file_hash(r0.file_hash)
        if modfile in xofs:
            if len(xofs[modfile]) == 1 and xofs[modfile][0][1].file_hash == fh:
                required_xofs.add(xofs[modfile][0][0])
            else:
                nmatch = 0
                matched = None
                for cand in xofs[modfile]:
                    if cand[1].file_hash == fh:
                        nmatch += 1
                        matched = cand[0]
                if nmatch == 1:
                    assert matched is not None
                    required_xofs.add(matched)
                else:
                    pass

    for oof in one_of_plugins:
        n = 0
        for of in oof:
            isel: FomodInstallerSelection = of[0]
            if isel in required_xofs:
                n += 1
        if n == 0:
            # none is needed, but this is not an option
            # we'll find the smallest one
            minsz = None
            minof = None
            for of in oof:
                nfiles = (
                    sum(1 for _ in of[1].all_files(fomodroot, ar4))
                    if of[1] is not None
                    else 0
                )
                if minsz is None or nfiles < minsz:
                    minsz = nfiles
                    minof = of
            if __debug__ and minsz is None:
                assert False
            assert minof is not None
            required_xofs.add(minof[0])
        elif n == 1:
            pass
        else:
            assert False  # TODO
    return list(required_xofs)


class _ProcessedFork:
    tofs: _FomodGuessPlugins
    oofs: list[_FomodGuessPlugins]
    engselections: list[FomodInstallerSelection]

    # engplugins: FomodFilesAndFolders - we cannot use engplugins from GuessFakeUI run, need to re-run with AutoplayFakeUI to ensure correct order

    def __init__(
        self,
        tofs: _FomodGuessPlugins,
        oofs: list[_FomodGuessPlugins],
        engselections: list[FomodInstallerSelection],
    ) -> None:
        self.tofs = tofs
        self.oofs = oofs
        self.engselections = engselections
        # self.engplugins=engplugins


def fomod_guess(
    fomodroot: str,
    modulecfg: FomodModuleConfig,
    archive: Archive,
    modfiles: dict[str, list[ArchiveFileRetriever]],
) -> tuple[ArInstaller, int] | None:
    processed_forks: list[_ProcessedFork] = []
    remaining_forks: list[_FomodGuessFork] = [_FomodGuessFork([])]
    info("Running simulations for FOMOD installer {}...".format(modulecfg.module_name))
    # if 'clear map' in modulecfg.module_name.lower():
    #    pass

    nmodfiles = 0
    for _, retr in modfiles.items():
        for r in retr:
            if r.archive_hash() == archive.archive_hash:
                nmodfiles += 1
                break  # for r

    while len(remaining_forks) > 0:
        startingfork = remaining_forks[0]
        remaining_forks = remaining_forks[1:]
        fakeui = _FomodGuessFakeUI(startingfork)
        engine = FomodEngine(modulecfg)
        engine.select_no_radio_hack = True
        engselections, _ = engine.run(
            fakeui
        )  # we cannot use engfiles from GuessFakeUI run, need to re-run using AutoplayFakeUI to ensure correct order
        processed_forks.append(
            _ProcessedFork(
                fakeui.current_fork.true_or_false_plugins,
                fakeui.current_fork.one_of_plugins,
                engselections,
            )
        )
        remaining_forks += fakeui.requested_forks
        if len(processed_forks) + len(remaining_forks) > 50000:
            alert("Too many simulations for {}, skipping".format(modulecfg.module_name))
            return None
    info("{}: {} fork(s) found".format(modulecfg.module_name, len(processed_forks)))

    best_arinstaller: ArInstaller | None = None
    best_coverage: int = 0
    best_desired: int | None = None
    i = 0
    ar4 = ArchiveForFomodFilesAndFolders(archive)
    for pf in processed_forks:
        i += 1
        if i % 500 == 0:
            info("{}...".format(i))
        selected_plugins: set[FomodInstallerSelection] = set(pf.engselections)
        known: dict[FomodInstallerSelection, FomodFilesAndFolders] = {}
        for sel, tof in pf.tofs:
            assert sel not in known
            if tof is not None:
                known[sel] = tof
        for oof in pf.oofs:
            for sel, of in oof:
                if sel in known:
                    assert False
                if of is not None:
                    known[sel] = of
        required_xofs: set[FomodInstallerSelection] = set(
            _find_required_xofs(ar4, fomodroot, modfiles, pf.tofs, pf.oofs)
        )

        """
        # gathering properly ordered selections
        selections: list[FomodInstallerSelection] = []
        # files: FomodFilesAndFolders = pf.engplugins.copy()
        for istep in modulecfg.install_steps:
            for group in istep.groups:
                for plugin in group.plugins:
                    sel = FomodInstallerSelection(istep.name, group.name, plugin.name)
                    if sel in required_xofs:
                        if sel in known:
                            assert known[sel] is not None
                            selections.append(sel)
                            # files.merge(known[sel])
                        else:
                            selections.append(sel)
                            # nothing to merge - it is empty (can happen as a result of empty entry in SelectExactlyOne)
                    elif sel in selected_plugins:
                        selections.append(sel)
                    else:
                        pass
        """

        # re-running FomodEngine with autoplay to ensure correct file overwrite order
        autoplay = FomodAutoinstallFakeUI(list(required_xofs | selected_plugins))
        engine2 = FomodEngine(modulecfg)
        engselections, engfiles = engine2.run(autoplay)
        autoplay.check_done()

        candidate: FomodArInstaller = FomodArInstaller(
            archive, fomodroot, engfiles, engselections
        )
        n = 0
        ndesired = 0
        for fpath, fia in candidate.all_desired_files():
            ndesired += 1
            if (
                fpath in modfiles
                and truncate_file_hash(modfiles[fpath][0].file_hash) == fia.file_hash
            ):
                n += 1
        if n > (ndesired / 2):
            if n > best_coverage:
                best_coverage = n
                best_arinstaller = candidate
                best_desired = ndesired
            else:
                assert best_desired is not None
                if n == best_coverage and ndesired < best_desired:
                    best_coverage = n
                    best_arinstaller = candidate
                    best_desired = ndesired

            if len(modfiles) == best_desired == best_coverage:  # ideal case found
                break

    if best_arinstaller is None:
        return None
    return best_arinstaller, best_coverage


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
