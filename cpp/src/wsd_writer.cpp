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

} // namespace wsd
