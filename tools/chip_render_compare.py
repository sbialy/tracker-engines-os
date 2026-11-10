#!/usr/bin/env python3
"""Render compare of chip.plg against the CHIP engine that was built into the firmware image (the bit identity gate of the move).

    TOOLCHAIN=.../arm-none-eabi- python3 tools/chip_render_compare.py --plg chip.plg --fw-tree WORKTREE_AT_0f41d40 --make-n make-n.txt \
        [--py /tmp/phzvenv/bin/python]

The reference is what the firmware itself compiled when CHIP was built in: the compile lines of engine_chip.cpp and
core/synth/engines/ChiptuneSynthVoice.cpp (make -n of the release recipe on the tree that still had CHIP, SYNTH_ENGINES with CHIP,
-O2 -ffp-contract=off) are run as they are, and those two objects behind the same plugin wrapper make chip-fwobj.plg. The harness
(plug/synth/synth_harness.cpp: a chord built up note by note and released, scenario 0 at the defaults, scenario 1 with every
parameter moved and ramped) renders both in the emulator, chip.plg at its FlexNVM home and in SRAM. Every checksum must be equal.
The worst block (instructions, 1 cycle each) of both is printed for the CPU budget.
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import build_set   # noqa: E402


def run(cmd, **kw):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)
    if r.returncode:
        sys.exit("FAILED: %s\n%s" % (" ".join(cmd), r.stdout))
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plg", required=True)
    ap.add_argument("--fw-tree", required=True, help="a tracker-ff tree that still has CHIP built in (release-1.3.0-int 0f41d40)")
    ap.add_argument("--make-n", required=True, help="make original -n of the release recipe on that tree (all engines + CHIP)")
    ap.add_argument("--py", default=sys.executable)
    ap.add_argument("--keep", help="keep the reference objects and chip-fwobj.plg here")
    a = ap.parse_args()
    tc = os.environ["TOOLCHAIN"]
    fw = os.path.abspath(a.fw_tree)
    env = dict(os.environ, TOOLCHAIN=tc)
    lines = open(a.make_n).read().splitlines()
    with tempfile.TemporaryDirectory(prefix="chipcmp") as tmp:
        sd = os.path.join(tmp, "stage")
        build_set.stage(ROOT, sd)
        so = os.path.join(sd, "synth-open")
        objs = []
        for src, oname in (("synth-open/engine_chip.cpp", "engine_chip.o"), ("core/synth/engines/ChiptuneSynthVoice.cpp", "ChiptuneSynthVoice.o")):
            hits = [l for l in lines if re.search(r'-o "[^"]*/' + re.escape(oname) + '"', l) and ("c++ " in l or "g++ " in l)]
            if not hits:
                sys.exit("no firmware compile line for " + src)
            obj = os.path.join(tmp, "fw-" + os.path.basename(src) + ".o")
            line = re.sub(r'-o\s+"?[^ "]*"?', "-o " + shlex.quote(obj), hits[0], count=1).replace("-MMD", "").replace("-MP", "")
            cwd = os.path.join(fw, "core")
            subprocess.run(line, shell=True, cwd=cwd, check=True)
            objs.append(obj)
        harness = os.path.join(tmp, "harness.plg")
        run([sys.executable, os.path.join(so, "plug", "build_plug.py"), "--id", "ff.test.synthharness", "--kind", "offline", "--opt",
             "-O2 -fno-builtin", "--out", harness, "-I", ".", "-I", "ot", "-I", "../synth/include", "plug/synth/synth_harness.cpp"], cwd=so, env=env)
        t = build_set.table()
        e = next(x for x in t["engines"] if x["id"] == "chip")
        shutil_copy = __import__("shutil").copy
        fwobj_cpp = os.path.join(so, "plug", "synth", "chip_fwobj.cpp")
        shutil_copy(os.path.join(HERE, "chip_fwobj.cpp"), fwobj_cpp)
        fwplg = os.path.join(tmp, "chip-fwobj.plg")
        run([sys.executable, os.path.join(so, "plug", "build_plug.py"), "--id", "org.opentracker.synth.chip", "--kind", "synth", "--version",
             "1.0.0", "--opt", t["wrapper_opt"], "--strip-ctors", "--synth", "6,8,8", "--out", fwplg, "-I", ".", "-I", "ot", "-I",
             "../synth/include", "-I", "../core/synth", "-I", "../core/config", "-I", "../util/include", "-I", "../util/3rdparty",
             "plug/synth/chip_plug.cpp", "plug/synth/chip_libc.cpp", "plug/synth/chip_fwobj.cpp"] + objs, cwd=so, env=env)
        if a.keep:
            os.makedirs(a.keep, exist_ok=True)
            shutil_copy(fwplg, a.keep)
            for o in objs:
                shutil_copy(o, a.keep)
        shutil_copy(os.path.join(HERE, "chip_harness.cpp"), os.path.join(so, "plug", "synth", "chip_harness.cpp"))
        harness2 = os.path.join(tmp, "chip-harness.plg")
        run([sys.executable, os.path.join(so, "plug", "build_plug.py"), "--id", "ff.test.chipharness", "--kind", "offline", "--opt",
             "-O2 -fno-builtin", "--out", harness2, "-I", ".", "-I", "ot", "-I", "../synth/include", "plug/synth/chip_harness.cpp"], cwd=so, env=env)
        emu = os.path.join(so, "plug", "emu_synth.py")
        fail = False
        for s in range(10):
            hn = harness if s < 2 else harness2   # scenarios 0 and 1 of the SDK harness, 2..9 = the eight models
            def sumof(plg, *extra):
                o = subprocess.run([a.py, "-I", emu, plg, hn, "--scenario", str(s)] + list(extra), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True).stdout
                m = re.search(r"^output checksum (\S+)", o, re.M)
                w = re.search(r"^worst block: (\d+)", o, re.M)
                return (m.group(1) if m else None), (w.group(1) if w else "?"), o
            p, pw, po = sumof(a.plg, "--base", "0x10000000", "--rw-base", "0x20027000")
            q, _, _ = sumof(a.plg, "--base", "0x1FFF6000")
            r, rw, ro = sumof(fwplg, "--base", "0x10000000", "--rw-base", "0x20027000")
            ok = p is not None and p == q == r
            fail = fail or not ok
            print("CHIP %s  scenario %d: plugin %s (FlexNVM) %s (SRAM), firmware objects %s, worst block %s / %s instructions (plugin / built in)" % (
                "ok  " if ok else "FAIL", s, p, q, r, pw, rw))
            if not ok:
                print(po[-600:])
                print(ro[-600:])
    print("render compare " + ("FAILED" if fail else "PASSED"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
