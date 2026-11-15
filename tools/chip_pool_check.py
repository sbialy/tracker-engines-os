#!/usr/bin/env python3
"""No stealing proof for a 16 record CHIP pair: 16 notes held at once against the sum of the 16 solo renders.

    TOOLCHAIN=.../arm-none-eabi- python3 tools/chip_pool_check.py --plg chip.plg [--expect-fail] [--py PY]

The harness (tools/chip_pool_harness.cpp, test only) plays 16 voice records at defaults (note 36 + 2 k, on at block 0, off at block 28).
Scenario 0 plays them all, scenario k plays record k - 1 alone. A plugin with fewer voice objects than records hands one object to two
records and the all-at-once render differs from the sum of the solos. The WAVs are 16 bit, so the sum of 16 solos may differ by the
rounding of 16 values: the limit is 20 LSB peak. --expect-fail turns the check into the negative control (the old 12 object plg).
"""
import argparse
import os
import subprocess
import sys
import tempfile
import wave
import array

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import build_set   # noqa: E402

LSB = 20


def wav(path):
    w = wave.open(path, "rb")
    a = array.array("h")
    a.frombytes(w.readframes(w.getnframes()))
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plg", required=True)
    ap.add_argument("--py", default=sys.executable)
    ap.add_argument("--expect-fail", action="store_true")
    a = ap.parse_args()
    env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="chippool") as tmp:
        sd = os.path.join(tmp, "stage")
        build_set.stage(ROOT, sd)
        so = os.path.join(sd, "synth-open")
        import shutil
        shutil.copy(os.path.join(HERE, "chip_pool_harness.cpp"), os.path.join(so, "plug", "synth", "chip_pool_harness.cpp"))
        h = os.path.join(tmp, "pool.plg")
        r = subprocess.run([sys.executable, os.path.join(so, "plug", "build_plug.py"), "--id", "ff.test.chippool", "--kind", "offline", "--opt",
                            "-O2 -fno-builtin", "--out", h, "-I", ".", "-I", "ot", "-I", "../synth/include",
                            "plug/synth/chip_pool_harness.cpp"], cwd=so, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode:
            sys.exit("harness build failed\n" + r.stdout[-2000:])
        emu = os.path.join(so, "plug", "emu_synth.py")

        def render(s):
            out = os.path.join(tmp, "s%d.wav" % s)
            r = subprocess.run([a.py, "-I", emu, a.plg, h, "--scenario", str(s), "--base", "0x10000000", "--rw-base", "0x20027000",
                                "--wav", out], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if r.returncode or not os.path.exists(out):
                sys.exit("emulator failed in scenario %d\n%s" % (s, r.stdout[-1500:]))
            return wav(out)

        allw = render(0)
        total = [0] * len(allw)
        for k in range(1, 17):
            s = render(k)
            for i, v in enumerate(s):
                total[i] += v
        peak = max(abs(v) for v in allw)
        diff = max(abs(x - y) for x, y in zip(allw, total))
        ok = diff <= LSB
        print("CHIP pool: 16 records at once vs sum of 16 solos: peak of the mix %d / 32767, worst difference %d LSB (limit %d) -> %s" % (
            peak, diff, LSB, "equal" if ok else "DIFFERENT"))
        if peak < 1000 or peak >= 32767:
            print("the mix is silent or clipped, the proof means nothing")
            return 1
        if a.expect_fail:
            print("negative control " + ("FAILED (the old plugin was not caught)" if ok else "caught, as expected"))
            return 1 if ok else 0
        print("no stealing " + ("PASSED" if ok else "FAILED"))
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
