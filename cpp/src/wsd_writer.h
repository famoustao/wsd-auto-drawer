#pragma once
#include "wsd_format.h"
#include <vector>
#include <string>

namespace wsd {

class Writer {
public:
    void write(const std::string& filepath, const std::vector<Object>& objects);
};

} // namespace wsd
