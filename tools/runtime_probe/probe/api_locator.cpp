#include "api_locator.h"

#include <algorithm>
#include <cstring>
#include <map>
#include <set>

#include "common.h"
#include "../gen/locator_prior.h"

namespace hsr_probe {

namespace prior = locator_prior;

bool ModuleMemoryReader::read_bytes(std::uint64_t absolute_addr, std::size_t size,
                                    void* out) const {
    if (absolute_addr < base_ || size > size_ ||
        absolute_addr - base_ > size_ - size) {
        return false;
    }
    std::memcpy(out, reinterpret_cast<const void*>(absolute_addr), size);
    return true;
}

bool BufferMemoryReader::read_bytes(std::uint64_t absolute_addr, std::size_t size,
                                    void* out) const {
    if (absolute_addr < base_ || size > buffer_.size() ||
        absolute_addr - base_ > buffer_.size() - size) {
        return false;
    }
    std::memcpy(out, buffer_.data() + (absolute_addr - base_), size);
    return true;
}

namespace {

bool scored_greater(const ScoredCandidate& a, const ScoredCandidate& b) {
    if (a.known_shape_profile_matches != b.known_shape_profile_matches) {
        return a.known_shape_profile_matches > b.known_shape_profile_matches;
    }
    if (a.known_desc_profile_matches != b.known_desc_profile_matches) {
        return a.known_desc_profile_matches > b.known_desc_profile_matches;
    }
    if (a.twin_relations != b.twin_relations) {
        return a.twin_relations > b.twin_relations;
    }
    if (a.known_slots_matched != b.known_slots_matched) {
        return a.known_slots_matched > b.known_slots_matched;
    }
    if (a.known_shape_ok != b.known_shape_ok) {
        return a.known_shape_ok > b.known_shape_ok;
    }
    if (a.known_unique != b.known_unique) {
        return a.known_unique > b.known_unique;
    }
    if (a.known_align20 != b.known_align20) {
        return a.known_align20 > b.known_align20;
    }
    return a.score > b.score;
}

int desc_delta_value(int key) {
    for (int i = 0; i < prior::kExpectedDescDeltaCount; ++i) {
        if (prior::kExpectedDescDeltaKeys[i] == key) {
            return prior::kExpectedDescDeltaValues[i];
        }
    }
    return 0;
}

}  // namespace

ApiTableLocator::ApiTableLocator(const ModuleInfo& unity,
                                 const LocatorMemory& memory)
    : unity_(unity), memory_(memory) {
    for (std::size_t i = 0; i < unity_.sections.size(); ++i) {
        sorted_section_indices_.push_back(static_cast<std::uint32_t>(i));
    }
    std::sort(sorted_section_indices_.begin(), sorted_section_indices_.end(),
              [this](std::uint32_t a, std::uint32_t b) {
                  return unity_.sections[a].rva < unity_.sections[b].rva;
              });
}

bool ApiTableLocator::read_mem(std::uint64_t rva, std::size_t size,
                               void* out) const {
    if (rva > unity_.size || size > unity_.size - rva) {
        return false;
    }
    return memory_.read_bytes(unity_.base + rva, size, out);
}

std::optional<std::uint64_t> ApiTableLocator::read_qword_rva(
    std::uint64_t rva) const {
    std::uint64_t value = 0;
    if (!read_mem(rva, sizeof(value), &value)) {
        return std::nullopt;
    }
    return value;
}

const PeSection* ApiTableLocator::section_at_rva(std::uint64_t rva) const {
    if (rva >= unity_.size) {
        return nullptr;
    }
    auto it = std::upper_bound(
        sorted_section_indices_.begin(), sorted_section_indices_.end(), rva,
        [this](std::uint64_t value, std::uint32_t index) {
            return value < unity_.sections[index].rva;
        });
    if (it == sorted_section_indices_.begin()) {
        return nullptr;
    }
    --it;
    const PeSection& section = unity_.sections[*it];
    if (rva - section.rva < section.mapped_size()) {
        return &section;
    }
    return nullptr;
}

bool ApiTableLocator::is_exec_rva(std::uint64_t rva) const {
    const PeSection* section = section_at_rva(rva);
    return section != nullptr && section->is_executable();
}

bool ApiTableLocator::is_data_rva(std::uint64_t rva) const {
    const PeSection* section = section_at_rva(rva);
    return section != nullptr && section->is_writable();
}

bool ApiTableLocator::is_exec_va(std::uint64_t va) const {
    if (va < unity_.base || va - unity_.base >= unity_.size) {
        return false;
    }
    return is_exec_rva(va - unity_.base);
}

bool ApiTableLocator::is_data_va(std::uint64_t va) const {
    if (va < unity_.base || va - unity_.base >= unity_.size) {
        return false;
    }
    return is_data_rva(va - unity_.base);
}

ApiTableLocator::WrapperProbe ApiTableLocator::wrapper_probe(
    std::uint64_t wrapper_rva) const {
    WrapperProbe probe;
    std::uint8_t bytes[48] = {};
    if (!read_mem(wrapper_rva, sizeof(bytes), bytes)) {
        return probe;
    }
    // Shape A: 45 33 C0 | 48 8D 0D <disp32> | 33 D2 | E9 <disp32>
    if (bytes[0] == 0x45 && bytes[1] == 0x33 && bytes[2] == 0xC0 &&
        bytes[3] == 0x48 && bytes[4] == 0x8D && bytes[5] == 0x0D &&
        bytes[10] == 0x33 && bytes[11] == 0xD2 && bytes[12] == 0xE9) {
        std::int32_t disp = 0;
        std::memcpy(&disp, bytes + 6, sizeof(disp));
        probe.shape = 'A';
        probe.descriptor_rva =
            static_cast<std::uint64_t>(static_cast<std::int64_t>(wrapper_rva) + 10 +
                                       static_cast<std::int64_t>(disp));
        return probe;
    }
    // Shape B: 48 83 EC 38 | 45 33 C9 | 48 C7 44 24 20 0,0,0,0
    //          | 45 33 C0 | 48 8D 15 <disp32> | 48 8D 0D <disp32> | E8 <disp32>
    if (bytes[0] == 0x48 && bytes[1] == 0x83 && bytes[2] == 0xEC &&
        bytes[3] == 0x38 && bytes[4] == 0x45 && bytes[5] == 0x33 &&
        bytes[6] == 0xC9 && bytes[7] == 0x48 && bytes[8] == 0xC7 &&
        bytes[9] == 0x44 && bytes[10] == 0x24 && bytes[11] == 0x20 &&
        bytes[12] == 0x00 && bytes[13] == 0x00 && bytes[14] == 0x00 &&
        bytes[15] == 0x00 && bytes[16] == 0x45 && bytes[17] == 0x33 &&
        bytes[18] == 0xC0 && bytes[19] == 0x48 && bytes[20] == 0x8D &&
        bytes[21] == 0x15 && bytes[26] == 0x48 && bytes[27] == 0x8D &&
        bytes[28] == 0x0D && bytes[33] == 0xE8) {
        std::int32_t disp = 0;
        std::memcpy(&disp, bytes + 29, sizeof(disp));
        probe.shape = 'B';
        probe.descriptor_rva =
            static_cast<std::uint64_t>(static_cast<std::int64_t>(wrapper_rva) + 33 +
                                       static_cast<std::int64_t>(disp));
        return probe;
    }
    // Shape C: SIMD prologue (66 0F 6F ...)
    if (bytes[0] == 0x66 && bytes[1] == 0x0F && bytes[2] == 0x6F) {
        probe.shape = 'C';
        return probe;
    }
    return probe;
}

ApiTableLocator::DescriptorProbe ApiTableLocator::descriptor_probe(
    char shape, std::uint64_t desc_rva) const {
    DescriptorProbe probe;
    if ((shape != 'A' && shape != 'B') || !is_data_rva(desc_rva)) {
        return probe;
    }
    std::uint64_t q[11] = {};
    for (int i = 0; i < 11; ++i) {
        auto value = read_qword_rva(desc_rva + static_cast<std::uint64_t>(i) * 8);
        if (!value.has_value()) {
            return probe;
        }
        q[i] = *value;
    }
    bool any_code = false;
    bool any_data = false;
    for (std::uint64_t value : q) {
        any_code = any_code || is_exec_va(value);
        any_data = any_data || is_data_va(value);
    }
    probe.ok = true;
    probe.soft = any_code && any_data;
    probe.sentinel = shape == 'A' ? q[1] == prior::kSentinel : q[9] == prior::kSentinel;
    if (shape == 'A') {
        probe.strong = q[1] == prior::kSentinel && is_exec_va(q[5]) &&
                       is_data_va(q[8]) && is_data_va(q[9]);
    } else {
        probe.strong = is_exec_va(q[2]) && is_data_va(q[5]) &&
                       is_data_va(q[6]) && q[9] == prior::kSentinel;
    }
    return probe;
}

ApiTableLocator::DescriptorLinks ApiTableLocator::descriptor_links(
    char shape, std::uint64_t desc_rva) const {
    DescriptorLinks links;
    int prev_index = shape == 'A' ? 8 : 5;
    int next_index = shape == 'A' ? 9 : 6;
    if (shape != 'A' && shape != 'B') {
        return links;
    }
    auto prev = read_qword_rva(desc_rva + static_cast<std::uint64_t>(prev_index) * 8);
    auto next = read_qword_rva(desc_rva + static_cast<std::uint64_t>(next_index) * 8);
    if (prev.has_value() && is_data_va(*prev)) {
        links.prev = *prev - unity_.base;
    }
    if (next.has_value() && is_data_va(*next)) {
        links.next = *next - unity_.base;
    }
    return links;
}

std::vector<std::uint64_t> ApiTableLocator::collect_candidates() const {
    std::vector<std::uint64_t> candidates;
    std::vector<int> required;
    for (int slot : prior::kKnownSlots) {
        required.push_back(slot);
    }
    for (const auto& group : prior::kFamilyGroups) {
        for (int i = 0; i < group.count; ++i) {
            required.push_back(group.indices[static_cast<std::size_t>(i)]);
        }
    }
    std::sort(required.begin(), required.end());
    required.erase(std::unique(required.begin(), required.end()), required.end());

    for (const PeSection& sec : unity_.sections) {
        if (!sec.is_readonly_data()) {
            continue;
        }
        if (sec.vsize < (prior::kMaxKnownSlot + 2) * 8ULL) {
            continue;
        }
        const std::uint64_t buf_size = sec.vsize - (sec.vsize % 8);
        const std::uint64_t n = buf_size / 8;
        if (n <= static_cast<std::uint64_t>(prior::kMaxKnownSlot) + 1) {
            continue;
        }
        std::vector<std::uint64_t> arr(static_cast<std::size_t>(n));
        if (!read_mem(sec.rva, static_cast<std::size_t>(buf_size), arr.data())) {
            continue;
        }
        const std::uint64_t n_cand = n - static_cast<std::uint64_t>(prior::kMaxKnownSlot);

        auto value_exec = [this](std::uint64_t value) {
            return is_exec_va(value);
        };

        for (std::uint64_t idx = 0; idx < n_cand; ++idx) {
            const std::uint64_t v63 = arr[idx + 63];
            const std::uint64_t v65 = arr[idx + 65];
            if (!value_exec(v63) || !value_exec(v65)) {
                continue;
            }
            if (!(v65 > v63) || v65 - v63 > 0x100) {
                continue;
            }
            bool ok = true;
            for (const auto& group : prior::kFamilyGroups) {
                std::uint64_t lo = UINT64_MAX;
                std::uint64_t hi = 0;
                for (int i = 0; i < group.count; ++i) {
                    const int slot = group.indices[static_cast<std::size_t>(i)];
                    const std::uint64_t value = arr[idx + static_cast<std::uint64_t>(slot)];
                    if (!value_exec(value)) {
                        ok = false;
                        break;
                    }
                    lo = (std::min)(lo, value);
                    hi = (std::max)(hi, value);
                }
                if (!ok) {
                    break;
                }
                if (hi - lo > static_cast<std::uint64_t>(group.span)) {
                    ok = false;
                    break;
                }
            }
            if (!ok) {
                continue;
            }
            for (int slot : prior::kKnownSlots) {
                if (!value_exec(arr[idx + static_cast<std::uint64_t>(slot)])) {
                    ok = false;
                    break;
                }
            }
            if (!ok) {
                continue;
            }
            candidates.push_back(sec.rva + idx * 8);
        }
    }
    return candidates;
}

ScoredCandidate ApiTableLocator::score_candidate(std::uint64_t table_rva) const {
    ScoredCandidate result;
    result.table_rva = table_rva;

    std::vector<std::optional<std::uint64_t>> slots(prior::kFullSlotCount);
    for (int i = 0; i < prior::kFullSlotCount; ++i) {
        auto value = read_qword_rva(table_rva + static_cast<std::uint64_t>(i) * 8);
        if (value.has_value()) {
            slots[static_cast<std::size_t>(i)] = *value;
        }
    }

    std::map<int, char> shapes;
    std::map<int, std::uint64_t> descs;
    int shape_count = 0;
    int desc_soft_count = 0;
    int desc_strong_count = 0;
    for (int i = 0; i < prior::kFullSlotCount; ++i) {
        const auto& value = slots[static_cast<std::size_t>(i)];
        if (!value.has_value()) {
            continue;
        }
        const std::uint64_t va = *value;
        if (!is_exec_va(va)) {
            continue;
        }
        const std::uint64_t wrapper_rva = va - unity_.base;
        WrapperProbe wrapper = wrapper_probe(wrapper_rva);
        if (wrapper.shape == 0) {
            continue;
        }
        ++shape_count;
        shapes[i] = wrapper.shape;
        if (wrapper.descriptor_rva.has_value()) {
            DescriptorProbe desc = descriptor_probe(wrapper.shape, *wrapper.descriptor_rva);
            if (desc.ok) {
                descs[i] = *wrapper.descriptor_rva;
                if (desc.soft) {
                    ++desc_soft_count;
                }
                if (desc.strong) {
                    ++desc_strong_count;
                }
            }
        }
    }

    int link_ok = 0;
    int link_checked = 0;
    for (const auto& [i, shape] : shapes) {
        if (shape != 'A' && shape != 'B') {
            continue;
        }
        auto desc_it = descs.find(i);
        if (desc_it == descs.end()) {
            continue;
        }
        DescriptorLinks links = descriptor_links(shape, desc_it->second);
        int prev_target = shape == 'A' ? i - 1 : i - 2;
        int next_target = shape == 'A' ? i + 1 : i + 2;
        if (prev_target >= 0) {
            auto target = descs.find(prev_target);
            if (target != descs.end()) {
                ++link_checked;
                if (links.prev.has_value() && *links.prev == target->second) {
                    ++link_ok;
                }
            }
        }
        if (next_target < prior::kFullSlotCount) {
            auto target = descs.find(next_target);
            if (target != descs.end()) {
                ++link_checked;
                if (links.next.has_value() && *links.next == target->second) {
                    ++link_ok;
                }
            }
        }
    }

    std::map<int, std::uint64_t> known_descs;
    int known_matched = 0;
    int known_shape_ok = 0;
    int known_unique_count = 0;
    int known_align20 = 0;
    int profile_matches = 0;
    std::set<std::uint64_t> known_unique_values;

    for (int slot : prior::kKnownSlots) {
        const auto& value = slots[static_cast<std::size_t>(slot)];
        if (!value.has_value()) {
            continue;
        }
        const std::uint64_t va = *value;
        if (!is_exec_va(va)) {
            continue;
        }
        const std::uint64_t wrapper_rva = va - unity_.base;
        known_unique_values.insert(va);
        if ((wrapper_rva & 0x1F) == 0) {
            ++known_align20;
        }
        WrapperProbe wrapper = wrapper_probe(wrapper_rva);
        if (wrapper.shape != 0) {
            ++known_shape_ok;
        }
        char expected_shape = 0;
        for (const auto& known : prior::kKnownSlotsDetailed) {
            if (known.index == slot) {
                expected_shape = known.shape;
                break;
            }
        }
        if (wrapper.shape != 0 && wrapper.shape == expected_shape) {
            ++profile_matches;
        }
        bool desc_valid = false;
        if (wrapper.descriptor_rva.has_value()) {
            DescriptorProbe desc = descriptor_probe(wrapper.shape, *wrapper.descriptor_rva);
            if (desc.ok) {
                known_descs[slot] = *wrapper.descriptor_rva;
                desc_valid = desc.soft;
            }
        }
        if (wrapper.shape != 0 && (wrapper.shape == 'C' || desc_valid)) {
            ++known_matched;
        }
    }
    known_unique_count = static_cast<int>(known_unique_values.size());

    int desc_profile_matches = 0;
    if (!known_descs.empty()) {
        auto slot22 = known_descs.find(22);
        if (slot22 != known_descs.end()) {
            for (int i = 0; i < prior::kExpectedDescDeltaCount; ++i) {
                const int slot = prior::kExpectedDescDeltaKeys[i];
                const int want = prior::kExpectedDescDeltaValues[i];
                auto found = known_descs.find(slot);
                if (found != known_descs.end()) {
                    const std::int64_t actual =
                        static_cast<std::int64_t>(found->second) -
                        static_cast<std::int64_t>(slot22->second);
                    if (actual == want) {
                        ++desc_profile_matches;
                    }
                }
            }
        } else {
            const auto ref = known_descs.begin();
            int expected_ref = desc_delta_value(ref->first);
            for (int i = 0; i < prior::kExpectedDescDeltaCount; ++i) {
                const int slot = prior::kExpectedDescDeltaKeys[i];
                const int want = prior::kExpectedDescDeltaValues[i] - expected_ref;
                auto found = known_descs.find(slot);
                if (found != known_descs.end()) {
                    const std::int64_t actual =
                        static_cast<std::int64_t>(found->second) -
                        static_cast<std::int64_t>(ref->second);
                    if (actual == want) {
                        ++desc_profile_matches;
                    }
                }
            }
        }
    }

    int twin_checks = 0;
    auto shape_of = [&shapes](int slot) -> char {
        auto it = shapes.find(slot);
        return it == shapes.end() ? 0 : it->second;
    };
    if (shape_of(63) == 'A' && shape_of(65) == 'A' && slots[63].has_value() &&
        slots[65].has_value()) {
        auto d63 = descs.find(63);
        auto d65 = descs.find(65);
        if (d63 != descs.end() && d65 != descs.end() &&
            *slots[65] - *slots[63] == 0x20 &&
            d65->second - d63->second == 0x58) {
            ++twin_checks;
        }
    }
    if (shape_of(10) == 'B' && shape_of(12) == 'B' && slots[10].has_value() &&
        slots[12].has_value()) {
        auto d10 = descs.find(10);
        auto d12 = descs.find(12);
        if (d10 != descs.end() && d12 != descs.end() &&
            *slots[12] - *slots[10] == 0x40 &&
            d12->second - d10->second == 0x58) {
            ++twin_checks;
        }
    }
    auto d10 = descs.find(10);
    auto d63 = descs.find(63);
    if (d10 != descs.end() && d63 != descs.end() &&
        d63->second - d10->second == 0x930) {
        ++twin_checks;
    }

    int group_ok = 0;
    for (const auto& group : prior::kFamilyGroups) {
        bool has_all = true;
        std::uint64_t lo = UINT64_MAX;
        std::uint64_t hi = 0;
        for (int i = 0; i < group.count; ++i) {
            const int slot = group.indices[static_cast<std::size_t>(i)];
            const auto& value = slots[static_cast<std::size_t>(slot)];
            if (!value.has_value()) {
                has_all = false;
                break;
            }
            lo = (std::min)(lo, *value);
            hi = (std::max)(hi, *value);
        }
        if (has_all && hi - lo <= static_cast<std::uint64_t>(group.span)) {
            ++group_ok;
        }
    }

    std::vector<std::string>& failed = result.failed_constraints;
    if (profile_matches < prior::kKnownSlotCount) {
        failed.push_back("known_slot_shape_profile=" + std::to_string(profile_matches) +
                         "/" + std::to_string(prior::kKnownSlotCount));
    }
    if (desc_profile_matches < prior::kExpectedDescDeltaCount) {
        failed.push_back("known_slot_desc_spacing_profile=" +
                         std::to_string(desc_profile_matches) + "/" +
                         std::to_string(prior::kExpectedDescDeltaCount));
    }
    if (twin_checks < 3) {
        failed.push_back("twin_pair_relations=" + std::to_string(twin_checks) + "/3");
    }
    if (group_ok < prior::kFamilyGroupCount) {
        failed.push_back("family_group_spacing=" + std::to_string(group_ok) + "/" +
                         std::to_string(prior::kFamilyGroupCount));
    }
    if (known_unique_count < prior::kKnownSlotCount) {
        failed.push_back("known_slot_unique=" + std::to_string(known_unique_count) +
                         "/" + std::to_string(prior::kKnownSlotCount));
    }
    if (known_align20 < prior::kKnownSlotCount) {
        failed.push_back("known_slot_align20=" + std::to_string(known_align20) + "/" +
                         std::to_string(prior::kKnownSlotCount));
    }
    const int wrapper_coverage_min =
        static_cast<int>(static_cast<double>(prior::kFullSlotCount) * 0.9);
    if (shape_count < wrapper_coverage_min) {
        failed.push_back("wrapper_coverage=" + std::to_string(shape_count) + "/" +
                         std::to_string(prior::kFullSlotCount));
    }
    const int descriptor_coverage_min =
        static_cast<int>(static_cast<double>(prior::kFullSlotCount - 3) * 0.9);
    if (desc_soft_count < descriptor_coverage_min) {
        failed.push_back("descriptor_coverage=" + std::to_string(desc_soft_count) + "/" +
                         std::to_string(prior::kFullSlotCount));
    }

    const double link_rate =
        link_checked == 0 ? 0.0 : static_cast<double>(link_ok) / static_cast<double>(link_checked);
    const double score =
        prior::kWShapeProfile *
            static_cast<double>(profile_matches) / static_cast<double>(prior::kKnownSlotCount) +
        prior::kWDescProfile *
            static_cast<double>(desc_profile_matches) /
            static_cast<double>(prior::kExpectedDescDeltaCount) +
        prior::kWTwin * static_cast<double>(twin_checks) / 3.0 +
        prior::kWWrapperCoverage * static_cast<double>(shape_count) /
            static_cast<double>(prior::kFullSlotCount) +
        prior::kWDescCoverage * static_cast<double>(desc_soft_count) /
            static_cast<double>(prior::kFullSlotCount) +
        prior::kWLinkCoverage * link_rate;

    result.score = py_round2(score);
    result.known_slots_matched = known_matched;
    result.known_shape_profile_matches = profile_matches;
    result.known_desc_profile_matches = desc_profile_matches;
    result.known_shape_ok = known_shape_ok;
    result.known_unique = known_unique_count;
    result.known_align20 = known_align20;
    result.wrapper_matches = shape_count;
    result.descriptor_matches = desc_soft_count;
    result.descriptor_strong = desc_strong_count;
    result.link_ok = link_ok;
    result.link_checked = link_checked;
    result.twin_relations = twin_checks;
    result.family_group_ok = group_ok;
    return result;
}

LocatorResult ApiTableLocator::locate(int top_n) const {
    LocatorResult result;
    std::vector<std::uint64_t> candidates = collect_candidates();
    result.candidates_scanned = static_cast<int>(candidates.size());
    if (candidates.empty()) {
        result.failed_constraints = {"no candidates"};
        return result;
    }

    std::vector<ScoredCandidate> scored;
    scored.reserve(candidates.size());
    for (std::uint64_t rva : candidates) {
        scored.push_back(score_candidate(rva));
    }
    result.candidates_scored = static_cast<int>(scored.size());
    std::sort(scored.begin(), scored.end(), scored_greater);

    const int keep = (std::min)(top_n, static_cast<int>(scored.size()));
    result.top_candidates.assign(scored.begin(), scored.begin() + keep);

    if (scored.empty()) {
        result.failed_constraints = {"no candidates"};
        return result;
    }
    const ScoredCandidate& best = scored.front();
    result.best = best;
    result.score = best.score;
    result.known_slots_matched = best.known_slots_matched;
    result.wrapper_matches = best.wrapper_matches;
    result.descriptor_matches = best.descriptor_matches;
    result.failed_constraints = best.failed_constraints;
    if (scored.size() > 1) {
        result.runner_up = scored[1];
    }

    std::string confidence = "low";
    if (best.known_shape_profile_matches == prior::kKnownSlotCount &&
        best.twin_relations == 3 && result.runner_up.has_value() &&
        best.score >= result.runner_up->score + 1.0) {
        confidence = "high";
    } else if (best.known_shape_profile_matches >= 24 &&
               (!result.runner_up.has_value() || best.score > result.runner_up->score)) {
        confidence = "medium";
    }
    result.confidence = confidence;

    const PeSection* section = section_at_rva(best.table_rva);
    result.success = true;
    result.best_table_rva = best.table_rva;
    result.best_table_va = unity_.base + best.table_rva;
    result.best_section = section == nullptr ? "" : section->name;
    return result;
}

}  // namespace hsr_probe
