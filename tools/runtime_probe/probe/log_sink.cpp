#include "log_sink.h"

#include <windows.h>

#include <chrono>
#include <cstdio>

namespace hsr_probe {

namespace {

std::string local_timestamp() {
    SYSTEMTIME st{};
    GetLocalTime(&st);
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%02d:%02d:%02d.%03d",
                  st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
    return buf;
}

}  // namespace

LogSink::~LogSink() {
    if (file_.is_open()) {
        file_.flush();
        file_.close();
    }
}

bool LogSink::open_file(const std::wstring& path) {
    if (file_.is_open()) {
        file_.close();
    }
    file_.open(path.c_str(), std::ios::out | std::ios::trunc);
    if (!file_.is_open()) {
        return false;
    }
    file_path_ = path;
    return true;
}

void LogSink::log(const std::string& line) {
    const std::string stamped = "[" + local_timestamp() + "] " + line + "\n";
    if (file_.is_open()) {
        file_ << stamped;
        file_.flush();
    }
    if (console_enabled_) {
        HANDLE console = GetStdHandle(STD_OUTPUT_HANDLE);
        if (console != nullptr && console != INVALID_HANDLE_VALUE) {
            DWORD written = 0;
            WriteFile(console, stamped.data(), static_cast<DWORD>(stamped.size()),
                      &written, nullptr);
        }
    }
}

}  // namespace hsr_probe
