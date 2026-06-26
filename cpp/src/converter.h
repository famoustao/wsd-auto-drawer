#pragma once
#include <string>

namespace converter {

/// SVG 转 WSD（模板替换模式）
/// 需要一个模板文件（能被 EduEditor 打开的 WSD 文件）
void svgToWsd(const std::string& templatePath, const std::string& svgInput, const std::string& wsdOutput);

/// WSD 转 SVG
void wsdToSvg(const std::string& input, const std::string& output);

} // namespace converter
