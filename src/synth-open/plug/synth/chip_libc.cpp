// The few C library functions the Polyend voice (ChiptuneSynthVoice.cpp, SDK base class with static_vector and shared_ptr) leaves
// undefined in a plugin: no newlib here, plug_rt.c has memcpy and memset only. CHIP plugin only.
//
// roundf and lroundf are exact functions (the nearest integer, halves away from zero), so any correct version gives the bits the
// firmware's newlib gave. The voice calls them on small values (a parameter in 0 to 36), the range checks only keep them total.
// Compiled with -fno-builtin (wrapper_opt) so no function calls itself, and without loop idiom recognition for the same reason.
#include <stddef.h>
#include <stdint.h>

#define CHIP_NO_IDIOM __attribute__((optimize("no-tree-loop-distribute-patterns")))

extern "C"
{
CHIP_NO_IDIOM int memcmp(const void* a, const void* b, size_t n)
{
    const unsigned char* p = static_cast<const unsigned char*>(a);
    const unsigned char* q = static_cast<const unsigned char*>(b);
    for (; n; n--, p++, q++)
    {
        if (*p != *q)
        {
            return *p < *q ? -1 : 1;
        }
    }
    return 0;
}

CHIP_NO_IDIOM void* memmove(void* d, const void* s, size_t n)
{
    unsigned char* dp = static_cast<unsigned char*>(d);
    const unsigned char* sp = static_cast<const unsigned char*>(s);
    if (dp < sp)
    {
        while (n--)
        {
            *dp++ = *sp++;
        }
    }
    else
    {
        dp += n;
        sp += n;
        while (n--)
        {
            *--dp = *--sp;
        }
    }
    return d;
}

void abort(void)
{
    for (;;)
    {
    }
}

float roundf(float x)
{
    // |x| >= 2^23 (and inf, nan) is an integer already
    if (!(x < 8388608.0f && x > -8388608.0f))
    {
        return x;
    }
    const float t = static_cast<float>(static_cast<int32_t>(x)); // truncated, exact below 2^23
    const float d = x - t;                                        // exact
    float r = t;
    if (d >= 0.5f)
    {
        r = t + 1.0f;
    }
    else if (d <= -0.5f)
    {
        r = t - 1.0f;
    }
    // keep the sign of a zero result (-0.3 rounds to -0.0)
    uint32_t bx, br;
    __builtin_memcpy(&bx, &x, 4);
    __builtin_memcpy(&br, &r, 4);
    br = (br & 0x7FFFFFFFu) | (bx & 0x80000000u);
    if ((br & 0x7FFFFFFFu) != 0)
    {
        return r;
    }
    __builtin_memcpy(&r, &br, 4);
    return r;
}

long lroundf(float x)
{
    if (!(x < 2147483648.0f && x > -2147483648.0f))
    {
        return x > 0 ? 2147483647L : (-2147483647L - 1);
    }
    return static_cast<long>(roundf(x));
}
}
