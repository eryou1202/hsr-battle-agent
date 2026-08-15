// read_cstring_mini.cpp - minimal regression test for PointerValidator::read_cstring.
//
// Regression for the Phase A hang investigation: the earlier hang was caused
// by the self-test writing "Hello\0" into a page that had already been
// switched to PAGE_READONLY (an access violation), not by read_cstring
// itself. This test keeps the page PAGE_READWRITE and additionally covers the
// max_len/no-terminator boundary so the loop cannot silently regress.

#include <windows.h>

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "../probe/pe_model.h"
#include "../probe/pointer_validation.h"

int wmain() {
    int failures = 0;
    const std::size_t region_size = 0x2000;
    std::uint8_t* raw = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, region_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (raw == nullptr) {
        std::printf("[FAIL] VirtualAlloc\n");
        return 1;
    }
    const std::uint64_t base = reinterpret_cast<std::uint64_t>(raw);

    // Write before any protection change; the page stays PAGE_READWRITE.
    std::memcpy(raw, "Hello\0", 6);
    std::memcpy(raw + 0x100, "ABCDE", 5);

    std::vector<hsr_probe::ModuleInfo> modules;
    hsr_probe::PointerValidator validator(&modules);

    std::string text;
    hsr_probe::PointerCheck check;
    const bool ok = validator.read_cstring(base, 64, text, &check);
    if (ok && text == "Hello" && check.valid && check.committed && check.readable) {
        std::printf("[PASS] read_cstring reads Hello\n");
    } else {
        std::printf("[FAIL] read_cstring reads Hello: ok=%d text=%s valid=%d\n",
                    ok ? 1 : 0, text.c_str(), check.valid ? 1 : 0);
        ++failures;
    }

    // "ABCDE" has no NUL; max_len=4 must return false and leave `out` empty.
    std::string bounded;
    const bool bounded_ok = validator.read_cstring(base + 0x100, 4, bounded, &check);
    if (!bounded_ok && bounded.empty()) {
        std::printf("[PASS] read_cstring max_len boundary stops without terminator\n");
    } else {
        std::printf("[FAIL] read_cstring max_len boundary: ok=%d len=%zu\n",
                    bounded_ok ? 1 : 0, bounded.size());
        ++failures;
    }

    VirtualFree(raw, 0, MEM_RELEASE);
    if (failures == 0) {
        std::printf("READ_CSTRING_MINI PASSED\n");
        return 0;
    }
    std::printf("READ_CSTRING_MINI FAILED\n");
    return 1;
}
