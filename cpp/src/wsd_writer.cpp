#include "wsd_writer.h"
#include <fstream>
#include <cstring>
#include <cmath>
#include <algorithm>

namespace wsd {

void Writer::write(const std::string& filepath, const std::vector<Object>& objects) {
    // 旧模式：从零生成 WSD 文件
    // 注意：此模式生成的文件无法被 EduEditor 打开（需要密码）
    // 请使用 writeWithTemplate() 替代
    std::ofstream file(filepath, std::ios::binary);
    if (!file) return;

    // 文件头
    file.put(0x00);
    file.write(FileHeader::MAGIC, 8);
    file.put(FileHeader::VERSION);

    // 字体表头 (50字节)
    static const uint8_t FONT_TABLE_HEADER[] = {
        0x00, 0x02, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0xff, 0xfe, 0xff, 0x00, 0xff, 0xfe, 0xff, 0x00, 0xff, 0xfe, 0xff, 0x00, 0xff, 0xfe, 0xff, 0x00,
        0xff, 0xfe, 0xff, 0x00, 0xff, 0xfe, 0xff, 0x00, 0xff, 0xfe, 0xff, 0x00, 0xff, 0xfe, 0xff, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    file.write(reinterpret_cast<const char*>(FONT_TABLE_HEADER), 50);

    // 写入对象
    for (const auto& obj : objects) {
        file.write(reinterpret_cast<const char*>(OBJECT_HEADER), 41);
        uint16_t count = static_cast<uint16_t>(obj.points.size());
        file.put(static_cast<char>((count >> 8) & 0xFF));
        file.put(static_cast<char>(count & 0xFF));
        file.put(0x00);
        for (const auto& pt : obj.points) {
            file.write(reinterpret_cast<const char*>(&pt.x), 2);
            file.put(0x00); file.put(0x00);
            file.write(reinterpret_cast<const char*>(&pt.y), 2);
            file.put(0x00); file.put(0x00);
        }
        file.put(static_cast<char>(obj.color.r));
        file.put(static_cast<char>(obj.color.g));
        file.put(static_cast<char>(obj.color.b));
        file.put(static_cast<char>(obj.color.a));
        file.put(0x00); file.put(0x00);
    }

    char tail[20] = {0};
    file.write(tail, 20);
    file.close();
}

bool Writer::parseTemplate(const std::string& template_path) {
    std::ifstream file(template_path, std::ios::binary);
    if (!file) return false;

    templateData.assign(std::istreambuf_iterator<char>(file),
                         std::istreambuf_iterator<char>());
    file.close();

    templateObjects.clear();
    const uint8_t marker[] = {0x64, 0x0f, 0x33, 0xff};

    size_t i = 0;
    while (i + 50 < templateData.size()) {
        if (templateData[i] == 0x01 && templateData[i + 1] == 0xff) {
            // 搜索 marker
            bool found = false;
            for (size_t j = 0; j < 46; j++) {
                if (i + 2 + j + 4 <= templateData.size() &&
                    templateData[i + 2 + j] == marker[0] &&
                    templateData[i + 2 + j + 1] == marker[1] &&
                    templateData[i + 2 + j + 2] == marker[2] &&
                    templateData[i + 2 + j + 3] == marker[3]) {
                    found = true;
                    break;
                }
            }
            if (found) {
                // 搜索 03 47 结束标记
                size_t hdr_end = 0;
                bool hdr_found = false;
                for (size_t j = 0; j < 60 && i + j + 1 < templateData.size(); j++) {
                    if (templateData[i + j] == 0x03 && templateData[i + j + 1] == 0x47) {
                        hdr_end = i + j;
                        hdr_found = true;
                        break;
                    }
                }
                if (hdr_found && hdr_end + 4 < templateData.size()) {
                    uint16_t point_count = (templateData[hdr_end + 2] << 8) |
                                           templateData[hdr_end + 3];
                    if (point_count > 0 && point_count <= 10000) {
                        size_t coord_offset = hdr_end + 5;
                        size_t coord_size = static_cast<size_t>(point_count) * 8;
                        if (coord_offset + coord_size <= templateData.size()) {
                            templateObjects.push_back({
                                i, coord_offset, coord_size, point_count
                            });
                        }
                    }
                }
            }
        }
        i++;
    }

    return !templateObjects.empty();
}

bool Writer::writeWithTemplate(
    const std::string& template_path,
    const std::vector<Object>& objects,
    const std::string& output_path)
{
    // 1. 解析模板
    if (!parseTemplate(template_path)) {
        return false;
    }

    // 2. 收集所有 SVG 点
    std::vector<std::pair<double, double>> allPoints;
    for (const auto& obj : objects) {
        for (const auto& pt : obj.points) {
            allPoints.push_back({static_cast<double>(pt.x),
                                 static_cast<double>(pt.y)});
        }
    }
    if (allPoints.size() < 2) return false;

    // 3. 计算缩放
    double min_x = allPoints[0].first, max_x = allPoints[0].first;
    double min_y = allPoints[0].second, max_y = allPoints[0].second;
    for (const auto& p : allPoints) {
        min_x = std::min(min_x, p.first);
        max_x = std::max(max_x, p.first);
        min_y = std::min(min_y, p.second);
        max_y = std::max(max_y, p.second);
    }
    double w = max_x - min_x;
    double h = max_y - min_y;
    if (w < 1) w = 1;
    if (h < 1) h = 1;

    double wsd_range = 25000.0;
    double scale = std::min(wsd_range / w, wsd_range / h);

    for (auto& p : allPoints) {
        p.first = (p.first - min_x - w / 2.0) * scale;
        p.second = -(p.second - min_y - h / 2.0) * scale;
    }

    // 4. 等弧长重采样到模板总点数
    size_t total_template = 0;
    for (const auto& t : templateObjects) {
        total_template += t.point_count;
    }

    // 计算累积弧长
    std::vector<double> cumLen(allPoints.size(), 0.0);
    for (size_t i = 1; i < allPoints.size(); i++) {
        double dx = allPoints[i].first - allPoints[i - 1].first;
        double dy = allPoints[i].second - allPoints[i - 1].second;
        cumLen[i] = cumLen[i - 1] + std::sqrt(dx * dx + dy * dy);
    }
    double totalLen = cumLen.back();

    std::vector<std::pair<double, double>> resampled(total_template);
    if (totalLen > 0 && total_template > 1) {
        for (size_t k = 0; k < total_template; k++) {
            double target = k * totalLen / (total_template - 1);
            // 二分查找
            size_t lo = 0, hi = cumLen.size() - 1;
            while (lo < hi - 1) {
                size_t mid = (lo + hi) / 2;
                if (cumLen[mid] <= target) lo = mid;
                else hi = mid;
            }
            double segLen = cumLen[hi] - cumLen[lo];
            double t = (segLen > 0) ? (target - cumLen[lo]) / segLen : 0;
            resampled[k].first = allPoints[lo].first + t * (allPoints[hi].first - allPoints[lo].first);
            resampled[k].second = allPoints[lo].second + t * (allPoints[hi].second - allPoints[lo].second);
        }
    } else {
        for (size_t k = 0; k < total_template; k++) {
            resampled[k] = allPoints[0];
        }
    }

    // 5. 替换模板中的坐标
    std::vector<uint8_t> result = templateData;
    size_t coord_idx = 0;
    size_t replaced = 0;

    for (const auto& t : templateObjects) {
        for (uint16_t j = 0; j < t.point_count; j++) {
            size_t pos = t.coord_offset + static_cast<size_t>(j) * 8;
            size_t src_idx = coord_idx + j;
            if (src_idx >= resampled.size()) src_idx = resampled.size() - 1;

            int16_t x = static_cast<int16_t>(
                std::max(-32768.0, std::min(32767.0, resampled[src_idx].first)));
            int16_t y = static_cast<int16_t>(
                std::max(-32768.0, std::min(32767.0, resampled[src_idx].second)));

            result[pos] = static_cast<uint8_t>(x & 0xFF);
            result[pos + 1] = static_cast<uint8_t>((x >> 8) & 0xFF);
            result[pos + 2] = 0;
            result[pos + 3] = 0;
            result[pos + 4] = static_cast<uint8_t>(y & 0xFF);
            result[pos + 5] = static_cast<uint8_t>((y >> 8) & 0xFF);
            result[pos + 6] = 0;
            result[pos + 7] = 0;
        }
        coord_idx += t.point_count;
        replaced++;
    }

    // 6. 写入文件
    std::ofstream out(output_path, std::ios::binary);
    if (!out) return false;
    out.write(reinterpret_cast<const char*>(result.data()), result.size());
    out.close();

    return (replaced == templateObjects.size());
}

// ============================================================
//  颜色索引表定义（已验证）
// ============================================================

const ColorIndex COLOR_INDEX_TABLE[] = {
    {"red",   {{0x00, 0x00, 0xff, 0xff}}},
    {"green", {{0x71, 0xb3, 0x3c, 0xff}}},
    {"blue",  {{0xf0, 0xb0, 0x00, 0xff}}},
    {"black", {{0x01, 0xff, 0x00, 0x00}}},
    {"white", {{0x02, 0xff, 0x00, 0x00}}},
};
const size_t COLOR_INDEX_TABLE_SIZE = sizeof(COLOR_INDEX_TABLE) / sizeof(COLOR_INDEX_TABLE[0]);

// ============================================================
//  记录表修改接口实现
// ============================================================

bool Writer::findColorByName(const std::string& colorName, std::array<uint8_t, 4>& result) {
    // 颜色名称查找（不区分大小写）
    std::string lowerName = colorName;
    std::transform(lowerName.begin(), lowerName.end(), lowerName.begin(), ::tolower);

    for (size_t i = 0; i < COLOR_INDEX_TABLE_SIZE; ++i) {
        if (COLOR_INDEX_TABLE[i].name == lowerName) {
            result = COLOR_INDEX_TABLE[i].value;
            return true;
        }
    }
    return false;
}

bool Writer::loadRecordFile(const std::string& wsd_path) {
    // 加载 WSD 文件到 recordData 缓冲区
    std::ifstream file(wsd_path, std::ios::binary);
    if (!file) return false;

    recordData.assign(std::istreambuf_iterator<char>(file),
                       std::istreambuf_iterator<char>());
    file.close();

    originalSize = recordData.size();
    records.clear();
    return !recordData.empty();
}

bool Writer::parseRecords() {
    // 解析文件尾部记录表 - 两遍扫描
    // 第一遍: 找到所有 marker 位置
    // 第二遍: 根据 byte 31 识别记录类型并逐条解析
    if (recordData.empty()) return false;

    records.clear();
    const size_t fileSize = recordData.size();

    // 从文件后半部分开始搜索（记录表通常在文件尾部）
    const size_t searchStart = (fileSize > 200) ? (fileSize / 2) : 0;

    // ========== 第一遍：找到所有 marker 位置 ==========
    std::vector<size_t> markerPositions;
    size_t i = searchStart;
    while (i + 32 < fileSize) {
        if (recordData[i] == 0x0f &&
            recordData[i + 1] == 0x33 &&
            recordData[i + 2] == 0xff &&
            recordData[i + 3] == 0x00 &&
            recordData[i + 4] == 0x07) {

            // 验证字段标记: 04 ff ff (marker+5)
            if (i + 8 < fileSize &&
                recordData[i + 5] == 0x04 &&
                recordData[i + 6] == 0xff &&
                recordData[i + 7] == 0xff) {
                markerPositions.push_back(i);
            }
        }
        i++;
    }

    if (markerPositions.empty()) return false;

    // 按偏移排序
    std::sort(markerPositions.begin(), markerPositions.end());

    // ========== 第二遍：逐条解析，根据 byte 31 识别记录类型 ==========
    for (size_t mi = 0; mi < markerPositions.size(); ++mi) {
        size_t m = markerPositions[mi];
        Record rec;
        rec.markerOffset = m;
        rec.canvasIndex = 0;
        rec.recordType = 0x00;

        // 读取 byte 31 (marker+31) 确定记录类型
        if (m + 32 <= fileSize) {
            uint8_t typeByte = recordData[m + 31];
            rec.recordType = typeByte;
        }

        // 提取颜色索引 (marker+8, 4字节)
        std::copy(recordData.begin() + m + COLOR_OFFSET,
                  recordData.begin() + m + COLOR_OFFSET + 4,
                  rec.color.begin());

        // 提取线宽 (marker+16, uint32 LE, 毫米 * 400)
        if (m + LINEWIDTH_OFFSET + 4 <= fileSize) {
            rec.lineWidthRaw = *reinterpret_cast<const uint32_t*>(
                recordData.data() + m + LINEWIDTH_OFFSET);
        } else {
            rec.lineWidthRaw = 0;
        }

        // 根据类型解析坐标区域
        rec.coordRegions.clear();

        if (rec.recordType == 0x04 && m + TYPE04_SIZE <= fileSize) {
            // ===== Type 0x04: 直接坐标记录 (53字节) =====
            // marker+34-35: endpoint count (uint16 LE)
            uint16_t epCount = static_cast<uint16_t>(
                recordData[m + 34] | (recordData[m + 35] << 8));

            // marker+36: 坐标数据 (x1,y1,x2,y2，各 uint32 LE，4字节)
            size_t coordOffset = m + 36;
            size_t coordPairs = epCount > 0 ? epCount : 2; // 默认2个点 (起点+终点)

            rec.coordRegions.push_back({
                coordOffset,                    // 数据偏移
                static_cast<uint16_t>(coordPairs), // 点数
                true,                           // uint32 格式
                "xy_pairs"                      // 格式标记
            });

            rec.recordSize = TYPE04_SIZE;

        } else if (rec.recordType == 0x01 && m + TYPE01_SIZE <= fileSize) {
            // ===== Type 0x01: 旋转矩阵记录 (77字节) =====
            // 坐标在 marker+56, 60, 64, 68, 72, 76 (各 uint32，共6个值)
            // 格式为 'uint32_type01': 每4字节一个uint32值 (非X/Y对)
            size_t coordOffsets[] = {56, 60, 64, 68, 72, 76};

            // 将旋转矩阵坐标作为一个整体区域存储
            rec.coordRegions.push_back({
                m + 56,         // 数据偏移
                6,              // 6个uint32值
                true,           // uint32 格式
                "uint32_type01" // 格式标记: 每4字节一个uint32值
            });

            rec.recordSize = TYPE01_SIZE;

        } else {
            // ===== 未知类型: 使用启发式方法解析 =====
            // 回退到旧的逐区域扫描逻辑
            size_t pos = m + COORD_DATA_START;

            while (pos + 6 < fileSize) {
                // 检测是否到达下一条记录
                bool hitNextMarker = false;
                for (size_t nk = mi + 1; nk < markerPositions.size(); ++nk) {
                    if (pos == markerPositions[nk]) {
                        hitNextMarker = true;
                        break;
                    }
                }
                if (hitNextMarker) break;

                // 简单检测下一个marker前缀
                if (recordData[pos] == 0x0f && pos + 4 < fileSize &&
                    recordData[pos + 1] == 0x33 &&
                    recordData[pos + 2] == 0xff) {
                    break;
                }

                // 检测 uint32 坐标格式
                uint16_t coordType   = (recordData[pos] << 8) | recordData[pos + 1];
                uint16_t coordHeader = (recordData[pos + 2] << 8) | recordData[pos + 3];
                uint16_t coordCount  = (recordData[pos + 4] << 8) | recordData[pos + 5];

                if (coordCount > 0 && coordCount <= 50000 &&
                    coordType > 0 && coordType < 0x0500 &&
                    coordHeader < 0x1000) {

                    const size_t coordDataSize = static_cast<size_t>(coordCount) * 8;
                    if (pos + 6 + coordDataSize <= fileSize) {
                        rec.coordRegions.push_back({
                            pos + 6,       // 数据偏移
                            coordCount,    // 点数
                            true,          // uint32 格式
                            "xy_pairs"     // 默认格式
                        });
                        pos = pos + 6 + coordDataSize;
                        continue;
                    }
                }

                // float 格式区域 - 跳过
                size_t scanEnd = std::min(pos + 200, fileSize - 4);
                size_t floatBytes = 0;
                while (pos + floatBytes < scanEnd) {
                    if (recordData[pos + floatBytes] == 0x0f &&
                        recordData[pos + floatBytes + 1] == 0x33 &&
                        recordData[pos + floatBytes + 2] == 0xff) {
                        break;
                    }
                    floatBytes++;
                }

                if (floatBytes > 16) {
                    rec.coordRegions.push_back({
                        pos,
                        static_cast<uint16_t>(floatBytes / 4),
                        false,         // float 格式
                        "float"        // 格式标记
                    });
                    pos += floatBytes;
                } else {
                    pos++;
                }
            }

            // 启发式计算记录大小
            if (mi + 1 < markerPositions.size()) {
                rec.recordSize = markerPositions[mi + 1] - m;
            } else {
                rec.recordSize = fileSize - m - 8;
            }
        }

        records.push_back(rec);
    }

    // 分配画布索引
    assignCanvasIndices();

    return !records.empty();
}

void Writer::assignCanvasIndices() {
    // 分配画布索引：基于记录间距离判断画布边界
    if (records.size() <= 1) return;

    // 计算相邻记录间距
    std::vector<size_t> gaps;
    for (size_t i = 1; i < records.size(); ++i) {
        gaps.push_back(records[i].markerOffset - records[i - 1].markerOffset);
    }
    if (gaps.empty()) return;

    // 使用间距中位数的 3 倍作为画布分隔阈值
    std::vector<size_t> sortedGaps = gaps;
    std::sort(sortedGaps.begin(), sortedGaps.end());
    size_t medianGap = sortedGaps[sortedGaps.size() / 2];
    size_t threshold = std::max(medianGap * 3, static_cast<size_t>(1000));

    int canvasIdx = 0;
    for (size_t i = 0; i < records.size(); ++i) {
        if (i > 0 && gaps[i - 1] > threshold) {
            canvasIdx++;
        }
        records[i].canvasIndex = canvasIdx;
    }
}

void Writer::updateTailChecksum() {
    // 更新文件尾部校验和
    // 格式: filesize_le32 + ff ff ff ff（共 8 字节）
    if (recordData.size() < 8) return;

    uint32_t fileSize = static_cast<uint32_t>(recordData.size());
    recordData[recordData.size() - 8] = static_cast<uint8_t>(fileSize & 0xFF);
    recordData[recordData.size() - 7] = static_cast<uint8_t>((fileSize >> 8) & 0xFF);
    recordData[recordData.size() - 6] = static_cast<uint8_t>((fileSize >> 16) & 0xFF);
    recordData[recordData.size() - 5] = static_cast<uint8_t>((fileSize >> 24) & 0xFF);
    recordData[recordData.size() - 4] = 0xFF;
    recordData[recordData.size() - 3] = 0xFF;
    recordData[recordData.size() - 2] = 0xFF;
    recordData[recordData.size() - 1] = 0xFF;
}

bool Writer::modifyRecordColor(size_t recordIndex, const std::array<uint8_t, 4>& newColor) {
    // 修改指定记录的颜色 (4字节 at marker+8)
    if (recordIndex >= records.size()) return false;

    Record& rec = records[recordIndex];
    size_t offset = rec.markerOffset + COLOR_OFFSET;

    if (offset + 4 > recordData.size()) return false;

    std::copy(newColor.begin(), newColor.end(),
              recordData.begin() + offset);
    rec.color = newColor;

    return true;
}

bool Writer::modifyRecordColorByName(size_t recordIndex, const std::string& colorName) {
    // 通过颜色名称修改记录颜色
    std::array<uint8_t, 4> colorBytes;
    if (!findColorByName(colorName, colorBytes)) return false;
    return modifyRecordColor(recordIndex, colorBytes);
}

bool Writer::modifyRecordLineWidth(size_t recordIndex, float lineWidthMM) {
    // 修改指定记录的线宽 (uint32 LE at marker+16, = 毫米 * 400)
    if (recordIndex >= records.size()) return false;

    Record& rec = records[recordIndex];
    size_t offset = rec.markerOffset + LINEWIDTH_OFFSET;

    if (offset + 4 > recordData.size()) return false;

    uint32_t lwRaw = static_cast<uint32_t>(lineWidthMM * 400.0f);
    recordData[offset]     = static_cast<uint8_t>(lwRaw & 0xFF);
    recordData[offset + 1] = static_cast<uint8_t>((lwRaw >> 8) & 0xFF);
    recordData[offset + 2] = static_cast<uint8_t>((lwRaw >> 16) & 0xFF);
    recordData[offset + 3] = static_cast<uint8_t>((lwRaw >> 24) & 0xFF);
    rec.lineWidthRaw = lwRaw;

    return true;
}

bool Writer::modifyRecordCoordinates(
    size_t recordIndex,
    size_t coordIndex,
    const std::vector<std::pair<uint32_t, uint32_t>>& newCoords)
{
    // 修改指定记录中 uint32 格式的坐标数据
    // 支持两种格式:
    //   "xy_pairs" (默认): 每点8字节 (X:4字节 + Y:4字节)
    //   "uint32_type01": 每4字节一个uint32值，pair的first和second分别写入相邻的4字节
    // float 格式不可修改
    // 值的总数必须与原始 count 匹配以保证文件大小不变

    if (recordIndex >= records.size()) return false;

    Record& rec = records[recordIndex];
    if (coordIndex >= rec.coordRegions.size()) return false;

    const CoordRegion& region = rec.coordRegions[coordIndex];
    if (!region.isUint32) return false;  // float 格式不可修改

    if (region.fmt == "uint32_type01") {
        // uint32_type01 格式: 每4字节一个uint32值
        // count 表示值的总个数（非点对数）
        // newCoords 每对提供2个连续的uint32值
        // 总共需要 count 个值 => 需要 (count+1)/2 个 pair
        size_t totalValues = static_cast<size_t>(region.count);
        size_t neededPairs = (totalValues + 1) / 2;
        if (newCoords.size() < neededPairs) return false;

        size_t valueIdx = 0;
        for (size_t p = 0; p < newCoords.size() && valueIdx < totalValues; ++p) {
            // 写入 pair.first
            if (valueIdx < totalValues) {
                size_t pos = region.offset + valueIdx * 4;
                if (pos + 4 > recordData.size()) return false;
                uint32_t val = newCoords[p].first;
                recordData[pos]     = static_cast<uint8_t>(val & 0xFF);
                recordData[pos + 1] = static_cast<uint8_t>((val >> 8) & 0xFF);
                recordData[pos + 2] = static_cast<uint8_t>((val >> 16) & 0xFF);
                recordData[pos + 3] = static_cast<uint8_t>((val >> 24) & 0xFF);
                valueIdx++;
            }
            // 写入 pair.second
            if (valueIdx < totalValues) {
                size_t pos = region.offset + valueIdx * 4;
                if (pos + 4 > recordData.size()) return false;
                uint32_t val = newCoords[p].second;
                recordData[pos]     = static_cast<uint8_t>(val & 0xFF);
                recordData[pos + 1] = static_cast<uint8_t>((val >> 8) & 0xFF);
                recordData[pos + 2] = static_cast<uint8_t>((val >> 16) & 0xFF);
                recordData[pos + 3] = static_cast<uint8_t>((val >> 24) & 0xFF);
                valueIdx++;
            }
        }
        return true;
    }

    // 默认 xy_pairs 格式: 每点8字节 (X:4字节 + Y:4字节)
    if (newCoords.size() != region.count) return false;  // 点数必须匹配

    for (size_t j = 0; j < newCoords.size(); ++j) {
        size_t pos = region.offset + j * 8;

        if (pos + 8 > recordData.size()) return false;

        // X 坐标 (uint32 LE)
        uint32_t x = newCoords[j].first;
        recordData[pos]     = static_cast<uint8_t>(x & 0xFF);
        recordData[pos + 1] = static_cast<uint8_t>((x >> 8) & 0xFF);
        recordData[pos + 2] = static_cast<uint8_t>((x >> 16) & 0xFF);
        recordData[pos + 3] = static_cast<uint8_t>((x >> 24) & 0xFF);

        // Y 坐标 (uint32 LE)
        uint32_t y = newCoords[j].second;
        recordData[pos + 4] = static_cast<uint8_t>(y & 0xFF);
        recordData[pos + 5] = static_cast<uint8_t>((y >> 8) & 0xFF);
        recordData[pos + 6] = static_cast<uint8_t>((y >> 16) & 0xFF);
        recordData[pos + 7] = static_cast<uint8_t>((y >> 24) & 0xFF);
    }

    return true;
}

const Record* Writer::getRecordInfo(size_t recordIndex) const {
    // 获取指定记录的详细信息
    if (recordIndex >= records.size()) return nullptr;
    return &records[recordIndex];
}

float Writer::getRotationAngle(int recordIndex) const {
    // 获取指定记录的旋转角度（仅 Type 0x01 有效）
    // 从旋转矩阵的 uint32 值计算角度（弧度转角度）
    if (recordIndex < 0 || static_cast<size_t>(recordIndex) >= records.size()) return 0.0f;

    const Record& rec = records[recordIndex];
    if (rec.recordType != 0x01) return 0.0f;

    // 旋转矩阵坐标在 marker+56,60,64,68,72,76 (uint32_type01格式)
    // 第一个值 (marker+56) 作为角度参数，使用 atan2 计算
    size_t m = rec.markerOffset;
    if (m + 76 + 4 > recordData.size()) return 0.0f;

    uint32_t val56 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 56);
    uint32_t val60 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 60);

