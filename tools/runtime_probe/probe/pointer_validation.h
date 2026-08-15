#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "pe_model.h"

namespace hsr_probe {

struct PointerCheck {
    bool valid = false;
    bool canonical = false;
    bool committed = false;
    bool readable = false;
    bool executable = false;
    std::uint32_t protect = 0;
    std::string module;   // owning known module, empty when heap/other
    std::string section;  // owning PE section, empty when outside a known section
};

// Validates every pointer returned by the game before it is dereferenced.
//
// - canonical: non-null, >= 0x10000 and low-half canonical user address.
// - committed/readable/executable: derived from VirtualQuery of the owning
//   region (MEM_IMAGE module mappings or other committed memory).
// - function pointers must additionally live in a known module's executable
//   section; il2cpp api-table wrappers are UnityPlayer .text stubs.
//
// The probe itself never writes to the game process. All reads of
// game-returned pointers go through ReadProcessMemory on the current process
// so a stale pointer fails cleanly instead of faulting the game.
class PointerValidator {
public:
    explicit PointerValidator(const std::vector<ModuleInfo>* modules)
        : modules_(modules) {}

    PointerCheck check_generic(std::uint64_t addr) const;
    PointerCheck check_exec_function(std::uint64_t addr) const;

    bool read_bytes(std::uint64_t addr, std::size_t size,
                    std::vector<std::uint8_t>& out,
                    PointerCheck* check = nullptr) const;

    // Reads a NUL-terminated string. `allow_empty` is ignored here (the C
    // string reader always accepts ""); callers apply their own sanity rules.
    bool read_cstring(std::uint64_t addr, std::size_t max_len, std::string& out,
                      PointerCheck* check = nullptr) const;

private:
    const std::vector<ModuleInfo>* modules_;
};

bool is_printable_utf8_string(const std::string& text);

}  // namespace hsr_probe
