// locator_prior.h
//
// GENERATED FILE - DO NOT EDIT BY HAND.
// Regenerate with:
//   python tools/runtime_probe/scripts/gen_locator_prior.py
//
// The values below are structural priors (slot indices, wrapper shape
// profiles, relative descriptor-spacing fingerprints and scoring weights)
// imported from tools/reverse/scripts/find_il2cpp_api_table.py.
// They are NOT version branches and contain NO api-table offsets.

#pragma once

#include <array>
#include <cstdint>

namespace hsr_probe {
namespace locator_prior {

inline constexpr int kKnownSlots[] = {
    22, 31, 33, 35, 37, 39, 40, 43, 45, 49, 53, 63, 65, 72, 73, 75, 76, 116, 117, 123, 124, 161, 162, 163, 168, 169, 170,
};
inline constexpr int kKnownSlotCount = 27;

struct KnownSlot {
    int index;
    const char* name;
    char shape;
};
inline constexpr KnownSlot kKnownSlotsDetailed[] = {
    {22, "assembly_get_image", 'B'},
    {31, "class_get_fields", 'A'},
    {33, "class_get_interfaces", 'A'},
    {35, "class_get_methods", 'A'},
    {37, "class_get_name", 'A'},
    {39, "class_get_namespace", 'A'},
    {40, "class_get_parent", 'B'},
    {43, "class_is_valuetype", 'A'},
    {45, "class_get_flags", 'A'},
    {49, "class_from_type", 'A'},
    {53, "class_is_enum", 'A'},
    {63, "domain_get", 'A'},
    {65, "domain_get_assemblies", 'A'},
    {72, "field_get_flags", 'B'},
    {73, "field_get_name", 'A'},
    {75, "field_get_offset", 'A'},
    {76, "field_get_type", 'B'},
    {116, "method_get_return_type", 'A'},
    {117, "method_get_name", 'B'},
    {123, "method_get_param_count", 'B'},
    {124, "method_get_param", 'A'},
    {161, "type_get_name", 'B'},
    {162, "type_is_byref", 'A'},
    {163, "type_get_attrs", 'B'},
    {168, "image_get_name", 'A'},
    {169, "image_get_class_count", 'B'},
    {170, "image_get_class", 'C'},
};

inline constexpr int kExpectedDescDeltaKeys[] = {
    22, 31, 33, 35, 37, 39, 40, 43, 45, 49, 53, 63, 65, 72, 73, 75, 76, 116, 117, 123, 124, 161, 162, 163, 168, 169,
};
inline constexpr int kExpectedDescDeltaValues[] = {
    0x0, 0x1A0, 0x1F8, 0x250, 0x2A8, 0x300, 0x318, 0x3B0, 0x408, 0x4B8, 0x568, 0x720, 0x778, 0x898, 0x8D8, 0x930, 0x948, 0x10E8, 0x1100, 0x1208, 0x1248, 0x18A8, 0x18E8, 0x1900, 0x19F0, 0x1A08,
};
inline constexpr int kExpectedDescDeltaCount = 26;

struct FamilyGroup {
    const char* name;
    int span;
    int count;
    std::array<int, 10> indices;
};
inline constexpr FamilyGroup kFamilyGroups[] = {
    {"domain_pair", 0x100, 2, {63, 65, 0, 0, 0, 0, 0, 0, 0, 0}},
    {"twin_pair", 0x100, 2, {10, 12, 0, 0, 0, 0, 0, 0, 0, 0}},
    {"image", 0x800, 3, {168, 169, 170, 0, 0, 0, 0, 0, 0, 0}},
    {"method", 0x1000, 4, {116, 117, 123, 124, 0, 0, 0, 0, 0, 0}},
    {"type", 0x1000, 3, {161, 162, 163, 0, 0, 0, 0, 0, 0, 0}},
    {"class", 0x4000, 10, {31, 33, 35, 37, 39, 40, 43, 45, 49, 53}},
};
inline constexpr int kFamilyGroupCount = 6;

inline constexpr int kMaxKnownSlot = 170;
inline constexpr int kFullSlotCount = 240;
inline constexpr std::uint64_t kSentinel = 0xFFFFFFFFFFFFFFFFULL;

inline constexpr double kWShapeProfile = 45.0;
inline constexpr double kWDescProfile = 20.0;
inline constexpr double kWTwin = 15.0;
inline constexpr double kWWrapperCoverage = 10.0;
inline constexpr double kWDescCoverage = 5.0;
inline constexpr double kWLinkCoverage = 5.0;

}  // namespace locator_prior
}  // namespace hsr_probe
