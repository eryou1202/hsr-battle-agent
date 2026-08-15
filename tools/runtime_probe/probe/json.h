#pragma once

// json.h - dependency-free JSON value + pretty printer for probe output.
// Object members preserve insertion order.

#include <cstdint>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace hsr_probe {

class Json {
public:
    enum class Type {
        Null,
        Bool,
        Int,
        Double,
        String,
        Array,
        Object,
    };

    Json() : type_(Type::Null) {}

    static Json null() { return Json(); }
    static Json boolean(bool value) { return Json(value); }
    static Json integer(std::int64_t value) { return Json(value); }
    static Json floating(double value) { return Json(value); }
    static Json string(const std::string& value) { return Json(value); }
    static Json array() { return Json(std::vector<Json>{}); }
    static Json object() { return Json(std::vector<std::pair<std::string, Json>>{}); }

    static Json array_of(std::vector<Json> items) { return Json(std::move(items)); }
    static Json object_of(std::vector<std::pair<std::string, Json>> members) {
        return Json(std::move(members));
    }

    Type type() const { return type_; }
    bool is_null() const { return type_ == Type::Null; }

    void push(Json item) { array_.push_back(std::move(item)); }
    void set(std::string key, Json value);

    std::string dump(int indent = 2) const;

private:
    explicit Json(bool value) : type_(Type::Bool), bool_(value) {}
    explicit Json(std::int64_t value) : type_(Type::Int), int_(value) {}
    explicit Json(double value) : type_(Type::Double), double_(value) {}
    explicit Json(std::string value) : type_(Type::String), string_(std::move(value)) {}
    explicit Json(std::vector<Json> items)
        : type_(Type::Array), array_(std::move(items)) {}
    explicit Json(std::vector<std::pair<std::string, Json>> members)
        : type_(Type::Object), object_(std::move(members)) {}

    void dump_to(std::string& out, int indent, int depth) const;

    Type type_;
    bool bool_ = false;
    std::int64_t int_ = 0;
    double double_ = 0.0;
    std::string string_;
    std::vector<Json> array_;
    std::vector<std::pair<std::string, Json>> object_;
};

}  // namespace hsr_probe
