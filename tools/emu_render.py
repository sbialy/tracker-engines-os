#!/usr/bin/env python3
"""Render a synth engine .plg in Unicorn with a free note / parameter script, write WAVs, report peak, RMS, NaN/Inf and CPU.

    emu_render.py --plg build/engines-autof/vps.plg --id vps [--out build/renders] [--py-checks]

For every engine: 2 s notes (gate 1.5 s, then the release tail) at C3 C4 C5 at the defaults, plus the extreme settings listed in
tools/render_sets.json for that id; and the CPU of 4 voices (a chord) at the defaults and at the worst case setting. CPU numbers
are the emulator's: "instr" = executed instructions / the 522,240 cycle block (what emu_synth.py prints, a lower bound) and
"est" = instructions weighted by a Cortex-M4F cost table (loads and stores 2, taken branches 3, VDIV and VSQRT 14, VMLA 3,
others 1) plus 24 cycles for every access to the engine's work memory (SDRAM on the device, plug_abi.h). The harness is tools/render_harness.cpp (built by this script from the vendored SDK, never shipped).
"""
import argparse
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SDKP = os.path.join(ROOT, "sdk", "files", "synth-open", "plug")
sys.path.insert(0, SDKP)
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402
import capstone  # noqa: E402
import emu_synth as E  # noqa: E402
import build_set  # noqa: E402
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, Uc, UC_ARCH_ARM, UC_MODE_THUMB  # noqa: E402
from unicorn.arm_const import (UC_ARM_REG_S0, UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,  # noqa: E402
                               UC_ARM_REG_R3, UC_ARM_REG_SP, UC_CPU_ARM_CORTEX_A15)

SDRAM = 0x70000000
SDRAM_SIZE = 0x800000
WORK_MEM = SDRAM + 0x600000
CFG = SDRAM + 0x7F0000
BLOCK_CYCLES = 522240
FS = 44100


def build_harness(tc, out):
    with tempfile.TemporaryDirectory(prefix="engrender") as tmp:
        sd = os.path.join(tmp, "stage")
        build_set.stage(ROOT, sd)
        so = os.path.join(sd, "synth-open")
        subprocess.run([sys.executable, os.path.join(so, "plug", "build_plug.py"), "--id", "ff.test.renderharness", "--kind", "offline",
                        "--opt", "-O2 -fno-builtin", "--out", out, "-I", ".", "-I", "ot", "-I", "../synth/include",
                        os.path.join(HERE, "render_harness.cpp")], cwd=so, env=dict(os.environ, TOOLCHAIN=tc), check=True,
                       stdout=subprocess.DEVNULL)


md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)


def cost_of(code):
    ins = next(md.disasm(code, 0), None)
    if ins is None:
        return 1
    m = ins.mnemonic
    if m.startswith(("vdiv", "vsqrt")):
        return 14
    if m.startswith(("vmla", "vmls", "vfma", "vfms", "vnmla", "vnmls", "vfnma", "vfnms")):
        return 3
    if m.startswith(("ldr", "vldr", "str", "vstr", "ldm", "stm", "push", "pop", "vldm", "vstm", "vpush", "vpop")):
        return 2
    if m.startswith(("sdiv", "udiv")):
        return 8
    return 1


