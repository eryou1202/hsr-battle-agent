// load_probe.cpp - explicit, visible research loader for the local,
// normally-initialized StarRail client.
//
// Mechanism: standard Win32 LoadLibraryW via CreateRemoteThread. The probe
// DLL appears in the target's module list under its real name
// (`hsr_runtime_health_probe.dll`). This loader does NOT:
//   - hide the module / unlink it from the PEB
//   - manual-map or use reflective loading
//   - hook, patch, or otherwise modify game code or data
//   - attempt to bypass any protection or anti-cheat
//
// If the client/protection rejects the standard loader path, the correct
// action is to STOP and report BLOCKED - never to escalate or evade.

#include <windows.h>
#include <psapi.h>
#include <tlhelp32.h>

#include <algorithm>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <optional>
#include <string>
#include <vector>

#include "../probe/api_locator.h"

#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "psapi.lib")

namespace {

struct Options {
    std::wstring process_name = L"StarRail.exe";
    std::wstring dll_path;
    DWORD pid = 0;
    bool check_only = false;
    bool list_only = false;
    DWORD timeout_ms = 30000;
};

std::wstring lower_wide(std::wstring value) {
    for (wchar_t& c : value) {
        if (c >= L'A' && c <= L'Z') {
            c = static_cast<wchar_t>(c - L'A' + L'a');
        }
    }
    return value;
}

std::wstring basename(const std::wstring& path) {
    const std::size_t pos = path.find_last_of(L"\\/");
    return pos == std::wstring::npos ? path : path.substr(pos + 1);
}

std::string utf8(const std::wstring& wide) {
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

void print_usage() {
    wprintf(L"Usage: load_probe.exe [options]\n"
            L"\n"
            L"Visible research loader for hsr_runtime_health_probe.dll.\n"
            L"\n"
            L"  --process <name>   target process name (default: StarRail.exe)\n"
            L"  --pid <id>         target pid (overrides --process)\n"
            L"  --dll <path>       probe dll (default: <loader dir>\\hsr_runtime_health_probe.dll)\n"
            L"  --check-only       verify target modules without loading the probe\n"
            L"  --list             list matching processes and exit\n"
            L"  --timeout-ms <n>   remote LoadLibrary wait timeout (default: 30000)\n"
            L"  --help             show this help\n"
            L"\n"
            L"The probe is loaded with the documented Win32 LoadLibraryW path and stays\n"
            L"visible in the target module list. If loading is blocked, stop and report\n"
            L"BLOCKED; this tool never bypasses protection.\n");
}

bool parse_args(int argc, wchar_t** argv, Options& options) {
    for (int i = 1; i < argc; ++i) {
        const std::wstring arg = argv[i];
        auto next = [&](std::wstring& out) -> bool {
            if (i + 1 >= argc) {
                wprintf(L"missing value for %s\n", arg.c_str());
                return false;
            }
            out = argv[++i];
            return true;
        };
        if (arg == L"--help" || arg == L"-h") {
            print_usage();
            return false;
        } else if (arg == L"--process") {
            if (!next(options.process_name)) return false;
        } else if (arg == L"--pid") {
            std::wstring value;
            if (!next(value)) return false;
            options.pid = static_cast<DWORD>(std::wcstoul(value.c_str(), nullptr, 10));
        } else if (arg == L"--dll") {
            if (!next(options.dll_path)) return false;
        } else if (arg == L"--check-only") {
            options.check_only = true;
        } else if (arg == L"--list") {
            options.list_only = true;
        } else if (arg == L"--timeout-ms") {
            std::wstring value;
            if (!next(value)) return false;
            options.timeout_ms = static_cast<DWORD>(std::wcstoul(value.c_str(), nullptr, 10));
        } else {
            wprintf(L"unknown argument: %s\n\n", arg.c_str());
            print_usage();
            return false;
        }
    }
    return true;
}

std::vector<DWORD> find_processes(const std::wstring& name) {
    std::vector<DWORD> result;
    const HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return result;
    }
    PROCESSENTRY32W entry{};
    entry.dwSize = sizeof(entry);
    const std::wstring wanted = lower_wide(name);
    if (Process32FirstW(snapshot, &entry)) {
        do {
            if (lower_wide(entry.szExeFile) == wanted) {
                result.push_back(entry.th32ProcessID);
            }
        } while (Process32NextW(snapshot, &entry));
    }
    CloseHandle(snapshot);
    return result;
}

bool process_name_for(DWORD pid, std::wstring& name) {
    const HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return false;
    }
    PROCESSENTRY32W entry{};
    entry.dwSize = sizeof(entry);
    bool found = false;
    if (Process32FirstW(snapshot, &entry)) {
        do {
            if (entry.th32ProcessID == pid) {
                name = entry.szExeFile;
                found = true;
                break;
            }
        } while (Process32NextW(snapshot, &entry));
    }
    CloseHandle(snapshot);
    return found;
}

struct ModuleRecord {
    bool present = false;
    std::wstring path;
    std::uint64_t base = 0;
    std::uint64_t size = 0;
};

struct ModuleSnapshot {
    DWORD pid = 0;
    ModuleRecord exe;
    ModuleRecord unity;
    ModuleRecord game;
    bool has_probe = false;

    // Raw diagnostics for TH32CS_SNAPMODULE enumeration (check-only only).
    bool snapshot_handle_valid = false;
    DWORD snapshot_error = 0;
    bool module_first_valid = false;
    DWORD module_first_error = 0;
    std::size_t module_count = 0;

