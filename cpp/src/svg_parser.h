#pragma once
#include "wsd_format.h"
#include <vector>
#include <string>

namespace svg {

class Parser {
public:
    std::vector<wsd::Object> parse(const std::string& filepath);
};

} // namespace svg
