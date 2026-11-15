#!/usr/bin/env python3
"""JU6 paraphony checks on two .plg files in Unicorn (host only, never shipped).

    TOOLCHAIN=.../arm-none-eabi- python3 -I tools/ju6_para_check.py OLD.plg NEW.plg [--base BASE.plg] [--blocks 48] [--seeds 40]

OLD is the JU6 before paraphony (23 parameters), NEW the one with Chord Mode / Chord / Voicing / Strum (27), BASE (optional) the
paraphonic JU6 before the Strum parameter (26).
1. Render diff, Chord Mode Poly: random patches over the 23 old parameters (enums included), 1 voice and a 4 voice chord, with random
   Chord / Voicing values that must be ignored, plus a ramped Cutoff (p.moving). OLD and NEW must agree on every float bit.
2. Chord Mode Para with Chord 0 (the played note only) equals Poly bit for bit.
3. Paraphony is a chord: Para with a maj7 chord on a wide open filter has the fundamentals of the four notes at the level of the
   single notes (scaled by 1 / sqrt(4)), and Poly with the same one note does not.
4. Every chord of the 68 entry table and all 4 voicings render finite and stay below 4.0 (the DCO sum is scaled to one note).
5. Strum 0 is the engine as it was: Para renders of random patches, chords and voicings are bit identical to BASE, and a Strum value on
   a Poly voice or on Chord 0 changes nothing.
6. Strum: the chord notes of a Para voice start N * 2 ms apart (rounded to whole 2,901 us blocks), + up (the played note first), -
   down (the top note first), measured from the fundamentals of an open filter, a sliding Goertzel window centred on each block.
Exit 0 = all pass.
"""
import argparse
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import emu_render as R  # noqa: E402

BASE = 0x1FFF6000
CHORD_MASK = None


def chord_notes(root, idx):
    """Semitone offsets of the stock MIDI Chord table entry idx (core/source/mtChordDefs.h), read from the engine source."""
    global CHORD_MASK
    if CHORD_MASK is None:
        import re
        src = open(os.path.join(os.path.dirname(HERE), "src", "synth-open", "ot-synths", "ju6", "ju6.cpp")).read()
        body = src[src.index("kChordMask[kChordCount] = {"):]
        body = body[:body.index("};")]
        CHORD_MASK = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]{4}", body)]
        assert len(CHORD_MASK) == 68
    return [root + b for b in range(15) if CHORD_MASK[idx] >> b & 1]


