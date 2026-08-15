#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace hsr_probe {

// In-memory PE section model. Mirrors PeSection/PeImage semantics of
// tools/reverse/scripts/find_il2cpp_api_table.py: section size is
// max(virtual_size, raw_size, 0x1000) so header and alignment padding count.
struct PeSection {
    std::string name;
    std::uint64_t rva = 0;
    std::uint64_t vsize = 0;
    std::uint64_t raw_size = 0;
    std::uint64_t raw_offset = 0;
    std::uint32_t characteristics = 0;

    std::uint64_t mapped_size() const {
        std::uint64_t size = vsize;
        if (raw_size > size) size = raw_size;
        if (size < 0x1000) size = 0x1000;
        return size;
    }
    bool is_executable() const { return (characteristics & 0x20000000U) != 0; }
    bool is_writable() const { return (characteristics & 0x80000000U) != 0; }
    bool is_readonly_data() const {
        return (characteristics & 0x40000000U) != 0 && !is_executable() &&
               !is_writable();
    }
};

struct ModuleInfo {
    std::string name;        // basename, e.g. "UnityPlayer.dll"
    std::string path;        // UTF-8 full path
    std::uint64_t base = 0;  // mapped image base
    std::uint64_t size = 0;  // SizeOfImage from GetModuleInformation

    std::vector<PeSection> sections;

    bool contains(std::uint64_t addr) const {
        return addr >= base && addr - base < size;
    }

    const PeSection* section_at_rva(std::uint64_t rva) const {
        for (const PeSection& section : sections) {
            if (rva >= section.rva && rva - section.rva < section.mapped_size()) {
                return &section;
            }
        }
        return nullptr;
    }

    const PeSection* section_at_addr(std::uint64_t addr) const {
        if (!contains(addr)) {
            return nullptr;
        }
        return section_at_rva(addr - base);
    }
};

// Parses the PE headers that are mapped at `base`. Returns false and sets
// `error` when headers are truncated or malformed. Only reads within
// [base, base + size).
bool parse_pe_from_memory(std::uint64_t base, std::uint64_t size,
                          std::vector<PeSection>& out_sections, std::string& error);

}  // namespace hsr_probe
