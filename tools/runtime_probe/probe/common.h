#pragma once

// common.h - shared small utilities for the runtime health-check probe.
//
// Everything in this probe is read-only with respect to the game process:
// the only writes are the probe's own log/JSON files and its own console.

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

#include <cstdint>
#include <string>
#include <vector>

namespace hsr_probe {

inline constexpr std::size_t kApiTableSlotCount = 240;

// Required API slots for the minimal health-check chain. Indices are the
// standard il2cpp api-table order validated by
// tools/reverse/scripts/find_il2cpp_api_table.py.
inline constexpr int kSlotAssemblyGetImage = 22;
inline constexpr int kSlotClassGetName = 37;
inline constexpr int kSlotClassGetNamespace = 39;
inline constexpr int kSlotDomainGet = 63;
inline constexpr int kSlotDomainGetAssemblies = 65;
inline constexpr int kSlotImageGetName = 168;
inline constexpr int kSlotImageGetClassCount = 169;
inline constexpr int kSlotImageGetClass = 170;

std::string wide_to_utf8(const std::wstring& wide);
std::wstring utf8_to_wide(const std::string& utf8);
std::string now_utc_iso();
std::string now_utc_compact();
std::string format_hex(std::uint64_t value);
std::string lower_ascii(std::string value);
bool read_entire_file(const std::wstring& path, std::vector<std::uint8_t>& out);
bool write_entire_file(const std::wstring& path, const std::string& content);

// Python-style round(x, 2): round-half-to-even on x*100 then divide by 100.
// The Python locator uses round(score, 2); this keeps C++/Python outputs equal.
double py_round2(double value);

}  // namespace hsr_probe