    // 将 uint32 值转为浮点数用于角度计算
    // 这些值通常是以定点数存储的 sin/cos 分量
    float sinVal = static_cast<float>(val56) / 10000.0f;
    float cosVal = static_cast<float>(val60) / 10000.0f;

    float angleRad = std::atan2(sinVal, cosVal);
    float angleDeg = angleRad * 180.0f / static_cast<float>(M_PI);

    return angleDeg;
}

std::vector<std::pair<uint32_t,uint32_t>> Writer::getEndpointCoords(int recordIndex) const {
    // 获取指定记录的端点坐标列表
    std::vector<std::pair<uint32_t,uint32_t>> result;

    if (recordIndex < 0 || static_cast<size_t>(recordIndex) >= records.size()) return result;

    const Record& rec = records[recordIndex];
    size_t m = rec.markerOffset;

    if (rec.recordType == 0x04) {
        // Type 0x04: 坐标在 marker+36 (x1,y1,x2,y2，各 uint32 LE，4字节)
        if (m + 36 + 16 <= recordData.size()) {
            uint32_t x1 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 36);
            uint32_t y1 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 40);
            uint32_t x2 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 44);
            uint32_t y2 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 48);
            result.push_back({x1, y1});
            result.push_back({x2, y2});
        }
    } else if (rec.recordType == 0x01) {
        // Type 0x01: 坐标在 marker+56,60,64,68,72,76 (各 uint32)
        // 返回为3个坐标对
        if (m + 56 + 24 <= recordData.size()) {
            uint32_t v0 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 56);
            uint32_t v1 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 60);
            uint32_t v2 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 64);
            uint32_t v3 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 68);
            uint32_t v4 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 72);
            uint32_t v5 = *reinterpret_cast<const uint32_t*>(recordData.data() + m + 76);
            result.push_back({v0, v1});
            result.push_back({v2, v3});
            result.push_back({v4, v5});
        }
    }
    // 未知类型不返回坐标

    return result;
}