    // Raw diagnostics for the PSAPI fallback (check-only only).
    bool psapi_attempted = false;
    bool psapi_ok = false;
    DWORD psapi_error = 0;
    DWORD psapi_needed = 0;
    std::size_t psapi_module_count = 0;
};

ModuleSnapshot inspect_modules(DWORD pid) {
    ModuleSnapshot result;
    result.pid = pid;
    const HANDLE snapshot =
        CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid);
    if (snapshot == INVALID_HANDLE_VALUE) {
        result.snapshot_handle_valid = false;
        result.snapshot_error = GetLastError();
        return result;
    }
    result.snapshot_handle_valid = true;
    result.snapshot_error = 0;

    MODULEENTRY32W entry{};
    entry.dwSize = sizeof(entry);
    if (Module32FirstW(snapshot, &entry) == FALSE) {
        result.module_first_valid = false;
        result.module_first_error = GetLastError();
        CloseHandle(snapshot);
        return result;
    }
    result.module_first_valid = true;
    result.module_first_error = 0;

    bool first = true;
    do {
        ++result.module_count;
        const std::wstring name = lower_wide(basename(entry.szExePath));
        if (name == L"unityplayer.dll") {
            result.unity = {true, entry.szExePath,
                            reinterpret_cast<std::uint64_t>(entry.modBaseAddr),
                            entry.modBaseSize};
        } else if (name == L"gameassembly.dll") {
            result.game = {true, entry.szExePath,
                           reinterpret_cast<std::uint64_t>(entry.modBaseAddr),
                           entry.modBaseSize};
        } else if (name == L"hsr_runtime_health_probe.dll") {
            result.has_probe = true;
        }
        if (first) {
            result.exe = {true, entry.szExePath,
                          reinterpret_cast<std::uint64_t>(entry.modBaseAddr),
                          entry.modBaseSize};
            first = false;
        }
    } while (Module32NextW(snapshot, &entry) != FALSE);
    CloseHandle(snapshot);
    return result;
}

// Read-only PSAPI fallback used only when the Toolhelp module snapshot was
// denied. Opens PROCESS_QUERY_INFORMATION | PROCESS_VM_READ (already verified
// by the diagnostic collector), enumerates with EnumProcessModulesEx and
// resolves UnityPlayer.dll / GameAssembly.dll by basename, never by order.
bool enumerate_modules_psapi(DWORD pid, ModuleSnapshot& out) {
    out.psapi_attempted = true;
    const HANDLE process =
        OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (process == nullptr) {
        out.psapi_ok = false;
        out.psapi_error = GetLastError();
        return false;
    }

    constexpr DWORD kMaxModules = 8192;
    std::vector<HMODULE> modules(kMaxModules, nullptr);
    DWORD needed = 0;
    if (EnumProcessModulesEx(process, modules.data(),
                             static_cast<DWORD>(modules.size() * sizeof(HMODULE)),
                             &needed, LIST_MODULES_ALL) == FALSE) {
        out.psapi_ok = false;
        out.psapi_error = GetLastError();
        out.psapi_needed = needed;
        CloseHandle(process);
        return false;
    }
    out.psapi_ok = true;
    out.psapi_error = 0;
    out.psapi_needed = needed;
    const std::size_t count = (std::min)(
        static_cast<std::size_t>(needed / sizeof(HMODULE)),
        static_cast<std::size_t>(kMaxModules));
    out.psapi_module_count = count;

    for (std::size_t i = 0; i < count; ++i) {
        wchar_t path[MAX_PATH] = {};
        if (GetModuleFileNameExW(process, modules[i], path, MAX_PATH) == 0) {
            continue;
        }
        MODULEINFO info{};
        if (GetModuleInformation(process, modules[i], &info, sizeof(info)) == FALSE) {
            continue;
        }
        const std::wstring name = lower_wide(basename(path));
        if (name == L"unityplayer.dll") {
            out.unity = {true, path,
                         reinterpret_cast<std::uint64_t>(info.lpBaseOfDll),
                         static_cast<std::uint64_t>(info.SizeOfImage)};
        } else if (name == L"gameassembly.dll") {
            out.game = {true, path,
                        reinterpret_cast<std::uint64_t>(info.lpBaseOfDll),
                        static_cast<std::uint64_t>(info.SizeOfImage)};
        } else if (name == L"hsr_runtime_health_probe.dll") {
            out.has_probe = true;
        }
    }
    CloseHandle(process);
    return true;
}

// Shared module resolution: try Toolhelp first; if it was denied, reuse the
// official PSAPI fallback. Used by both --check-only selection and the real
// loader preflight. This changes only module discovery, never the loading
// mechanism.
ModuleSnapshot resolve_modules(DWORD pid) {
    ModuleSnapshot modules = inspect_modules(pid);
    if (!modules.snapshot_handle_valid &&
        modules.snapshot_error == ERROR_ACCESS_DENIED) {
        enumerate_modules_psapi(pid, modules);
    }
    return modules;
}

std::string win_error(DWORD code);

struct IntegrityDiagnostics {
    bool token_open_ok = false;
    DWORD token_open_error = 0;
    bool integrity_query_ok = false;
    DWORD integrity_query_error = 0;
    DWORD rid = 0;
    std::wstring level;
    bool elevation_query_ok = false;
    DWORD elevation_query_error = 0;
    bool elevated = false;
};

std::wstring integrity_level_name(DWORD rid) {
    switch (rid) {
        case 0x0000: return L"Untrusted";
        case 0x1000: return L"Low";
        case 0x2000: return L"Medium";
        case 0x3000: return L"High";
        case 0x4000: return L"System";
        case 0x5000: return L"ProtectedProcess";
        default: return L"Unknown";
    }
}

