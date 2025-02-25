# Copyright (C) 2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Sherry Ignatchenko


"""
summonmm.gitdata.stable_json: newer and more flexible mechanism to store github-friendly JSON files. 
"""

from summonmm.common import *


class StableJsonFlags(Flag):
    NoFlags = 0x0
    Unsorted = 0x1


class _StableJsonSingleTypeDescriptor:
    typ: Any
    flags: StableJsonFlags
    default: Any

    def __init__(self, typ: Any, flags: StableJsonFlags, default: Any) -> None:
        self.typ = typ
        self.flags = flags
        self.default = default


_PRIMITIVE_TYPES = (str, int, float, bytes, bool, IntFlag, IntEnum)

type StableJsonTypeDescriptor = (
    tuple[str, str | None]
    | tuple[
        str, str | None, Any
    ]  # 3rd parameter here can be either item type (for lists/dicts), or default value (for primitive types)
    | tuple[str, str | None, type, StableJsonFlags]
)

type StableJsonJsonPrimitive = str | int | float | bytes | bool | int
type StableJsonJsonSomething = (
    StableJsonJsonPrimitive
    | list[StableJsonJsonSomething]
    | dict[StableJsonJsonSomething, StableJsonJsonSomething]
)
type StableJsonJsonDict = dict[str, StableJsonJsonSomething]


def _get_type(
    target4typeonly: Any, sj: StableJsonTypeDescriptor
) -> _StableJsonSingleTypeDescriptor:
    if len(sj) == 2:
        return _StableJsonSingleTypeDescriptor(None, StableJsonFlags.NoFlags, None)
    elif len(sj) == 3:
        if isinstance(target4typeonly, _PRIMITIVE_TYPES):
            return _StableJsonSingleTypeDescriptor(None, StableJsonFlags.NoFlags, sj[2])
        else:
            assert isinstance(target4typeonly, (dict, list))
            return _StableJsonSingleTypeDescriptor(sj[2], StableJsonFlags.NoFlags, None)
    else:
        assert len(sj) == 4
        return _StableJsonSingleTypeDescriptor(sj[2], sj[3], None)


def _create_from_typ(typ: Any) -> Any:
    if hasattr(typ, "for_summon_stable_json_load"):
        return typ.for_summon_stable_json_load()
    else:
        return typ()


def _validate_sjdecl(obj: Any) -> None:
    assert hasattr(obj, "SUMMON_JSON")
    sjlist = obj.SUMMON_JSON
    for sj in sjlist:
        if __debug__ and sj[0] not in obj.__dict__:
            assert False
        assert sj[1] is None or isinstance(sj[1], str)
        if sj[1] is None:
            assert len(sjlist) == 1
        target = obj.__dict__[sj[0]]
        if isinstance(target, list):
            if __debug__ and len(sj) != 3 and len(sj) != 4:
                assert False
            if len(sj) == 4:
                assert isinstance(sj[3], StableJsonFlags)
            instance = _create_from_typ(sj[2])
            assert isinstance(instance, _PRIMITIVE_TYPES) or hasattr(
                instance, "SUMMON_JSON"
            )
        elif isinstance(target, dict):
            assert len(sj) == 3 or len(sj) == 4
            if len(sj) == 4:
                assert isinstance(sj[3], StableJsonFlags)
            assert isinstance(sj[2], tuple)
            assert len(sj[2]) == 2
            instance0 = _create_from_typ(sj[2][0])
            instance1 = _create_from_typ(sj[2][1])
            assert isinstance(instance0, _PRIMITIVE_TYPES) or hasattr(
                instance0, "SUMMON_JSON"
            )
            assert isinstance(instance1, _PRIMITIVE_TYPES) or hasattr(
                instance1, "SUMMON_JSON"
            )
        elif hasattr(target, "SUMMON_JSON"):
            assert len(sj) == 2
        else:
            if (
                __debug__
                and target is not None
                and not isinstance(target, _PRIMITIVE_TYPES)
            ):
                assert False
            assert len(sj) == 2 or len(sj) == 3
            if len(sj) == 3:
                assert type(sj[2]) == type(target)


