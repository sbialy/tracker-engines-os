# poly-engines-os

The public synth engine plugins of tracker-ff (the custom firmware for the Polyend Tracker): the ten OpenTracker 3.x module engines
JU6, FM4, B-Type, D-Type, CS-Type, A-Type, T-Type, 8-Type, Hand-Type and Arc-Type, each built into a device file (`<id>.plg` plus the
card logo `<id>.plgi`) and a browser file for the poly-editor (`<id>.wasm` plus the manifest `<id>.json`).

tracker-ff 1.2.0 is split into five repositories:

| Repository | Holds |
|---|---|
| tracker-ff | the firmware: plugin host, plugin SDK, the built-in engines ACD FAT VAP WTFM PERC CHIP, `.ptfx` effects |
| poly-engines-os (this one) | the public synth engine plugins (open source) |
| poly-engines | the private synth engine plugins (PHZ, PLK, FORM, FLUX, freeware binaries only) |
| poly-effects-os | the public master insert plugins Dirt, Tape, Lo-Fi, BBD, Phaser (open source) |
| poly-effects | the private master insert plugins Console, Tube (freeware binaries only) |

The firmware pins a release of every module repository in its `engines/external.lock.json` and checks the published files against
the engine numbers it keeps in `engines/engines.json`.

## Layout

| Path | What |
|---|---|
| `src/synth-open/` | the engine sources at their tracker-ff paths: `engine_<id>.cpp` (parameter table), `ot-synths/<module>/` (the OpenTracker DSP), `plug/synth/<id>_plug.cpp` (the plugin wrapper) |
| `sdk/files/` | the plugin SDK, a pinned copy of tracker-ff files (headers, `build_plug.py`, `plug_rt.c`, `plug.ld`, emulators, logo tools, `plug_wasm.h`, `plug_rt_wasm.c`). `sdk/SOURCE` names the tracker-ff commit |
| `sdk/headers.txt`, `sources.txt`, `tools.txt`, `VERSION` | what a build may see (the engine compiles in a scratch tree that holds only these files) |
| `engines.json` | the table: numbers (stored, patch and type id, they must match tracker-ff), flags per flavour, version, logo, licence |
| `build_set.py`, `Makefile` | the `.plg` set build and its checks, the set also gets NOTICE.md and the licence texts |
| `wasm/` | the `.wasm` twins and their manifests (`build_modules.py`, emcc pinned in `wasm.json`) |
| `tools/sdk_sync.py` | compares or refreshes `sdk/files/` against a tracker-ff checkout |
| `licenses/`, `LICENSE`, `NOTICE.md` | the licence texts and notices that ship with the files |

## Build

Needs the Arm GNU toolchain 12.3.rel1 (the release bytes were made with it), Python 3, and for the render checks a Python with
`unicorn`. The `.wasm` build needs emsdk 6.0.13 (`EMSDK=...` or `--emsdk`) and clang for the arm64 descriptor dump.

```bash
export TOOLCHAIN=/path/to/arm-gnu-toolchain-12.3.rel1/bin/arm-none-eabi-
make PY=/path/to/python-with-unicorn     # build/engines-autof: 10 .plg + 10 .plgi, SET.json, SHA256SUMS, previews/
make verify
make wasm                                # build/wasm: 10 .wasm + .json, NOTICE.md, licences, MODULES.json, SHA256SUMS
make package                             # build/tracker-ff-engines-1.0.0-autof.zip, unzip at the card root
```

`FLAVOUR=autof` (default) is the tracker-ff 1.2.0 release flavour: `-O2 -ffp-contract=off` on every engine, FM4 and B-Type at `-O3`.
`FLAVOUR=fused` keeps the compiler's fused multiply add (the unpublished AUTO fallback). The build is byte reproducible: the same
toolchain gives the same files, no dates or paths are written. The 1.2.0 set built here is byte identical to the `.plg` and `.plgi`
files of the tracker-ff 1.2.0 release.

## The SDK copy

A clone of this repository builds on its own: nothing outside it is read. The SDK it compiles against is the copy in `sdk/files/`,
taken from tracker-ff at the commit in `sdk/SOURCE`. With a tracker-ff checkout next to it:

```bash
make sdk-check FW=../tracker-ff          # every file of sdk/files equals the checkout
make sdk-sync FW=../tracker-ff           # take the checkout's files (then rebuild, compare, bump versions if bytes changed)
```

The checks that need the firmware itself (the firmware's own `checkSynth` in an emulator, the card logo device tests) run in
tracker-ff: `TOOLCHAIN=... PY=... engines/crosscheck.sh build/engines-autof` from the tracker-ff checkout.

## Adding or changing an engine

A new engine needs its numbers from tracker-ff first (a row in tracker-ff `engines/engines.json` and `synth-open/engine_list.h`),
then its sources under `src/synth-open/`, a row in `engines.json` here, its files in `sdk/sources.txt`, and the headers it includes in
`sdk/headers.txt` (copied into `sdk/files/` with `make sdk-sync`). Bump `version` of an engine whose `.plg` bytes change on purpose.
A release is a tag `vX.Y.Z` with the files of `build/engines-autof` and `build/wasm` as release assets. tracker-ff pins the tag, its
commit and the sha256 of every file.

## Licence

MIT for the tracker-ff parts (`LICENSE`), MIT (Marcin Spoczynski) for the OpenTracker module engines, Apache 2.0 for the OpenTracker
3.x headers. Details and the texts: `NOTICE.md` and `licenses/`.
