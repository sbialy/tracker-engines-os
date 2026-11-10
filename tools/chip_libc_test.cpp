// Host test of chip_libc.cpp's roundf and lroundf against the C library over every float bit pattern (2^32): the plugin must give the
// bits newlib's gave. clang++ -O2 -std=c++17 -Wno-unknown-attributes -fno-builtin -Dabort=chip_abort -Dmemcmp=chip_memcmp \
//   -Dmemmove=chip_memmove tools/chip_libc_test.cpp -o /tmp/chip_libc_test && /tmp/chip_libc_test
#include <stdlib.h>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

#define roundf chip_roundf
#define lroundf chip_lroundf
#include "../src/synth-open/plug/synth/chip_libc.cpp"
#undef roundf
#undef lroundf

int main()
{
    uint64_t bad = 0, n = 0;
    for (uint64_t u = 0; u < (1ull << 32); u++)
    {
        const uint32_t b = uint32_t(u);
        float x;
        memcpy(&x, &b, 4);
        n++;
        const float r = chip_roundf(x), e = ::roundf(x);
        uint32_t rb, eb;
        memcpy(&rb, &r, 4);
        memcpy(&eb, &e, 4);
        const bool nan = std::isnan(x);
        if (nan ? !std::isnan(r) : rb != eb)
        {
            if (bad++ < 5) printf("roundf %08x: %08x vs %08x\n", b, rb, eb);
        }
        // lroundf is only defined in range, the voice calls it on small values: check |x| < 2^31
        if (!nan && std::fabs(x) < 2147483648.0f)
        {
            if (chip_lroundf(x) != ::lroundf(x) && bad++ < 5) printf("lroundf %08x\n", b);
        }
    }
    printf("%llu floats, %llu mismatches\n", (unsigned long long)n, (unsigned long long)bad);
    return bad ? 1 : 0;
}