def _to_sort_key(jsonobj: Any, sjlist: list[StableJsonTypeDescriptor] | None) -> Any:
    if sjlist is not None:
        for sj in sjlist:
            if sj[1] in jsonobj:
                return _to_sort_key(jsonobj[sj[1]], None)
        assert False  # no field found
    elif isinstance(jsonobj, list):
        key = ""
        item: Any
        for item in jsonobj:
            if len(key) != 0:
                key += "|"
            key = key + _to_sort_key(item, None)
        return key
    elif isinstance(jsonobj, str):
        return "s" + jsonobj
    elif isinstance(jsonobj, int):
        return "i{:09d}".format(jsonobj)
    else:
        assert False


def _stable_json_list(
    data: list[Any], typ: _StableJsonSingleTypeDescriptor
) -> list[StableJsonJsonSomething]:
    assert isinstance(data, list)
    if len(data) == 0:
        return []
    d0 = data[0]
    if isinstance(d0, str):
        if __debug__:
            for i in data:
                assert isinstance(i, str)
        return data if (typ.flags & StableJsonFlags.Unsorted) else sorted(data)
    elif isinstance(d0, int):
        if __debug__:
            for i in data:
                assert isinstance(i, int)
        return data if (typ.flags & StableJsonFlags.Unsorted) else sorted(data)
    elif isinstance(d0, bytes):
        if __debug__:
            for i in data:
                assert isinstance(i, bytes)
        data1 = [to_json_hash(x) for x in data]
        data2: list[str] = (
            data1 if (typ.flags & StableJsonFlags.Unsorted) else sorted(data1)
        )
        return data2  # type: ignore (list[str] IS valid list[StableJsonJsonSomething])

    if __debug__:
        if not hasattr(d0, "SUMMON_JSON"):
            assert False
        for i in data:
            assert d0.SUMMON_JSON == i.SUMMON_JSON
    data3: list[StableJsonJsonSomething] = [_to_stable_json(d) for d in data]
    if typ.flags & StableJsonFlags.Unsorted:
        return data3
    else:
        # info(repr(data2))
        return sorted(data3, key=lambda x: _to_sort_key(x, d0.SUMMON_JSON))


def _to_stable_json_object(data: Any) -> StableJsonJsonSomething:
    if hasattr(data, "to_summon_stable_json"):
        return data.to_summon_stable_json()
    assert hasattr(data, "SUMMON_JSON")
    if __debug__:
        _validate_sjdecl(data)
    if hasattr(data, "summon_stable_json_make_canonical"):
        data.summon_stable_json_make_canonical()
    out: dict[str, StableJsonJsonSomething] = {}
    di = data.__dict__
    for sj in data.SUMMON_JSON:  # len(sj) can be 2 or 3
        field = sj[0]
        jfield = sj[1]
        v = di[field]
        if v is None:
            pass
        elif isinstance(v, list) and len(v) == 0:  # type: ignore (rather spurious warning; while type is not entirely defined, its len is well-defined)
            pass
        elif isinstance(v, dict) and len(v) == 0:  # type: ignore (same as above)
            pass
        else:
            if jfield is None:
                assert len(data.SUMMON_JSON) == 1
                return _to_stable_json(v, _get_type(v, sj))
            ftyp = _get_type(v, sj)
            if v != ftyp.default:
                vjson = _to_stable_json(v, ftyp)
                out[jfield] = vjson
    out2: dict[StableJsonJsonSomething, StableJsonJsonSomething] = out  # type: ignore (dict[str,StableJsonJsonSomething] IS valid dict[StableJsonJsonSomething,StableJsonJsonSomething])
    return out2