// Read-only token diagnostics. OpenProcessToken + GetTokenInformation
// (TokenIntegrityLevel, TokenElevation). No privileges are adjusted and no
// handle keeps any write access.
IntegrityDiagnostics query_integrity_diagnostics(HANDLE process) {
    IntegrityDiagnostics diag;
    HANDLE token = nullptr;
    if (OpenProcessToken(process, TOKEN_QUERY, &token) == FALSE) {
        diag.token_open_ok = false;
        diag.token_open_error = GetLastError();
        return diag;
    }
    diag.token_open_ok = true;
    diag.token_open_error = 0;

    DWORD needed = 0;
    GetTokenInformation(token, TokenIntegrityLevel, nullptr, 0, &needed);
    if (needed == 0) {
        diag.integrity_query_ok = false;
        diag.integrity_query_error = GetLastError();
    } else {
        std::vector<std::uint8_t> buffer(needed);
        if (GetTokenInformation(token, TokenIntegrityLevel, buffer.data(), needed,
                                &needed) == FALSE) {
            diag.integrity_query_ok = false;
            diag.integrity_query_error = GetLastError();
        } else {
            const auto* label =
                reinterpret_cast<const TOKEN_MANDATORY_LABEL*>(buffer.data());
            PSID sid = label->Label.Sid;
            if (sid == nullptr) {
                diag.integrity_query_ok = false;
                diag.integrity_query_error = ERROR_INVALID_SID;
            } else {
                diag.integrity_query_ok = true;
                diag.integrity_query_error = 0;
                const DWORD count = *GetSidSubAuthorityCount(sid);
                diag.rid = count == 0 ? 0 : *GetSidSubAuthority(sid, count - 1);
                diag.level = integrity_level_name(diag.rid);
            }
        }
    }

    TOKEN_ELEVATION elevation{};
    DWORD elevation_size = sizeof(elevation);
    if (GetTokenInformation(token, TokenElevation, &elevation, elevation_size,
                            &elevation_size) == FALSE) {
        diag.elevation_query_ok = false;
        diag.elevation_query_error = GetLastError();
    } else {
        diag.elevation_query_ok = true;
        diag.elevation_query_error = 0;
        diag.elevated = elevation.TokenIsElevated != 0;
    }

    CloseHandle(token);
    return diag;
}

struct ProcessDiagnostics {
    DWORD pid = 0;
    bool open_limited_ok = false;
    DWORD open_limited_error = 0;
    bool open_read_ok = false;
    DWORD open_read_error = 0;
    bool path_ok = false;
    DWORD path_error = 0;
    std::wstring path;
    bool times_ok = false;
    DWORD times_error = 0;
    std::wstring creation_time_utc;
    std::wstring creation_time_local;
    IntegrityDiagnostics integrity;
};

// Read-only per-process diagnostic collection. Opens each requested access
// combination separately, records success + GetLastError, and closes the
// handle. Never writes to the target process.
ProcessDiagnostics collect_process_diagnostics(DWORD pid) {
    ProcessDiagnostics diag;
    diag.pid = pid;

    const HANDLE limited =
        OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (limited == nullptr) {
        diag.open_limited_ok = false;
        diag.open_limited_error = GetLastError();
    } else {
        diag.open_limited_ok = true;
        diag.open_limited_error = 0;

        FILETIME creation{};
        FILETIME exit_time{};
        FILETIME kernel_time{};
        FILETIME user_time{};
        if (GetProcessTimes(limited, &creation, &exit_time, &kernel_time,
                            &user_time) == FALSE) {
            diag.times_ok = false;
            diag.times_error = GetLastError();
        } else {
            diag.times_ok = true;
            diag.times_error = 0;
            SYSTEMTIME st_utc{};
            FileTimeToSystemTime(&creation, &st_utc);
            wchar_t buffer[64] = {};
            std::swprintf(buffer, 64, L"%04u-%02u-%02u %02u:%02u:%02u",
                          st_utc.wYear, st_utc.wMonth, st_utc.wDay,
                          st_utc.wHour, st_utc.wMinute, st_utc.wSecond);
            diag.creation_time_utc = buffer;

            FILETIME local_ft{};
            SYSTEMTIME st_local{};
            if (FileTimeToLocalFileTime(&creation, &local_ft) != FALSE &&
                FileTimeToSystemTime(&local_ft, &st_local) != FALSE) {
                std::swprintf(buffer, 64, L"%04u-%02u-%02u %02u:%02u:%02u",
                              st_local.wYear, st_local.wMonth, st_local.wDay,
                              st_local.wHour, st_local.wMinute, st_local.wSecond);
                diag.creation_time_local = buffer;
            }
        }

        wchar_t path[MAX_PATH] = {};
        DWORD path_len = MAX_PATH;
        if (QueryFullProcessImageNameW(limited, 0, path, &path_len) == FALSE) {
            diag.path_ok = false;
            diag.path_error = GetLastError();
        } else {
            diag.path_ok = true;
            diag.path_error = 0;
            diag.path = path;
        }

        diag.integrity = query_integrity_diagnostics(limited);
        CloseHandle(limited);
    }

    const HANDLE read_handle =
        OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (read_handle == nullptr) {
        diag.open_read_ok = false;
        diag.open_read_error = GetLastError();
    } else {
        diag.open_read_ok = true;
        diag.open_read_error = 0;
        CloseHandle(read_handle);
    }
    return diag;
}