bool Writer::modifyRecordEndpoints(int recordIndex, const std::vector<std::pair<uint32_t,uint32_t>>& newCoords) {
    // 修改指定记录的端点坐标
    if (recordIndex < 0 || static_cast<size_t>(recordIndex) >= records.size()) return false;

    Record& rec = records[recordIndex];
    size_t m = rec.markerOffset;

    auto writeU32 = [&](size_t pos, uint32_t val) -> bool {
        if (pos + 4 > recordData.size()) return false;
        recordData[pos]     = static_cast<uint8_t>(val & 0xFF);
        recordData[pos + 1] = static_cast<uint8_t>((val >> 8) & 0xFF);
        recordData[pos + 2] = static_cast<uint8_t>((val >> 16) & 0xFF);
        recordData[pos + 3] = static_cast<uint8_t>((val >> 24) & 0xFF);
        return true;
    };

    if (rec.recordType == 0x04) {
        // Type 0x04: 修改 marker+36 处的 x1,y1,x2,y2 (各uint32)
        // 需要2个坐标对
        if (newCoords.size() < 2) return false;

        bool ok = true;
        ok &= writeU32(m + 36, newCoords[0].first);   // x1
        ok &= writeU32(m + 40, newCoords[0].second);   // y1
        ok &= writeU32(m + 44, newCoords[1].first);    // x2
        ok &= writeU32(m + 48, newCoords[1].second);   // y2
        return ok;

    } else if (rec.recordType == 0x01) {
        // Type 0x01: 修改 marker+56,60,64,68,72,76 处的旋转矩阵坐标
        // 需要3个坐标对 (6个uint32值)
        if (newCoords.size() < 3) return false;

        bool ok = true;
        ok &= writeU32(m + 56, newCoords[0].first);    // val56
        ok &= writeU32(m + 60, newCoords[0].second);   // val60
        ok &= writeU32(m + 64, newCoords[1].first);    // val64
        ok &= writeU32(m + 68, newCoords[1].second);   // val68
        ok &= writeU32(m + 72, newCoords[2].first);    // val72
        ok &= writeU32(m + 76, newCoords[2].second);   // val76
        return ok;
    }

    return false;  // 未知类型不支持
}

