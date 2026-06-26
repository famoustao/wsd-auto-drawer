#pragma once
#include "wsd_format.h"
#include <vector>
#include <string>
#include <cstdint>
#include <array>
#include <utility>

namespace wsd {

// ============================================================
//  已验证的逆向工程常量 - WSD 记录表格式
// ============================================================

// 记录表标记: 0f 33 ff 00 07（5字节），位于文件尾部
constexpr uint8_t RECORD_MARKER[5] = {0x0f, 0x33, 0xff, 0x00, 0x07};
// 字段标记: 04 ff ff（3字节）
constexpr uint8_t FIELD_MARKER[3] = {0x04, 0xff, 0xff};

// 记录表结构偏移量（相对于记录标记起始位置）
constexpr size_t COLOR_OFFSET      = 8;   // 颜色索引: marker+8，4字节
constexpr size_t PADDING_OFFSET    = 12;  // 填充: marker+12，4字节 (00 00 00 00)
constexpr size_t LINEWIDTH_OFFSET  = 16;  // 线宽: marker+16，uint32 LE (毫米 * 400)
constexpr size_t COORD_DATA_START  = 32;  // 坐标数据起始: marker+32

// 颜色索引映射表（已验证）
struct ColorIndex {
    const char* name;
    std::array<uint8_t, 4> value;
};

// 标准颜色索引表
extern const ColorIndex COLOR_INDEX_TABLE[];
extern const size_t COLOR_INDEX_TABLE_SIZE;

// 模板中的矢量对象信息
struct TemplateObject {
    size_t obj_start;       // 对象在文件中的起始偏移
    size_t coord_offset;    // 坐标数据起始偏移
    size_t coord_size;      // 坐标数据大小 (point_count * 8)
    uint16_t point_count;   // 点数
};

// ============================================================
//  WSD 记录信息（文件尾部记录表中的一条记录）
// ============================================================

// 坐标区域信息
struct CoordRegion {
    size_t offset;          // 数据在文件中的偏移
    uint16_t count;         // 坐标点数
    bool isUint32;          // true=uint32格式(可修改), false=float格式(不可修改)
    std::string fmt;        // 格式标记: "xy_pairs"(默认,每点8字节X/Y对), "uint32_type01"(每4字节一个uint32值)
};

// 单条记录
// recordType 说明:
//   0x00 = 未知类型（启发式方法解析）
//   0x01 = 旋转矩阵记录（77字节，坐标在marker+56,60,64,68,72,76，格式为 uint32_type01）
//   0x04 = 直接坐标记录（53字节，坐标在marker+36为x1,y1,x2,y2，uint32各4字节）
struct Record {
    size_t markerOffset;    // 记录标记在文件中的绝对偏移
    int canvasIndex;        // 所属画布索引
    uint8_t recordType;     // 记录类型: 0x01=旋转矩阵, 0x04=直接坐标, 0x00=未知
    std::array<uint8_t, 4> color;       // 4字节颜色索引
    uint32_t lineWidthRaw;                // uint32 LE 线宽原始值（毫米 * 400）
    std::vector<CoordRegion> coordRegions; // 坐标区域列表
    size_t recordSize;     // 记录总大小
};

// 修改指令
struct Modification {
    // 颜色修改: recordIndex >= 0 时有效
    int recordIndex = -1;
    bool changeColor = false;
    std::array<uint8_t, 4> newColor{};

    // 线宽修改: recordIndex >= 0 时有效
    bool changeLineWidth = false;
    float lineWidthMM = 0.0f;

    // 坐标修改: recordIndex >= 0 且 coordIndex >= 0 时有效
    int coordIndex = -1;
    bool changeCoords = false;
    std::vector<std::pair<uint32_t, uint32_t>> newCoords;
};

// ============================================================
//  Writer - WSD 文件读写器
// ============================================================

class Writer {
public:
    // ============================================================
    //  记录类型常量（基于 byte 31 识别）
    // ============================================================
    static constexpr size_t TYPE01_SIZE = 77;       // 旋转矩阵记录大小 (byte31=0x01)
    static constexpr size_t TYPE04_SIZE = 53;       // 直接坐标记录大小 (byte31=0x04)
    static constexpr size_t COMMON_TAIL_SIZE = 31;  // 公共尾部大小（用于从记录末尾反推尾部数据）

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

    // ============================================================
    //  记录表修改接口（基于逆向工程验证的记录表结构）
    // ============================================================

