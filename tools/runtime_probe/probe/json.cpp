#include "json.h"

#include <cmath>
#include <cstdio>

namespace hsr_probe {

namespace {

std::string escape_string(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (unsigned char c : value) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += static_cast<char>(c);
                }
        }
    }
    return out;
}

std::string format_double(double value) {
    if (std::isfinite(value) && value == static_cast<double>(static_cast<std::int64_t>(value))) {
        return std::to_string(static_cast<std::int64_t>(value));
    }
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.15g", value);
    return buf;
}

void indent_to(std::string& out, int indent, int depth) {
    out.append(static_cast<std::size_t>(indent) * static_cast<std::size_t>(depth), ' ');
}

}  // namespace

void Json::set(std::string key, Json value) {
    if (type_ != Type::Object) {
        return;
    }
    for (auto& member : object_) {
        if (member.first == key) {
            member.second = std::move(value);
            return;
        }
    }
    object_.emplace_back(std::move(key), std::move(value));
}

void Json::dump_to(std::string& out, int indent, int depth) const {
    switch (type_) {
        case Type::Null:
            out += "null";
            break;
        case Type::Bool:
            out += bool_ ? "true" : "false";
            break;
        case Type::Int:
            out += std::to_string(int_);
            break;
        case Type::Double:
            out += format_double(double_);
            break;
        case Type::String:
            out += '"';
            out += escape_string(string_);
            out += '"';
            break;
        case Type::Array: {
            if (array_.empty()) {
                out += "[]";
                break;
            }
            out += "[\n";
            for (std::size_t i = 0; i < array_.size(); ++i) {
                indent_to(out, indent, depth + 1);
                array_[i].dump_to(out, indent, depth + 1);
                if (i + 1 != array_.size()) {
                    out += ',';
                }
                out += '\n';
            }
            indent_to(out, indent, depth);
            out += ']';
            break;
        }
        case Type::Object: {
            if (object_.empty()) {
                out += "{}";
                break;
            }
            out += "{\n";
            for (std::size_t i = 0; i < object_.size(); ++i) {
                indent_to(out, indent, depth + 1);
                out += '"';
                out += escape_string(object_[i].first);
                out += "\": ";
                object_[i].second.dump_to(out, indent, depth + 1);
                if (i + 1 != object_.size()) {
                    out += ',';
                }
                out += '\n';
            }
            indent_to(out, indent, depth);
            out += '}';
            break;
        }
    }
}

std::string Json::dump(int indent) const {
    std::string out;
    dump_to(out, indent, 0);
    out += '\n';
    return out;
}

}  // namespace hsr_probe