bool Writer::modifyWSD(
    const std::string& templatePath,
    const std::string& outputPath,
    const std::vector<Modification>& modifications)
{
    // WSD 文件修改主函数
    // 1. 加载模板文件
    if (!loadRecordFile(templatePath)) return false;

    // 2. 解析记录表
    if (!parseRecords()) return false;

    // 3. 应用所有修改指令
    for (const auto& mod : modifications) {
        size_t ri = static_cast<size_t>(mod.recordIndex);

        // 颜色修改
        if (mod.changeColor && ri < records.size()) {
            modifyRecordColor(ri, mod.newColor);
        }

        // 线宽修改
        if (mod.changeLineWidth && ri < records.size()) {
            modifyRecordLineWidth(ri, mod.lineWidthMM);
        }

        // 坐标修改
        if (mod.changeCoords && ri < records.size()) {
            size_t ci = static_cast<size_t>(mod.coordIndex);
            modifyRecordCoordinates(ri, ci, mod.newCoords);
        }
    }

    // 4. 校验文件大小（关键要求：必须与原始文件大小相同！）
    if (recordData.size() != originalSize) {
        return false;  // 严重错误：文件大小改变会导致 EduEditor 无法打开
    }

    // 5. 更新尾部校验和
    updateTailChecksum();

    // 6. 写入输出文件
    std::ofstream out(outputPath, std::ios::binary);
    if (!out) return false;
    out.write(reinterpret_cast<const char*>(recordData.data()), recordData.size());
    out.close();

    return true;
}

} // namespace wsd