class Run:
    """One loaded engine plus the harness in Unicorn; run() renders one script and returns (audio, instr per block, est per block)."""

    def __init__(self, plg, harness, base=0x1FFF6000, files=None):
        """files: None, or a list of int16 arrays: the host then answers query(PLUG_EXT_FILES) (ABI 1.2) with a list of those waves
        (count, name "wNNNN.wav", read_wave), for the user waves of a wavetable engine"""
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A15)
        uc.mem_map(E.SRAM, E.SRAM_SIZE)
        uc.mem_map(SDRAM, SDRAM_SIZE)
        uc.reg_write(UC_ARM_REG_C1_C0_2, uc.reg_read(UC_ARM_REG_C1_C0_2) | (0xF << 20))
        uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
        eng = E.load(uc, plg, base, None)
        har = E.load(uc, harness, E.HARNESS)
        uc.mem_write(E.TRAP, b"\xfe\xe7")
        stubs = E.TRAP + 0x100
        names = ["sinf", "cosf", "tanf", "tanhf", "expf", "logf", "powf", "memcpy", "memset", "alloc", "cycles", "query", "exp2f", "log2f"]
        fnames = ["files_count", "files_name", "files_read"]
        uc.mem_write(stubs, b"\x70\x47\x00\xbf" * (len(names) + len(fnames)))
        files_ext = E.WORK + 0x1800
        if files is not None:
            uc.mem_write(files_ext, struct.pack("<4I", 16, *[(stubs + 4 * (len(names) + i)) | 1 for i in range(3)]))
        self.files_reads = 0
        self.count = [0, 0]   # instructions, estimated cycles
        self.prev = [0, 0]
        count = self.count

        def service(u, addr, size, ud):
            k = (addr - stubs) // 4
            if k >= len(names):   # PLUG_EXT_FILES
                n = fnames[k - len(names)]
                r = [u.reg_read(x) for x in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
                if n == "files_count":
                    out = len(files)
                elif n == "files_name":
                    nm = b"w%04d.wav\0" % r[0]
                    out = len(nm) - 1 if r[0] < len(files) else -1
                    if out > 0 and r[2]:
                        u.mem_write(r[1], nm[:r[2]])
                else:
                    self.files_reads += 1
                    if r[0] >= len(files):
                        out = -1
                    else:
                        w = files[r[0]]
                        part = w[r[1]:r[1] + r[3]] if r[1] < len(w) else w[:0]
                        if len(part):
                            u.mem_write(r[2], part.astype("<i2").tobytes())
                        out = len(w) if 0 < len(w) <= 2048 else -3
                u.reg_write(UC_ARM_REG_R0, out & 0xFFFFFFFF)
                return
            n = names[k]
            if n in ("sinf", "cosf"):   # hard float: argument and result in s0 (a main thread wave builder)
                x = struct.unpack("<f", struct.pack("<I", u.reg_read(UC_ARM_REG_S0) & 0xFFFFFFFF))[0]
                y = math.sin(x) if n == "sinf" else math.cos(x)
                u.reg_write(UC_ARM_REG_S0, struct.unpack("<I", struct.pack("<f", y))[0])
            elif n == "cycles":
                u.reg_write(UC_ARM_REG_R0, count[0] & 0xFFFFFFFF)
            elif n == "query":
                q = u.reg_read(UC_ARM_REG_R0)
                if q == 5:   # PLUG_EXT_FILES: NULL as on an ABI 1.1 host unless files were given
                    u.reg_write(UC_ARM_REG_R0, files_ext if files is not None else 0)
                else:
                    u.reg_write(UC_ARM_REG_R0, count[1] & 0xFFFFFFFF)
            elif n == "memset":
                d, c, ln = (u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
                u.mem_write(d, bytes([c & 255]) * ln)
            elif n == "memcpy":
                d, sr, ln = (u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
                u.mem_write(d, bytes(u.mem_read(sr, ln)))
            else:
                u.reg_write(UC_ARM_REG_R0, 0)
        uc.hook_add(UC_HOOK_CODE, service, begin=stubs, end=stubs + 4 * (len(names) + len(fnames)) - 1)
        host = E.WORK
        fields = [(15 + 2) * 4, 1, struct.unpack("<I", struct.pack("<f", 44117.64706))[0]] + [(stubs + 4 * i) | 1 for i in range(14)]
        uc.mem_write(host, struct.pack("<%dI" % len(fields), *fields))
        prev = self.prev
        cost = {}   # per Run: engines are loaded at the same base, an address means another instruction in the next one

        def tick(u, addr, size, ud):
            count[0] += 1
            c = cost.get(addr)
            if c is None:
                c = cost[addr] = cost_of(bytes(u.mem_read(addr, size)))
            if prev[0] and addr != prev[0] + prev[1]:
                c += 2   # taken branch refill
            prev[0], prev[1] = addr, size
            count[1] += c
        uc.hook_add(UC_HOOK_CODE, tick)
        self.sdram = [0]

        def mem(u, access, addr, size, value, ud):   # the engine's work memory is SDRAM on the device: plug_abi.h says 20 to 30 cycles
            self.sdram[0] += 1
            count[1] += 24
        self.mem_hook = mem
        self.uc = uc

        def call(fn, *args):
            uc.reg_write(UC_ARM_REG_SP, E.WORK + 0xE000)
            uc.reg_write(UC_ARM_REG_LR, E.TRAP | 1)
            for r, v in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args):
                uc.reg_write(r, v)
            count[0] = count[1] = 0
            prev[0] = prev[1] = 0
            uc.emu_start(fn | 1, E.TRAP)
            return uc.reg_read(UC_ARM_REG_R0)
        self.call = call
        u32 = lambda p: struct.unpack("<I", bytes(uc.mem_read(p, 4)))[0]
        desc = call(eng["entry"], host, (1 << 16) | 1)
        assert call(u32(desc + 28), E.WORK + 0x1000, host) == 0
        ext = call(u32(desc + 44), 3)
        assert ext, "no PLUG_EXT_SYNTH"
        self.ext = ext
        x = struct.unpack("<IIiiiIIIIIIIiII", bytes(uc.mem_read(ext, 60)))
        self.nparams = x[7]
        self.work = u32(ext + 60)
        self.eng = eng
        if self.work:
            call(u32(ext + 64), WORK_MEM, self.work)
            uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self.mem_hook, begin=WORK_MEM, end=WORK_MEM + self.work - 1)
        hdesc = call(har["entry"], host, (1 << 16) | 1)
        call(u32(hdesc + 28), E.WORK + 0x1100, host)
        self.runfn = call(u32(hdesc + 44), 0x7E)
        # parameter table (name, def, min, max) for overrides by name
        pt = u32(ext + 24)
        self.params = []
        for i in range(self.nparams):
            a = pt + i * 24
            nm = bytes(uc.mem_read(u32(a), 16)).split(b"\0")[0].decode()
            df, mn, mx = struct.unpack("<fff", bytes(uc.mem_read(a + 4, 12)))
            self.params.append((nm, df, mn, mx))

    def run(self, blocks, voices, notes, off_block, over, ramp=None):
        """ramp: (param index, from, to, blocks) moves one parameter linearly (start != end inside every block), None = static"""
        uc = self.uc
        cfg = struct.pack("<III4I", voices, off_block, len(over), *(notes + [0] * (4 - len(notes))))
        idx = [i for i, _ in over] + [0] * (64 - len(over))
        val = [v for _, v in over] + [0.0] * (64 - len(over))
        cfg += struct.pack("<64I", *idx) + struct.pack("<64f", *val)
        rb, ri, rf, rt = (ramp[3], ramp[0], ramp[1], ramp[2]) if ramp else (0, 0, 0.0, 0.0)
        cfg += struct.pack("<IIff", rb, ri, rf, rt)
        uc.mem_write(CFG, cfg)
        uc.mem_write(SDRAM, bytes(blocks * (2 * E.N + 2) * 4))
        self.call(self.runfn, self.ext, SDRAM, blocks, CFG)
        ob = bytes(uc.mem_read(SDRAM, blocks * 2 * E.N * 4))
        fl = np.frombuffer(ob, dtype="<f4").reshape(blocks, 2, E.N)
        per = np.frombuffer(bytes(uc.mem_read(SDRAM + blocks * 2 * E.N * 4, 8 * blocks)), dtype="<u4")
        return fl, per[:blocks], per[blocks:]

    def pidx(self, name):
        for i, p in enumerate(self.params):
            if p[0] == name:
                return i
        raise KeyError(name)


def write_wav(path, mono):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = wave.open(path, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(FS)
    w.writeframes((np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes())
    w.close()
