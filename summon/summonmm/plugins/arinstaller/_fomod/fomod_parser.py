# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


"""
FOMOD XML parser, from ModuleConfig.xml to fomod_common data structures
"""

import xml.etree.ElementTree as ElementTree

from summonmm.plugins.arinstaller._fomod.fomod_common import *


def _raise_unknown_tag(
    parent: ElementTree.Element | None, e: ElementTree.Element
) -> None:
    raise SummonError(
        "unknown tag in moduleconfig.xml: {} in {}".format(
            e.tag, parent.tag if parent is not None else "''"
        )
    )


def _raise_unknown_attr(e: ElementTree.Element, attrname: str) -> None:
    raise SummonError(
        "unknown attribute in moduleconfig.xml: {} in {}".format(attrname, e.tag)
    )


def _raise_incomplete_tag(e: ElementTree.Element) -> None:
    raise SummonError("incomplete tag in moduleconfig.xml: {}".format(e.tag))


def _check_no_text(e: ElementTree.Element) -> None:
    if e.text is not None and e.text.strip() != "":
        raise SummonError("unexpected text in moduleconfig.xml: {}".format(e.tag))


def _check_no_attrs(n: ElementTree.Element) -> None:
    for an in n.attrib:
        _raise_unknown_attr(n, an)


def _check_no_children(n: ElementTree.Element) -> None:
    for child in n:
        _raise_unknown_tag(n, child)


def _text(e: ElementTree.Element) -> str:
    return e.text.strip() if e.text is not None else ""


def _parse_src_dst(n: ElementTree.Element) -> FomodSrcDst:
    _check_no_text(n)
    _check_no_children(n)
    out = FomodSrcDst()
    for an, av in n.attrib.items():
        match an:
            case "source":
                out.src = av
            case "destination":
                out.dst = av
            case "priority":
                out.priority = int(av)
            case "alwaysInstall":
                out.flags |= FomodSrcDstFlags.AlwaysInstall
            case "installIfUsable":
                out.flags |= FomodSrcDstFlags.InstallIfUsable
            case _:
                _raise_unknown_attr(n, an)
    if out.src is None or out.dst is None:
        _raise_incomplete_tag(n)
    return out


def _parse_files_and_folders(n: ElementTree.Element) -> FomodFilesAndFolders:
    out = FomodFilesAndFolders()
    _check_no_text(n)
    _check_no_attrs(n)
    for child in n:
        match child.tag:
            case "file":
                out.files.append(_parse_src_dst(child))
            case "folder":
                out.folders.append(_parse_src_dst(child))
            case _:
                _raise_unknown_tag(n, child)
    return out


def _parse_flag_dependency(n: ElementTree.Element) -> FomodFlagDependency:
    out = FomodFlagDependency()
    _check_no_text(n)
    _check_no_children(n)
    for an, av in n.attrib.items():
        match an:
            case "flag":
                out.name = av
            case "value":
                out.value = av
            case _:
                _raise_unknown_attr(n, an)
    return out


def _parse_flag(n: ElementTree.Element) -> FomodFlagDependency:
    out = FomodFlagDependency()
    _check_no_children(n)
    for an, av in n.attrib.items():
        if an == "name":
            out.name = av
        else:
            _raise_unknown_attr(n, av)
    out.value = _text(n)
    return out


def _parse_file_dependency(n: ElementTree.Element) -> FomodFileDependency:
    out = FomodFileDependency()
    _check_no_text(n)
    _check_no_children(n)
    for an, av in n.attrib.items():
        match an:
            case "file":
                out.file = av
            case "state":
                match av:
                    case "Active":
                        out.state = FomodFileDependencyState.Active
                    case "Inactive":
                        out.state = FomodFileDependencyState.Inactive
                    case "Missing":
                        out.state = FomodFileDependencyState.Missing
                    case _:
                        _raise_unknown_attr(n, av)
            case _:
                _raise_unknown_attr(n, an)
    return out


def _parse_game_dependency(n: ElementTree.Element) -> FomodGameDependency:
    out = FomodGameDependency()
    _check_no_text(n)
    _check_no_children(n)
    for an, av in n.attrib.items():
        if an == "version":
            out.version = av
        else:
            _raise_unknown_attr(n, av)
    return out