def _to_stable_json(
    data: Any, typ: _StableJsonSingleTypeDescriptor | None = None
) -> StableJsonJsonSomething:
    assert data is not None
    if hasattr(data, "SUMMON_JSON") or hasattr(data, "to_summon_stable_json"):
        return _to_stable_json_object(data)
    elif isinstance(data, list):
        assert typ is not None
        data1: list[Any] = data
        return _stable_json_list(data1, typ)
    elif isinstance(data, dict):
        data2: dict[Any, Any] = data
        return _to_stable_json_dict(data2)
    elif isinstance(data, bytes):
        return to_json_hash(data)
    elif isinstance(data, IntEnum):
        return int(data)
    elif isinstance(data, IntFlag):
        return int(data)
    elif isinstance(data, _PRIMITIVE_TYPES):
        return data
    assert False


def _to_stable_json_dict(
    data: dict[Any, Any], typ: _StableJsonSingleTypeDescriptor | None = None
) -> dict[StableJsonJsonSomething, StableJsonJsonSomething]:
    if len(data) == 0:
        return {}
    k0 = next(iter(data))  # just any key; all others are assumed to have the same type
    if hasattr(k0, "SUMMON_JSON"):
        sjlist = k0.SUMMON_JSON
    else:
        sjlist = None
    data3 = sorted(
        [(_to_stable_json(k), _to_stable_json(v)) for k, v in data.items()],
        key=lambda x: _to_sort_key(x[0], sjlist),
    )
    return {k: v for k, v in data3}


def to_stable_json(data: Any) -> StableJsonJsonSomething:
    """
    data: SUMMON_JSON-compliant object
    """
    return _to_stable_json_object(data)


def write_stable_json(fname: str, data: StableJsonJsonSomething) -> None:
    with open_git_data_file_for_writing(fname) as f:
        write_stable_json_opened(f, data)


def write_stable_json_opened(f: typing.TextIO, data: StableJsonJsonSomething) -> None:
    # noinspection PyTypeChecker
    json.dump(data, f, indent=1)


def _from_stable_json_primitive(data: Any, target4typeonly: Any) -> Any:
    if isinstance(target4typeonly, bytes):
        raise_if_not(isinstance(data, str))
        return from_json_hash(data)
    elif isinstance(target4typeonly, (IntEnum, IntFlag)):
        raise_if_not(isinstance(data, (str, int)))
        typ = type(target4typeonly)
        return typ(int(data))
    elif isinstance(target4typeonly, str):
        raise_if_not(isinstance(data, str))
        return data
    elif isinstance(
        target4typeonly, bool
    ):  # MUST be before int, as isinstance(bool,int) is True
        raise_if_not(isinstance(data, (bool, int)))
        return bool(data)
    elif isinstance(target4typeonly, int):
        raise_if_not(isinstance(data, (str, int)))
        return int(data)
    elif isinstance(target4typeonly, float):
        raise_if_not(isinstance(data, (str, int, float)))
        return float(data)
    else:
        assert False


