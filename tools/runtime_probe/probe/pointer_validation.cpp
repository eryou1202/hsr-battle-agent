#include "pointer_validation.h"

#include <windows.h>

#include <algorithm>

namespace hsr_probe {

namespace {

constexpr std::uint64_t kCanonicalUserMask = 0xFFFF000000000000ULL;
constexpr std::uint64_t kMinUserAddress = 0x10000ULL;

bool protection_readable(std::uint32_t protect) {
    switch (protect) {
        case PAGE_READONLY:
        case PAGE_READWRITE:
        case PAGE_WRITECOPY:
        case PAGE_EXECUTE_READ:
        case PAGE_EXECUTE_READWRITE:
        case PAGE_EXECUTE_WRITECOPY:
            return true;
        default:
            return false;
    }
}

bool protection_executable(std::uint32_t protect) {
    switch (protect) {
        case PAGE_EXECUTE:
        case PAGE_EXECUTE_READ:
        case PAGE_EXECUTE_READWRITE:
        case PAGE_EXECUTE_WRITECOPY:
            return true;
        default:
            return false;
    }
}

}  // namespace

PointerCheck PointerValidator::check_generic(std::uint64_t addr) const {
    PointerCheck check;
    check.canonical = addr >= kMinUserAddress && (addr & kCanonicalUserMask) == 0;
    if (!check.canonical) {
        return check;
    }

    if (modules_ != nullptr) {
        for (const ModuleInfo& module : *modules_) {
            if (module.contains(addr)) {
                check.module = module.name;
                const PeSection* section = module.section_at_addr(addr);
                if (section != nullptr) {
                    check.section = section->name;
                }
                break;
            }
        }
    }

    MEMORY_BASIC_INFORMATION info{};
    if (VirtualQuery(reinterpret_cast<const void*>(addr), &info,
                     sizeof(info)) != 0) {
        check.committed = info.State == MEM_COMMIT;
        check.protect = info.Protect;
        check.readable = check.committed && protection_readable(info.Protect);
        check.executable = check.committed && protection_executable(info.Protect);
    }
    check.valid = check.committed && check.readable;
    return check;
}

PointerCheck PointerValidator::check_exec_function(std::uint64_t addr) const {
    PointerCheck check = check_generic(addr);
    if (!check.valid || !check.executable) {
        check.valid = false;
        return check;
    }
    if (modules_ == nullptr) {
        check.valid = false;
        return check;
    }
    bool in_exec_section = false;
    for (const ModuleInfo& module : *modules_) {
        if (!module.contains(addr)) {
            continue;
        }
        const PeSection* section = module.section_at_addr(addr);
        if (section != nullptr && section->is_executable()) {
            in_exec_section = true;
        }
        break;
    }
    check.valid = in_exec_section;
    return check;
}

bool PointerValidator::read_bytes(std::uint64_t addr, std::size_t size,
                                  std::vector<std::uint8_t>& out,
                                  PointerCheck* check) const {
    PointerCheck local = check_generic(addr);
    if (check != nullptr) {
        *check = local;
    }
    out.clear();
    if (size == 0) {
        return local.valid;
    }
    if (!local.valid) {
        return false;
    }
    out.resize(size);
    SIZE_T done = 0;
    const BOOL ok = ReadProcessMemory(GetCurrentProcess(),
                                      reinterpret_cast<const void*>(addr),
                                      out.data(), size, &done);
    if (ok == FALSE || done != size) {
        out.clear();
        return false;
    }
    return true;
}

bool PointerValidator::read_cstring(std::uint64_t addr, std::size_t max_len,
                                    std::string& out, PointerCheck* check) const {
    PointerCheck local = check_generic(addr);
    if (check != nullptr) {
        *check = local;
    }
    out.clear();
    if (!local.valid || max_len == 0) {
        return false;
    }
    std::vector<std::uint8_t> chunk;
    std::size_t offset = 0;
    while (offset < max_len) {
        const std::size_t want = (std::min)(std::size_t{256}, max_len - offset + 1);
        chunk.clear();
        if (!read_bytes(addr + offset, want, chunk, nullptr)) {
            return false;
        }
        bool terminated = false;
        std::size_t take = 0;
        for (std::size_t i = 0; i < chunk.size(); ++i) {
            take = i;
            if (chunk[i] == 0) {
                terminated = true;
                break;
            }
        }
        out.append(reinterpret_cast<const char*>(chunk.data()), take);
        if (terminated) {
            return true;
        }
        offset += chunk.size();
        if (chunk.size() < want) {
            break;
        }
    }
    // No terminator within max_len.
    out.clear();
    return false;
}

bool is_printable_utf8_string(const std::string& text) {
    for (std::size_t i = 0; i < text.size();) {
        const unsigned char c = static_cast<unsigned char>(text[i]);
        if (c < 0x20) {
            return false;
        }
        if (c < 0x80) {
            ++i;
            continue;
        }
        int extra = 0;
        if ((c & 0xE0) == 0xC0) {
            extra = 1;
        } else if ((c & 0xF0) == 0xE0) {
            extra = 2;
        } else if ((c & 0xF8) == 0xF0) {
            extra = 3;
        } else {
            return false;
        }
        if (i + static_cast<std::size_t>(extra) >= text.size()) {
            return false;
        }
        for (int j = 1; j <= extra; ++j) {
            if ((static_cast<unsigned char>(text[i + static_cast<std::size_t>(j)]) &
                 0xC0) != 0x80) {
                return false;
            }
        }
        i += static_cast<std::size_t>(extra) + 1;
    }
    return true;
}

}  // namespace hsr_probe