def _parse_some_dependency(n: ElementTree.Element) -> FomodSomeDependency:
    match n.tag:
        case "fileDependency":
            return FomodSomeDependency(_parse_file_dependency(n))
        case "flagDependency":
            return FomodSomeDependency(_parse_flag_dependency(n))
        case "gameDependency":
            return FomodSomeDependency(_parse_game_dependency(n))
        case "dependencies":
            return FomodSomeDependency(_parse_dependencies(n))
        case _:
            _raise_unknown_tag(n, n)
            assert False


def _parse_dependencies(n: ElementTree.Element) -> FomodDependencies:
    out = FomodDependencies()
    out.oroperator = False
    for an, av in n.attrib.items():
        if an == "operator":
            match av:
                case "Or":
                    out.oroperator = True
                case "And":
                    out.oroperator = False
                case _:
                    _raise_unknown_attr(n, av)
    for child in n:
        out.dependencies.append(_parse_some_dependency(child))
    return out


def _parse_fomod_type(n: ElementTree.Element) -> FomodType:
    _check_no_text(n)
    _check_no_children(n)
    for an, av in n.attrib.items():
        if an == "name":
            match av:
                case "Recommended":
                    return FomodType.Recommended
                case "Optional":
                    return FomodType.Optional
                case "Required":
                    return FomodType.Required
                case "NotUsable":
                    return FomodType.NotUsable
                case "CouldBeUsable":
                    return FomodType.CouldBeUsable
                case _:
                    _raise_unknown_attr(n, av)
                    assert False
    _raise_incomplete_tag(n)
    assert False


def _parse_pattern(n: ElementTree.Element) -> FomodPattern:
    out = FomodPattern()
    _check_no_text(n)
    _check_no_attrs(n)
    for child in n:
        match child.tag:
            case "dependencies":
                out.dependencies = _parse_dependencies(child)
            case "type":
                out.type = _parse_fomod_type(child)
            case "files":
                out.files = _parse_files_and_folders(child)
            case _:
                _raise_unknown_tag(n, child)
    return out


def _parse_patterns(n: ElementTree.Element) -> list[FomodPattern]:
    out: list[FomodPattern] = []
    _check_no_text(n)
    _check_no_attrs(n)
    for child in n:
        if child.tag == "pattern":
            out.append(_parse_pattern(child))
        else:
            _raise_unknown_tag(n, child)
    return out


def _parse_type_descriptor(n: ElementTree.Element) -> FomodTypeDescriptor:
    out = FomodTypeDescriptor()
    _check_no_text(n)
    _check_no_attrs(n)
    for child in n:
        match child.tag:
            case "type":
                out.type = _parse_fomod_type(child)
            case "dependencyType":
                for ch2 in child:
                    match ch2.tag:
                        case "defaultType":
                            out.type = _parse_fomod_type(ch2)
                        case "patterns":
                            out.patterns = _parse_patterns(ch2)
                        case _:
                            _raise_unknown_tag(child, ch2)
            case _:
                _raise_unknown_tag(n, child)
                assert False
    return out


def _parse_plugin(n: ElementTree.Element) -> FomodPlugin:
    out = FomodPlugin()
    for an, av in n.attrib.items():
        match an:
            case "name":
                out.name = av
            case _:
                _raise_unknown_attr(n, an)
    for child in n:
        match child.tag:
            case "description":
                _check_no_attrs(child)
                _check_no_children(child)
                out.description = _text(child)
            case "image":
                _check_no_text(child)
                _check_no_children(child)
                for an, av in child.attrib.items():
                    if an == "path":
                        out.image = av
            case "files":
                _check_no_text(child)
                _check_no_attrs(child)
                out.files = _parse_files_and_folders(child)
            case "typeDescriptor":
                out.type_descriptor = _parse_type_descriptor(child)
            case "conditionFlags":
                _check_no_text(child)
                _check_no_attrs(child)
                for ch2 in child:
                    if ch2.tag == "flag":
                        out.condition_flags.append(_parse_flag(ch2))
                    else:
                        _raise_unknown_tag(child, ch2)
            case _:
                _raise_unknown_tag(n, child)
    return out


def _parse_order_attr(e: ElementTree.Element, av: str) -> FomodOrder:
    match av:
        case "Explicit":
            return FomodOrder.Explicit
        case "Descending":
            return FomodOrder.Descending
        case "Ascending":
            return FomodOrder.Descending
        case _:
            _raise_unknown_attr(e, av)
            assert False