// For --check-only: list every matching process (PID / start time / module
// state) and select the single one that has BOTH UnityPlayer.dll and
// GameAssembly.dll. Never silently picks the first process.
bool select_game_process_check_only(const std::vector<DWORD>& processes,
                                    DWORD& selected_pid,
                                    std::vector<ModuleSnapshot>& snapshots) {
    snapshots.clear();
    std::vector<DWORD> fully_initialized;
    ProcessDiagnostics first_diag;
    bool have_diag = false;
    wprintf(L"%zu StarRail.exe process(es) found:\n", processes.size());

    const IntegrityDiagnostics probe_integrity =
        query_integrity_diagnostics(GetCurrentProcess());
    wprintf(L"probe integrity: token_open=%d (error=%lu) rid=0x%04lX level=%s "
            L"elevated=%d (elevation_query_ok=%d error=%lu)\n",
            probe_integrity.token_open_ok ? 1 : 0,
            static_cast<unsigned long>(probe_integrity.token_open_error),
            static_cast<unsigned long>(probe_integrity.rid),
            probe_integrity.level.c_str(),
            probe_integrity.elevated ? 1 : 0,
            probe_integrity.elevation_query_ok ? 1 : 0,
            static_cast<unsigned long>(probe_integrity.elevation_query_error));

    for (DWORD candidate : processes) {
        ModuleSnapshot modules = inspect_modules(candidate);
        snapshots.push_back(modules);
        ProcessDiagnostics diag;
        if (!have_diag) {
            diag = collect_process_diagnostics(candidate);
            first_diag = diag;
            have_diag = true;
        } else {
            diag = collect_process_diagnostics(candidate);
        }
        std::wstring name;
        process_name_for(candidate, name);

        wprintf(L"  pid=%lu name=%s\n", candidate, name.c_str());
        wprintf(L"    started_utc=%s started_local=%s times_ok=%d times_error=%lu\n",
                diag.times_ok ? diag.creation_time_utc.c_str() : L"unavailable",
                diag.times_ok ? (diag.creation_time_local.empty()
                                     ? L"unavailable"
                                     : diag.creation_time_local.c_str())
                              : L"unavailable",
                diag.times_ok ? 1 : 0,
                static_cast<unsigned long>(diag.times_error));
        wprintf(L"    QueryFullProcessImageNameW: %s path=%s (error=%lu %hs)\n",
                diag.path_ok ? L"OK" : L"FAIL",
                diag.path_ok ? diag.path.c_str() : L"<none>",
                static_cast<unsigned long>(diag.path_error),
                diag.path_error == 0 ? "" : win_error(diag.path_error).c_str());
        wprintf(L"    OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION): %s "
                L"(error=%lu %hs)\n",
                diag.open_limited_ok ? L"OK" : L"FAIL",
                static_cast<unsigned long>(diag.open_limited_error),
                diag.open_limited_error == 0 ? ""
                                             : win_error(diag.open_limited_error).c_str());
        wprintf(L"    OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ): %s "
                L"(error=%lu %hs)\n",
                diag.open_read_ok ? L"OK" : L"FAIL",
                static_cast<unsigned long>(diag.open_read_error),
                diag.open_read_error == 0 ? "" : win_error(diag.open_read_error).c_str());
        wprintf(L"    target OpenProcessToken: %s (error=%lu %hs); "
                L"integrity_query=%s rid=0x%04lX level=%s; elevated=%d "
                L"(elevation_query_ok=%d error=%lu)\n",
                diag.integrity.token_open_ok ? L"OK" : L"FAIL",
                static_cast<unsigned long>(diag.integrity.token_open_error),
                diag.integrity.token_open_error == 0
                    ? ""
                    : win_error(diag.integrity.token_open_error).c_str(),
                diag.integrity.integrity_query_ok ? L"OK" : L"FAIL",
                static_cast<unsigned long>(diag.integrity.rid),
                diag.integrity.level.c_str(),
                diag.integrity.elevated ? 1 : 0,
                diag.integrity.elevation_query_ok ? 1 : 0,
                static_cast<unsigned long>(diag.integrity.elevation_query_error));

        if (!modules.snapshot_handle_valid) {
            // B: CreateToolhelp32Snapshot(TH32CS_SNAPMODULE...) failed.
            wprintf(L"    module_snapshot=FAIL handle=INVALID error=%lu (%hs)\n",
                    static_cast<unsigned long>(modules.snapshot_error),
                    win_error(modules.snapshot_error).c_str());
            wprintf(L"    classification=B(snapshot_failed); "
                    L"unity/game presence UNKNOWN\n");
        } else if (!modules.module_first_valid) {
            // C: snapshot succeeded but Module32FirstW failed.
            wprintf(L"    module_snapshot=OK handle=VALID; Module32FirstW=FAIL "
                    L"error=%lu (%hs)\n",
                    static_cast<unsigned long>(modules.module_first_error),
                    win_error(modules.module_first_error).c_str());
            wprintf(L"    classification=C(Module32FirstW_failed); "
                    L"unity/game presence UNKNOWN\n");
        } else if (modules.module_count == 0) {
            // A: real enumeration succeeded and truly produced zero entries.
            wprintf(L"    module_snapshot=OK handle=VALID; Module32FirstW=OK; "
                    L"module_count=0\n");
            wprintf(L"    classification=A(snapshot_ok_real_zero_modules); "
                    L"unity/game presence UNKNOWN\n");
        } else {
            // D would be reported through the OpenProcess lines above.
            wprintf(L"    module_snapshot=OK handle=VALID; Module32FirstW=OK; "
                    L"module_count=%zu\n",
                    modules.module_count);
            wprintf(L"    unity=%s game=%s probe=%s\n",
                    modules.unity.present ? L"yes" : L"no",
                    modules.game.present ? L"yes" : L"no",
                    modules.has_probe ? L"yes" : L"no");
        }

        // Official PSAPI fallback only when Toolhelp was denied with
        // ERROR_ACCESS_DENIED. Uses PROCESS_QUERY_INFORMATION | PROCESS_VM_READ.
        if (!modules.snapshot_handle_valid &&
            modules.snapshot_error == ERROR_ACCESS_DENIED) {
            wprintf(L"    probe_arch=%hs\n", sizeof(void*) == 8 ? "x64" : "x86");
            enumerate_modules_psapi(candidate, modules);
            wprintf(L"    PSAPI EnumProcessModulesEx(LIST_MODULES_ALL): %s "
                    L"error=%lu (%hs) lpcbNeeded=%lu module_count=%zu\n",
                    modules.psapi_ok ? L"OK" : L"FAIL",
                    static_cast<unsigned long>(modules.psapi_error),
                    modules.psapi_error == 0 ? "" : win_error(modules.psapi_error).c_str(),
                    static_cast<unsigned long>(modules.psapi_needed),
                    modules.psapi_module_count);
            if (modules.psapi_ok) {
                if (modules.unity.present || modules.game.present) {
                    wprintf(L"    PSAPI unity=%s game=%s\n",
                            modules.unity.present ? L"yes" : L"no",
                            modules.game.present ? L"yes" : L"no");
                } else {
                    wprintf(L"    PSAPI enumeration succeeded but "
                            L"UnityPlayer.dll/GameAssembly.dll were not found\n");
                }
            }
        }

        const bool toolhelp_enumeration_ok =
            modules.snapshot_handle_valid && modules.module_first_valid;
        const bool psapi_enumeration_ok = modules.psapi_ok;
        const bool enumeration_succeeded =
            toolhelp_enumeration_ok || psapi_enumeration_ok;
        if (enumeration_succeeded && modules.unity.present &&
            modules.game.present && !modules.has_probe) {
            fully_initialized.push_back(candidate);
        }
        // Store the post-fallback snapshot (PSAPI results included).
        if (!snapshots.empty()) {
            snapshots.back() = modules;
        }
    }

    if (fully_initialized.size() == 1) {
        selected_pid = fully_initialized.front();
        wprintf(L"selected game process: pid=%lu (only one with UnityPlayer.dll "
                L"and GameAssembly.dll)\n",
                selected_pid);
        return true;
    }
    if (fully_initialized.empty()) {
        wprintf(L"BLOCKED: no StarRail.exe process currently has both "
                L"UnityPlayer.dll and GameAssembly.dll.\n");
        if (!snapshots.empty()) {
            const ModuleSnapshot& first = snapshots.front();
            if (first.psapi_attempted && first.psapi_ok &&
                (!first.unity.present || !first.game.present)) {
                wprintf(L"PRECHECK = FAIL_NOT_INITIALIZED_OR_WRONG_PROCESS: "
                        L"PSAPI enumeration succeeded but UnityPlayer.dll=%s "
                        L"GameAssembly.dll=%s\n",
                        first.unity.present ? L"yes" : L"no",
                        first.game.present ? L"yes" : L"no");
                return false;
            }
            if (first.psapi_attempted && !first.psapi_ok) {
                wprintf(L"PRECHECK = BLOCKED_MODULE_ENUMERATION: "
                        L"EnumProcessModulesEx failed error=%lu (%hs)\n",
                        static_cast<unsigned long>(first.psapi_error),
                        win_error(first.psapi_error).c_str());
                return false;
            }
        }
        if (!have_diag) {
            wprintf(L"diagnostic: no process diagnostics were collected.\n");
        } else if (!first_diag.integrity.token_open_ok ||
                   !first_diag.integrity.integrity_query_ok) {
            wprintf(L"diagnostic: target integrity token is not readable; "
                    L"OpenProcessToken=%s error=%lu; GetTokenInformation=%s error=%lu\n",
                    first_diag.integrity.token_open_ok ? L"OK" : L"FAIL",
                    static_cast<unsigned long>(first_diag.integrity.token_open_error),
                    first_diag.integrity.integrity_query_ok ? L"OK" : L"FAIL",
                    static_cast<unsigned long>(first_diag.integrity.integrity_query_error));
        } else if (probe_integrity.integrity_query_ok &&
                   probe_integrity.rid != first_diag.integrity.rid) {
            wprintf(L"diagnostic: integrity-level mismatch probe=%s(0x%04lX) "
                    L"target=%s(0x%04lX)\n",
                    probe_integrity.level.c_str(),
                    static_cast<unsigned long>(probe_integrity.rid),
                    first_diag.integrity.level.c_str(),
                    static_cast<unsigned long>(first_diag.integrity.rid));
            if (probe_integrity.rid == 0x2000 &&
                first_diag.integrity.rid == 0x3000) {
                wprintf(L"LIKELY ROOT CAUSE: integrity-level mismatch "
                        L"(probe=Medium target=High). Do NOT self-elevate; "
                        L"restart the harness at the same privilege level.\n");
            }
        } else if (!first_diag.open_read_ok) {
            wprintf(L"BLOCKED_BY_PROCESS_ACCESS_POLICY: probe and target integrity "
                    L"levels match, but PROCESS_VM_READ is still denied. "
                    L"Stop; no bypass.\n");
        }
        return false;
    }
    wprintf(L"BLOCKED: %zu processes have both UnityPlayer.dll and "
            L"GameAssembly.dll; re-run with --pid to disambiguate:\n",
            fully_initialized.size());
    for (DWORD candidate : fully_initialized) {
        wprintf(L"  --pid %lu\n", candidate);
    }
    return false;
}

