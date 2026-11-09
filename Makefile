# tracker-engines-os: the public synth engine plugins of tracker-ff (OpenTracker 3.x module engine ports). Works with Apple make 3.81.
#
#   make TOOLCHAIN=/path/to/arm-none-eabi- [PY=python-with-unicorn]   the release set (FLAVOUR=autof) into build/engines-autof
#   make TOOLCHAIN=... FLAVOUR=fused OUT=/tmp/set                      the fused-maths flavour
#   make verify [OUT=...]                                               SHA256SUMS, SET.json, ABI of a finished set
#   make wasm [WASM_OUT=...]                                            the browser modules (.wasm + manifest), needs emsdk 6.0.13
#   make package [OUT=...]                                              build/tracker-ff-engines-<set>-<flavour>.zip, files under Plugins/Synth/
#   make sdk-check FW=../tracker-ff                                     the vendored SDK (sdk/files) equals a tracker-ff checkout
#   make sdk-sync FW=../tracker-ff                                      copy the SDK files from that checkout (review the diff)
#
# TOOLCHAIN is the compiler prefix with the trailing dash (Arm GNU 12.3.rel1 gives the released bytes), there is no default.
# PY is a Python with unicorn: it runs the render checks (without it they are skipped and SET.json says so). Every build starts
# from a scratch copy of the listed files, so make does not need to track flags.
FLAVOUR  ?= autof
PY       ?= python3
HERE     := $(dir $(lastword $(MAKEFILE_LIST)))
OUT      ?= $(abspath $(HERE))/build/engines-$(FLAVOUR)
WASM_OUT ?= $(abspath $(HERE))/build/wasm
HOST_ABI ?= $(HERE)sdk/files/synth-open/plug/plug_abi.h
FW       ?=

.PHONY: all verify package wasm sdk-check sdk-sync clean
all:
	python3 "$(HERE)build_set.py" build --out "$(OUT)" --flavour "$(FLAVOUR)" --py "$(PY)"

verify:
	python3 "$(HERE)build_set.py" verify "$(OUT)" --host-abi "$(HOST_ABI)"

package: verify
	python3 "$(HERE)build_set.py" package "$(OUT)" --host-abi "$(HOST_ABI)"

wasm:
	python3 "$(HERE)wasm/build_modules.py" --out "$(WASM_OUT)" $(if $(wildcard $(OUT)/SET.json),--engines-plg "$(OUT)")

sdk-check:
	@test -n "$(FW)" || { echo "set FW to a tracker-ff checkout"; exit 2; }
	python3 -I "$(HERE)tools/sdk_sync.py" check "$(FW)"

sdk-sync:
	@test -n "$(FW)" || { echo "set FW to a tracker-ff checkout"; exit 2; }
	python3 -I "$(HERE)tools/sdk_sync.py" sync "$(FW)"

clean:
	rm -rf "$(HERE)build"