def spectrum_level(sig, hz, fs=44117.647):
    """Magnitude of the strongest bin within +-3 % of hz (Hann window)."""
    n = len(sig)
    spec = np.abs(np.fft.rfft(sig * np.hanning(n)))
    f = np.fft.rfftfreq(n, 1.0 / fs)
    sel = (f > hz * 0.97) & (f < hz * 1.03)
    return float(spec[sel].max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--base", default=None)
    ap.add_argument("--blocks", type=int, default=48)
    ap.add_argument("--seeds", type=int, default=40)
    a = ap.parse_args()
    tc = os.environ["TOOLCHAIN"]
    harness = os.path.join("/tmp", "ju6_para_harness.plg")
    R.build_harness(tc, harness)
    old, new = R.Run(a.old, harness, BASE), R.Run(a.new, harness, BASE)
    assert old.nparams == 23 and new.nparams == 27, (old.nparams, new.nparams)
    for i, (o, n) in enumerate(zip(old.params, new.params)):
        assert o == n, ("parameter %d differs" % i, o, n)
    kmode, kchord, kvoic = new.pidx("Chord Mode"), new.pidx("Chord"), new.pidx("Voicing")
    assert (kmode, kchord, kvoic) == (23, 24, 25)
    kstrum = new.pidx("Strum")
    assert kstrum == 26 and new.params[kstrum] == ("Strum", 0.0, -63.0, 63.0), new.params[kstrum:]
    rng = random.Random(1)
    fails = 0

    # 1. random patches, Poly
    checked = 0
    for seed in range(a.seeds):
        over = []
        for i, (nm, df, mn, mx) in enumerate(old.params):
            if nm == "Volume":
                continue
            v = rng.uniform(mn, mx)
            if mx - mn <= 3 and float(mx).is_integer():
                v = float(rng.randint(int(mn), int(mx)))
            over.append((i, v))
        junk = [(kchord, float(rng.randint(0, 67))), (kvoic, float(rng.randint(0, 3)))]
        for voices, notes in ((1, [48]), (4, [48, 55, 60, 64]), (2, [60, 72])):
            ramp = (old.pidx("Cutoff"), 300.0, 6000.0, 8) if seed % 3 == 0 else None
            fo, _, _ = old.run(a.blocks, voices, notes, a.blocks * 2 // 3, over, ramp)
            fn, _, _ = new.run(a.blocks, voices, notes, a.blocks * 2 // 3, over + junk, ramp)
            checked += 1
            if fo.tobytes() != fn.tobytes():
                fails += 1
                print("FAIL poly render differs: seed %d voices %d" % (seed, voices))
    print("1. poly render diff: %d renders old vs new, %d differ%s" % (checked, fails, "" if fails else " (all bit identical)"))

    # 2. Para with Chord 0 == Poly
    f0, _, _ = new.run(a.blocks, 1, [60], 32, [])
    f1, _, _ = new.run(a.blocks, 1, [60], 32, [(kmode, 1.0), (kchord, 0.0)])
    ok2 = f0.tobytes() == f1.tobytes()
    print("2. Para + Chord 0 == Poly: %s" % ("PASS" if ok2 else "FAIL"))
    fails += not ok2

    # 3. fundamentals of a maj7 chord on an open filter
    blocks = 64
    patch = [(new.pidx(n), v) for n, v in (("Cutoff", 20000.0), ("Resonance", 0.0), ("Env", 0.0), ("Key Follow", 0.0), ("Sub", 0.0),
                                           ("HPF", 1.0), ("Attack", 0.0), ("Sustain", 1.0), ("LFO", 0.0), ("Vibrato", 0.0), ("PWM", 0.0))]
    root = 48
    chord_notes(root, 0)   # loads the table
    maj7 = next(i for i in range(68) if chord_notes(0, i) == [0, 4, 7, 11])
    notes = chord_notes(root, maj7)
    para, _, _ = new.run(blocks, 1, [root], blocks, patch + [(kmode, 1.0), (kchord, float(maj7))])
    sig = para[8:, 0, :].reshape(-1)
    hzs = [440.0 * 2 ** ((n - 69) / 12.0) for n in notes]
    single = []
    for n in notes:
        s, _, _ = new.run(blocks, 1, [n], blocks, patch)
        single.append(s[8:, 0, :].reshape(-1))
    ok3 = True
    for n, hz, s in zip(notes, hzs, single):
        lp, ls = spectrum_level(sig, hz), spectrum_level(s, hz)
        ratio = lp / ls
        good = 0.5 * 0.7 < ratio < 0.5 * 1.4
        ok3 = ok3 and good
        print("   note %3d %7.1f Hz  para %.1f  single %.1f  ratio %.2f (want 0.50)%s" % (n, hz, lp, ls, ratio, "" if good else "  <-- off"))
    off = [spectrum_level(sig, 440.0 * 2 ** ((root + d - 69) / 12.0) * 1.0) for d in (1, 2, 5, 6, 9)]   # notes that are not in the chord
    print("   non chord semitones (+1 +2 +5 +6 +9): %s" % ", ".join("%.1f" % x for x in off))
    plain = new.run(blocks, 1, [root], blocks, patch)[0][8:, 0, :].reshape(-1)
    miss = spectrum_level(plain, hzs[1]) / spectrum_level(sig, hzs[1])
    print("   Poly third / Para third = %.3f (the Poly voice has no third)" % miss)
    ok3 = ok3 and miss < 0.1
    print("3. chord fundamentals: %s" % ("PASS" if ok3 else "FAIL"))
    fails += not ok3

    # 4. all chords, all voicings
    worst, bad = 0.0, 0
    for ci in range(68):
        for vo in range(4):
            f, _, _ = new.run(24, 1, [60], 16, patch + [(kmode, 1.0), (kchord, float(ci)), (kvoic, float(vo))])
            if not np.isfinite(f).all():
                bad += 1
            worst = max(worst, float(np.abs(f).max()))
    ok4 = bad == 0 and worst < 4.0
    print("4. 68 chords x 4 voicings: non finite %d, peak %.3f: %s" % (bad, worst, "PASS" if ok4 else "FAIL"))
    fails += not ok4
    # 5. Strum 0 is the engine as it was
    if a.base:
        base = R.Run(a.base, harness, BASE)
        assert base.nparams == 26, base.nparams
        n5 = bad5 = 0
        for seed in range(a.seeds):
            over = []
            for i, (nm, df, mn, mx) in enumerate(base.params):
                if nm == "Volume":
                    continue
                v = rng.uniform(mn, mx)
                if mx - mn <= 3 and float(mx).is_integer():
                    v = float(rng.randint(int(mn), int(mx)))
                over.append((i, v))
            over = [(i, v) for i, v in over if i not in (kmode, kchord, kvoic)]
            over += [(kmode, 1.0), (kchord, float(rng.randint(0, 67))), (kvoic, float(rng.randint(0, 3)))]
            for voices, notes in ((1, [48]), (1, [60, 64, 67]), (4, [48, 55, 60, 64])):
                fb, _, _ = base.run(a.blocks, voices, notes, a.blocks * 2 // 3, over)
                fn, _, _ = new.run(a.blocks, voices, notes, a.blocks * 2 // 3, over + [(kstrum, 0.0)])
                n5 += 1
                if fb.tobytes() != fn.tobytes():
                    bad5 += 1
                    print("FAIL Strum 0 differs from the paraphonic base: seed %d voices %d" % (seed, voices))
        # a Strum value where there is nothing to strum: Poly, and Para with one note
        for mode, chord in ((0.0, maj7), (1.0, 0)):
            fz, _, _ = new.run(a.blocks, 1, [60], 32, patch + [(kmode, mode), (kchord, float(chord)), (kstrum, 0.0)])
            fs, _, _ = new.run(a.blocks, 1, [60], 32, patch + [(kmode, mode), (kchord, float(chord)), (kstrum, 37.0)])
            n5 += 1
            if fz.tobytes() != fs.tobytes():
                bad5 += 1
                print("FAIL Strum changes a voice with nothing to strum (mode %g chord %d)" % (mode, chord))
        ok5 = bad5 == 0
        print("5. Strum 0 vs paraphonic base: %d renders, %d differ: %s" % (n5, bad5, "PASS" if ok5 else "FAIL"))
        fails += not ok5
    else:
        print("5. skipped (no --base)")

    # 6. strum timing and order. 5add9 (0 7 14): the fundamentals are far enough apart, none is a harmonic of another
    strum_chord = next(i for i in range(68) if chord_notes(0, i) == [0, 7, 14])
    notes6 = chord_notes(root, strum_chord)
    hz6 = [440.0 * 2 ** ((n - 69) / 12.0) for n in notes6]
    nb6, win = 200, 2048

    def onsets(strum):
        f, _, _ = new.run(nb6, 1, [root], nb6, patch + [(kmode, 1.0), (kchord, float(strum_chord)), (kstrum, float(strum))])
        sig = f[:, 0, :].reshape(-1)
        out = []
        for hz in hz6:
            lv = []
            for b in range(nb6):
                c = b * 128 + 64
                lo, hi = max(0, c - win // 2), min(len(sig), c + win // 2)
                seg = sig[lo:hi] * np.hanning(hi - lo)
                t = np.arange(lo, hi)
                lv.append(abs(np.sum(seg * np.exp(-2j * np.pi * hz / 44117.647 * t))) / (hi - lo))
            lv = np.array(lv)
            ref = lv[nb6 - 40:nb6 - 8].mean()
            out.append(int(np.argmax(lv > 0.5 * ref)))
        return out

    ok6 = True
    for st in (30, -30, 15, 0):
        gap = abs(st) * 2000.0 / 2901.0
        want = [(k if st >= 0 else 2 - k) * gap for k in range(3)]
        got = onsets(st)
        base0 = min(got)
        rel = [g - base0 for g in got]
        good = all(abs(r - (w - min(want))) <= 4.5 for r, w in zip(rel, want))
        ok6 = ok6 and good
        print("   Strum %+3d: onset blocks %s, expected relative %s%s" % (st, rel, ["%.1f" % (w - min(want)) for w in want], "" if good else "  <-- off"))
    print("6. strum timing and order: %s" % ("PASS" if ok6 else "FAIL"))
    fails += not ok6
    print("RESULT %s" % ("PASS" if not fails else "FAIL (%d)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
