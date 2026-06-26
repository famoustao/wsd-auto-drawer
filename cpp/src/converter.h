#pragma once
#include <string>

namespace converter {

void svgToWsd(const std::string& input, const std::string& output);
void wsdToSvg(const std::string& input, const std::string& output);

} // namespace converter
