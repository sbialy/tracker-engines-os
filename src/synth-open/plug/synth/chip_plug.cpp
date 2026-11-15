// CHIP (Polyend's open Chiptune voice, core/synth/engines/ChiptuneSynthVoice.cpp of tracker-ff, unchanged) as a synth plugin:
// engine_chip.cpp hosts it behind the shim's ISynthEngine interface, 12 voice objects in the plugin's bss and 4 more in the host's work memory
// (CHIP_WORK_POOL, work_bytes), 16 in all for a CHIP pair at 8 + 8 voices on the Synth play page. Stored 6 and .patch
// engine 8 (InstrumentTypeId::kChiptuneSynth) are the numbers CHIP always had, so projects and .patch files load unchanged.
#define PLUG_SYNTH_AUTHOR "Polyend Chiptune (CE licence)"
#include "synth_plug.h"
namespace polysynth::open
{
extern const EngineDef kChipDef;
uint32_t chipWorkBytes();
void chipSetWork(void* work, uint32_t bytes);
}
PLUG_SYNTH_PLUGIN_WORK("CHIP", polysynth::open::kChipDef, 6, 8, polysynth::open::chipWorkBytes(), polysynth::open::chipSetWork)
