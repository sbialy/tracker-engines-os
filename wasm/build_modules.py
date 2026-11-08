#!/usr/bin/env python3
"""The browser twin of the engine plugins of poly-engines-os: one .wasm module and one manifest per engine (plug_wasm.h of the SDK).

    python3 wasm/build_modules.py --out DIR [--only ju6,fm4] [--engines-plg DIR] [--emsdk DIR] [--wasm-abi-major N]

The table is engines.json. Engines are built in a scratch copy of the listed files (src/ and the vendored SDK in sdk/files/, like
build_set.py), with the EDITOR HOST's compile flags (wasm.json "engine_cxxflags" must equal `common` of poly-editor
scripts/build-wasm.ts, or a module is not bit identical to the linked-in engine). Every module is checked (only the five module
imports, plug_entry and plug_wasm_abi exported, no name section, no DWARF), and the descriptor is read from the plugin's own sources
(native arm64 build), so no number is typed twice.

DIR gets <id>.wasm, <id>.json per module, NOTICE.md, the licence texts the modules name, MODULES.json (the set) and SHA256SUMS.
No dates, paths or host names in any file: a rebuild is a diff. Never runs an x86_64 binary (the descriptor dump is arm64).
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.dirname(HERE)
ROOT = ENG
sys.path.insert(0, HERE)
sys.path.insert(0, ENG)
import build_set  # noqa: E402  (stage, table, abi_of)
import wasm_common as wc  # noqa: E402

SO = os.path.join(ROOT, "sdk", "files", "synth-open")   # the vendored SDK headers (plug_abi.h, plug_wasm.h)
SOURCE_REPO = "poly-engines-os"
FIELDS = ("max_voices", "volume_param", "work_bytes", "slot_fx", "params", "sections", "macros")


def check_table(t):
    """engines.json sanity: unique ids, every row public."""
    ids = [r["id"] for r in t["engines"]]
    if len(ids) != len(set(ids)):
        sys.exit("engines.json: duplicate module ids")
    for r in t["engines"]:
        if r.get("visibility") != "public" or "repo" in r:
            sys.exit("engines.json: %s: every module of this repository is public and names no repo" % r["id"])



def native_dump(srcs, so, tmp, tag, inc, extra_for=None):
    """Descriptor JSON of a plugin from its own sources, arm64 clang. C stays C (plug_entry keeps its unmangled name)."""
    objs = []
    for src in list(srcs) + [os.path.join(HERE, "dump_desc.cpp")]:
        o = os.path.join(tmp, "%s_%s.native.o" % (tag, os.path.basename(src)))
        cxx = src.endswith(".cpp")
        fl = (["clang++", "-std=c++20", "-fno-exceptions", "-fno-rtti"] if cxx else ["clang", "-std=c11"]) + ["-arch", "arm64", "-O1", "-include",
              os.path.join(HERE, "native_compat.h")]
        fl += (extra_for or {}).get(src, []) + inc + ["-c", src, "-o", o]
        wc.run(fl, so, os.environ)
        objs.append(o)
    dump = os.path.join(tmp, tag + "_dump")
    wc.run(["clang++", "-arch", "arm64"] + objs + ["-o", dump], so, os.environ)
    return json.loads(wc.run([dump], so, os.environ))


def link_and_check(e, objs, w, so, tmp, out, env):
    wasm = os.path.join(out, e["id"] + ".wasm")
    wc.run(["emcc"] + w["linkflags"].split() + objs + ["-o", wasm], so, env)
    data = open(wasm, "rb").read()
    imps, exps = wc.imports_exports(data)
    bad = [x for x in imps if (x[0], x[1]) not in wc.ALLOWED_IMPORTS]
    if bad:
        sys.exit("%s: imports outside the module ABI: %s" % (e["id"], bad))
    names = {n for n, _ in exps}
    if not {"plug_entry", "plug_wasm_abi"} <= names:
        sys.exit("%s: exports %s lack plug_entry or plug_wasm_abi" % (e["id"], sorted(names)))
    custom = [n for sid, n, _ in wc.wasm_sections(data) if sid == 0]
    if any(n == "name" or n.startswith(".debug") or n == "sourceMappingURL" for n in custom):
        sys.exit("%s: not stripped (custom sections %s)" % (e["id"], custom))
    return data, imps, custom, wasm


def build_engine(e, t, w, sd, tmp, out, env, emver, abi, wabi, claim, plg_dir):
    so = os.path.join(sd, "synth-open")
    rtflags = w["rtflags"].split()
    if claim is not None:
        rtflags += ["-DPLUG_RT_WASM_ABI=((%d<<16)|%d)" % (claim, wabi[1])]
    rt = os.path.join(tmp, e["id"] + "_rt.o")
    wc.run(["emcc"] + rtflags + ["-I", "plug", "-c", "plug/plug_rt_wasm.c", "-o", rt], so, env)
    objs = [rt]
    inc = ["-I", ".", "-I", "ot", "-I", "../synth/include", "-I", "plug"]
    for src in (e["wrapper"], e["def"], e["dsp"]):
        o = os.path.join(tmp, "%s_%s.o" % (e["id"], os.path.basename(src)))
        # the DSP source also gets the engine's own defines (engines.json "extra", e.g. -DPLUCK_WORK_POOL: the plugin takes its work
        # pool from host memory, as it does on the device)
        wc.run(["em++"] + w["engine_cxxflags"].split() + w["moduleflags"].split() + (e["extra"].split() if src == e["dsp"] else []) +
               ["-DSYNTH_ENGINE_%s" % e["name"]] + inc + ["-c", src, "-o", o], so, env)
        objs.append(o)
    data, imps, custom, wasm = link_and_check(e, objs, w, so, tmp, out, env)
    nf = {src: e["extra"].split() for src in (e["dsp"],)}
    desc = native_dump([e["wrapper"], e["def"], e["dsp"]], so, tmp, e["id"], ["-DSYNTH_ENGINE_%s" % e["name"]] + inc, nf)
    syn = desc.pop("synth")
    if (syn["stored"], syn["patch_engine"], syn["type_id"], syn["name"]) != (e["stored"], e["patch"], e["type"], e["name"]):
        sys.exit("%s: the extension's numbers differ from engines.json" % e["id"])
    module = re.search(r"ot-synths/(\w+)/", e["dsp"])
    notice = t["notices"][e["notice"]].replace("{module}", module.group(1) if module else e["id"]) if e.get("notice") else None
    man = {
        "format": "ffmod", "format_version": 1, "id": "org.opentracker.synth." + e["id"], "kind": "synth", "name": e["name"],
        "version": e["version"], "abi": "%d.%d" % abi[:2], "min_host": 1, "wasm_abi": "%d.%d" % (claim if claim is not None else wabi[0], wabi[1]),
        "visibility": e["visibility"], "source_repo": SOURCE_REPO,
        "licence": e["licence"], "author": e.get("author", "tracker-ff"),
        "synth": {"stored": e["stored"], "patch_engine": e["patch"], "type_id": e["type"]},
        "build": {"emcc": emver, "cxxflags": w["engine_cxxflags"], "moduleflags": w["moduleflags"], "rtflags": w["rtflags"], "linkflags": w["linkflags"],
                  "extra": e["extra"], "editor_flags_from": w["editor_flags_from"]},
        "files": {"wasm": {"name": e["id"] + ".wasm", "size": len(data), "sha256": wc.sha(wasm)}},
        "imports": sorted("%s.%s" % (m, f) for m, f, _ in imps), "custom_sections": custom,
    }
    if notice:
        man["notice"] = notice
    man["synth"].update({k: syn[k] for k in FIELDS})
    man["descriptor"] = desc
    if plg_dir and os.path.exists(os.path.join(plg_dir, e["id"] + ".plg")):
        plg = os.path.join(plg_dir, e["id"] + ".plg")
        man["files"]["plg"] = {"name": e["id"] + ".plg", "size": os.path.getsize(plg), "sha256": wc.sha(plg)}
    return man, len(data), notice




def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--only")
    ap.add_argument("--engines-plg", help="the finished engine .plg set (build_set.py): its sha256 goes into the manifests")
    ap.add_argument("--emsdk", default=os.environ.get("EMSDK") or next((p for p in (os.path.join(ROOT, "agt", "emsdk"), os.path.expanduser("~/prj/poly/agt/emsdk")) if os.path.isdir(p)), "emsdk"),
                    help="emsdk 6.0.13 (default: $EMSDK, <repo>/agt/emsdk, ~/prj/poly/agt/emsdk)")
    ap.add_argument("--wasm-abi-major", type=int, help="claim another module ABI major (refusal test only)")
    a = ap.parse_args()
    t = build_set.table()
    check_table(t)
    if not a.out:
        ap.error("--out is required")
    w = json.load(open(os.path.join(HERE, "wasm.json")))
    env, up = wc.emsdk_env(a.emsdk)
    emver = wc.run([os.path.join(up, "emcc"), "--version"], ROOT, env).splitlines()[0]
    if w["emcc"] not in emver:
        sys.exit("wasm.json pins emcc %s, found: %s" % (w["emcc"], emver))
    maj, mi, _ = build_set.abi_of(os.path.join(SO, "plug", "plug_abi.h"))
    wtext = open(os.path.join(SO, "plug", "plug_wasm.h")).read()
    wabi = (int(wtext.split("#define PLUG_WASM_ABI_MAJOR")[1].split()[0]), int(wtext.split("#define PLUG_WASM_ABI_MINOR")[1].split()[0]))
    out = os.path.abspath(a.out)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    engines = [e for e in t["engines"] if not a.only or e["id"] in a.only.split(",")]
    recs, notices, licences = [], [], set()
    with tempfile.TemporaryDirectory(prefix="modwasm") as tmp:
        sd = os.path.join(tmp, "stage")
        build_set.stage(ROOT, sd)
        for e in engines:
            man, size, notice = build_engine(e, t, w, sd, tmp, out, env, emver, (maj, mi), wabi, a.wasm_abi_major, a.engines_plg)
            recs.append(man)
            notices.append((e["id"], notice))
            licences.update(e["licence_files"])
            print("%-7s engine %-7s %6d B  %s" % (e["id"], e["visibility"], size, ",".join(man["custom_sections"]) or "none"))
    for m in recs:
        with open(os.path.join(out, m["files"]["wasm"]["name"].replace(".wasm", ".json")), "w") as f:
            json.dump(m, f, indent=1)
            f.write("\n")
    for lf in sorted(licences):
        shutil.copy(os.path.join(ROOT, lf), os.path.join(out, os.path.basename(lf)))
    with open(os.path.join(out, "NOTICE.md"), "w") as f:
        f.write("# Notices for the browser modules in this directory\n\nShip every module with this file and the licence texts it names.\n\n")
        for i, n in notices:
            f.write("## %s\n\n%s\n\n" % (i, n or "Own code of tracker-ff, MIT licence (LICENSE-tracker-ff-MIT.txt)."))
    with open(os.path.join(out, "MODULES.json"), "w") as f:
        json.dump({"set": SOURCE_REPO, "set_version": t["set_version"], "abi": "%d.%d" % (maj, mi), "wasm_abi": "%d.%d" % wabi, "emcc": emver,
                   "modules": [{"id": m["files"]["wasm"]["name"][:-5], "plug_id": m["id"], "kind": m["kind"], "name": m["name"], "version": m["version"],
                                "visibility": m["visibility"], "licence": m["licence"], "wasm": m["files"]["wasm"]} for m in recs]}, f, indent=1)
        f.write("\n")
    with open(os.path.join(out, "SHA256SUMS"), "w") as f:
        for p in sorted(os.listdir(out)):
            if p != "SHA256SUMS":
                f.write("%s  %s\n" % (wc.sha(os.path.join(out, p)), p))
    print("%s: %d engine modules" % (out, len(recs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