    /// 加载 WSD 文件用于记录修改
    /// wsd_path: WSD 文件路径
    /// 成功返回 true
    bool loadRecordFile(const std::string& wsd_path);

    /// 解析文件尾部的记录表，查找所有 0f 33 ff 00 07 标记
    /// 返回找到的记录列表。支持多画布文件。
    /// 需要先通过 loadRecordFile() 加载文件
    bool parseRecords();

    /// 修改指定记录的颜色
    /// recordIndex: 记录索引（0-based）
    /// newColor: 4字节颜色索引
    /// 成功返回 true
    bool modifyRecordColor(size_t recordIndex, const std::array<uint8_t, 4>& newColor);

    /// 通过颜色名称修改记录颜色
    /// recordIndex: 记录索引
    /// colorName: 颜色名称 ("red", "green", "blue", "black", "white")
    /// 成功返回 true
    bool modifyRecordColorByName(size_t recordIndex, const std::string& colorName);

    /// 修改指定记录的线宽
    /// recordIndex: 记录索引
    /// lineWidthMM: 线宽（毫米），将转换为 uint32 LE (毫米 * 400)
    /// 成功返回 true
    bool modifyRecordLineWidth(size_t recordIndex, float lineWidthMM);

    /// 修改指定记录中 uint32 格式的坐标数据
    /// 注意：仅支持 uint32 格式，float 格式（画布参数）不可修改
    /// 点数必须与原始相同以保证文件大小不变
    /// recordIndex: 记录索引
    /// coordIndex: 坐标区域索引
    /// newCoords: 新坐标列表 (X, Y)，每个坐标为 uint32
    /// 成功返回 true
    bool modifyRecordCoordinates(
        size_t recordIndex,
        size_t coordIndex,
        const std::vector<std::pair<uint32_t, uint32_t>>& newCoords
    );

    /// WSD 文件修改主函数
    /// 基于 WSD 模板文件 + 修改指令列表，输出修改后的文件
    /// templatePath: 模板 WSD 文件路径
    /// outputPath: 输出文件路径
    /// modifications: 修改指令列表
    /// 成功返回 true（文件大小保持不变）
    bool modifyWSD(
        const std::string& templatePath,
        const std::string& outputPath,
        const std::vector<Modification>& modifications
    );

    /// 获取解析后的记录列表（只读）
    const std::vector<Record>& getRecords() const { return records; }

    /// 获取指定记录的详细信息
    /// 返回 nullptr 如果索引无效
    const Record* getRecordInfo(size_t recordIndex) const;

    /// 获取指定记录的旋转角度（仅 Type 0x01 有效）
    /// 从旋转矩阵的 uint32 值计算角度（弧度转角度）
    /// recordIndex: 记录索引
    /// 返回旋转角度（度），如果无效返回 0.0f
    float getRotationAngle(int recordIndex) const;

    /// 获取指定记录的端点坐标列表
    /// Type 0x04: 返回 (x1,y1), (x2,y2)
    /// Type 0x01: 返回旋转矩阵的坐标值对
    /// recordIndex: 记录索引
    std::vector<std::pair<uint32_t,uint32_t>> getEndpointCoords(int recordIndex) const;

    /// 修改指定记录的端点坐标
    /// Type 0x04: 修改 marker+36 处的 x1,y1,x2,y2 (各uint32)
    /// Type 0x01: 修改 marker+56,60,64,68,72,76 处的旋转矩阵坐标
    /// recordIndex: 记录索引
    /// newCoords: 新端点坐标列表
    /// 成功返回 true
    bool modifyRecordEndpoints(int recordIndex, const std::vector<std::pair<uint32_t,uint32_t>>& newCoords);

    /// 通过颜色名查找颜色索引字节
    /// 返回 true 找到，result 中填入4字节颜色索引
    static bool findColorByName(const std::string& colorName, std::array<uint8_t, 4>& result);

private:
    /// 解析模板文件中的矢量对象位置
    bool parseTemplate(const std::string& template_path);

    /// 分配画布索引：基于记录间距离判断画布边界
    void assignCanvasIndices();

    /// 更新文件尾部校验和 (filesize_le32 + ff ff ff ff)
    void updateTailChecksum();

    std::vector<TemplateObject> templateObjects;
    std::vector<uint8_t> templateData;

    // 记录表修改相关数据
    std::vector<Record> records;       // 解析后的记录列表
    std::vector<uint8_t> recordData;  // 文件数据（用于修改）
    size_t originalSize = 0;           // 原始文件大小（校验用）
};

} // namespace wsd
