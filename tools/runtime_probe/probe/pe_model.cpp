#include "pe_model.h"

#include <windows.h>

#include <cstring>

namespace hsr_probe {

namespace {

bool copy_at(std::uint64_t base, std::uint64_t size, std::uint64_t offset,
             void* out, std::size_t count) {
    if (offset > size || count > size - offset) {
        return false;
    }
    std::memcpy(out, reinterpret_cast<const void*>(base + offset), count);
    return true;
}

}  // namespace

bool parse_pe_from_memory(std::uint64_t base, std::uint64_t size,
                          std::vector<PeSection>& out_sections, std::string& error) {
    out_sections.clear();
    if (size < sizeof(IMAGE_DOS_HEADER)) {
        error = "module too small for DOS header";
        return false;
    }
    IMAGE_DOS_HEADER dos{};
    copy_at(base, size, 0, &dos, sizeof(dos));
    if (dos.e_magic != IMAGE_DOS_SIGNATURE) {
        error = "bad MZ signature";
        return false;
    }
    const std::uint64_t nt_offset = dos.e_lfanew;
    IMAGE_NT_HEADERS64 nt{};
    if (!copy_at(base, size, nt_offset, &nt, sizeof(nt))) {
        error = "bad NT header offset";
        return false;
    }
    if (nt.Signature != IMAGE_NT_SIGNATURE) {
        error = "bad PE signature";
        return false;
    }
    if (nt.FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64) {
        error = "not a PE32+ (AMD64) image";
        return false;
    }
    const std::uint64_t section_table = nt_offset + offsetof(IMAGE_NT_HEADERS64, OptionalHeader) +
                                        nt.FileHeader.SizeOfOptionalHeader;
    for (int i = 0; i < nt.FileHeader.NumberOfSections; ++i) {
        IMAGE_SECTION_HEADER header{};
        if (!copy_at(base, size, section_table + static_cast<std::uint64_t>(i) *
                                                  sizeof(IMAGE_SECTION_HEADER),
                     &header, sizeof(header))) {
            error = "truncated section table";
            return false;
        }
        PeSection section;
        char name[9] = {};
        std::memcpy(name, header.Name, 8);
        section.name = name;
        section.rva = header.VirtualAddress;
        section.vsize = header.Misc.VirtualSize;
        section.raw_size = header.SizeOfRawData;
        section.raw_offset = header.PointerToRawData;
        section.characteristics = header.Characteristics;
        if (section.rva > size || section.mapped_size() > size - section.rva) {
            error = "section " + section.name + " exceeds mapped module size";
            return false;
        }
        out_sections.push_back(std::move(section));
    }
    return true;
}

}  // namespace hsr_probe
