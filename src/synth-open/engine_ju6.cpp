// JU6 parameter metadata for the open PolySynth shim on MK66. JU6 is a Juno-style polysynth voice from OpenTracker 3.x
// (module opentracker-synths/modules/ju6, MIT, synth-open/ot-synths/ju6). The ranges, defaults, labels, enum names and the
// section split follow that module's descriptor (modules/ju6/src/ju6_desc.cpp, MIT, Copyright (c) 2026 Marcin
// Spoczynski, see licenses/LICENSE-OpenTracker-synths-MIT.txt). Edit curves and the default macros are this shim's choice.
//
// The built-in chorus runs once per slot on the voice sum (ISynthEngine::slotPost), see EngineDef::slotFx.
//
// tracker-ff addition: paraphony. Chord Mode / Chord / Voicing are appended after Chorus (indices 23 to 25), so every older patch
// keeps its values and plays polyphonic (Chord Mode Poly = the engine as it was). Chord is the stock MIDI Chord FX table (68
// entries, 0 = the played note), named like the FX value list. The "Chord" section is last.
#include "open_engine.h"

#include "PolySynth/config.h"
#include "ot-synths/ju6/ju6.h"

namespace polysynth::open
{
namespace
{
using ot::audio::ju6::Param;

const char* const kPwm[] = { "Manual", "LFO" };
const char* const kHpf[] = { "0 Boost", "1 Flat", "2", "3" };
const char* const kVca[] = { "Env", "Gate" };
const char* const kChorus[] = { "Off", "I", "II" };
const char* const kChordMode[] = { "Poly", "Para" };
const char* const kVoicing[] = { "Close", "Drop 2", "Open", "Spread" };
// The interval digits of the MIDI Chord FX value list (core/source/mtChordDefs.h chordDefName), one name per chordDef entry
const char* const kChordName[ot::audio::ju6::kChordCount] = {
    "---", "27",  "28",  "36",  "37",  "47",  "48",  "57",  "5A",  "5C",  "67",  "7C",  "7E",  "279", "27A", "27B", "369", "36A", "378",
    "379", "37A", "37B", "479", "47A", "47B", "489", "48A", "48B", "57A", "57B", "38",  "59",  "49",  "58",  "459", "158", "358", "259",
    "368", "359", "269", "39",  "69",  "6A",  "46",  "16",  "5B",  "469", "258", "458", "148", "468", "248", "26A", "478", "348", "159",
    "257", "35A", "58A", "357", "249", "59A", "457", "138", "267", "45A", "168",
};

using F = Fmt;
using C = CurveKind;

const ParamDef kParams[Param::kParamCount] = {
    { "Saw", 1, 0, 1, F::kOnOff, C::kLinear, nullptr },
    { "Pulse", 0, 0, 1, F::kOnOff, C::kLinear, nullptr },
    { "PW", 0.4f, 0, 1, F::kPct, C::kLinear, nullptr },
    { "PWM", 1, 0, 1, F::kEnum, C::kLinear, kPwm },
    { "Sub", 0.35f, 0, 1, F::kPct, C::kLinear, nullptr },
    { "Noise", 0, 0, 1, F::kPct, C::kLinear, nullptr },
    { "Vibrato", 0, 0, 1, F::kPct, C::kLinear, nullptr },
    { "HPF", 1, 0, 3, F::kEnum, C::kLinear, kHpf },
    { "Cutoff", 1400, 20, 20000, F::kHz, C::kExp, nullptr },
    { "Resonance", 0.15f, 0, 1, F::kPct, C::kLinear, nullptr },
    { "Env", 0.4f, -1, 1, F::kPctMax, C::kLinear, nullptr },
    { "LFO", 0, 0, 1, F::kPct, C::kLinear, nullptr },
    { "Key Follow", 0.5f, 0, 1, F::kPct, C::kLinear, nullptr },
    { "Velocity", 0, 0, 1, F::kPct, C::kLinear, nullptr },
    { "VCA", 0, 0, 1, F::kEnum, C::kLinear, kVca },
    { "Attack", 0.06f, 0, 10, F::kSec, C::kSteep, nullptr },
    { "Decay", 1.0f, 0, 10, F::kSec, C::kSteep, nullptr },
    { "Sustain", 0.65f, 0, 1, F::kPct, C::kLinear, nullptr },
    { "Release", 0.45f, 0, 10, F::kSec, C::kSteep, nullptr },
    { "LFO Rate", 3.5f, 0.1f, 20, F::kLfoHz, C::kExp, nullptr },
    { "LFO Delay", 0.6f, 0, 5, F::kSec, C::kPower, nullptr },
    { "Volume", 1, 0, 2, F::kPct, C::kLinear, nullptr },
    { "Chorus", 0, 0, 2, F::kEnum, C::kLinear, kChorus },
    { "Chord Mode", 0, 0, 1, F::kEnum, C::kLinear, kChordMode },
    { "Chord", 0, 0, ot::audio::ju6::kChordCount - 1, F::kEnum, C::kLinear, kChordName },
    { "Voicing", 0, 0, 3, F::kEnum, C::kLinear, kVoicing },
};

const uint8_t kDco[] = { Param::kSaw, Param::kPulse, Param::kPw, Param::kPwMode, Param::kSub, Param::kNoise,
                         Param::kVibrato };
const uint8_t kVcf[] = { Param::kHpf,       Param::kCutoff,    Param::kResonance, Param::kEnvAmt,
                         Param::kVcfLfo,    Param::kKeyFollow, Param::kVelVcf };
const uint8_t kVcaSec[] = { Param::kVcaMode, Param::kVolume };
const uint8_t kEnv[] = { Param::kAttack, Param::kDecay, Param::kSustain, Param::kRelease };
const uint8_t kLfo[] = { Param::kLfoRate, Param::kLfoDelay };
const uint8_t kCho[] = { Param::kChorus };
const uint8_t kPara[] = { Param::kChordMode, Param::kChord, Param::kVoicing };

// The editor picks the section icon from the name ("Oscillator", "Filter", "Amplifier", ...)
const SectionDef kSections[] = {
    { "Oscillator", "DCO", kDco, sizeof(kDco) },
    { "Filter", "VCF", kVcf, sizeof(kVcf) },
    { "Amplifier", "VCA", kVcaSec, sizeof(kVcaSec) },
    { "Envelope", "ENV", kEnv, sizeof(kEnv) },
    { "LFO", "LFO", kLfo, sizeof(kLfo) },
    { "Modulation", "Chorus", kCho, sizeof(kCho) },
    { "Chord", "CHORD", kPara, sizeof(kPara) },
};

const MacroDef kMacros[] = {
    { "Cutoff", false, 1, { { Param::kCutoff, 0.4f } } },
    { "Resonance", false, 1, { { Param::kResonance, 1.0f } } },
    { "Env Amount", true, 1, { { Param::kEnvAmt, 1.0f } } },
    { "Decay / Release", false, 2, { { Param::kDecay, 0.3f }, { Param::kRelease, 0.3f } } },
    { "Pulse Width", true, 1, { { Param::kPw, 0.5f } } },
    { "LFO Rate", false, 1, { { Param::kLfoRate, 0.3f } } },
};

} // namespace

// ---- PARA-HOST STUB (tracker-ff `paraphony` firmware branch, poly-para-host) --------------------------------------------------
// The host side of the chord (ref/alco-paraphonic.md 3b): a MIDI Chord step on a part whose patch is paraphonic becomes ONE note-on,
// and the host writes the step's chord index (the stock chordDef index, 0 to 67) into the engine's Chord parameter for that note-on
// only. The engine already latches Chord at every note-on (ot-synths/ju6 latchChord), so this is all the host has to know:
//   PLUG_EXT_CHORD (plug_abi.h, being defined by poly-para-host, NOT in the vendored ABI yet) -> { struct_size, param_index [, mode] }
// kJu6ChordExt is that answer for JU6. It is not wired into the plugin descriptor: plugsynth::query (synth_plug.h, vendored SDK)
// answers PLUG_EXT_SYNTH only. When the ABI has the id, the sdk-sync brings the query hook and ju6_plug.cpp passes this struct to it.
// mode_param is the one open point against the design doc: the host must write Chord only while Chord Mode is Para (the patch's
// poly / paraphonic choice), in Poly mode the engine ignores Chord and plays the root, so the host has to keep the stock N note-ons.
struct Ju6ChordExt
{
    uint32_t struct_size;
    uint32_t param_index;   // the engine's Chord parameter (enum, chordDef order)
    uint32_t mode_param;    // the Chord Mode parameter (0 Poly, 1 Para): the host routes only while it reads Para
};
extern const Ju6ChordExt kJu6ChordExt;
const Ju6ChordExt kJu6ChordExt = { sizeof(Ju6ChordExt), Param::kChord, Param::kChordMode };
// ---- end PARA-HOST STUB -------------------------------------------------------------------------------------------------------

const EngineDef kJu6Def = {
    "JU6",
    0x81, // no Polyend id: OpenTracker's engine id, see engine_list.h
    kParams,
    Param::kParamCount,
    kSections,
    static_cast<int>(sizeof(kSections) / sizeof(kSections[0])),
    kMacros,
    static_cast<int>(sizeof(kMacros) / sizeof(kMacros[0])),
    Param::kVolume,
    kMaxVoicesPerInstrument,
    &ot::audio::ju6::engine,
    true, // the chorus
};

} // namespace polysynth::open
