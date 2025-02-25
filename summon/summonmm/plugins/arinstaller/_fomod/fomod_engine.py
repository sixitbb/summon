# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
FOMOD installer engine. More or less clean FOMOD installer itself, on top of (already-parsed by
  fomod_parser) ModuleConfig.xml.
To support auto-install, uses FomodAutoinstallFakeUI.
Also heavily used for FOMOD guessing.
"""

from summonmm.plugins.arinstaller._fomod.fomod_common import *


class FomodAutoinstallFakeUI(LinearUI):
    selections: set[FomodInstallerSelection]
    selected: set[FomodInstallerSelection]

    def __init__(self, selections: list[FomodInstallerSelection]) -> None:
        self.selections = set(selections)
        self.selected = set()

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
        for grp in wizardpage.controls:
            assert isinstance(grp, LinearUIGroup)
            for chkbox in grp.controls:
                assert isinstance(chkbox, LinearUICheckbox)
                sel = FomodInstallerSelection(wizardpage.name, grp.name, chkbox.name)
                val = False
                assert sel not in self.selected
                if sel in self.selections:
                    val = True
                    self.selected.add(sel)
                if chkbox.disabled:
                    raise_if_not(val == chkbox.value)
                else:
                    chkbox.value = val

        if validator is not None:
            errstr = validator(wizardpage)
            raise_if_not(errstr is None)

    def check_done(self) -> None:
        raise_if_not(len(self.selected) == len(self.selections))


class FomodEnginePluginSelector:
    istep_ctrl: LinearUIGroup
    istep: FomodInstallStep
    grp_ctrl: LinearUIGroup | None
    grp: FomodGroup | None
    plugin_ctrl: LinearUICheckbox | None
    plugin: FomodPlugin | None

    def __init__(self, ctrl: LinearUIGroup) -> None:
        assert isinstance(ctrl, LinearUIGroup)
        self.istep_ctrl = ctrl
        tag, self.istep = ctrl.extra_data
        assert tag == 0
        assert isinstance(self.istep, FomodInstallStep)
        self.grp_ctrl = None
        self.grp = None
        self.plugin_ctrl = None
        self.plugin = None

    def set_grp(self, c2: LinearUIControl) -> None:
        # assert self.grp_ctrl is None
        # assert self.grp is None
        # assert self.plugin_ctrl is None
        # assert self.plugin is None

        assert isinstance(c2, LinearUIGroup)
        self.grp_ctrl = c2
        tag, self.grp = c2.extra_data
        assert tag == 1
        assert isinstance(self.grp, FomodGroup)
        self.plugin_ctrl = None
        self.plugin = None

    def set_chkbox(self, c3: LinearUIControl) -> None:
        assert self.grp_ctrl is not None
        assert self.grp is not None
        # assert self.plugin_ctrl is None
        # assert self.plugin is None

        assert isinstance(c3, LinearUICheckbox)
        self.plugin_ctrl = c3
        tag, self.plugin = c3.extra_data
        assert tag == 2
        assert isinstance(self.plugin, FomodPlugin)


def _fomod_wizard_page_validator(wizardpage: LinearUIGroup) -> str | None:
    it = FomodEnginePluginSelector(wizardpage)
    for grp in wizardpage.controls:
        assert isinstance(grp, LinearUIGroup)
        it.set_grp(grp)
        assert it.grp is not None
        sel = it.grp.select
        nsel = 0
        for chk in grp.controls:
            assert isinstance(chk, LinearUICheckbox)
            it.set_chkbox(chk)
            if chk.value:
                nsel += 1

        assert nsel >= 0
        match sel:
            case FomodGroupSelect.SelectAll:
                assert nsel == len(grp.controls)
            case FomodGroupSelect.SelectAny:
                pass
            case FomodGroupSelect.SelectExactlyOne:
                assert nsel == 1
            case FomodGroupSelect.SelectAtMostOne:
                if nsel > 1:
                    return "Too many selections in group {}".format(grp.name)
            case FomodGroupSelect.SelectAtLeastOne:
                if nsel < 1:
                    return "Too few selections in group {}".format(grp.name)
            case _:
                assert False
    return None


class FomodEngine:
    module_config: FomodModuleConfig
    select_no_radio_hack: bool  # for very specific _FomodGuessFakeUI use cases

    def __init__(self, modulecfg: FomodModuleConfig) -> None:
        self.module_config = modulecfg
        self.select_no_radio_hack = False

    def run(
        self, ui: LinearUI
    ) -> tuple[list[FomodInstallerSelection], FomodFilesAndFolders]:
        flags: dict[str, str] = {}
        runtimedeps: FomodDependencyEngineRuntimeData = (
            FomodDependencyEngineRuntimeData(flags)
        )
        selections: list[FomodInstallerSelection] = []
        files = self.module_config.required.copy()  # copying, as we'll append to files
        for istep in self.module_config.install_steps:
            if not istep.visible.is_satisfied(runtimedeps):
                continue  # TODO: what about potential mandatory settings within non-visible pages?
            assert istep.name is not None
            wizpage = LinearUIGroup(istep.name, [])
            wizpage.extra_data = (0, istep)
            for grp in istep.groups:
                assert grp.name is not None
                wizpagegrp = LinearUIGroup(grp.name, [])
                wizpagegrp.extra_data = (1, grp)
                wizpage.add_control(wizpagegrp)
                for plugin in grp.plugins:
                    assert plugin.name is not None
                    match grp.select:
                        case (
                            FomodGroupSelect.SelectAny
                            | FomodGroupSelect.SelectAtMostOne
                            | FomodGroupSelect.SelectAtLeastOne
                        ):
                            wizpageplugin = LinearUICheckbox(plugin.name, False, False)
                        case FomodGroupSelect.SelectExactlyOne:
                            wizpageplugin = LinearUICheckbox(plugin.name, False, True)
                        case FomodGroupSelect.SelectAll:
                            wizpageplugin = LinearUICheckbox(plugin.name, True, False)
                            wizpageplugin.disabled = True
                        case _:
                            assert False
                    wizpageplugin.extra_data = (2, plugin)
                    wizpagegrp.add_control(wizpageplugin)
            ui.wizard_page(wizpage, _fomod_wizard_page_validator)

            pgextra = FomodEnginePluginSelector(wizpage)
            for grp in wizpage.controls:
                assert isinstance(grp, LinearUIGroup)
                pgextra.set_grp(grp)
                n = 0
                for chkbox in grp.controls:
                    assert isinstance(chkbox, LinearUICheckbox)
                    pgextra.set_chkbox(chkbox)
                    assert pgextra.plugin is not None
                    if chkbox.value:
                        n += 1
                        if pgextra.plugin.files is not None:
                            files.merge(pgextra.plugin.files)
                        for dep in pgextra.plugin.condition_flags:
                            assert dep.name is not None
                            assert dep.value is not None
                            flags[dep.name] = dep.value
                        assert pgextra.istep.name is not None
                        assert pgextra.grp is not None
                        assert pgextra.grp.name is not None
                        assert pgextra.plugin.name is not None
                        selections.append(
                            FomodInstallerSelection(
                                pgextra.istep.name,
                                pgextra.grp.name,
                                pgextra.plugin.name,
                            )
                        )
                assert pgextra.grp is not None
                match pgextra.grp.select:
                    case FomodGroupSelect.SelectExactlyOne:
                        assert n == 1 or (self.select_no_radio_hack and n == 0)
                    case FomodGroupSelect.SelectAny:
                        pass
                    case FomodGroupSelect.SelectAtMostOne:
                        assert n <= 1
                    case FomodGroupSelect.SelectAtLeastOne:
                        assert n >= 1
                    case FomodGroupSelect.SelectAll:
                        assert n == len(grp.controls)
                    case _:
                        assert False
        for cond in self.module_config.conditional_file_installs:
            assert cond.dependencies is not None
            assert cond.files is not None
            if cond.dependencies.is_satisfied(runtimedeps):
                files.merge(cond.files)
        return selections, files


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
