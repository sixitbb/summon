# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko

import re
import xml.etree.ElementTree as ElementTree

from summonmm.common import *
from summonmm.helpers.project_config import LocalProjectConfig
from summonmm.plugins.globaltools import (
    GlobalToolPluginBase,
    ResolvedVFS,
    CouldBeProducedByGlobalTool,
)


class _BodySlideToolPluginContext:
    rel_output_files: dict[str, int]
    target_files: set[str]

    def __init__(self) -> None:
        self.rel_output_files = {}
        self.target_files = set()


def _parse_osp(fname: str) -> list[str]:
    try:
        tree = ElementTree.parse(fname)
        root = tree.getroot()
        if root.tag.lower() != "slidersetinfo":
            warn("Unexpected root tag {} in {}".format(root.tag, fname))
            return []
        out: list[str] = []
        for ch in root:
            if ch.tag.lower() == "sliderset":
                slidersetname = ch.attrib.get("name", "?")
                outputfile = None
                outputpath = None
                for ch2 in ch:
                    if ch2.tag.lower() == "outputfile":
                        if outputfile is not None:
                            warn(
                                "Duplicate <OutputFile> tag for {} in {}".format(
                                    slidersetname, fname
                                )
                            )
                        else:
                            assert ch2.text is not None
                            outputfile = ch2.text.strip()
                    elif ch2.tag.lower() == "outputpath":
                        if outputpath is not None:
                            warn(
                                "Duplicate <OutputPath> tag for {} in {}".format(
                                    slidersetname, fname
                                )
                            )
                        else:
                            assert ch2.text is not None
                            outputpath = ch2.text.strip()

                if outputfile is None or outputpath is None:
                    warn(
                        "Missing <OutputFile> or <OutputPath> tag for {} in {}".format(
                            slidersetname, fname
                        )
                    )
                else:
                    path = "data\\" + outputpath + "\\" + outputfile
                    out.append(path.lower())
        return out
    except Exception as e:
        warn("Error parsing {}: {}={}".format(fname, type(e), e))
        return []


class BodySlideGlobalToolPlugin(GlobalToolPluginBase):
    def name(self) -> str:
        return "BodySlide"

    def supported_games(self) -> list[str]:
        return ["SKYRIM"]

    def extensions(self) -> list[str]:
        return [".tri", ".nif"]

    def create_context(self, cfg: LocalProjectConfig, resolvedvfs: ResolvedVFS) -> Any:
        ctx: _BodySlideToolPluginContext = _BodySlideToolPluginContext()
        osppattern = re.compile(
            r"data\\CalienteTools\\Bodyslide\\SliderSets\\.*\.osp$", re.IGNORECASE
        )
        for relpath in resolvedvfs.all_target_files():
            assert relpath not in ctx.target_files
            ext = os.path.splitext(relpath)[1]
            if ext in [".tri", ".nif"]:
                ctx.target_files.add(relpath)
            if osppattern.match(relpath):
                srcfiles = resolvedvfs.files_for_target(relpath)
                assert len(srcfiles) > 0
                modified = _parse_osp(srcfiles[-1].file_path)
                ctx.rel_output_files |= {m: 1 for m in modified}
        return ctx

    def could_be_produced(
        self, context: Any, srcpath: str, targetpath: str
    ) -> CouldBeProducedByGlobalTool:
        assert isinstance(context, _BodySlideToolPluginContext)
        f, ext = os.path.splitext(targetpath)
        assert ext in self.extensions()
        if ext == ".tri":
            if f in context.rel_output_files:
                return CouldBeProducedByGlobalTool.WithCurrentConfig
            f0 = f + "_0.nif"
            f1 = f + "_1.nif"
            if f0 in context.target_files and f1 in context.target_files:
                return CouldBeProducedByGlobalTool.Maybe

            fnif = f + ".nif"
            if fnif in context.target_files:
                return CouldBeProducedByGlobalTool.Maybe
            return CouldBeProducedByGlobalTool.NotFound

        assert ext == ".nif"
        if f.endswith("_0") or f.endswith("_1"):
            if f[:-2] in context.rel_output_files:
                return CouldBeProducedByGlobalTool.WithCurrentConfig
            f0 = f[:-2] + "_0.nif"
            f1 = f[:-2] + "_1.nif"
            ftri = f[:-2] + ".tri"
            if (
                f0 in context.target_files
                and f1 in context.target_files
                and ftri in context.target_files
            ):
                return CouldBeProducedByGlobalTool.Maybe
            return CouldBeProducedByGlobalTool.NotFound
        else:
            if f in context.rel_output_files:
                return CouldBeProducedByGlobalTool.WithCurrentConfig
            ftri = f + ".tri"
            if ftri in context.target_files:
                return CouldBeProducedByGlobalTool.Maybe
            return CouldBeProducedByGlobalTool.NotFound


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
