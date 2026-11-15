// Test only (tools/chip_pool_check.py), never shipped: the SDK harness (plug/synth/synth_harness.cpp, see chip_harness.cpp) with 16 voice records.
// Scenario 0: the 16 records play at once (notes 36 + 2 k, all on at block 0, off at block 28). Scenario k = 1..16: only record k - 1 plays the same
// note. The check sums the solo renders and compares them with scenario 0: a record without a voice object of its own (a pool of 12) takes over
// the object of another one and the sums differ. Parameters at their defaults.
#include "plug_abi.h"
#include "audio/synth_engine.h"

#include <string.h>

using namespace ot::audio;

namespace
{
constexpr int kVoices = 16;
// raw storage: the structs have member initializers, a global of their type would need a static constructor
alignas(8) uint8_t g_pMem[sizeof(SynthParams)], g_scMem[sizeof(SynthSlotScratch)], g_vMem[kVoices][sizeof(SynthVoice)];
SynthParams& g_p = *reinterpret_cast<SynthParams*>(g_pMem);
SynthSlotScratch& g_sc = *reinterpret_cast<SynthSlotScratch*>(g_scMem);
SynthVoice* const g_v = reinterpret_cast<SynthVoice*>(g_vMem);
bool g_on[kVoices];
float g_gain[kVoices];
float g_busL[kBlock], g_busR[kBlock];
const plug_host* g_host;   // init: the emulator's host table (cycles = instructions so far)

struct Ev
{
    uint8_t block, voice, note, on;   // on: 1 note on, 0 note off
};

// out: blocks x 256 floats (L then R per block), then blocks x uint32: the instructions of each block (prepare, voices, slot_post)
void run(const plug_ext_synth* x, float* out, uint32_t blocks, uint32_t scenario)
{
    memset(&g_p, 0, sizeof(g_p));
    g_p.engine = x->type_id;
    g_p.count = int(x->param_count);
    for (uint32_t i = 0; i < x->param_count; i++) g_p.start[i] = g_p.end[i] = x->params[i].def;
    memset(&g_sc, 0, sizeof(g_sc));
    if (x->slot_reset) x->slot_reset(&g_sc);
    if (x->set_tempo) x->set_tempo(120.0f);
    for (uint32_t b = 0; b < blocks; b++)
    {
        const uint32_t t0 = g_host->cycles();   // the block's note events count too, as on the device
        g_p.moving = false;
        g_p.serial++;
        for (int k = 0; k < kVoices; k++)
        {
            if (scenario && uint32_t(k) != scenario - 1) continue;
            if (b != 0 && b != 28) continue;
            const Ev e = { uint8_t(b), uint8_t(k), uint8_t(36 + 2 * k), uint8_t(b == 0) };
            SynthVoice& v = g_v[e.voice];
            if (e.on)
            {
                SynthNote n;
                n.note = e.note;
                n.pitch = float(e.note);
                n.velocity = x->volume_param < 0 ? 100.0f / 127.0f : 1.0f;
                v = SynthVoice{};
                memset(v.state, 0, sizeof(v.state));
                v.slotScratch = &g_sc;
                v.note = e.note;
                v.gate = true;
                g_on[e.voice] = true;
                g_gain[e.voice] = 0.0f;
                x->note_on(&v, &g_p, &n);
            }
            else if (g_on[e.voice])
            {
                v.gate = false;
                x->note_off(&v, &g_p);
            }
        }
        float* L = out + b * 2 * kBlock;
        float* R = L + kBlock;
        memset(L, 0, 2 * kBlock * sizeof(float));
        const bool fx = (x->flags & PLUG_SYNTH_SLOT_FX) && x->slot_post;
        if (fx)
        {
            memset(g_busL, 0, sizeof(g_busL));
            memset(g_busR, 0, sizeof(g_busR));
        }
        if (x->prepare) x->prepare(&g_sc, &g_p);
        for (int k = 0; k < kVoices; k++)
        {
            if (!g_on[k]) continue;
            const float target = 0.06f * (x->volume_param >= 0 ? g_p.end[x->volume_param] : 1.0f);   // 16 notes at once must not clip the 16 bit WAV
            const float g0 = g_gain[k];
            g_gain[k] = target;
            if (!x->render(&g_v[k], &g_p, g0, (target - g0) * (1.0f / float(kBlock)), fx ? g_busL : L, fx ? g_busR : R))
                g_on[k] = false;
        }
        if (fx)
        {
            x->slot_post(0, &g_sc, &g_p, g_busL, g_busR);
            for (uint32_t i = 0; i < kBlock; i++)
            {
                L[i] += g_busL[i];
                R[i] += g_busR[i];
            }
        }
        reinterpret_cast<uint32_t*>(out + blocks * 2 * kBlock)[b] = g_host->cycles() - t0;
        memcpy(g_p.start, g_p.end, sizeof(g_p.start));
    }
}

int32_t init(void*, const plug_host* h)
{
    g_host = h;
    return 0;
}
void process(void*, float* const*, uint32_t, uint32_t) {}
const void* query(uint32_t id) { return id == 0x7E ? reinterpret_cast<const void*>(&run) : nullptr; }

PLUG_DESCRIPTOR const plug_desc kDesc = {
    sizeof(plug_desc), PLUG_KIND_OFFLINE, "SynthHarness", "test", 0, nullptr, 8, init, nullptr, nullptr, process, query,
};
}   // namespace

extern "C" const plug_host* plug_rt_host;
extern "C" PLUG_ENTRY const plug_desc* plug_entry(const plug_host* host, uint32_t)
{
    plug_rt_host = host;
    return &kDesc;
}
