#pragma once
#include "wsd_format.h"
#include <vector>
#include <string>

namespace wsd {

class Parser {
public:
    std::vector<Object> parse(const std::string& filepath);
};

} // namespace wsd
