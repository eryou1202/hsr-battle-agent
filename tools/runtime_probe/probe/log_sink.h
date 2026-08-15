#pragma once

#include <fstream>
#include <string>

namespace hsr_probe {

// Human-readable log: console (when attached) + UTF-8 text file.
// Every line is flushed so a hard failure still leaves a readable trace.
class LogSink {
public:
    LogSink() = default;
    LogSink(const LogSink&) = delete;
    LogSink& operator=(const LogSink&) = delete;
    ~LogSink();

    bool open_file(const std::wstring& path);
    void enable_console(bool enable) { console_enabled_ = enable; }
    bool console_enabled() const { return console_enabled_; }
    const std::wstring& file_path() const { return file_path_; }

    void log(const std::string& line);

private:
    std::ofstream file_;
    std::wstring file_path_;
    bool console_enabled_ = false;
};

}  // namespace hsr_probe
