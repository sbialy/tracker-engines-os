// JU6 (OpenTracker 3.x module engine, MIT) as a synth plugin: engine_ju6.cpp and ot-synths/ju6/ju6.cpp as they are.
// Paraphonic (PLUG_EXT_CHORD, ABI 1.2): a MIDI Chord step on a Para patch is one note-on with the step chord in Chord,
// and a Strum FX of the step in Strum (the notes of the chord start one after another).
#include "synth_plug.h"
#include "ot-synths/ju6/ju6.h"
namespace polysynth::open
{
extern const EngineDef kJu6Def;
}
PLUG_SYNTH_PLUGIN_CHORD_STRUM("JU6", polysynth::open::kJu6Def, 7, 0x81, 0, nullptr, ot::audio::ju6::kChord,
                              ot::audio::ju6::kChordMode, ot::audio::ju6::kStrum)
