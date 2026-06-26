#pragma once
#include "wsd_format.h"
#include <vector>
#include <string>

namespace wsd {

// 模板中的矢量对象信息
struct TemplateObject {
    size_t obj_start;       // 对象在文件中的起始偏移
    size_t coord_offset;    // 坐标数据起始偏移
    size_t coord_size;      // 坐标数据大小 (point_count * 8)
    uint16_t point_count;   // 点数
};

class Writer {
public:
    /// 旧模式（从零生成，无法被 EduEditor 打开）
    void write(const std::string& filepath, const std::vector<Object>& objects);

    /// 模板替换模式 - 基于可打开的 WSD 模板文件，仅替换坐标数据
    /// template_path: 模板文件路径（必须能被 EduEditor 打开）
    /// objects: 新的矢量对象（坐标将被缩放并重采样到模板点数）
    /// output_path: 输出文件路径
    /// 成功返回 true
    bool writeWithTemplate(
        const std::string& template_path,
        const std::vector<Object>& objects,
        const std::string& output_path
    );

private:
    /// 解析模板文件中的矢量对象位置
    bool parseTemplate(const std::string& template_path);

    std::vector<TemplateObject> templateObjects;
    std::vector<uint8_t> templateData;
};

} // namespace wsd
