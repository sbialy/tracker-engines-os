// CHIP (Polyend's open Chiptune voice, core/synth/engines/ChiptuneSynthVoice.cpp of tracker-ff, unchanged) as a synth plugin:
// engine_chip.cpp hosts it behind the shim's ISynthEngine interface, 12 voice objects in the plugin's bss. Stored 6 and .patch
// engine 8 (InstrumentTypeId::kChiptuneSynth) are the numbers CHIP always had, so projects and .patch files load unchanged.
#define PLUG_SYNTH_AUTHOR "Polyend Chiptune (CE licence)"
#include "synth_plug.h"
namespace polysynth::open
{
extern const EngineDef kChipDef;
}
PLUG_SYNTH_PLUGIN("CHIP", polysynth::open::kChipDef, 6, 8)
