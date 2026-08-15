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
#include <tlhelp32.h>

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

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

struct ModuleSnapshot {
    bool has_unity = false;
    bool has_game = false;
    bool has_probe = false;
    std::vector<std::wstring> paths;
};

ModuleSnapshot inspect_modules(DWORD pid) {
    ModuleSnapshot result;
    const HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return result;
    }
    MODULEENTRY32W entry{};
    entry.dwSize = sizeof(entry);
    if (Module32FirstW(snapshot, &entry)) {
        do {
            const std::wstring name = lower_wide(basename(entry.szExePath));
            if (name == L"unityplayer.dll") result.has_unity = true;
            if (name == L"gameassembly.dll") result.has_game = true;
            if (name == L"hsr_runtime_health_probe.dll") result.has_probe = true;
            result.paths.push_back(entry.szExePath);
        } while (Module32NextW(snapshot, &entry));
    }
    CloseHandle(snapshot);
    return result;
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
        if (processes.size() > 1) {
            wprintf(L"BLOCKED: %zu processes named %s are running. Re-run with --pid.\n",
                    processes.size(), options.process_name.c_str());
            for (DWORD candidate : processes) {
                wprintf(L"  pid=%lu\n", candidate);
            }
            return 2;
        }
        pid = processes.front();
    }

    std::wstring process_name;
    process_name_for(pid, process_name);
    wprintf(L"target: pid=%lu name=%s\n", pid, process_name.c_str());

    const ModuleSnapshot modules = inspect_modules(pid);
    if (modules.has_probe) {
        wprintf(L"BLOCKED: probe module is already loaded in the target.\n"
                L"Unload it by restarting the game client, then retry.\n");
        return 2;
    }
    if (!modules.has_unity || !modules.has_game) {
        wprintf(L"BLOCKED: client is not fully initialized for this process:\n"
                L"  UnityPlayer.dll loaded = %s\n"
                L"  GameAssembly.dll loaded = %s\n"
                L"Wait for normal startup to complete, then retry.\n",
                modules.has_unity ? L"yes" : L"no",
                modules.has_game ? L"yes" : L"no");
        return 2;
    }
    wprintf(L"preflight: UnityPlayer.dll and GameAssembly.dll are loaded.\n");

    if (options.check_only) {
        wprintf(L"check-only: ok\n");
        return 0;
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
