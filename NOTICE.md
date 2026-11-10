# Notices

tracker-engines-os holds the public synth engine plugins of tracker-ff. Every `.plg`, `.plgi`, `.wasm` and manifest built here ships with
this file and the licence texts in `licenses/` (the build copies the ones a module names next to it).

## 1. opentracker-synths (the ten module engines)

* **Location**: `src/synth-open/ot-synths/<module>/<module>.{cpp,h}` for `ju6` (JU6), `fm4` (FM4), `dtype` (D-Type), `cstype` (CS-Type),
  `atype` (A-Type), `ttype` (T-Type drums), `eight` (8-Type), `hand` (Hand-Type), `btype` (B-Type) and `arc` (Arc-Type). Each file is
  unmodified apart from a two line provenance notice at the top. `src/synth-open/engine_<name>.cpp` carries the parameter ranges,
  labels, value formats, enum names and sections of the module's descriptor (`modules/<name>/src/<name>_desc.cpp`), marked in its
  header. The default macros and the edit curves in those files are tracker-ff's own choice. The module wrappers (`*_module.cpp`)
  and the descriptors themselves are not compiled.
* **Source**: https://github.com/opentracker-fw/opentracker-synths (commit eb150a5f741b, `modules/<name>`)
* **License**: MIT, Copyright (c) 2026 Marcin Spoczynski, text in `licenses/LICENSE-OpenTracker-synths-MIT.txt`. The repository
  states it contains no Polyend code.
* **Note**: D-Type's OpenTracker engine id (0x82) is the id of tracker-ff's PHZ engine, so D-Type is keyed 0xA2 in the picker and in
  `.patch` files, the same as the browser editor stores it (the engine code itself is unchanged).

## 2. OpenTracker 3.x headers (vendored with the SDK)

* **Location**: `sdk/files/synth-open/ot/` (`audio/synth_engine.h`, `audio/bbd_chorus.h`, `audio/{chip_dsp,fm_dsp,va_dsp}.h`,
  `audio/dsp.h`, `audio/audio_tables.h`, `model/synth_patch.h`, `fastrun.h`), copies of the files tracker-ff keeps (each with a
  provenance line).
* **Source**: https://github.com/sandlbn/polyend-tracker-re (commit 927b1516385e, the 3.x files from branch `v3_fixes`, commit 789d55a4c5e8)
* **License**: Apache License 2.0, text in `licenses/LICENSE-OpenTracker-Apache-2.0.txt`. The upstream project ships no NOTICE file.
  `audio/dsp.h` keeps its embedded notice for the PJRC Teensy Audio Library (MIT, Copyright (c) 2014-2017 Paul Stoffregen, PJRC.COM, LLC).

## 3. tracker-ff (plugin wrappers, engine definitions, plugin SDK and runtime)

* **Location**: `src/synth-open/plug/synth/*_plug.cpp`, the tracker-ff parts of `src/synth-open/engine_*.cpp`, `sdk/files/` (the
  plugin SDK of https://github.com/sbialy/tracker-ff, `synth-open/plug/`, linked into every plugin), `build_set.py`, `wasm/`, `tools/`.
* **License**: MIT, Copyright (c) 2026 sbialy (tracker-ff), text in `LICENSE` and `licenses/LICENSE-tracker-ff-MIT.txt`.

## 4. Polyend Tracker Community Edition (the open PolySynth header)

* **Location**: `sdk/files/synth/include/PolySynth/config.h` (vendored from tracker-ff `synth/include/PolySynth/`, Polyend's open
  PolySynth API header, compiled into the engines for its constants). `sdk/files/synth-open/engine_list.h` and `open_engine.h` are
  tracker-ff's shim headers (section 3).
* **License**: the Polyend Tracker Community Edition License (MIT with a Wholesale Commercial Clone Restriction), Copyright (c) 2020-2026 Polyend Sp. z o.o. and contributors, text in
  `licenses/LICENSE-PolyendTracker-CE.txt`. No closed Polyend code (`libPolySynth.a`, `libPolyDSP.a`) is used.

## 5. Polyend Chiptune voice (CHIP)

* **Location**: `sdk/files/core/synth/engines/ChiptuneSynthVoice.{cpp,h}` (Polyend's open Chiptune voice, vendored unchanged from tracker-ff
  `core/synth/engines/` apart from the `FEATURE_SYNTH_OPEN` hooks tracker-ff added), the PolySynth headers it includes (`sdk/files/synth/include/PolySynth/`,
  `core/config/config.h`, `util/include/PolyUtil/misc.h`) and the third party headers those pull in (`sdk/files/util/3rdparty/`: `fmt`, `boost`
  `container` and its dependencies, `tiny`, `constexpr-string`, `enum_util.h`), all listed in `sdk/polysynth.txt`. `src/synth-open/engine_chip.cpp`
  hosts the voice behind the shim's engine interface (parameter table, sections and macros follow the voice's `createMetadata`, voice objects
  in the plugin's bss), `src/synth-open/plug/synth/chip_libc.cpp` is the five C library functions a plugin lacks (tracker-ff, MIT).
* **License**: the Polyend Tracker Community Edition License (MIT with a Wholesale Commercial Clone Restriction) for the voice and the PolySynth
  headers, text in `licenses/LICENSE-PolyendTracker-CE.txt`. fmt is MIT (Copyright (c) 2012 - present, Victor Zverovich), constexpr-string MIT
  (Copyright (c) 2019 Marek Bogusovsky), tiny optional and the boost headers the Boost Software License 1.0 (the headers carry their notices).
  These are headers only: the plugin contains the code of the few templates it instantiates.
