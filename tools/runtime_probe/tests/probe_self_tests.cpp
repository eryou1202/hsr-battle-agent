// probe_self_tests.cpp - offline self-tests for the runtime health-check probe.
//
// Runs without StarRail.exe:
//   1. pointer validation helpers on committed local memory
//   2. full synthetic api-table locator run (crafted wrappers/descriptors)
//   3. failure-stop runtime chain (domain_get returns null -> stops)
//   4. full mock runtime chain (domain -> assemblies -> image -> classes -> names)
//   5. optional real UnityPlayer locator parity check
//        probe_self_tests.exe --unity-path <UnityPlayer.dll> --expect-rva 0x1A36480
//
// The real-module check only runs the read-only structural locator; it never
// calls an il2cpp runtime API.

#include <windows.h>
#include <psapi.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "../probe/api_locator.h"
#include "../probe/common.h"
#include "../probe/health_check.h"
#include "../probe/json.h"
#include "../probe/log_sink.h"
#include "../probe/pe_model.h"
#include "../probe/pointer_validation.h"
#include "../gen/locator_prior.h"

#pragma comment(lib, "psapi.lib")

namespace {

using namespace hsr_probe;

int g_failures = 0;

#define CHECK(cond, name)                                              \
    do {                                                               \
        if (cond) {                                                    \
            std::printf("[PASS] %s\n", name);                          \
        } else {                                                       \
            std::printf("[FAIL] %s\n", name);                          \
            ++g_failures;                                              \
        }                                                              \
    } while (0)

void write_u64(std::vector<std::uint8_t>& buffer, std::uint64_t rva,
               std::uint64_t value) {
    std::memcpy(buffer.data() + rva, &value, sizeof(value));
}

std::uint64_t read_u64(const std::vector<std::uint8_t>& buffer, std::uint64_t rva) {
    std::uint64_t value = 0;
    std::memcpy(&value, buffer.data() + rva, sizeof(value));
    return value;
}

bool write_wrapper(std::vector<std::uint8_t>& buffer, std::uint64_t wrapper_rva,
                   char shape, std::uint64_t desc_rva, std::uint64_t code_ptr) {
    if (shape == 'A') {
        std::uint8_t bytes[16] = {};
        bytes[0] = 0x45; bytes[1] = 0x33; bytes[2] = 0xC0;
        bytes[3] = 0x48; bytes[4] = 0x8D; bytes[5] = 0x0D;
        const std::int64_t disp =
            static_cast<std::int64_t>(desc_rva) -
            (static_cast<std::int64_t>(wrapper_rva) + 10);
        std::int32_t disp32 = static_cast<std::int32_t>(disp);
        std::memcpy(bytes + 6, &disp32, 4);
        bytes[10] = 0x33; bytes[11] = 0xD2; bytes[12] = 0xE9;
        std::memcpy(buffer.data() + wrapper_rva, bytes, sizeof(bytes));
        return true;
    }
    if (shape == 'B') {
        std::uint8_t bytes[38] = {};
        bytes[0] = 0x48; bytes[1] = 0x83; bytes[2] = 0xEC; bytes[3] = 0x38;
        bytes[4] = 0x45; bytes[5] = 0x33; bytes[6] = 0xC9;
        bytes[7] = 0x48; bytes[8] = 0xC7; bytes[9] = 0x44; bytes[10] = 0x24;
        bytes[11] = 0x20; bytes[12] = 0x00; bytes[13] = 0x00; bytes[14] = 0x00;
        bytes[15] = 0x00;
        bytes[16] = 0x45; bytes[17] = 0x33; bytes[18] = 0xC0;
        bytes[19] = 0x48; bytes[20] = 0x8D; bytes[21] = 0x15;
        const std::int64_t stub_disp =
            static_cast<std::int64_t>(code_ptr) -
            (static_cast<std::int64_t>(wrapper_rva) + 26);
        std::int32_t stub32 = static_cast<std::int32_t>(stub_disp);
        std::memcpy(bytes + 22, &stub32, 4);
        bytes[26] = 0x48; bytes[27] = 0x8D; bytes[28] = 0x0D;
        const std::int64_t disp =
            static_cast<std::int64_t>(desc_rva) -
            (static_cast<std::int64_t>(wrapper_rva) + 33);
        std::int32_t disp32 = static_cast<std::int32_t>(disp);
        std::memcpy(bytes + 29, &disp32, 4);
        bytes[33] = 0xE8;
        std::memcpy(buffer.data() + wrapper_rva, bytes, sizeof(bytes));
        return true;
    }
    if (shape == 'C') {
        std::uint8_t bytes[8] = {0x66, 0x0F, 0x6F, 0, 0, 0, 0, 0};
        std::memcpy(buffer.data() + wrapper_rva, bytes, sizeof(bytes));
        return true;
    }
    return false;
}

bool write_descriptor(std::vector<std::uint8_t>& buffer, std::uint64_t desc_rva,
                      char shape, std::uint64_t code_va, std::uint64_t data_va) {
    for (int i = 0; i < 11; ++i) {
        write_u64(buffer, desc_rva + static_cast<std::uint64_t>(i) * 8, 0);
    }
    const std::uint64_t sentinel = 0xFFFFFFFFFFFFFFFFULL;
    if (shape == 'A') {
        write_u64(buffer, desc_rva + 1 * 8, sentinel);
        write_u64(buffer, desc_rva + 5 * 8, code_va);
        write_u64(buffer, desc_rva + 8 * 8, data_va);
        write_u64(buffer, desc_rva + 9 * 8, data_va);
    } else if (shape == 'B') {
        write_u64(buffer, desc_rva + 2 * 8, code_va);
        write_u64(buffer, desc_rva + 5 * 8, data_va);
        write_u64(buffer, desc_rva + 6 * 8, data_va);
        write_u64(buffer, desc_rva + 9 * 8, sentinel);
    }
    return true;
}

void test_json() {
    Json obj = Json::object();
    obj.set("string", Json::string("a\"b\\c\n"));
    obj.set("number", Json::integer(-7));
    obj.set("flag", Json::boolean(true));
    Json nested = Json::object();
    nested.set("value", Json::floating(98.64));
    obj.set("nested", std::move(nested));
    Json arr = Json::array();
    arr.push(Json::integer(1));
    arr.push(Json::string("two"));
    obj.set("array", std::move(arr));
    const std::string dumped = obj.dump(2);
    CHECK(dumped.find("\"a\\\"b\\\\c\\n\"") != std::string::npos, "json escaping");
    CHECK(dumped.find("\"value\": 98.64") != std::string::npos, "json pretty float");
    CHECK(dumped.find("\"number\": -7") != std::string::npos, "json integer");
}

void test_pointer_validation() {
    const std::uint64_t size = 0x10000;
    std::uint8_t* raw = static_cast<std::uint8_t*>(
        VirtualAlloc(nullptr, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    CHECK(raw != nullptr, "pointer validation: VirtualAlloc");
    if (raw == nullptr) {
        return;
    }
    const std::uint64_t base = reinterpret_cast<std::uint64_t>(raw);

    ModuleInfo module;
    module.name = "UnityPlayer.dll";
    module.base = base;
    module.size = size;
    PeSection text;
    text.name = ".text";
    text.rva = 0x1000;
    text.vsize = 0x4000;
    text.raw_size = 0x4000;
    text.characteristics = 0x60000020;
    module.sections.push_back(text);
    PeSection rdata;
    rdata.name = ".rdata";
    rdata.rva = 0x5000;
    rdata.vsize = 0x4000;
    rdata.raw_size = 0x4000;
    rdata.characteristics = 0x40000040;
    module.sections.push_back(rdata);
    PeSection data;
    data.name = ".data";
    data.rva = 0x9000;
    data.vsize = 0x4000;
    data.raw_size = 0x4000;
    data.characteristics = 0xC0000040;
    module.sections.push_back(data);

    std::memcpy(raw + 0x5200, "Hello\0", 6);

    DWORD old = 0;
    VirtualProtect(raw + 0x1000, 0x1000, PAGE_EXECUTE_READ, &old);
    VirtualProtect(raw + 0x5000, 0x1000, PAGE_READONLY, &old);
    VirtualProtect(raw + 0x9000, 0x1000, PAGE_READWRITE, &old);

    std::vector<ModuleInfo> modules{module};
    PointerValidator validator(&modules);

    PointerCheck code = validator.check_exec_function(base + 0x1100);
    CHECK(code.valid && code.executable && code.section == ".text",
          "pointer validation: executable section");
    PointerCheck ro = validator.check_generic(base + 0x5200);
    CHECK(ro.valid && ro.readable && ro.section == ".rdata",
          "pointer validation: readable section");
    PointerCheck data_p = validator.check_generic(base + 0x9100);
    CHECK(data_p.valid && data_p.readable && data_p.section == ".data",
          "pointer validation: writable section");
    PointerCheck null_p = validator.check_generic(0);
    CHECK(!null_p.valid && !null_p.canonical, "pointer validation: null");
    PointerCheck low = validator.check_generic(0x1);
    CHECK(!low.valid && !low.canonical, "pointer validation: low address");
    PointerCheck data_as_code = validator.check_exec_function(base + 0x9100);
    CHECK(!data_as_code.valid, "pointer validation: data is not executable");

    std::string text_out;
    PointerCheck string_check;
    const bool cstring_ok = validator.read_cstring(base + 0x5200, 64, text_out,
                                                   &string_check);
    CHECK(cstring_ok && text_out == "Hello" && string_check.valid,
          "pointer validation: safe cstring read");

    VirtualFree(raw, 0, MEM_RELEASE);
}

void test_synthetic_locator() {
    const std::uint64_t base = 0x180000000ULL;
    const std::uint64_t module_size = 0x40000;
    std::vector<std::uint8_t> buffer(module_size, 0);

    ModuleInfo module;
    module.name = "UnityPlayer.dll";
    module.base = base;
    module.size = module_size;
    PeSection text;
    text.name = ".text";
    text.rva = 0x1000;
    text.vsize = 0x8000;
    text.raw_size = 0x8000;
    text.characteristics = 0x60000020;
    module.sections.push_back(text);
    PeSection rdata;
    rdata.name = ".rdata";
    rdata.rva = 0x10000;
    rdata.vsize = 0x8000;
    rdata.raw_size = 0x8000;
    rdata.characteristics = 0x40000040;
    module.sections.push_back(rdata);
    PeSection data;
    data.name = ".data";
    data.rva = 0x20000;
    data.vsize = 0x20000;
    data.raw_size = 0x20000;
    data.characteristics = 0xC0000040;
    module.sections.push_back(data);

    // Assign wrapper RVAs.
    //
    // Shape A needs >= 0x20 spacing and shape B needs >= 0x40 spacing for its
    // checked prologue bytes to stay intact. Known-slot addresses are laid out
    // first so the twin relations are exact:
    //   slot 63/65 = A at delta 0x20
    //   slot 10/12 = B at delta 0x40
    const int slot_count = hsr_probe::locator_prior::kFullSlotCount;
    std::vector<std::uint64_t> wrappers(slot_count, 0);
    std::vector<char> shapes(slot_count, 'A');
    std::vector<bool> is_known(slot_count, false);
    for (const auto& known : hsr_probe::locator_prior::kKnownSlotsDetailed) {
        shapes[static_cast<std::size_t>(known.index)] = known.shape;
        is_known[static_cast<std::size_t>(known.index)] = true;
    }
    wrappers[63] = 0x1200;
    wrappers[65] = 0x1220;
    wrappers[10] = 0x1300;
    wrappers[12] = 0x1340;
    shapes[10] = 'B';
    shapes[12] = 'B';
    std::uint64_t cursor = 0x1400;
    for (int slot = 0; slot < slot_count; ++slot) {
        if (is_known[static_cast<std::size_t>(slot)] && wrappers[slot] == 0) {
            wrappers[static_cast<std::size_t>(slot)] = cursor;
            cursor += 0x40;
        }
    }
    std::uint64_t unknown_cursor = 0x2000;
    for (int slot = 0; slot < slot_count; ++slot) {
        if (is_known[static_cast<std::size_t>(slot)] || slot == 10 || slot == 12) {
            continue;
        }
        shapes[static_cast<std::size_t>(slot)] = (slot % 2 == 0) ? 'A' : 'B';
        wrappers[static_cast<std::size_t>(slot)] = unknown_cursor;
        unknown_cursor +=
            shapes[static_cast<std::size_t>(slot)] == 'B' ? 0x40 : 0x20;
    }

    // Descriptor RVAs.
    const std::uint64_t desc_base = 0x21000;
    const std::uint64_t other_base = 0x24000;
    std::vector<std::uint64_t> descs(slot_count, 0);
    for (int i = 0; i < hsr_probe::locator_prior::kExpectedDescDeltaCount; ++i) {
        const int slot = hsr_probe::locator_prior::kExpectedDescDeltaKeys[i];
        descs[static_cast<std::size_t>(slot)] =
            desc_base + static_cast<std::uint64_t>(
                            hsr_probe::locator_prior::kExpectedDescDeltaValues[i]);
    }
    descs[10] = descs[63] - 0x930;
    descs[12] = descs[10] + 0x58;
    for (int slot = 0; slot < slot_count; ++slot) {
        if (descs[static_cast<std::size_t>(slot)] == 0 && shapes[slot] != 'C') {
            descs[static_cast<std::size_t>(slot)] =
                other_base + static_cast<std::uint64_t>(slot) * 0x58;
        }
    }

    const std::uint64_t table_rva = 0x10040;
    const std::uint64_t code_va = base + wrappers[0];
    const std::uint64_t data_va = base + desc_base;
    for (int slot = 0; slot < slot_count; ++slot) {
        const std::uint64_t wrapper_rva = wrappers[static_cast<std::size_t>(slot)];
        if (shapes[static_cast<std::size_t>(slot)] == 'C') {
            write_wrapper(buffer, wrapper_rva, 'C', 0, 0);
        } else {
            const std::uint64_t desc_rva = descs[static_cast<std::size_t>(slot)];
            write_wrapper(buffer, wrapper_rva, shapes[static_cast<std::size_t>(slot)],
                          desc_rva, code_va);
            write_descriptor(buffer, desc_rva, shapes[static_cast<std::size_t>(slot)],
                             code_va, data_va);
        }
        write_u64(buffer, table_rva + static_cast<std::uint64_t>(slot) * 8,
                  base + wrapper_rva);
    }

    BufferMemoryReader memory(base, buffer);
    ApiTableLocator locator(module, memory);
    LocatorResult result = locator.locate(40);

    std::printf("  synthetic locator metrics: best=0x%llX shape=%d desc=%d twin=%d "
                "wrapper=%d descriptors=%d confidence=%s candidates=%d\n",
                static_cast<unsigned long long>(result.best_table_rva),
                result.best.known_shape_profile_matches,
                result.best.known_desc_profile_matches, result.best.twin_relations,
                result.best.wrapper_matches, result.best.descriptor_matches,
                result.confidence.c_str(), result.candidates_scanned);
    CHECK(result.success, "synthetic locator: success");
    CHECK(result.best_table_rva == table_rva, "synthetic locator: exact table rva");
    CHECK(result.best.known_shape_profile_matches == 27,
          "synthetic locator: known shape profile 27/27");
    CHECK(result.best.known_desc_profile_matches == 26,
          "synthetic locator: known desc spacing 26/26");
    CHECK(result.best.twin_relations == 3, "synthetic locator: twin relations 3/3");
    CHECK(result.best.wrapper_matches == 240, "synthetic locator: wrapper coverage");
    CHECK(result.best.descriptor_matches >= 237,
          "synthetic locator: descriptor coverage");
    CHECK(result.failed_constraints.empty(), "synthetic locator: no failed constraints");
    CHECK(result.confidence == "high", "synthetic locator: high confidence");
    CHECK(result.candidates_scanned > 1, "synthetic locator: runners were scored");
}

// --- mock il2cpp runtime -----------------------------------------------------

struct MockDomain { int value = 1; };
struct MockAssembly { int value = 2; };
struct MockImage { int value = 3; };
struct MockClass { int value = 4; };

MockDomain g_mock_domain;
MockAssembly g_mock_assembly0;
MockAssembly g_mock_assembly1;
MockImage g_mock_image;
MockClass g_mock_class0;
MockClass g_mock_class1;
MockClass g_mock_class2;
std::uint64_t g_mock_assembly_array[2] = {0, 0};

const char* const g_mock_image_name = "Assembly-CSharp.dll";
const char* const g_mock_names[3] = {"TestAbilityMixin", "DealDamageBlackSwan", "PredicateBase"};
const char* const g_mock_namespaces[3] = {"RPG.Client.Test", "", "Battle"};

void* mock_domain_get() { return &g_mock_domain; }
void* mock_domain_get_null() { return nullptr; }

void** mock_domain_get_assemblies(void*, std::size_t* count) {
    *count = 2;
    return reinterpret_cast<void**>(g_mock_assembly_array);
}

void* mock_assembly_get_image(void*) { return &g_mock_image; }
const char* mock_image_get_name(void*) { return g_mock_image_name; }
std::size_t mock_image_get_class_count(void*) { return 3; }

void* mock_image_get_class(void*, std::size_t index) {
    if (index == 0) return &g_mock_class0;
    if (index == 1) return &g_mock_class1;
    if (index == 2) return &g_mock_class2;
    return nullptr;
}

const char* mock_class_get_name(void* klass) {
    if (klass == &g_mock_class0) return g_mock_names[0];
    if (klass == &g_mock_class1) return g_mock_names[1];
    if (klass == &g_mock_class2) return g_mock_names[2];
    return nullptr;
}

const char* mock_class_get_namespace(void* klass) {
    if (klass == &g_mock_class0) return g_mock_namespaces[0];
    if (klass == &g_mock_class1) return g_mock_namespaces[1];
    if (klass == &g_mock_class2) return g_mock_namespaces[2];
    return nullptr;
}

bool test_module_of_self(ModuleInfo& out) {
    const HMODULE self = GetModuleHandleW(nullptr);
    MODULEINFO info{};
    if (GetModuleInformation(GetCurrentProcess(), self, &info, sizeof(info)) == FALSE) {
        return false;
    }
    wchar_t path[MAX_PATH] = {};
    GetModuleFileNameW(self, path, MAX_PATH);
    out.name = "probe_self_tests.exe";
    out.path = hsr_probe::wide_to_utf8(path);
    out.base = reinterpret_cast<std::uint64_t>(info.lpBaseOfDll);
    out.size = static_cast<std::uint64_t>(info.SizeOfImage);
    std::string error;
    return hsr_probe::parse_pe_from_memory(out.base, out.size, out.sections, error);
}

void fill_mock_table(hsr_probe::ApiTableView& table) {
    auto put = [&table](int slot, void* fn) {
        table.slots[static_cast<std::size_t>(slot)] =
            reinterpret_cast<std::uint64_t>(fn);
        table.valid[static_cast<std::size_t>(slot)] = true;
    };
    put(hsr_probe::kSlotDomainGet, &mock_domain_get);
    put(hsr_probe::kSlotDomainGetAssemblies, &mock_domain_get_assemblies);
    put(hsr_probe::kSlotAssemblyGetImage, &mock_assembly_get_image);
    put(hsr_probe::kSlotImageGetName, &mock_image_get_name);
    put(hsr_probe::kSlotImageGetClassCount, &mock_image_get_class_count);
    put(hsr_probe::kSlotImageGetClass, &mock_image_get_class);
    put(hsr_probe::kSlotClassGetName, &mock_class_get_name);
    put(hsr_probe::kSlotClassGetNamespace, &mock_class_get_namespace);
}

void test_failure_stop() {
    ModuleInfo self;
    CHECK(test_module_of_self(self), "failure stop: self module parse");
    if (self.sections.empty()) {
        return;
    }
    std::vector<ModuleInfo> modules{self};
    hsr_probe::ApiTableView table;
    table.slots[hsr_probe::kSlotDomainGet] =
        reinterpret_cast<std::uint64_t>(&mock_domain_get_null);
    table.valid[hsr_probe::kSlotDomainGet] = true;

    hsr_probe::ProbeConfig config;
    hsr_probe::LogSink log;
    hsr_probe::RuntimeSteps runtime(&self, modules, table, config, log);
    std::vector<Json> steps;
    const bool ok = runtime.run(steps);
    CHECK(!ok, "failure stop: run fails on null domain");
    CHECK(steps.size() == 1, "failure stop: exactly one step executed");
    CHECK(runtime.failed_step_name() == "domain_get",
          "failure stop: failure step is domain_get");
    CHECK(steps.front().dump().find("\"success\": false") != std::string::npos,
          "failure stop: step JSON records failure");
}

void test_full_mock_chain() {
    ModuleInfo self;
    CHECK(test_module_of_self(self), "mock chain: self module parse");
    if (self.sections.empty()) {
        return;
    }
    g_mock_assembly_array[0] = reinterpret_cast<std::uint64_t>(&g_mock_assembly0);
    g_mock_assembly_array[1] = reinterpret_cast<std::uint64_t>(&g_mock_assembly1);

    std::vector<ModuleInfo> modules{self};
    hsr_probe::ApiTableView table;
    fill_mock_table(table);

    hsr_probe::ProbeConfig config;
    config.max_assemblies_to_report = 5;
    config.max_classes_to_read = 10;
    config.max_class_count_reasonable = 1000;
    hsr_probe::LogSink log;
    hsr_probe::RuntimeSteps runtime(&self, modules, table, config, log);
    std::vector<Json> steps;
    const bool ok = runtime.run(steps);
    CHECK(ok, "mock chain: full chain passes");
    CHECK(steps.size() == 7, "mock chain: seven runtime steps executed");
    CHECK(runtime.failed_step_name().empty(), "mock chain: no failure recorded");

    const std::string dumped = steps.back().dump();
    CHECK(dumped.find("\"name\": \"DealDamageBlackSwan\"") != std::string::npos,
          "mock chain: class names reach JSON");
    CHECK(dumped.find("\"namespace\": \"RPG.Client.Test\"") != std::string::npos,
          "mock chain: namespaces reach JSON");
}

void test_real_unity_parity(const std::wstring& unity_path,
                            std::uint64_t expected_rva) {
    if (unity_path.empty()) {
        std::printf("[SKIP] real UnityPlayer locator parity (no --unity-path)\n");
        return;
    }
    const HMODULE unity = LoadLibraryW(unity_path.c_str());
    if (unity == nullptr) {
        std::printf("[SKIP] real UnityPlayer parity: LoadLibrary failed (%lu)\n",
                    GetLastError());
        return;
    }
    MODULEINFO info{};
    if (GetModuleInformation(GetCurrentProcess(), unity, &info, sizeof(info)) == FALSE) {
        std::printf("[FAIL] real UnityPlayer parity: GetModuleInformation failed\n");
        ++g_failures;
        return;
    }
    ModuleInfo module;
    module.name = "UnityPlayer.dll";
    module.path = hsr_probe::wide_to_utf8(unity_path);
    module.base = reinterpret_cast<std::uint64_t>(info.lpBaseOfDll);
    module.size = static_cast<std::uint64_t>(info.SizeOfImage);
    std::string error;
    if (!hsr_probe::parse_pe_from_memory(module.base, module.size, module.sections, error)) {
        std::printf("[FAIL] real UnityPlayer parity: %s\n", error.c_str());
        ++g_failures;
        return;
    }
    hsr_probe::ModuleMemoryReader reader(module.base, module.size);
    hsr_probe::ApiTableLocator locator(module, reader);
    hsr_probe::LocatorResult result = locator.locate(40);
    std::printf("  candidates=%d scored=%d best=0x%llX score=%.2f confidence=%s "
                "known=%d wrapper=%d desc=%d\n",
                result.candidates_scanned, result.candidates_scored,
                static_cast<unsigned long long>(result.best_table_rva),
                result.score, result.confidence.c_str(), result.known_slots_matched,
                result.wrapper_matches, result.descriptor_matches);
    CHECK(result.success, "real UnityPlayer parity: locator success");
    CHECK(result.best_table_rva == expected_rva,
          "real UnityPlayer parity: best rva equals independent value");
    CHECK(result.candidates_scanned == 958,
          "real UnityPlayer parity: candidate count matches Python locator (958)");
    CHECK(result.score > 98.0 && result.confidence == "high",
          "real UnityPlayer parity: high confidence score");
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    std::wstring unity_path;
    std::uint64_t expected_rva = 0;
    for (int i = 1; i < argc; ++i) {
        const std::wstring arg = argv[i];
        if (arg == L"--unity-path" && i + 1 < argc) {
            unity_path = argv[++i];
        } else if (arg == L"--expect-rva" && i + 1 < argc) {
            expected_rva = std::wcstoull(argv[++i], nullptr, 16);
        }
    }

    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("probe_self_tests\n");
    std::printf("running json tests\n");
    test_json();
    std::printf("running pointer validation tests\n");
    test_pointer_validation();
    std::printf("running synthetic locator test\n");
    test_synthetic_locator();
    std::printf("running failure-stop test\n");
    test_failure_stop();
    std::printf("running full mock chain test\n");
    test_full_mock_chain();
    std::printf("running optional real-unity parity test\n");
    test_real_unity_parity(unity_path, expected_rva);

    if (g_failures == 0) {
        std::printf("ALL TESTS PASSED\n");
        return 0;
    }
    std::printf("%d TEST(S) FAILED\n", g_failures);
    return 1;
}
