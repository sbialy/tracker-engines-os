// Test only, never shipped: what the firmware's own engine_chip.o needs to run inside a plugin for the render compare
// (tools/chip_render_compare.py). The firmware object makes its 12 voices with std::make_unique, so operator new has to exist:
// a bump allocator over a static block (the objects are never freed). chip_libc.cpp covers memcmp, memmove, abort, roundf.
#include <stddef.h>
#include <stdint.h>

namespace
{
alignas(8) unsigned char g_heap[8192];
size_t g_used;
}   // namespace

void* operator new(size_t n)
{
    n = (n + 7u) & ~size_t(7);
    if (g_used + n > sizeof(g_heap))
    {
        for (;;)
        {
        }
    }
    void* p = g_heap + g_used;
    g_used += n;
    return p;
}
