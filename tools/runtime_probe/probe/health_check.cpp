#include "health_check.h"

#include <windows.h>
#include <psapi.h>

#pragma comment(lib, "psapi.lib")
#pragma comment(lib, "version.lib")

#include <algorithm>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <fstream>

namespace hsr_probe {

namespace {

using DomainGetFn = void* (*)();
using DomainGetAssembliesFn = void** (*)(void*, std::size_t*);
using AssemblyGetImageFn = void* (*)(void*);
using ImageGetNameFn = const char* (*)(void*);
using ImageGetClassCountFn = std::size_t (*)(void*);
using ImageGetClassFn = void* (*)(void*, std::size_t);
using ClassGetNameFn = const char* (*)(void*);

// x64 SEH guard around one il2cpp API call. The function pointer is called
// with a uniform 4-register signature: on x64 all scalar/pointer args travel
// in RCX/RDX/R8/R9 and the callee simply ignores the registers it does not
// read. This free function deliberately contains no C++ object with a
// destructor, which keeps it compatible with MSVC __try/__except.
using RawApiFn = std::uintptr_t (*)(std::uintptr_t, std::uintptr_t,
                                    std::uintptr_t, std::uintptr_t);

__declspec(noinline) bool seh_call_raw(const char* api_name,
                                       std::uintptr_t fn_addr,
                                       std::uintptr_t* result,
                                       std::uintptr_t a0, std::uintptr_t a1,
                                       std::uintptr_t a2, std::uintptr_t a3,
                                       DWORD* seh_code) {
    (void)api_name;
    RawApiFn fn = nullptr;
    static_assert(sizeof(fn) == sizeof(fn_addr), "unexpected function pointer size");
    std::memcpy(&fn, &fn_addr, sizeof(fn));
    __try {
        *result = fn(a0, a1, a2, a3);
        return true;
    } __except (*seh_code = GetExceptionCode(), EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

Json pointer_check_json(const PointerCheck& check) {
    Json obj = Json::object();
    obj.set("valid", Json::boolean(check.valid));
    obj.set("canonical", Json::boolean(check.canonical));
    obj.set("committed", Json::boolean(check.committed));
    obj.set("readable", Json::boolean(check.readable));
    obj.set("executable", Json::boolean(check.executable));
    obj.set("protect", Json::string(format_hex(check.protect)));
    obj.set("module", Json::string(check.module));
    obj.set("section", Json::string(check.section));
    return obj;
}

Json module_json(const ModuleInfo& module) {
    Json sections = Json::array();
    for (const PeSection& section : module.sections) {
        Json sec = Json::object();
        sec.set("name", Json::string(section.name));
        sec.set("rva", Json::string(format_hex(section.rva)));
        sec.set("mapped_size", Json::string(format_hex(section.mapped_size())));
        sec.set("executable", Json::boolean(section.is_executable()));
        sec.set("writable", Json::boolean(section.is_writable()));
        sec.set("readonly_data", Json::boolean(section.is_readonly_data()));
        sections.push(std::move(sec));
    }
    Json obj = Json::object();
    obj.set("name", Json::string(module.name));
    obj.set("path", Json::string(module.path));
    obj.set("base", Json::string(format_hex(module.base)));
    obj.set("size", Json::string(format_hex(module.size)));
    obj.set("sections", std::move(sections));
    return obj;
}

Json pass_step(const std::string& name) {
    Json step = Json::object();
    step.set("step", Json::string(name));
    step.set("success", Json::boolean(true));
    return step;
}

Json fail_step(const std::string& name, const std::string& code,
               const std::string& error, Json details = Json::null()) {
    Json step = Json::object();
    step.set("step", Json::string(name));
    step.set("success", Json::boolean(false));
    step.set("error_code", Json::string(code));
    step.set("error", Json::string(error));
    if (!details.is_null()) {
        step.set("details", std::move(details));
    }
    return step;
}

bool scan_version_segment(const std::string& text, std::string& version) {
    for (std::size_t i = 0; i < text.size(); ++i) {
        if (!std::isdigit(static_cast<unsigned char>(text[i]))) {
            continue;
        }
        std::size_t j = i;
        while (j < text.size() &&
               (std::isdigit(static_cast<unsigned char>(text[j])) || text[j] == '.')) {
            ++j;
        }
        std::string candidate = text.substr(i, j - i);
        int dots = 0;
        bool valid = true;
        std::string part;
        for (char c : candidate) {
            if (c == '.') {
                if (part.empty() || part.size() > 4) {
                    valid = false;
                    break;
                }
                ++dots;
                part.clear();
            } else {
                part += c;
            }
        }
        if (valid && dots == 2 && !part.empty() && part.size() <= 4) {
            version = candidate;
            return true;
        }
        i = j == i ? i : j - 1;
    }
    return false;
}

bool parse_binary_version(const std::vector<std::uint8_t>& data,
                          std::string& version, std::string& build) {
    std::string best_run;
    std::string current;
    for (std::uint8_t byte : data) {
        if (byte >= 0x20 && byte <= 0x7E) {
            current += static_cast<char>(byte);
        } else {
            if (current.find("BetaLive") != std::string::npos &&
                current.size() > best_run.size()) {
                best_run = current;
            }
            current.clear();
        }
    }
    if (current.find("BetaLive") != std::string::npos &&
        current.size() > best_run.size()) {
        best_run = current;
    }
    if (best_run.empty()) {
        return false;
    }
    build = best_run;
    const std::size_t win = best_run.find("Win");
    const std::string version_part =
        win == std::string::npos ? best_run : best_run.substr(win);
    return scan_version_segment(version_part, version);
}

bool file_version_of_exe(const std::wstring& exe_path, std::string& version) {
    DWORD handle = 0;
    const DWORD size = GetFileVersionInfoSizeW(exe_path.c_str(), &handle);
    if (size == 0) {
        return false;
    }
    std::vector<std::uint8_t> buffer(size);
    if (GetFileVersionInfoW(exe_path.c_str(), 0, size, buffer.data()) == FALSE) {
        return false;
    }
    VS_FIXEDFILEINFO* info = nullptr;
    UINT info_len = 0;
    if (VerQueryValueW(buffer.data(), L"\\", reinterpret_cast<void**>(&info),
                       &info_len) == FALSE ||
        info == nullptr || info_len < sizeof(VS_FIXEDFILEINFO)) {
        return false;
    }
    const int a = HIWORD(info->dwFileVersionMS);
    const int b = LOWORD(info->dwFileVersionMS);
    const int c = HIWORD(info->dwFileVersionLS);
    version = std::to_string(a) + "." + std::to_string(b) + "." + std::to_string(c);
    return true;
}

bool module_info_for(HMODULE handle, const wchar_t* name, ModuleInfo& out) {
    wchar_t path[MAX_PATH] = {};
    const DWORD len = GetModuleFileNameW(handle, path, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) {
        return false;
    }
    MODULEINFO info{};
    if (GetModuleInformation(GetCurrentProcess(), handle, &info, sizeof(info)) == FALSE) {
        return false;
    }
    const std::string utf8_path = wide_to_utf8(path);
    const std::size_t slash = utf8_path.find_last_of("\\/");
    out.name = (name != nullptr && name[0] != L'\0')
                   ? wide_to_utf8(name)
                   : (slash == std::string::npos ? utf8_path
                                                 : utf8_path.substr(slash + 1));
    out.path = utf8_path;
    out.base = reinterpret_cast<std::uint64_t>(info.lpBaseOfDll);
    out.size = static_cast<std::uint64_t>(info.SizeOfImage);
    std::string error;
    if (!parse_pe_from_memory(out.base, out.size, out.sections, error)) {
        return false;
    }
    return true;
}

}  // namespace

// ---------------------------------------------------------------------------
// ProbeConfig
// ---------------------------------------------------------------------------

bool ProbeConfig::load_ini(const std::wstring& path, ProbeConfig& out,
                           std::string& error) {
    wchar_t value[1024] = {};
    const wchar_t* section = L"health_check";

    const DWORD rva_len = GetPrivateProfileStringW(section, L"expected_table_rva", L"",
                                                   value, 1024, path.c_str());
    if (rva_len > 0) {
        std::wstring wide(value);
        const std::size_t pos = wide.find(L"0x");
        if (pos != std::wstring::npos) {
            wide = wide.substr(pos);
        }
        wchar_t* end = nullptr;
        const unsigned long long parsed = std::wcstoull(wide.c_str(), &end, 16);
        if (end == wide.c_str()) {
            error = "expected_table_rva is not a hex number";
            return false;
        }
        out.expected_table_rva = static_cast<std::uint64_t>(parsed);
    }
    out.expect_rva_enabled =
        GetPrivateProfileIntW(section, L"expect_rva_enabled", 0, path.c_str()) != 0;

    GetPrivateProfileStringW(section, L"output_dir", L"", value, 1024, path.c_str());
    out.output_dir = wide_to_utf8(value);

    out.max_assemblies_to_report = static_cast<int>(
        GetPrivateProfileIntW(section, L"max_assemblies_to_report", 5, path.c_str()));
    out.max_classes_to_read = static_cast<int>(
        GetPrivateProfileIntW(section, L"max_classes_to_read", 10, path.c_str()));
    out.max_class_count_reasonable = static_cast<std::uint64_t>(
        GetPrivateProfileIntW(section, L"max_class_count_reasonable", 1000000,
                              path.c_str()));
    out.max_string_length = static_cast<std::size_t>(
        GetPrivateProfileIntW(section, L"max_string_length", 4096, path.c_str()));
    out.wait_before_run_ms = static_cast<std::uint32_t>(
        GetPrivateProfileIntW(section, L"wait_before_run_ms", 1000, path.c_str()));

    if (out.max_classes_to_read <= 0) {
        out.max_classes_to_read = 1;
    }
    if (out.max_assemblies_to_report <= 0) {
        out.max_assemblies_to_report = 1;
    }
    if (out.max_string_length == 0) {
        out.max_string_length = 4096;
    }
    return true;
}

// ---------------------------------------------------------------------------
// ApiTableView
// ---------------------------------------------------------------------------

bool ApiTableView::load(const ModuleInfo& unity, const LocatorMemory& memory,
                        std::uint64_t table_rva) {
    for (std::size_t i = 0; i < kSlots; ++i) {
        std::uint64_t value = 0;
        const std::uint64_t rva = table_rva + static_cast<std::uint64_t>(i) * 8;
        if (rva > unity.size || sizeof(value) > unity.size - rva) {
            valid[i] = false;
            continue;
        }
        if (!memory.read_bytes(unity.base + rva, sizeof(value), &value)) {
            valid[i] = false;
            continue;
        }
        slots[i] = value;
        valid[i] = value != 0;
    }
    return true;
}

// ---------------------------------------------------------------------------
// RuntimeSteps
// ---------------------------------------------------------------------------

RuntimeSteps::RuntimeSteps(const ModuleInfo* unity,
                           const std::vector<ModuleInfo>& modules,
                           const ApiTableView& table, const ProbeConfig& config,
                           LogSink& log)
    : unity_(unity), modules_(modules), table_(table), config_(config), log_(log) {}

bool RuntimeSteps::run(std::vector<Json>& steps) {
    PointerValidator validator(&modules_);
    failed_step_name_.clear();
    failed_error_.clear();
    if (unity_ == nullptr) {
        failed_step_name_ = "domain_get";
        failed_error_ = "UnityPlayer module information is unavailable";
        steps.push_back(fail_step(failed_step_name_, "NO_UNITY_MODULE", failed_error_));
        log_.log("[STEP domain_get] FAIL: " + failed_error_);
        return false;
    }

    // STEP 2: domain_get ----------------------------------------------------
    {
        const std::size_t slot = static_cast<std::size_t>(kSlotDomainGet);
        if (!table_.valid[slot]) {
            failed_step_name_ = "domain_get";
            failed_error_ = "api table slot 63 (domain_get) is null";
            steps.push_back(fail_step(failed_step_name_, "API_SLOT_MISSING", failed_error_));
            log_.log("[STEP domain_get] FAIL: " + failed_error_);
            return false;
        }
        const std::uint64_t fn_addr = table_.slots[slot];
        PointerCheck fn_check = validator.check_exec_function(fn_addr);
        if (!fn_check.valid) {
            failed_step_name_ = "domain_get";
            failed_error_ = "domain_get wrapper is not in an executable module section";
            Json details = Json::object();
            details.set("slot", Json::integer(kSlotDomainGet));
            details.set("function_pointer", Json::string(format_hex(fn_addr)));
            details.set("pointer_check", pointer_check_json(fn_check));
            steps.push_back(fail_step(failed_step_name_, "INVALID_API_FUNCTION_POINTER",
                                      failed_error_, std::move(details)));
            log_.log("[STEP domain_get] FAIL: " + failed_error_ + " " +
                     format_hex(fn_addr));
            return false;
        }

        std::uint64_t domain = 0;
        DWORD seh_code = 0;
        if (!seh_call_raw("domain_get", fn_addr, &domain, 0, 0, 0, 0,
                          &seh_code)) {
            failed_step_name_ = "domain_get";
            failed_error_ = "domain_get raised SEH exception " +
                            format_hex(seh_code);
            steps.push_back(fail_step(failed_step_name_, "API_CALL_FAULT", failed_error_));
            log_.log("[STEP domain_get] FAIL: " + failed_error_);
            return false;
        }
        PointerCheck domain_check = validator.check_generic(domain);
        if (domain == 0 || !domain_check.valid) {
            failed_step_name_ = "domain_get";
            failed_error_ = domain == 0 ? "il2cpp_domain_get returned null"
                                        : "domain pointer is not readable";
            Json details = Json::object();
            details.set("domain_pointer", Json::string(format_hex(domain)));
            details.set("pointer_check", pointer_check_json(domain_check));
            steps.push_back(fail_step(failed_step_name_, "DOMAIN_INVALID", failed_error_,
                                      std::move(details)));
            log_.log("[STEP domain_get] FAIL: " + failed_error_ + " " +
                     format_hex(domain));
            return false;
        }
        domain_ = domain;

        Json step = pass_step("domain_get");
        Json details = Json::object();
        details.set("domain_va", Json::string(format_hex(domain)));
        details.set("pointer_check", pointer_check_json(domain_check));
        step.set("details", std::move(details));
        steps.push_back(std::move(step));
        log_.log("[STEP domain_get] PASS domain=" + format_hex(domain));
    }

    // STEP 3: domain_get_assemblies -----------------------------------------
    {
        const std::size_t slot = static_cast<std::size_t>(kSlotDomainGetAssemblies);
        if (!table_.valid[slot]) {
            failed_step_name_ = "domain_get_assemblies";
            failed_error_ = "api table slot 65 (domain_get_assemblies) is null";
            steps.push_back(fail_step(failed_step_name_, "API_SLOT_MISSING", failed_error_));
            log_.log("[STEP domain_get_assemblies] FAIL: " + failed_error_);
            return false;
        }
        const std::uint64_t fn_addr = table_.slots[slot];
        PointerCheck fn_check = validator.check_exec_function(fn_addr);
        if (!fn_check.valid) {
            failed_step_name_ = "domain_get_assemblies";
            failed_error_ = "domain_get_assemblies wrapper is not in an executable module section";
            steps.push_back(fail_step(failed_step_name_, "INVALID_API_FUNCTION_POINTER",
                                      failed_error_));
            log_.log("[STEP domain_get_assemblies] FAIL: " + failed_error_);
            return false;
        }

        std::size_t count = 0;
        std::uint64_t raw_assemblies = 0;
        DWORD seh_code = 0;
        if (!seh_call_raw("domain_get_assemblies", fn_addr, &raw_assemblies, domain_,
                          reinterpret_cast<std::uintptr_t>(&count), 0, 0,
                          &seh_code)) {
            failed_step_name_ = "domain_get_assemblies";
            failed_error_ = "domain_get_assemblies raised SEH exception " +
                            format_hex(seh_code);
            steps.push_back(fail_step(failed_step_name_, "API_CALL_FAULT", failed_error_));
            log_.log("[STEP domain_get_assemblies] FAIL: " + failed_error_);
            return false;
        }
        void** assemblies = reinterpret_cast<void**>(raw_assemblies);
        PointerCheck array_check = validator.check_generic(
            reinterpret_cast<std::uint64_t>(assemblies));
        if (count == 0 || count > 65536 || assemblies == nullptr || !array_check.valid) {
            failed_step_name_ = "domain_get_assemblies";
            failed_error_ = count == 0
                                ? "assembly count is zero"
                                : (count > 65536 ? "assembly count is unreasonable (>65536)"
                                                 : "assembly array pointer is invalid");
            Json details = Json::object();
            details.set("assembly_count", Json::integer(static_cast<std::int64_t>(count)));
            details.set("array_pointer",
                        Json::string(format_hex(reinterpret_cast<std::uint64_t>(assemblies))));
            details.set("pointer_check", pointer_check_json(array_check));
            steps.push_back(fail_step(failed_step_name_, "ASSEMBLIES_INVALID", failed_error_,
                                      std::move(details)));
            log_.log("[STEP domain_get_assemblies] FAIL: " + failed_error_);
            return false;
        }

        std::vector<std::uint8_t> raw;
        if (!validator.read_bytes(reinterpret_cast<std::uint64_t>(assemblies),
                                  count * sizeof(std::uint64_t), raw, &array_check)) {
            failed_step_name_ = "domain_get_assemblies";
            failed_error_ = "assembly pointer array is not readable";
            steps.push_back(fail_step(failed_step_name_, "ASSEMBLY_ARRAY_UNREADABLE",
                                      failed_error_));
            log_.log("[STEP domain_get_assemblies] FAIL: " + failed_error_);
            return false;
        }
        assemblies_.clear();
        assemblies_.resize(count);
        std::memcpy(assemblies_.data(), raw.data(), raw.size());
        Json reported = Json::array();
        for (std::size_t i = 0; i < count; ++i) {
            PointerCheck assembly_check = validator.check_generic(assemblies_[i]);
            if (!assembly_check.valid) {
                failed_step_name_ = "domain_get_assemblies";
                failed_error_ = "assembly pointer " + std::to_string(i) +
                                " is not readable";
                steps.push_back(fail_step(failed_step_name_, "ASSEMBLY_POINTER_INVALID",
                                          failed_error_));
                log_.log("[STEP domain_get_assemblies] FAIL: " + failed_error_);
                return false;
            }
            if (i < static_cast<std::size_t>(config_.max_assemblies_to_report)) {
                Json item = Json::object();
                item.set("index", Json::integer(static_cast<std::int64_t>(i)));
                item.set("assembly_va", Json::string(format_hex(assemblies_[i])));
                item.set("pointer_check", pointer_check_json(assembly_check));
                reported.push(std::move(item));
            }
        }

        Json step = pass_step("domain_get_assemblies");
        Json details = Json::object();
        details.set("assembly_count", Json::integer(static_cast<std::int64_t>(count)));
        details.set("assemblies_reported", Json::integer(
            static_cast<std::int64_t>(
                (std::min)(static_cast<std::size_t>(config_.max_assemblies_to_report),
                           static_cast<std::size_t>(count)))));
        details.set("assemblies", std::move(reported));
        step.set("details", std::move(details));
        steps.push_back(std::move(step));
        log_.log("[STEP domain_get_assemblies] PASS count=" + std::to_string(count));
    }

    // STEP 4: assembly_get_image ---------------------------------------------
    {
        const std::size_t slot = static_cast<std::size_t>(kSlotAssemblyGetImage);
        if (!table_.valid[slot]) {
            failed_step_name_ = "assembly_get_image";
            failed_error_ = "api table slot 22 (assembly_get_image) is null";
            steps.push_back(fail_step(failed_step_name_, "API_SLOT_MISSING", failed_error_));
            return false;
        }
        const std::uint64_t fn_addr = table_.slots[slot];
        PointerCheck fn_check = validator.check_exec_function(fn_addr);
        if (!fn_check.valid) {
            failed_step_name_ = "assembly_get_image";
            failed_error_ = "assembly_get_image wrapper is not in an executable module section";
            steps.push_back(fail_step(failed_step_name_, "INVALID_API_FUNCTION_POINTER",
                                      failed_error_));
            return false;
        }

        std::uint64_t raw_image = 0;
        DWORD seh_code = 0;
        if (!seh_call_raw("assembly_get_image", fn_addr, &raw_image,
                          assemblies_[0], 0, 0, 0, &seh_code)) {
            failed_step_name_ = "assembly_get_image";
            failed_error_ = "assembly_get_image raised SEH exception " +
                            format_hex(seh_code);
            steps.push_back(fail_step(failed_step_name_, "API_CALL_FAULT", failed_error_));
            return false;
        }
        void* image = reinterpret_cast<void*>(raw_image);
        PointerCheck image_check = validator.check_generic(
            reinterpret_cast<std::uint64_t>(image));
        if (image == nullptr || !image_check.valid) {
            failed_step_name_ = "assembly_get_image";
            failed_error_ = image == nullptr ? "il2cpp_assembly_get_image returned null"
                                             : "image pointer is not readable";
            Json details = Json::object();
            details.set("assembly_index", Json::integer(0));
            details.set("assembly_va", Json::string(format_hex(assemblies_[0])));
            details.set("image_pointer",
                        Json::string(format_hex(reinterpret_cast<std::uint64_t>(image))));
            details.set("pointer_check", pointer_check_json(image_check));
            steps.push_back(fail_step(failed_step_name_, "IMAGE_INVALID", failed_error_,
                                      std::move(details)));
            log_.log("[STEP assembly_get_image] FAIL: " + failed_error_);
            return false;
        }
        image_ = reinterpret_cast<std::uint64_t>(image);

        Json step = pass_step("assembly_get_image");
        Json details = Json::object();
        details.set("assembly_index", Json::integer(0));
        details.set("assembly_va", Json::string(format_hex(assemblies_[0])));
        details.set("image_va", Json::string(format_hex(image_)));
        details.set("pointer_check", pointer_check_json(image_check));
        step.set("details", std::move(details));
        steps.push_back(std::move(step));
        log_.log("[STEP assembly_get_image] PASS image=" + format_hex(image_));
    }

    // STEP 5: image name / metadata sanity ------------------------------------
    {
        const std::size_t slot = static_cast<std::size_t>(kSlotImageGetName);
        if (!table_.valid[slot]) {
            failed_step_name_ = "image_name";
            failed_error_ = "api table slot 168 (image_get_name) is null";
            steps.push_back(fail_step(failed_step_name_, "API_SLOT_MISSING", failed_error_));
            return false;
        }
        const std::uint64_t fn_addr = table_.slots[slot];
        PointerCheck fn_check = validator.check_exec_function(fn_addr);
        if (!fn_check.valid) {
            failed_step_name_ = "image_name";
            failed_error_ = "image_get_name wrapper is not in an executable module section";
            steps.push_back(fail_step(failed_step_name_, "INVALID_API_FUNCTION_POINTER",
                                      failed_error_));
            return false;
        }

        std::uint64_t raw_name = 0;
        DWORD seh_code = 0;
        if (!seh_call_raw("image_get_name", fn_addr, &raw_name, image_, 0, 0, 0,
                          &seh_code)) {
            failed_step_name_ = "image_name";
            failed_error_ = "image_get_name raised SEH exception " +
                            format_hex(seh_code);
            steps.push_back(fail_step(failed_step_name_, "API_CALL_FAULT", failed_error_));
            return false;
        }
        const char* name = reinterpret_cast<const char*>(raw_name);
        std::string image_name;
        PointerCheck name_check = validator.check_generic(
            reinterpret_cast<std::uint64_t>(name));
        if (name == nullptr || !name_check.valid ||
            !validator.read_cstring(reinterpret_cast<std::uint64_t>(name),
                                    config_.max_string_length, image_name,
                                    &name_check) ||
            image_name.empty() || !is_printable_utf8_string(image_name)) {
            failed_step_name_ = "image_name";
            failed_error_ = "image_get_name did not return a readable, printable string";
            Json details = Json::object();
            details.set("name_pointer",
                        Json::string(format_hex(reinterpret_cast<std::uint64_t>(name))));
            details.set("pointer_check", pointer_check_json(name_check));
            steps.push_back(fail_step(failed_step_name_, "IMAGE_NAME_INVALID", failed_error_,
                                      std::move(details)));
            log_.log("[STEP image_name] FAIL: " + failed_error_);
            return false;
        }

        Json step = pass_step("image_name");
        Json details = Json::object();
        details.set("image_name", Json::string(image_name));
        details.set("name_length", Json::integer(static_cast<std::int64_t>(image_name.size())));
        details.set("printable_utf8", Json::boolean(true));
        step.set("details", std::move(details));
        steps.push_back(std::move(step));
        log_.log("[STEP image_name] PASS name=" + image_name);
    }

    // STEP 6: image_get_class_count ------------------------------------------
    {
        const std::size_t slot = static_cast<std::size_t>(kSlotImageGetClassCount);
        if (!table_.valid[slot]) {
            failed_step_name_ = "image_get_class_count";
            failed_error_ = "api table slot 169 (image_get_class_count) is null";
            steps.push_back(fail_step(failed_step_name_, "API_SLOT_MISSING", failed_error_));
            return false;
        }
        const std::uint64_t fn_addr = table_.slots[slot];
        PointerCheck fn_check = validator.check_exec_function(fn_addr);
        if (!fn_check.valid) {
            failed_step_name_ = "image_get_class_count";
            failed_error_ = "image_get_class_count wrapper is not in an executable module section";
            steps.push_back(fail_step(failed_step_name_, "INVALID_API_FUNCTION_POINTER",
                                      failed_error_));
            return false;
        }

        std::uint64_t raw_count = 0;
        DWORD seh_code = 0;
        if (!seh_call_raw("image_get_class_count", fn_addr, &raw_count, image_, 0, 0,
                          0, &seh_code)) {
            failed_step_name_ = "image_get_class_count";
            failed_error_ = "image_get_class_count raised SEH exception " +
                            format_hex(seh_code);
            steps.push_back(fail_step(failed_step_name_, "API_CALL_FAULT", failed_error_));
            return false;
        }
        std::size_t count = static_cast<std::size_t>(raw_count);
        const bool reasonable = count > 0 &&
                                count <= config_.max_class_count_reasonable;
        if (!reasonable) {
            failed_step_name_ = "image_get_class_count";
            failed_error_ = "class count is unreasonable: " + std::to_string(count);
            Json details = Json::object();
            details.set("class_count", Json::integer(static_cast<std::int64_t>(count)));
            details.set("max_reasonable",
                        Json::integer(static_cast<std::int64_t>(
                            config_.max_class_count_reasonable)));
            steps.push_back(fail_step(failed_step_name_, "CLASS_COUNT_UNREASONABLE",
                                      failed_error_, std::move(details)));
            log_.log("[STEP image_get_class_count] FAIL: " + failed_error_);
            return false;
        }
        class_count_ = count;

        Json step = pass_step("image_get_class_count");
        Json details = Json::object();
        details.set("class_count", Json::integer(static_cast<std::int64_t>(count)));
        details.set("reasonable", Json::boolean(true));
        step.set("details", std::move(details));
        steps.push_back(std::move(step));
        log_.log("[STEP image_get_class_count] PASS count=" + std::to_string(count));
    }

    // STEP 7: read a small number of classes --------------------------------
    {
        const std::size_t slot = static_cast<std::size_t>(kSlotImageGetClass);
        if (!table_.valid[slot]) {
            failed_step_name_ = "image_get_classes";
            failed_error_ = "api table slot 170 (image_get_class) is null";
            steps.push_back(fail_step(failed_step_name_, "API_SLOT_MISSING", failed_error_));
            return false;
        }
        const std::uint64_t fn_addr = table_.slots[slot];
        PointerCheck fn_check = validator.check_exec_function(fn_addr);
        if (!fn_check.valid) {
            failed_step_name_ = "image_get_classes";
            failed_error_ = "image_get_class wrapper is not in an executable module section";
            steps.push_back(fail_step(failed_step_name_, "INVALID_API_FUNCTION_POINTER",
                                      failed_error_));
            return false;
        }

        const std::size_t read_count =
            (std::min)(static_cast<std::size_t>(config_.max_classes_to_read),
                       static_cast<std::size_t>(class_count_));
        classes_.clear();
        Json classes = Json::array();
        for (std::size_t i = 0; i < read_count; ++i) {
            std::uint64_t raw_klass = 0;
            DWORD seh_code = 0;
            if (!seh_call_raw("image_get_class", fn_addr, &raw_klass, image_,
                              static_cast<std::uintptr_t>(i), 0, 0, &seh_code)) {
                failed_step_name_ = "image_get_classes";
                failed_error_ = "image_get_class(" + std::to_string(i) +
                                ") raised SEH exception " + format_hex(seh_code);
                steps.push_back(fail_step(failed_step_name_, "API_CALL_FAULT",
                                          failed_error_));
                log_.log("[STEP image_get_classes] FAIL: " + failed_error_);
                return false;
            }
            void* klass = reinterpret_cast<void*>(raw_klass);
            PointerCheck class_check = validator.check_generic(
                reinterpret_cast<std::uint64_t>(klass));
            if (klass == nullptr || !class_check.valid) {
                failed_step_name_ = "image_get_classes";
                failed_error_ = "image_get_class(" + std::to_string(i) +
                                ") returned an invalid pointer";
                steps.push_back(fail_step(failed_step_name_, "CLASS_POINTER_INVALID",
                                          failed_error_));
                log_.log("[STEP image_get_classes] FAIL: " + failed_error_);
                return false;
            }
            classes_.push_back(reinterpret_cast<std::uint64_t>(klass));
            Json item = Json::object();
            item.set("index", Json::integer(static_cast<std::int64_t>(i)));
            item.set("class_va", Json::string(format_hex(classes_.back())));
            item.set("pointer_check", pointer_check_json(class_check));
            classes.push(std::move(item));
        }

        Json step = pass_step("image_get_classes");
        Json details = Json::object();
        details.set("classes_read", Json::integer(static_cast<std::int64_t>(read_count)));
        details.set("classes", std::move(classes));
        step.set("details", std::move(details));
        steps.push_back(std::move(step));
        log_.log("[STEP image_get_classes] PASS read=" + std::to_string(read_count));
    }

    // STEP 8: class name / namespace ----------------------------------------
    {
        const std::size_t name_slot = static_cast<std::size_t>(kSlotClassGetName);
        const std::size_t ns_slot = static_cast<std::size_t>(kSlotClassGetNamespace);
        if (!table_.valid[name_slot] || !table_.valid[ns_slot]) {
            failed_step_name_ = "class_names";
            failed_error_ = "api table slot 37 (class_get_name) or 39 "
                            "(class_get_namespace) is null";
            steps.push_back(fail_step(failed_step_name_, "API_SLOT_MISSING", failed_error_));
            return false;
        }
        const std::uint64_t name_fn_addr = table_.slots[name_slot];
        const std::uint64_t ns_fn_addr = table_.slots[ns_slot];
        PointerCheck name_fn_check = validator.check_exec_function(name_fn_addr);
        PointerCheck ns_fn_check = validator.check_exec_function(ns_fn_addr);
        if (!name_fn_check.valid || !ns_fn_check.valid) {
            failed_step_name_ = "class_names";
            failed_error_ = "class_get_name or class_get_namespace wrapper is not in an "
                            "executable module section";
            steps.push_back(fail_step(failed_step_name_, "INVALID_API_FUNCTION_POINTER",
                                      failed_error_));
            return false;
        }

        Json classes = Json::array();
        for (std::size_t i = 0; i < classes_.size(); ++i) {
            std::uint64_t raw_name_value = 0;
            std::uint64_t raw_ns_value = 0;
            DWORD seh_code = 0;
            if (!seh_call_raw("class_get_name", name_fn_addr, &raw_name_value,
                              classes_[i], 0, 0, 0, &seh_code)) {
                failed_step_name_ = "class_names";
                failed_error_ = "class_get_name(" + std::to_string(i) +
                                ") raised SEH exception " + format_hex(seh_code);
                steps.push_back(fail_step(failed_step_name_, "API_CALL_FAULT",
                                          failed_error_));
                return false;
            }
            if (!seh_call_raw("class_get_namespace", ns_fn_addr, &raw_ns_value,
                              classes_[i], 0, 0, 0, &seh_code)) {
                failed_step_name_ = "class_names";
                failed_error_ = "class_get_namespace(" + std::to_string(i) +
                                ") raised SEH exception " + format_hex(seh_code);
                steps.push_back(fail_step(failed_step_name_, "API_CALL_FAULT",
                                          failed_error_));
                return false;
            }
            const char* raw_name = reinterpret_cast<const char*>(raw_name_value);
            const char* raw_ns = reinterpret_cast<const char*>(raw_ns_value);

            std::string class_name;
            std::string class_namespace;
            PointerCheck name_check = validator.check_generic(
                reinterpret_cast<std::uint64_t>(raw_name));
            PointerCheck ns_check = validator.check_generic(
                reinterpret_cast<std::uint64_t>(raw_ns));
            const bool name_ok =
                raw_name != nullptr && name_check.valid &&
                validator.read_cstring(reinterpret_cast<std::uint64_t>(raw_name),
                                       config_.max_string_length, class_name,
                                       &name_check) &&
                !class_name.empty() && is_printable_utf8_string(class_name);
            const bool ns_ok =
                raw_ns != nullptr && ns_check.valid &&
                validator.read_cstring(reinterpret_cast<std::uint64_t>(raw_ns),
                                       config_.max_string_length, class_namespace,
                                       &ns_check) &&
                is_printable_utf8_string(class_namespace);
            if (!name_ok || !ns_ok) {
                failed_step_name_ = "class_names";
                failed_error_ = "class " + std::to_string(i) +
                                " name/namespace is not a readable printable string";
                Json details = Json::object();
                details.set("class_index", Json::integer(static_cast<std::int64_t>(i)));
                details.set("name_pointer",
                            Json::string(format_hex(reinterpret_cast<std::uint64_t>(raw_name))));
                details.set("namespace_pointer",
                            Json::string(format_hex(reinterpret_cast<std::uint64_t>(raw_ns))));
                steps.push_back(fail_step(failed_step_name_, "CLASS_NAME_INVALID",
                                          failed_error_, std::move(details)));
                log_.log("[STEP class_names] FAIL: " + failed_error_);
                return false;
            }

            Json item = Json::object();
            item.set("index", Json::integer(static_cast<std::int64_t>(i)));
            item.set("class_va", Json::string(format_hex(classes_[i])));
            item.set("namespace", Json::string(class_namespace));
            item.set("name", Json::string(class_name));
            classes.push(std::move(item));
        }

        Json step = pass_step("class_names");
        Json details = Json::object();
        details.set("classes", std::move(classes));
        step.set("details", std::move(details));
        steps.push_back(std::move(step));
        log_.log("[STEP class_names] PASS " + std::to_string(classes_.size()) +
                 " classes named");
    }

    return true;
}

// ---------------------------------------------------------------------------
// HealthCheck
// ---------------------------------------------------------------------------

HealthCheck::HealthCheck(const ProbeConfig& config, LogSink& log)
    : config_(config), log_(log) {}

bool HealthCheck::step_module_discovery() {
    log_.log("[STEP module_discovery] begin");
    pid_ = GetCurrentProcessId();

    wchar_t exe_path[MAX_PATH] = {};
    const DWORD exe_len = GetModuleFileNameW(nullptr, exe_path, MAX_PATH);
    if (exe_len == 0 || exe_len >= MAX_PATH) {
        failure_step_ = "module_discovery";
        failure_error_ = "GetModuleFileNameW failed";
        steps_.push_back(fail_step(failure_step_, "PROCESS_PATH_UNKNOWN", failure_error_));
        log_.log("[STEP module_discovery] FAIL: " + failure_error_);
        return false;
    }
    process_path_ = wide_to_utf8(exe_path);
    const std::size_t slash = process_path_.find_last_of("\\/");
    process_name_ = slash == std::string::npos ? process_path_
                                               : process_path_.substr(slash + 1);

    const HMODULE exe_handle = GetModuleHandleW(nullptr);
    const HMODULE unity_handle = GetModuleHandleW(L"UnityPlayer.dll");
    const HMODULE game_handle = GetModuleHandleW(L"GameAssembly.dll");
    if (unity_handle == nullptr || game_handle == nullptr) {
        failure_step_ = "module_discovery";
        failure_error_ = "UnityPlayer.dll and GameAssembly.dll must both be loaded";
        Json details = Json::object();
        details.set("UnityPlayer.dll_loaded", Json::boolean(unity_handle != nullptr));
        details.set("GameAssembly.dll_loaded", Json::boolean(game_handle != nullptr));
        steps_.push_back(fail_step(failure_step_, "REQUIRED_MODULE_NOT_LOADED",
                                   failure_error_, std::move(details)));
        log_.log("[STEP module_discovery] FAIL: " + failure_error_);
        return false;
    }

    modules_.clear();
    ModuleInfo info;
    if (!module_info_for(exe_handle, L"", info)) {
        failure_step_ = "module_discovery";
        failure_error_ = "failed to parse StarRail.exe module";
        steps_.push_back(fail_step(failure_step_, "PE_PARSE_FAILED", failure_error_));
        return false;
    }
    modules_.push_back(info);
    if (!module_info_for(unity_handle, L"UnityPlayer.dll", info)) {
        failure_step_ = "module_discovery";
        failure_error_ = "failed to parse UnityPlayer.dll module";
        steps_.push_back(fail_step(failure_step_, "PE_PARSE_FAILED", failure_error_));
        return false;
    }
    modules_.push_back(info);
    if (!module_info_for(game_handle, L"GameAssembly.dll", info)) {
        failure_step_ = "module_discovery";
        failure_error_ = "failed to parse GameAssembly.dll module";
        steps_.push_back(fail_step(failure_step_, "PE_PARSE_FAILED", failure_error_));
        return false;
    }
    modules_.push_back(info);
    exe_module_ = &modules_[0];
    unity_module_ = &modules_[1];
    game_module_ = &modules_[2];

    // Version truth: installed asset, never the directory name.
    game_version_ = "unknown";
    version_source_ = "unknown";
    const std::wstring exe_wide = utf8_to_wide(process_path_);
    const std::wstring exe_dir =
        exe_wide.substr(0, exe_wide.find_last_of(L"\\/") + 1);
    std::vector<std::uint8_t> binary_version;
    const std::wstring binary_version_path =
        exe_dir + L"StarRail_Data\\StreamingAssets\\BinaryVersion.bytes";
    if (read_entire_file(binary_version_path, binary_version)) {
        if (parse_binary_version(binary_version, game_version_, build_string_)) {
            version_source_ = "BinaryVersion.bytes";
        }
    }
    if (game_version_ == "unknown" && file_version_of_exe(exe_wide, game_version_)) {
        version_source_ = "StarRail.exe version resource";
    }

    Json step = pass_step("module_discovery");
    Json details = Json::object();
    Json process = Json::object();
    process.set("pid", Json::integer(static_cast<std::int64_t>(pid_)));
    process.set("name", Json::string(process_name_));
    process.set("path", Json::string(process_path_));
    details.set("process", std::move(process));
    details.set("game_version", Json::string(game_version_));
    details.set("version_source", Json::string(version_source_));
    if (!build_string_.empty()) {
        details.set("build_string", Json::string(build_string_));
    }
    Json modules = Json::array();
    for (const ModuleInfo& module : modules_) {
        modules.push(module_json(module));
    }
    details.set("modules", std::move(modules));
    step.set("details", std::move(details));
    steps_.push_back(std::move(step));
    log_.log("[STEP module_discovery] PASS " + process_name_ +
             " pid=" + std::to_string(pid_) + " version=" + game_version_);
    return true;
}

bool HealthCheck::step_api_table_locator() {
    log_.log("[STEP api_table_locator] begin");
    ModuleMemoryReader reader(unity_module_->base, unity_module_->size);
    ApiTableLocator locator(*unity_module_, reader);
    const LocatorResult result = locator.locate(40);

    Json details = Json::object();
    details.set("candidates_scanned", Json::integer(result.candidates_scanned));
    details.set("candidates_scored", Json::integer(result.candidates_scored));
    if (result.success) {
        details.set("rva", Json::string(format_hex(result.best_table_rva)));
        details.set("va", Json::string(format_hex(result.best_table_va)));
        details.set("section", Json::string(result.best_section));
        details.set("score", Json::floating(result.score));
        details.set("confidence", Json::string(result.confidence));
        details.set("known_slots_matched", Json::integer(result.known_slots_matched));
        details.set("wrapper_matches", Json::integer(result.wrapper_matches));
        details.set("descriptor_matches", Json::integer(result.descriptor_matches));
        details.set("twin_relations", Json::integer(result.best.twin_relations));
    }
    Json failed = Json::array();
    for (const std::string& item : result.failed_constraints) {
        failed.push(Json::string(item));
    }
    details.set("failed_constraints", std::move(failed));

    bool ok = result.success;
    std::string failure_code = "LOCATOR_FAILED";
    if (ok && result.confidence != "high") {
        ok = false;
        failure_step_ = "api_table_locator";
        failure_code = "LOCATOR_CONFIDENCE_LOW";
        failure_error_ = "locator confidence is " + result.confidence +
                         "; high confidence required before calling game code";
    } else if (ok && (result.known_slots_matched != 27 ||
                      !result.failed_constraints.empty())) {
        ok = false;
        failure_step_ = "api_table_locator";
        failure_code = "LOCATOR_CONSTRAINTS_FAILED";
        failure_error_ = "locator result failed structural constraints";
    } else if (!ok) {
        failure_step_ = "api_table_locator";
        failure_error_ = "no candidate passed the structural prefilter";
    }

    if (ok && config_.expect_rva_enabled) {
        const bool expected_matches =
            result.best_table_rva == config_.expected_table_rva;
        details.set("expected_table_rva",
                    Json::string(format_hex(config_.expected_table_rva)));
        details.set("expected_rva_matches", Json::boolean(expected_matches));
        log_.log("[STEP api_table_locator] validation-only comparison: expected=" +
                 format_hex(config_.expected_table_rva) +
                 " actual=" + format_hex(result.best_table_rva));
        if (!expected_matches) {
            ok = false;
            failure_step_ = "api_table_locator";
            failure_code = "EXPECTED_RVA_MISMATCH";
            failure_error_ =
                "located table RVA does not match the independently known "
                "verification value (the value is comparison-only, never locator input)";
        }
    }

    if (!ok) {
        steps_.push_back(fail_step(failure_step_, failure_code, failure_error_,
                                   std::move(details)));
        log_.log("[STEP api_table_locator] FAIL: " + failure_error_);
        return false;
    }

    located_table_rva_ = result.best_table_rva;
    Json step = pass_step("api_table_locator");
    step.set("details", std::move(details));
    steps_.push_back(std::move(step));
    log_.log("[STEP api_table_locator] PASS rva=" +
             format_hex(result.best_table_rva) +
             " score=" + std::to_string(result.score) +
             " confidence=" + result.confidence);
    return true;
}

bool HealthCheck::run() {
    if (config_.wait_before_run_ms != 0) {
        Sleep(config_.wait_before_run_ms);
    }

    namespace fs = std::filesystem;
    std::wstring output_dir = utf8_to_wide(config_.output_dir);
    if (output_dir.empty()) {
        output_dir = fs::current_path().wstring();
    }
    std::error_code ec;
    fs::create_directories(output_dir, ec);
    if (ec) {
        output_dir = fs::current_path().wstring();
    }
    const std::string base_name =
        "runtime_health_check_" + now_utc_compact() + "_pid" +
        std::to_string(GetCurrentProcessId());
    log_path_ = output_dir + L"\\" + utf8_to_wide(base_name) + L".log";
    json_path_ = output_dir + L"\\" + utf8_to_wide(base_name) + L".json";
    log_.open_file(log_path_);
    log_.log("hsr-runtime-health-probe: read-only IL2CPP health check");
    log_.log("probe module loaded visibly (no hooks, no patches, no stealth)");

    bool ok = step_module_discovery();
    if (ok) {
        ok = step_api_table_locator();
    }
    if (ok) {
        ApiTableView table;
        ModuleMemoryReader reader(unity_module_->base, unity_module_->size);
        table.load(*unity_module_, reader, located_table_rva_);
        RuntimeSteps runtime(unity_module_, modules_, table, config_, log_);
        ok = runtime.run(steps_);
        if (!ok) {
            failure_step_ = runtime.failed_step_name();
            failure_error_ = runtime.failed_error();
        }
    }

    hd2_ = ok;
    finish_json();
    return ok;
}

void HealthCheck::finish_json() {
    result_ = Json::object();
    result_.set("schema_version", Json::integer(1));
    result_.set("tool",
                Json::string("tools/runtime_probe/probe/hsr_runtime_health_probe.dll"));
    result_.set("game_version", Json::string(game_version_));
    result_.set("version_source", Json::string(version_source_));
    if (!build_string_.empty()) {
        result_.set("build_string", Json::string(build_string_));
    }
    result_.set("generated_utc", Json::string(now_utc_iso()));
    result_.set("pid", Json::integer(static_cast<std::int64_t>(pid_ == 0 ? GetCurrentProcessId() : pid_)));
    result_.set("process_name", Json::string(process_name_));
    result_.set("process_path", Json::string(process_path_));
    Json steps = Json::array();
    for (const Json& step : steps_) {
        steps.push(step);
    }
    result_.set("steps", std::move(steps));
    result_.set("failure_step",
                failure_step_.empty() ? Json::null() : Json::string(failure_step_));
    result_.set("error",
                failure_error_.empty() ? Json::null() : Json::string(failure_error_));
    result_.set("hd2", Json::boolean(hd2_));

    if (!json_path_.empty()) {
        write_entire_file(json_path_, result_.dump(2));
        log_.log("JSON written: " + wide_to_utf8(json_path_));
    }
    if (hd2_) {
        log_.log("HD-2 = PASS");
    } else {
        log_.log("HD-2 = FAIL / BLOCKED step=" +
                 (failure_step_.empty() ? std::string("unknown") : failure_step_) +
                 " error=" +
                 (failure_error_.empty() ? std::string("none") : failure_error_));
    }
    log_.log("probe finished; module remains loaded until game exit (no hooks)");
}

}  // namespace hsr_probe