std::string win_error(DWORD code) {
    wchar_t* buffer = nullptr;
    const DWORD size = FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER |
                                          FORMAT_MESSAGE_FROM_SYSTEM |
                                          FORMAT_MESSAGE_IGNORE_INSERTS,
                                      nullptr, code, 0,
                                      reinterpret_cast<wchar_t*>(&buffer), 0, nullptr);
    if (size != 0 && buffer != nullptr) {
        std::string message = utf8(buffer);
        LocalFree(buffer);
        return "error " + std::to_string(code) + ": " + message;
    }
    return "error " + std::to_string(code);
}

// Read-only external memory backend for the shared C++ api-table locator.
// It only uses ReadProcessMemory inside the module's mapped range and never
// writes to the target process.
class RemoteMemoryReader : public hsr_probe::LocatorMemory {
public:
    RemoteMemoryReader(HANDLE process, std::uint64_t base, std::uint64_t size)
        : process_(process), base_(base), size_(size) {}

    bool read_bytes(std::uint64_t absolute_addr, std::size_t size,
                    void* out) const override {
        if (absolute_addr < base_ || size > size_ ||
            absolute_addr - base_ > size_ - size) {
            return false;
        }
        std::size_t done = 0;
        while (done < size) {
            const std::size_t want =
                (std::min)(std::size_t{1} << 16, size - done);
            SIZE_T got = 0;
            if (ReadProcessMemory(process_,
                                  reinterpret_cast<const void*>(absolute_addr + done),
                                  static_cast<std::uint8_t*>(out) + done, want,
                                  &got) == FALSE ||
                got == 0) {
                return false;
            }
            done += static_cast<std::size_t>(got);
        }
        return true;
    }

private:
    HANDLE process_;
    std::uint64_t base_;
    std::uint64_t size_;
};

