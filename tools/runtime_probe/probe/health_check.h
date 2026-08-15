#pragma once

// health_check.h - staged, read-only IL2CPP runtime health check.
//
// Strict order, one step must pass before the next one runs:
//   module_discovery -> api_table_locator -> domain_get ->
//   domain_get_assemblies -> assembly_get_image -> image_name ->
//   image_get_class_count -> image_get_classes -> class_names
//
// On the first failing step the run records the failure and stops. No pointer
// returned by the game is dereferenced before validation, and every API call
// is wrapped in SEH so a faulty wrapper cannot silently advance the pipeline.

#include <array>
#include <cstdint>
#include <string>
#include <vector>

#include "api_locator.h"
#include "common.h"
#include "json.h"
#include "log_sink.h"
#include "pe_model.h"
#include "pointer_validation.h"

namespace hsr_probe {

struct ProbeConfig {
    bool expect_rva_enabled = false;
    std::uint64_t expected_table_rva = 0;
    std::string output_dir;  // absolute UTF-8 path; empty = current dir
    int max_assemblies_to_report = 5;
    int max_classes_to_read = 10;
    std::uint64_t max_class_count_reasonable = 1000000;
    std::size_t max_string_length = 4096;
    std::uint32_t wait_before_run_ms = 1000;

    static bool load_ini(const std::wstring& path, ProbeConfig& out,
                         std::string& error);
};

struct ApiTableView {
    static constexpr std::size_t kSlots = kApiTableSlotCount;
    std::array<std::uint64_t, kSlots> slots{};
    std::array<bool, kSlots> valid{};

    bool load(const ModuleInfo& unity, const LocatorMemory& memory,
              std::uint64_t table_rva);
};

// The runtime chain (domain -> assemblies -> image -> classes -> names).
// Separated from module discovery so self-tests can drive it with mock APIs.
class RuntimeSteps {
public:
    RuntimeSteps(const ModuleInfo* unity, const std::vector<ModuleInfo>& modules,
                 const ApiTableView& table, const ProbeConfig& config,
                 LogSink& log);

    // Appends one JSON record per executed step. Returns true when the whole
    // chain passed; on the first failure appends the failing step and returns
    // false. No later step is executed.
    bool run(std::vector<Json>& steps);

    const std::string& failed_step_name() const { return failed_step_name_; }
    const std::string& failed_error() const { return failed_error_; }

private:
    const ModuleInfo* unity_;
    const std::vector<ModuleInfo>& modules_;
    const ApiTableView& table_;
    const ProbeConfig& config_;
    LogSink& log_;

    std::uint64_t domain_ = 0;
    std::vector<std::uint64_t> assemblies_;
    std::uint64_t image_ = 0;
    std::uint64_t class_count_ = 0;
    std::vector<std::uint64_t> classes_;

    std::string failed_step_name_;
    std::string failed_error_;
};

class HealthCheck {
public:
    HealthCheck(const ProbeConfig& config, LogSink& log);

    // Runs the complete staged check and writes human log + machine-readable
    // JSON. Never throws.
    bool run();

    const Json& result_json() const { return result_; }
    const std::vector<Json>& steps() const { return steps_; }
    bool hd2() const { return hd2_; }
    const std::string& failure_step() const { return failure_step_; }
    const std::string& final_status() const { return final_status_; }

private:
    bool step_module_discovery();
    bool step_api_table_locator();
    void finish_json();

    const ProbeConfig& config_;
    LogSink& log_;

    std::vector<ModuleInfo> modules_;
    const ModuleInfo* exe_module_ = nullptr;
    const ModuleInfo* unity_module_ = nullptr;
    const ModuleInfo* game_module_ = nullptr;
    std::string game_version_;
    std::string build_string_;
    std::string version_source_;
    std::uint64_t located_table_rva_ = 0;

    std::vector<Json> steps_;
    Json result_;
    bool hd2_ = false;
    std::string failure_step_;
    std::string failure_error_;
    std::string final_status_;
    std::uint32_t pid_ = 0;
    std::string process_name_;
    std::string process_path_;
    std::wstring json_path_;
    std::wstring log_path_;
};

}  // namespace hsr_probe
