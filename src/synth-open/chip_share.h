// CHIP plugin (engine_chip.cpp and chip_voice.cpp): the filter coefficients of one voice's block, for the next voices on the same path.
// While the envelope moves (attack, decay, release) the voice computes its filter coefficient every sample from the envelope level
// (fastPow2 and fastSine). The level of every sample is a function of the stage and level at the block start and the four envelope
// parameters, the coefficient a function of that level and the three filter parameters. A voice whose key (those nine words, bit for
// bit) equals the stored one reads the stored coefficients instead: the same values it would compute. Lives in the plugin's bss.
#pragma once
#include <stdint.h>

namespace polysynth::open
{
struct ChipFilterShare
{
    uint32_t valid;     // key and tab hold a block
    uint32_t key[9];    // stage, level, attack, decay, sustain, release, cutoff, resonance, env amount (float bits)
    float tab[128];     // per sample: the coefficient after the sample's filter update, or -1 when the filter is off (bypassed)
};
} // namespace polysynth::open
