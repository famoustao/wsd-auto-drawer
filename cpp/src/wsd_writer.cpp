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
    // 解析文件尾部记录表 - 查找所有 0f 33 ff 00 07 标记
    if (recordData.empty()) return false;

    records.clear();
    const size_t fileSize = recordData.size();

    // 从文件后半部分开始搜索（记录表通常在文件尾部）
    const size_t searchStart = (fileSize > 200) ? (fileSize / 2) : 0;

    size_t i = searchStart;
    while (i + 32 < fileSize) {
        // 查找记录标记: 0f 33 ff 00 07
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

                // 提取颜色索引 (marker+8, 4字节)
                Record rec;
                rec.markerOffset = i;
                rec.canvasIndex = static_cast<int>(records.size());
                std::copy(recordData.begin() + i + COLOR_OFFSET,
                          recordData.begin() + i + COLOR_OFFSET + 4,
                          rec.color.begin());

                // 提取线宽 (marker+16, uint32 LE, 毫米 * 400)
                if (i + LINEWIDTH_OFFSET + 4 <= fileSize) {
                    rec.lineWidthRaw = *reinterpret_cast<const uint32_t*>(
                        recordData.data() + i + LINEWIDTH_OFFSET);
                } else {
                    rec.lineWidthRaw = 0;
                }

                // 解析坐标数据区域 (marker+32 起)
                rec.coordRegions.clear();
                size_t pos = i + COORD_DATA_START;

                while (pos + 6 < fileSize) {
                    // 检测是否到达下一条记录
                    if (recordData[pos] == 0x0f && pos + 4 < fileSize &&
                        recordData[pos + 1] == 0x33 &&
                        recordData[pos + 2] == 0xff) {
                        break;  // 下一条记录标记
                    }

                    // 检测 uint32 坐标格式
                    // 格式: type(2B BE) + header(2B BE) + count(2B BE) + X/Y 对 (各4字节 LE)
                    uint16_t coordType   = (recordData[pos] << 8) | recordData[pos + 1];
                    uint16_t coordHeader = (recordData[pos + 2] << 8) | recordData[pos + 3];
                    uint16_t coordCount  = (recordData[pos + 4] << 8) | recordData[pos + 5];

                    // 合理性检查
                    if (coordCount > 0 && coordCount <= 50000 &&
                        coordType > 0 && coordType < 0x0500 &&
                        coordHeader < 0x1000) {

                        const size_t coordDataSize = static_cast<size_t>(coordCount) * 8;
                        if (pos + 6 + coordDataSize <= fileSize) {
                            rec.coordRegions.push_back({
                                pos + 6,       // 数据偏移
                                coordCount,    // 点数
                                true           // uint32 格式（可修改）
                            });
                            pos = pos + 6 + coordDataSize;
                            continue;
                        }
                    }

                    // float 格式区域（画布参数）- 跳过，不修改
                    // 查找下一个结构标记
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
                        // float 区域（画布参数），标记但不可修改
                        rec.coordRegions.push_back({
                            pos,
                            static_cast<uint16_t>(floatBytes / 4),
                            false  // float 格式（不可修改）
                        });
                        pos += floatBytes;
                    } else {
                        pos++;
                    }
                }

                // 计算记录大小
                if (!records.empty()) {
                    rec.recordSize = i - records.back().markerOffset;
                } else {
                    // 最后一条（最早发现的）记录，到文件末尾减去校验和(8字节)
                    rec.recordSize = fileSize - i - 8;
                }

                records.push_back(rec);

                // 跳过已解析区域
                i += std::max(rec.recordSize, static_cast<size_t>(32));
                continue;
            }
        }
        i++;
    }

    // 按偏移排序（从文件头到尾的顺序）
    std::sort(records.begin(), records.end(),
              [](const Record& a, const Record& b) {
                  return a.markerOffset < b.markerOffset;
              });

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
    // 仅支持 uint32 格式，float 格式不可修改
    // 点数必须与原始相同以保证文件大小不变

    if (recordIndex >= records.size()) return false;

    Record& rec = records[recordIndex];
    if (coordIndex >= rec.coordRegions.size()) return false;

    const CoordRegion& region = rec.coordRegions[coordIndex];
    if (!region.isUint32) return false;  // float 格式不可修改

    if (newCoords.size() != region.count) return false;  // 点数必须匹配

    // 逐点写入 uint32 LE 坐标 (X: 4字节, Y: 4字节)
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