bool read_remote_bytes(HANDLE process, std::uint64_t addr, std::size_t size,
                       void* out) {
    std::size_t done = 0;
    while (done < size) {
        const std::size_t want = (std::min)(std::size_t{1} << 16, size - done);
        SIZE_T got = 0;
        if (ReadProcessMemory(process, reinterpret_cast<const void*>(addr + done),
                              static_cast<std::uint8_t*>(out) + done, want,
                              &got) == FALSE ||
            got == 0) {
            return false;
        }
        done += static_cast<std::size_t>(got);
    }
    return true;
}

// Parses the PE headers from the target process image without touching the
// target beyond ReadProcessMemory.
bool parse_remote_pe(HANDLE process, const ModuleRecord& record,
                     hsr_probe::ModuleInfo& out, std::string& error) {
    out = {};
    out.path = utf8(record.path);
    const std::wstring base_name = basename(record.path);
    out.name = utf8(base_name);
    out.base = record.base;
    out.size = record.size;

    IMAGE_DOS_HEADER dos{};
    if (!read_remote_bytes(process, record.base, sizeof(dos), &dos) ||
        dos.e_magic != IMAGE_DOS_SIGNATURE) {
        error = "remote DOS header is not readable or has a bad signature";
        return false;
    }
    const std::uint64_t nt_offset = dos.e_lfanew;
    IMAGE_NT_HEADERS64 nt{};
    if (!read_remote_bytes(process, record.base + nt_offset, sizeof(nt), &nt) ||
        nt.Signature != IMAGE_NT_SIGNATURE ||
        nt.FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64) {
        error = "remote NT header is not a valid PE32+ image";
        return false;
    }
    const std::uint64_t section_table =
        nt_offset + offsetof(IMAGE_NT_HEADERS64, OptionalHeader) +
        nt.FileHeader.SizeOfOptionalHeader;
    for (int i = 0; i < nt.FileHeader.NumberOfSections; ++i) {
        IMAGE_SECTION_HEADER header{};
        if (!read_remote_bytes(process,
                               record.base + section_table +
                                   static_cast<std::uint64_t>(i) * sizeof(header),
                               sizeof(header), &header)) {
            error = "remote section table is not readable";
            return false;
        }
        hsr_probe::PeSection section;
        char name[9] = {};
        std::memcpy(name, header.Name, 8);
        section.name = name;
        section.rva = header.VirtualAddress;
        section.vsize = header.Misc.VirtualSize;
        section.raw_size = header.SizeOfRawData;
        section.raw_offset = header.PointerToRawData;
        section.characteristics = header.Characteristics;
        if (section.rva > out.size || section.mapped_size() > out.size - section.rva) {
            error = "remote section " + section.name + " exceeds module size";
            return false;
        }
        out.sections.push_back(std::move(section));
    }
    return true;
}

std::optional<std::uint64_t> expected_rva_from_config(
    const std::wstring& self_dir) {
    wchar_t value[64] = {};
    const std::wstring ini = self_dir + L"\\probe_config.ini";
    if (GetPrivateProfileStringW(L"health_check", L"expected_table_rva", L"", value,
                                 64, ini.c_str()) == 0) {
        return std::nullopt;
    }
    std::wstring wide(value);
    const std::size_t pos = wide.find(L"0x");
    if (pos != std::wstring::npos) {
        wide = wide.substr(pos);
    }
    wchar_t* end = nullptr;
    const unsigned long long parsed = std::wcstoull(wide.c_str(), &end, 16);
    if (end == wide.c_str()) {
        return std::nullopt;
    }
    return static_cast<std::uint64_t>(parsed);
}

