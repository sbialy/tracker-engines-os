#!/usr/bin/env python3
"""JU6 chords 68..76 (madd9 add9 9 m9 maj9 6/9 7#9 7b9 7b5, firmware 2.0.0 plug_chord.h) in the Unicorn emulator (host only, never shipped).

    TOOLCHAIN=... python3 -I tools/ju6_chord77_check.py OLD.plg NEW.plg [--fw TRACKER_FF_CHECKOUT]

OLD is the pinned release build (v1.4.0, JU6 1.1.0, 68 chords), NEW the build with 77.
1. the table: ju6.cpp kChordMask has 77 masks equal to the firmware's chordDef (--fw), at most 4 tones, the 77 Chord names equal the
   firmware's chordDefName (interval digits, entries 68..76 are 37E 47E 4AE 3AE 4BE 49E 4AF 4AD 46A).
2. every chord of the 77, all 4 voicings, Para: finite, below 4.0. For the 68..76 (Close): the fundamentals of the (up to) four notes of
   an open filter are present at 1 / sqrt(4) of the single note, as in ju6_para_check.py section 3.
3. the old release is untouched: chords 0..67, 4 voicings, Para and Poly, renders of OLD and NEW are bit identical. Poly ignores
   Chord 68..76 (bit identical to Chord 0).
Exit 0 = all pass.
"""
import argparse
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import emu_render as R  # noqa: E402

BASE = 0x1FFF6000
ROOT = os.path.dirname(HERE)


def level(sig, hz, fs=44117.647):
    n = len(sig)
    spec = np.abs(np.fft.rfft(sig * np.hanning(n)))
    f = np.fft.rfftfreq(n, 1.0 / fs)
    sel = (f > hz * 0.97) & (f < hz * 1.03)
    return float(spec[sel].max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--fw", default=os.path.expanduser("~/prj/poly-wt/rel200-int"))
    a = ap.parse_args()
    bad = 0

    def fail(m):
        nonlocal bad
        bad += 1
        print("FAIL", m)

    harness = os.path.join("/tmp", "ju6_chord77_harness.plg")
    R.build_harness(os.environ["TOOLCHAIN"], harness)
    old, new = R.Run(a.old, harness, BASE), R.Run(a.new, harness, BASE)
    assert old.nparams == new.nparams == 27, (old.nparams, new.nparams)
    kmode, kchord, kvoic = new.pidx("Chord Mode"), new.pidx("Chord"), new.pidx("Voicing")

    # 1. the table
    src = open(os.path.join(ROOT, "src", "synth-open", "ot-synths", "ju6", "ju6.cpp")).read()
    body = src[src.index("kChordMask[kChordCount] = {"):]
    mine = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]{4}", body[:body.index("};")])]
    t = open(os.path.join(a.fw, "core", "source", "mtChordDefs.h")).read()
    fw = [int(x, 2) for x in re.findall(r"0b([01]{16}),", t)]
    if len(fw) != 77 or mine != fw:
        fail("ju6.cpp kChordMask (%d) differs from chordDef (%d)" % (len(mine), len(fw)))
    else:
        print("ok   table: 77 masks equal to the firmware's chordDef, max %d notes" % max(bin(m).count("1") for m in mine))
    if max(bin(m).count("1") for m in mine) > 4:
        fail("a chord with more than 4 notes")
    names_fw = re.findall(r'"([ 0-9A-F\-]{3})"', t[t.index("chordDefName"):t.index("chordShortName")])
    names_fw = [n.strip() for n in names_fw]
    names_me = re.findall(r'"([0-9A-F\-]{2,3})"', open(os.path.join(ROOT, "src", "synth-open", "engine_ju6.cpp")).read().split("kChordName")[1].split("};")[0])
    names_me = [n.replace("---", "---") for n in names_me]
    if len(names_me) != 77 or names_me != names_fw:
        fail("Chord names differ from chordDefName (%d vs %d): %s" % (len(names_me), len(names_fw), names_me[66:]))
    else:
        print("ok   names: 77 equal to chordDefName, 68..76 = %s" % " ".join(names_me[68:]))

    patch = [(new.pidx(n), v) for n, v in (("Cutoff", 20000.0), ("Resonance", 0.0), ("Env", 0.0), ("Key Follow", 0.0), ("Sub", 0.0),
                                           ("HPF", 1.0), ("Attack", 0.0), ("Sustain", 1.0), ("LFO", 0.0), ("Vibrato", 0.0), ("PWM", 0.0))]
    print("     Chord parameter:", new.params[kchord])

    # 2. every chord, voicing: finite and bounded. 68..76: the fundamentals
    root, blocks = 48, 64
    worst, nonfin = 0.0, 0
    for ci in range(77):
        for vo in range(4):
            f, _, _ = new.run(24, 1, [60], 16, patch + [(kmode, 1.0), (kchord, float(ci)), (kvoic, float(vo))])
            nonfin += not np.isfinite(f).all()
            worst = max(worst, float(np.abs(f).max()))
    print("2a. 77 chords x 4 voicings: non finite %d, peak %.3f: %s" % (nonfin, worst, "PASS" if not nonfin and worst < 4.0 else "FAIL"))
    if nonfin or worst >= 4.0:
        fail("non finite or loud")
    single = {}
    for ci in range(68, 77):
        notes = [root + b for b in range(16) if mine[ci] >> b & 1]
        para, _, _ = new.run(blocks, 1, [root], blocks, patch + [(kmode, 1.0), (kchord, float(ci))])
        sig = para[8:, 0, :].reshape(-1)
        ratios = []
        for n in notes:
            if n not in single:
                s, _, _ = new.run(blocks, 1, [n], blocks, patch)
                single[n] = s[8:, 0, :].reshape(-1)
            hz = 440.0 * 2 ** ((n - 69) / 12.0)
            ratios.append(level(sig, hz) / level(single[n], hz))
        # 4 notes: 0.5 each. The root has the harmonics of the other notes on top, so the window is wide
        ok = len(notes) == 4 and all(0.5 * 0.6 < r < 0.5 * 1.6 for r in ratios)
        print("%s   chord %d notes %s ratios %s (want 0.50)" % ("ok  " if ok else "FAIL", ci, notes, " ".join("%.2f" % r for r in ratios)))
        if not ok:
            fail("chord %d fundamentals" % ci)

    # 3. the old 68 are untouched
    def rnd(r, ci, vo, mode):
        return r.run(48, 1, [60], 32, patch + [(kmode, mode), (kchord, float(ci)), (kvoic, float(vo))])[0].tobytes()

    n3 = d3 = 0
    for ci in range(68):
        for vo in range(4):
            for mode in (1.0, 0.0):
                n3 += 1
                if rnd(old, ci, vo, mode) != rnd(new, ci, vo, mode):
                    d3 += 1
                    fail("render differs from the pinned build: Chord %d Voicing %d Mode %g" % (ci, vo, mode))
    print("3. old 68 chords x 4 voicings x Para/Poly: %d renders, %d differ from the pinned v1.4.0 build" % (n3, d3))
    p0 = rnd(new, 0, 2, 0.0)
    pn = sum(rnd(new, ci, 2, 0.0) != p0 for ci in range(68, 77))
    if pn:
        fail("Poly renders of Chord 68..76 differ from Chord 0 (%d)" % pn)
    else:
        print("ok   Poly ignores Chord 68..76 (bit identical to Chord 0)")
    print("RESULT:", "PASS" if not bad else "FAIL (%d)" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
