#include "common.h"

#include <cfenv>
#include <cmath>
#include <cstdio>
#include <fstream>

namespace hsr_probe {

std::string wide_to_utf8(const std::wstring& wide) {
    if (wide.empty()) {
        return {};
    }
    const int size = WideCharToMultiByte(CP_UTF8, 0, wide.data(),
                                         static_cast<int>(wide.size()), nullptr, 0,
                                         nullptr, nullptr);
    if (size <= 0) {
        return {};
    }
    std::string out(static_cast<std::size_t>(size), '\0');
    WideCharToMultiByte(CP_UTF8, 0, wide.data(), static_cast<int>(wide.size()),
                        out.data(), size, nullptr, nullptr);
    return out;
}

std::wstring utf8_to_wide(const std::string& utf8) {
    if (utf8.empty()) {
        return {};
    }
    const int size = MultiByteToWideChar(CP_UTF8, 0, utf8.data(),
                                         static_cast<int>(utf8.size()), nullptr, 0);
    if (size <= 0) {
        return {};
    }
    std::wstring out(static_cast<std::size_t>(size), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, utf8.data(), static_cast<int>(utf8.size()),
                        out.data(), size);
    return out;
}

std::string now_utc_iso() {
    SYSTEMTIME st{};
    GetSystemTime(&st);
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02dZ",
                  st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    return buf;
}

std::string now_utc_compact() {
    SYSTEMTIME st{};
    GetSystemTime(&st);
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%04d%02d%02dT%02d%02d%02d",
                  st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    return buf;
}

std::string format_hex(std::uint64_t value) {
    char buf[32];
    std::snprintf(buf, sizeof(buf), "0x%llX", static_cast<unsigned long long>(value));
    return buf;
}

std::string lower_ascii(std::string value) {
    for (char& c : value) {
        if (c >= 'A' && c <= 'Z') {
            c = static_cast<char>(c - 'A' + 'a');
        }
    }
    return value;
}

bool read_entire_file(const std::wstring& path, std::vector<std::uint8_t>& out) {
    out.clear();
    HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) {
        return false;
    }
    LARGE_INTEGER size{};
    const bool got_size = GetFileSizeEx(h, &size) != FALSE;
    if (!got_size || size.QuadPart < 0 || size.QuadPart > 0x40000000LL) {
        CloseHandle(h);
        return false;
    }
    out.resize(static_cast<std::size_t>(size.QuadPart));
    std::size_t done = 0;
    bool ok = true;
    while (done < out.size()) {
        DWORD chunk = 0;
        const DWORD want = static_cast<DWORD>(
            (std::min)(static_cast<std::uint64_t>(out.size() - done),
                       static_cast<std::uint64_t>(0x4000000)));
        if (ReadFile(h, out.data() + done, want, &chunk, nullptr) == FALSE ||
            chunk == 0) {
            ok = false;
            break;
        }
        done += chunk;
    }
    CloseHandle(h);
    if (ok) {
        out.resize(done);
    }
    return ok;
}

bool write_entire_file(const std::wstring& path, const std::string& content) {
    HANDLE h = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) {
        return false;
    }
    DWORD done = 0;
    const BOOL ok = WriteFile(h, content.data(), static_cast<DWORD>(content.size()),
                              &done, nullptr);
    CloseHandle(h);
    return ok != FALSE && done == content.size();
}

double py_round2(double value) {
    std::fenv_t env{};
    std::fegetenv(&env);
    std::fesetround(FE_TONEAREST);
    const double scaled = std::nearbyint(value * 100.0);
    std::fesetenv(&env);
    return scaled / 100.0;
}

}  // namespace hsr_probe