def _from_stable_json(
    target: Any,
    data: Any,
    typ: _StableJsonSingleTypeDescriptor | None = None,
    ignore_unknown: bool = False,
) -> None:
    assert target is not None
    if hasattr(target, "from_summon_stable_json"):
        return target.from_summon_stable_json(data)
    if hasattr(target, "SUMMON_JSON"):
        if __debug__:
            _validate_sjdecl(target)
        skipname = len(target.SUMMON_JSON) == 1 and target.SUMMON_JSON[0][1] is None
        raise_if_not(skipname or isinstance(data, dict))
        if __debug__:
            if skipname:
                pass
            elif not ignore_unknown:
                assert isinstance(data, dict)
                known_keys = set([sj[1] for sj in target.SUMMON_JSON])
                key: Any
                for key in data:
                    assert key in known_keys
        tgdi = target.__dict__
        for sj in target.SUMMON_JSON:  # len(sj) can be 2 or 3
            field = sj[0]
            assert field in tgdi
            jfield = sj[1]
            tgt = tgdi[field]
            sjtyp = _get_type(tgt, sj)
            if hasattr(tgt, "SUMMON_JSON"):
                assert sjtyp.flags == StableJsonFlags.NoFlags
                if jfield is None:
                    assert len(target.SUMMON_JSON) == 1
                    _from_stable_json(tgt, data, sjtyp)
                else:
                    if jfield not in data:
                        pass
                    else:
                        _from_stable_json(tgt, data[jfield], sjtyp)
            elif isinstance(tgt, list):
                tgt1: list[Any] = tgt
                assert len(tgt1) == 0
                if jfield is None:
                    assert len(target.SUMMON_JSON) == 1
                    _from_stable_json(tgt, data, sjtyp)
                elif jfield not in data:
                    assert len(tgt1) == 0
                    pass  # leave tgt as []
                else:
                    _from_stable_json(tgt, data[jfield], sjtyp)
            elif isinstance(tgt, dict):
                tgt2: dict[Any, Any] = tgt
                assert len(tgt2) == 0
                assert sjtyp.flags == StableJsonFlags.NoFlags
                if jfield is None:
                    assert len(target.SUMMON_JSON) == 1
                    _from_stable_json(tgt2, data, sjtyp)
                elif jfield not in data:
                    assert len(tgt2) == 0
                    pass  # leave tgt as {}
                else:
                    _from_stable_json(tgt2, data[jfield], sjtyp)
            else:
                if __debug__:
                    if not isinstance(tgt, _PRIMITIVE_TYPES):
                        assert False
                    assert sjtyp.flags == StableJsonFlags.NoFlags
                    if isinstance(tgt, (int, float)):
                        pass  # can have any value, even unrelated to sjtyp.default
                    else:
                        assert isinstance(tgt, (str, bytes))
                        assert len(tgt) == 0
                    # else:
                    #    assert False
                assert jfield is not None
                if jfield not in data:
                    tgdi[field] = sjtyp.default
                else:
                    tgdi[field] = _from_stable_json_primitive(data[jfield], tgt)
                    assert type(tgdi[field]) == type(tgt)
        if hasattr(target, "summon_stable_json_make_canonical"):
            target.summon_stable_json_make_canonical()
    elif isinstance(target, list):
        target1: list[Any] = target
        assert len(target1) == 0
        raise_if_not(isinstance(data, list))
        for d in data:
            assert typ is not None
            e = _create_from_typ(typ.typ)
            if isinstance(e, _PRIMITIVE_TYPES):
                target1.append(_from_stable_json_primitive(d, e))
            else:
                assert hasattr(e, "SUMMON_JSON")
                target1.append(e)
                _from_stable_json(e, d)
    elif isinstance(target, dict):
        target2: dict[Any, Any] = target
        assert len(target2) == 0
        raise_if_not(isinstance(data, dict))
        for k, v in data.items():
            assert typ is not None
            typ0, typ1 = typ.typ
            e0 = _create_from_typ(typ0)
            e1 = _create_from_typ(typ1)
            assert isinstance(e0, _PRIMITIVE_TYPES)
            ktgt = _from_stable_json_primitive(k, e0)
            if isinstance(e1, _PRIMITIVE_TYPES):
                vtgt = _from_stable_json_primitive(v, e1)
            else:
                assert hasattr(e1, "SUMMON_JSON")
                vtgt = e1
                _from_stable_json(e1, v)
            assert ktgt not in target2
            target2[ktgt] = vtgt
    else:
        assert not isinstance(
            data, _PRIMITIVE_TYPES
        )  # no primitive types in _from_stable_json
        assert False


def from_stable_json(target: Any, data: StableJsonJsonSomething) -> None:
    return _from_stable_json(target, data)


"""
The 3-Clause BSD License

Copyright (C) 2025 Six Impossible Things Before Breakfast Limited.

Contributors: Sherry Ignatchenko

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
