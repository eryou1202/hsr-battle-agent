#pragma once

// api_locator.h - in-process C++ port of the structural IL2CPP api-table
// locator (tools/reverse/scripts/find_il2cpp_api_table.py).
//
// The structural priors are generated into gen/locator_prior.h directly from
// the Python locator constants. This file contains no api-table offset and no
// version branch; it only reads UnityPlayer's mapped image.

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "pe_model.h"

namespace hsr_probe {

// Read-only memory backend. The real backend reads directly from the mapped
// UnityPlayer image; the synthetic backend is used by self-tests.
struct LocatorMemory {
    virtual ~LocatorMemory() = default;
    virtual bool read_bytes(std::uint64_t absolute_addr, std::size_t size,
                            void* out) const = 0;
};

class ModuleMemoryReader : public LocatorMemory {
public:
    ModuleMemoryReader(std::uint64_t base, std::uint64_t size)
        : base_(base), size_(size) {}
    bool read_bytes(std::uint64_t absolute_addr, std::size_t size,
                    void* out) const override;

private:
    std::uint64_t base_;
    std::uint64_t size_;
};

class BufferMemoryReader : public LocatorMemory {
public:
    BufferMemoryReader(std::uint64_t base, const std::vector<std::uint8_t>& buffer)
        : base_(base), buffer_(buffer) {}
    bool read_bytes(std::uint64_t absolute_addr, std::size_t size,
                    void* out) const override;

private:
    std::uint64_t base_;
    const std::vector<std::uint8_t>& buffer_;
};

struct ScoredCandidate {
    std::uint64_t table_rva = 0;
    double score = 0.0;
    int known_slots_matched = 0;
    int known_shape_profile_matches = 0;
    int known_desc_profile_matches = 0;
    int known_shape_ok = 0;
    int known_unique = 0;
    int known_align20 = 0;
    int wrapper_matches = 0;
    int descriptor_matches = 0;
    int descriptor_strong = 0;
    int link_ok = 0;
    int link_checked = 0;
    int twin_relations = 0;
    int family_group_ok = 0;
    std::vector<std::string> failed_constraints;
};

struct LocatorResult {
    bool success = false;
    std::uint64_t best_table_rva = 0;
    std::uint64_t best_table_va = 0;
    std::string best_section;
    std::string confidence;
    double score = 0.0;
    int candidates_scanned = 0;
    int candidates_scored = 0;
    int known_slots_matched = 0;
    int wrapper_matches = 0;
    int descriptor_matches = 0;
    std::vector<std::string> failed_constraints;
    ScoredCandidate best;
    std::optional<ScoredCandidate> runner_up;
    std::vector<ScoredCandidate> top_candidates;
};

class ApiTableLocator {
public:
    ApiTableLocator(const ModuleInfo& unity, const LocatorMemory& memory);

    LocatorResult locate(int top_n = 40) const;

private:
    struct WrapperProbe {
        char shape = 0;  // 0 = unrecognized, 'A', 'B' or 'C'
        std::optional<std::uint64_t> descriptor_rva;
    };
    struct DescriptorProbe {
        bool ok = false;
        bool soft = false;
        bool strong = false;
        bool sentinel = false;
    };
    struct DescriptorLinks {
        std::optional<std::uint64_t> prev;
        std::optional<std::uint64_t> next;
    };

    bool read_mem(std::uint64_t rva, std::size_t size, void* out) const;
    std::optional<std::uint64_t> read_qword_rva(std::uint64_t rva) const;
    bool is_exec_rva(std::uint64_t rva) const;
    bool is_data_rva(std::uint64_t rva) const;
    bool is_exec_va(std::uint64_t va) const;
    bool is_data_va(std::uint64_t va) const;
    const PeSection* section_at_rva(std::uint64_t rva) const;

    WrapperProbe wrapper_probe(std::uint64_t wrapper_rva) const;
    DescriptorProbe descriptor_probe(char shape, std::uint64_t desc_rva) const;
    DescriptorLinks descriptor_links(char shape, std::uint64_t desc_rva) const;

    std::vector<std::uint64_t> collect_candidates() const;
    ScoredCandidate score_candidate(std::uint64_t table_rva) const;

    const ModuleInfo& unity_;
    const LocatorMemory& memory_;
    std::vector<std::uint32_t> sorted_section_indices_;
};

}  // namespace hsr_probe
