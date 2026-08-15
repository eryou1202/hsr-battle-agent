#include <windows.h>

#include <filesystem>
#include <string>

#include "common.h"
#include "health_check.h"
#include "log_sink.h"

namespace {

// Resolves a repo-relative output path against the repository root derived
// from the probe DLL location (.../tools/runtime_probe/build/<dll>).
std::string resolve_output_dir(const std::wstring& dll_path,
                               const std::string& configured) {
    if (configured.empty()) {
        return {};
    }
    // Absolute Windows path -> use as-is.
    if (configured.size() >= 2 && configured[1] == ':') {
        return configured;
    }
    if (configured.rfind("\\\\", 0) == 0 || configured.rfind("//", 0) == 0) {
        return configured;
    }

    namespace fs = std::filesystem;
    fs::path probe_dir = fs::path(dll_path).parent_path();
    fs::path root = probe_dir;
    for (int i = 0; i < 6; ++i) {
        if (fs::exists(root / ".git") || fs::exists(root / "pyproject.toml")) {
            break;
        }
        root = root.parent_path();
    }
    return (root / configured).lexically_normal().string();
}

std::wstring module_path_of(HMODULE module) {
    wchar_t buffer[MAX_PATH] = {};
    const DWORD len = GetModuleFileNameW(module, buffer, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) {
        return {};
    }
    return std::wstring(buffer);
}

DWORD WINAPI probe_thread(LPVOID parameter) {
    std::wstring* dll_path = static_cast<std::wstring*>(parameter);

    AllocConsole();
    SetConsoleOutputCP(CP_UTF8);

    hsr_probe::LogSink log;
    log.enable_console(true);
    log.log("hsr-runtime-health-probe loaded");
    log.log("loading mode: visible LoadLibrary module (no stealth, no hooks)");
    log.log("dll path: " + hsr_probe::wide_to_utf8(*dll_path));

    const std::wstring config_path =
        std::filesystem::path(*dll_path).parent_path().wstring() +
        L"\\probe_config.ini";
    hsr_probe::ProbeConfig config;
    std::string error;
    if (!hsr_probe::ProbeConfig::load_ini(config_path, config, error)) {
        log.log("FAIL: cannot read probe config: " + error);
        log.log("HD-2 = FAIL / BLOCKED step=config error=" + error);
        delete dll_path;
        return 1;
    }
    config.output_dir = resolve_output_dir(*dll_path, config.output_dir);
    log.log("output dir: " + (config.output_dir.empty() ? std::string("<cwd>")
                                                        : config.output_dir));
    log.log("wait before run: " + std::to_string(config.wait_before_run_ms) + " ms");

    hsr_probe::HealthCheck health_check(config, log);
    const bool ok = health_check.run();
    log.log(ok ? "health check finished: PASS" : "health check finished: FAIL");

    // The probe module intentionally stays loaded and visible until the game
    // exits. It installed no hooks and modified no game memory.
    delete dll_path;
    return ok ? 0 : 1;
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        std::wstring* path = new (std::nothrow) std::wstring(module_path_of(instance));
        if (path == nullptr) {
            return FALSE;
        }
        HANDLE thread = CreateThread(nullptr, 0, &probe_thread, path, 0, nullptr);
        if (thread == nullptr) {
            delete path;
            return FALSE;
        }
        CloseHandle(thread);
    }
    return TRUE;
}