def _parse_group(e: ElementTree.Element) -> FomodGroup:
    out = FomodGroup()
    for an, av in e.attrib.items():
        match an:
            case "name":
                out.name = av
            case "type":
                match av:
                    case "SelectAny":
                        out.select = FomodGroupSelect.SelectAny
                    case "SelectAll":
                        out.select = FomodGroupSelect.SelectAll
                    case "SelectExactlyOne":
                        out.select = FomodGroupSelect.SelectExactlyOne
                    case "SelectAtMostOne":
                        out.select = FomodGroupSelect.SelectAtMostOne
                    case "SelectAtLeastOne":
                        out.select = FomodGroupSelect.SelectAtLeastOne
                    case _:
                        _raise_unknown_attr(e, av)
            case _:
                _raise_unknown_attr(e, an)
    for child in e:
        if child.tag == "plugins":
            for an, av in child.attrib.items():
                if an == "order":
                    out.order = _parse_order_attr(child, av)
                else:
                    _raise_unknown_attr(e, an)

            for ch2 in child:
                if ch2.tag == "plugin":
                    plg = _parse_plugin(ch2)
                    out.plugins.append(plg)
                else:
                    _raise_unknown_tag(child, ch2)
        else:
            _raise_unknown_tag(e, child)
    return out


def _parse_install_step(e: ElementTree.Element) -> FomodInstallStep:
    out = FomodInstallStep()
    for an, av in e.attrib.items():
        if an == "name":
            out.name = av
        else:
            _raise_unknown_attr(e, an)
    for child in e:
        match child.tag:
            case "optionalFileGroups":
                for an, av in child.attrib.items():
                    if an == "order":
                        out.order = _parse_order_attr(child, av)
                    else:
                        _raise_unknown_attr(e, an)

                for ch2 in child:
                    if ch2.tag == "group":
                        plg = _parse_group(ch2)
                        out.groups.append(plg)
                    else:
                        _raise_unknown_tag(child, ch2)
            case "visible":
                _check_no_text(child)
                _check_no_attrs(child)
                for ch2 in child:
                    out.visible.dependencies.append(_parse_some_dependency(ch2))
            case _:
                _raise_unknown_tag(e, child)
    return out


def parse_fomod_moduleconfig(root: ElementTree.Element) -> FomodModuleConfig:
    out = FomodModuleConfig()
    if root.tag != "config":
        _raise_unknown_tag(None, root)
    for child in root:
        match child.tag:
            case "moduleName":
                for an, av in child.attrib.items():
                    match an:
                        case "colour":
                            out.eye_candy_attr["colour"] = av
                        case "position":
                            out.eye_candy_attr["position"] = av
                        case _:
                            _raise_unknown_attr(child, an)
                _check_no_children(child)
                out.module_name = _text(child)
            case "moduleImage":
                _check_no_text(child)
                _check_no_children(child)
                for an, av in child.attrib.items():
                    match an:
                        case "path":
                            out.eye_candy_attr["image.path"] = av
                        case "showImage":
                            out.eye_candy_attr["image.show"] = av
                        case "height":
                            out.eye_candy_attr["image.height"] = av
                        case "showFade":
                            out.eye_candy_attr["image.showfade"] = av
                        case _:
                            _raise_unknown_attr(child, av)
            case "requiredInstallFiles":
                out.required = _parse_files_and_folders(child)
            case "installSteps":
                for an, av in child.attrib.items():
                    if an == "order":
                        out.install_steps_order = _parse_order_attr(child, av)
                    else:
                        _raise_unknown_attr(child, an)
                for ch2 in child:
                    if ch2.tag == "installStep":
                        istep = _parse_install_step(ch2)
                        out.install_steps.append(istep)
                    else:
                        _raise_unknown_tag(child, ch2)
            case "conditionalFileInstalls":
                _check_no_text(child)
                _check_no_attrs(child)
                for ch2 in child:
                    if ch2.tag == "patterns":
                        _check_no_text(ch2)
                        _check_no_attrs(ch2)
                        out.conditional_file_installs = _parse_patterns(ch2)
                    else:
                        _raise_unknown_tag(child, ch2)
            case "moduleDependencies":
                _check_no_text(child)
                _check_no_attrs(child)
                for ch2 in child:
                    if ch2.tag == "fileDependency":
                        out.module_dependencies.append(_parse_file_dependency(ch2))
                    else:
                        _raise_unknown_tag(child, ch2)
            case _:
                _raise_unknown_tag(None, child)
    return out


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