// Check-only path: process/module discovery + base/size + read-only remote
// locator. No LoadLibrary, no CreateRemoteThread, no writes, no runtime API.
int run_check_only(DWORD pid, const ModuleSnapshot& modules,
                   const std::wstring& self_dir) {
    wprintf(L"read-only check:\n");
    wprintf(L"  StarRail.exe    base=0x%llX size=0x%llX path=%s\n",
            static_cast<unsigned long long>(modules.exe.base),
            static_cast<unsigned long long>(modules.exe.size),
            modules.exe.path.c_str());
    wprintf(L"  UnityPlayer.dll base=0x%llX size=0x%llX path=%s\n",
            static_cast<unsigned long long>(modules.unity.base),
            static_cast<unsigned long long>(modules.unity.size),
            modules.unity.path.c_str());
    wprintf(L"  GameAssembly.dll base=0x%llX size=0x%llX path=%s\n",
            static_cast<unsigned long long>(modules.game.base),
            static_cast<unsigned long long>(modules.game.size),
            modules.game.path.c_str());

    const HANDLE process =
        OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (process == nullptr) {
        const DWORD code = GetLastError();
        wprintf(L"BLOCKED: read-only OpenProcess failed (%hs). "
                L"Stop and report BLOCKED; no bypass.\n",
                win_error(code).c_str());
        return 3;
    }

    hsr_probe::ModuleInfo unity;
    std::string error;
    if (!parse_remote_pe(process, modules.unity, unity, error)) {
        wprintf(L"BLOCKED: remote UnityPlayer PE parse failed: %hs\n", error.c_str());
        CloseHandle(process);
        return 3;
    }

    RemoteMemoryReader reader(process, unity.base, unity.size);
    hsr_probe::ApiTableLocator locator(unity, reader);
    const hsr_probe::LocatorResult result = locator.locate(40);

    wprintf(L"remote locator: candidates=%d best=0x%llX score=%.2f "
            L"confidence=%hs known=%d wrapper=%d desc=%d twin=%d\n",
            result.candidates_scanned,
            static_cast<unsigned long long>(result.best_table_rva), result.score,
            result.confidence.c_str(), result.known_slots_matched,
            result.wrapper_matches, result.descriptor_matches,
            result.best.twin_relations);

    bool ok = result.success && result.confidence == "high" &&
              result.known_slots_matched == 27 &&
              result.failed_constraints.empty();
    if (!ok) {
        wprintf(L"BLOCKED: remote locator did not produce a high-confidence result.\n");
        CloseHandle(process);
        return 3;
    }

    const std::optional<std::uint64_t> expected =
        expected_rva_from_config(self_dir);
    if (expected.has_value()) {
        const bool matches = result.best_table_rva == *expected;
        wprintf(L"comparison-only: expected=0x%llX actual=0x%llX -> %hs\n",
                static_cast<unsigned long long>(*expected),
                static_cast<unsigned long long>(result.best_table_rva),
                matches ? "MATCH" : "MISMATCH");
        ok = matches;
    } else {
        wprintf(L"comparison-only: probe_config.ini has no expected_table_rva; skipped\n");
    }

    CloseHandle(process);
    if (!ok) {
        wprintf(L"BLOCKED: remote locator result does not match the static result.\n");
        return 3;
    }
    wprintf(L"check-only: PASS (read-only; nothing loaded, nothing written)\n");
    wprintf(L"PRECHECK = PASS\n");
    return 0;
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    SetConsoleOutputCP(CP_UTF8);

    Options options;
    wchar_t self_path[MAX_PATH] = {};
    GetModuleFileNameW(nullptr, self_path, MAX_PATH);
    std::wstring self_dir = self_path;
    const std::size_t slash = self_dir.find_last_of(L"\\/");
    if (slash != std::wstring::npos) {
        self_dir.resize(slash);
    }
    options.dll_path = self_dir + L"\\hsr_runtime_health_probe.dll";

    if (!parse_args(argc, argv, options)) {
        return 1;
    }

    DWORD pid = options.pid;
    std::vector<ModuleSnapshot> selected_snapshots;
    if (pid == 0) {
        const std::vector<DWORD> processes = find_processes(options.process_name);
        if (options.list_only) {
            wprintf(L"matching processes:\n");
            for (DWORD candidate : processes) {
                std::wstring name;
                process_name_for(candidate, name);
                wprintf(L"  pid=%lu name=%s\n", candidate, name.c_str());
            }
            return processes.empty() ? 2 : 0;
        }
        if (processes.empty()) {
            wprintf(L"BLOCKED: no process named %s is running.\n"
                    L"Start the client normally and wait until UnityPlayer.dll and\n"
                    L"GameAssembly.dll are loaded before retrying.\n",
                    options.process_name.c_str());
            return 2;
        }
        if (options.check_only) {
            if (!select_game_process_check_only(processes, pid, selected_snapshots)) {
                return 2;
            }
        } else if (processes.size() > 1) {
            wprintf(L"BLOCKED: %zu processes named %s are running. Re-run with --pid.\n",
                    processes.size(), options.process_name.c_str());
            for (DWORD candidate : processes) {
                wprintf(L"  pid=%lu\n", candidate);
            }
            return 2;
        } else {
            pid = processes.front();
        }
    } else if (options.check_only) {
        const std::vector<DWORD> one_process{pid};
        if (!select_game_process_check_only(one_process, pid, selected_snapshots)) {
            return 2;
        }
    }

    std::wstring process_name;
    process_name_for(pid, process_name);
    wprintf(L"target: pid=%lu name=%s\n", pid, process_name.c_str());

    ModuleSnapshot modules;
    if (options.check_only) {
        bool found = false;
        for (const ModuleSnapshot& snapshot : selected_snapshots) {
            if (snapshot.pid == pid) {
                modules = snapshot;
                found = true;
                break;
            }
        }
        if (!found) {
            wprintf(L"BLOCKED: selected process snapshot not found.\n");
            return 2;
        }
    } else {
        modules = resolve_modules(pid);
    }
    if (modules.has_probe) {
        wprintf(L"BLOCKED: probe module is already loaded in the target.\n"
                L"Unload it by restarting the game client, then retry.\n");
        return 2;
    }
    if (!modules.unity.present || !modules.game.present) {
        wprintf(L"BLOCKED: client is not fully initialized for this process:\n"
                L"  UnityPlayer.dll loaded = %s\n"
                L"  GameAssembly.dll loaded = %s\n"
                L"Wait for normal startup to complete, then retry.\n",
                modules.unity.present ? L"yes" : L"no",
                modules.game.present ? L"yes" : L"no");
        return 2;
    }
    wprintf(L"preflight: UnityPlayer.dll and GameAssembly.dll are loaded.\n");

    if (options.check_only) {
        return run_check_only(pid, modules, self_dir);
    }

    wchar_t full_dll[MAX_PATH] = {};
    const DWORD full_len = GetFullPathNameW(options.dll_path.c_str(), MAX_PATH, full_dll,
                                            nullptr);
    if (full_len == 0 || full_len >= MAX_PATH) {
        wprintf(L"BLOCKED: cannot resolve probe dll path: %s\n",
                options.dll_path.c_str());
        return 2;
    }
    if (GetFileAttributesW(full_dll) == INVALID_FILE_ATTRIBUTES) {
        wprintf(L"BLOCKED: probe dll not found: %s\n", full_dll);
        return 2;
    }
    wprintf(L"loading (visible LoadLibraryW): %s\n", full_dll);

    const HANDLE process = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
                                           PROCESS_VM_OPERATION | PROCESS_VM_WRITE |
                                           PROCESS_VM_READ,
                                       FALSE, pid);
    if (process == nullptr) {
        const DWORD code = GetLastError();
        wprintf(L"BLOCKED: OpenProcess failed (%hs).\n"
                L"Do not attempt to bypass this restriction; report BLOCKED.\n",
                win_error(code).c_str());
        return 3;
    }

    const std::wstring full_dll_path(full_dll);
    const std::size_t remote_size =
        (full_dll_path.size() + 1) * sizeof(wchar_t);
    void* remote = VirtualAllocEx(process, nullptr, remote_size, MEM_COMMIT | MEM_RESERVE,
                                  PAGE_READWRITE);
    if (remote == nullptr) {
        const DWORD code = GetLastError();
        wprintf(L"BLOCKED: VirtualAllocEx failed (%hs). Stop and report BLOCKED.\n",
                win_error(code).c_str());
        CloseHandle(process);
        return 3;
    }

    SIZE_T written = 0;
    if (WriteProcessMemory(process, remote, full_dll_path.c_str(), remote_size,
                           &written) == FALSE ||
        written != remote_size) {
        const DWORD code = GetLastError();
        wprintf(L"BLOCKED: WriteProcessMemory failed (%hs). Stop and report BLOCKED.\n",
                win_error(code).c_str());
        VirtualFreeEx(process, remote, 0, MEM_RELEASE);
        CloseHandle(process);
        return 3;
    }

    const HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
    const auto load_library_w = reinterpret_cast<LPTHREAD_START_ROUTINE>(
        GetProcAddress(kernel32, "LoadLibraryW"));
    if (load_library_w == nullptr) {
        wprintf(L"BLOCKED: cannot resolve LoadLibraryW.\n");
        VirtualFreeEx(process, remote, 0, MEM_RELEASE);
        CloseHandle(process);
        return 3;
    }

    const HANDLE thread =
        CreateRemoteThread(process, nullptr, 0, load_library_w, remote, 0, nullptr);
    if (thread == nullptr) {
        const DWORD code = GetLastError();
        wprintf(L"BLOCKED: CreateRemoteThread failed (%hs).\n"
                L"Stop and report BLOCKED; this loader never bypasses protection.\n",
                win_error(code).c_str());
        VirtualFreeEx(process, remote, 0, MEM_RELEASE);
        CloseHandle(process);
        return 3;
    }

    wprintf(L"remote LoadLibraryW started; waiting up to %lu ms...\n",
            options.timeout_ms);
    const DWORD wait = WaitForSingleObject(thread, options.timeout_ms);
    DWORD exit_code = 0;
    GetExitCodeThread(thread, &exit_code);
    CloseHandle(thread);
    VirtualFreeEx(process, remote, 0, MEM_RELEASE);
    CloseHandle(process);

    if (wait == WAIT_TIMEOUT) {
        wprintf(L"BLOCKED: remote LoadLibraryW did not return within timeout.\n");
        return 3;
    }
    if (exit_code == 0) {
        wprintf(L"BLOCKED: LoadLibraryW returned null in the target process.\n"
                L"The client rejected the standard, visible loading path.\n"
                L"Stop and report BLOCKED; do not bypass.\n");
        return 3;
    }
    wprintf(L"OK: probe loaded at 0x%lX in pid %lu.\n"
            L"The probe allocates a visible console, writes JSON/log output and keeps\n"
            L"the module loaded until the game exits (restart the client to unload).\n",
            static_cast<unsigned long>(exit_code), pid);
    return 0;
}
