#include "wsd_parser.h"
#include <fstream>
#include <algorithm>
#include <cstring>

namespace wsd {

std::vector<Object> Parser::parse(const std::string& filepath) {
    std::vector<Object> objects;
    std::ifstream file(filepath, std::ios::binary);
    if (!file) return objects;

    file.seekg(0, std::ios::end);
    size_t size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::vector<uint8_t> data(size);
    file.read(reinterpret_cast<char*>(data.data()), size);
    file.close();

    if (size < 10 || std::memcmp(data.data() + 1, FileHeader::MAGIC, 7) != 0) {
        return objects;
    }

    // 查找所有对象
    std::vector<size_t> objStarts;
    for (size_t i = 0; i + 50 < size; ++i) {
        if (data[i] == 0x01 && data[i+1] == 0xff) {
            for (size_t j = i; j < i + 50 && j < size; ++j) {
                if (data[j] == 0x64 && j+3 < size && data[j+1] == 0x0f &&
                    data[j+2] == 0x33 && data[j+3] == 0xff) {
                    objStarts.push_back(i);
                    break;
                }
            }
        }
    }

    for (size_t idx = 0; idx < objStarts.size(); ++idx) {
        size_t start = objStarts[idx];
        size_t end = (idx + 1 < objStarts.size()) ? objStarts[idx + 1] : size;
        if (end - start < 50) continue;

        // 查找对象头结束 03 47
        size_t headerEnd = static_cast<size_t>(-1);
        for (size_t i = 0; i < 60 && i + 2 < (end - start); ++i) {
            if (data[start + i] == 0x03 && data[start + i + 1] == 0x47) {
                headerEnd = i;
                break;
            }
        }
        if (headerEnd == static_cast<size_t>(-1)) continue;

        // 点数 (大端序)
        uint16_t pointCount = (data[start + headerEnd + 2] << 8) | data[start + headerEnd + 3];
        if (pointCount == 0 || pointCount > 10000) continue;

        size_t coordStart = headerEnd + 5;
        size_t coordSize = pointCount * 8;
        if (coordStart + coordSize > end - start) continue;

        Object obj;
        obj.points.reserve(pointCount);

        for (uint16_t i = 0; i < pointCount; ++i) {
            size_t offset = start + coordStart + i * 8;
            int16_t x = *reinterpret_cast<int16_t*>(&data[offset]);
            int16_t y = *reinterpret_cast<int16_t*>(&data[offset + 4]);
            obj.points.push_back({x, y});
        }

        if (obj.points.size() < 2) continue;

        // 判断是否闭合
        const auto& first = obj.points.front();
        const auto& last = obj.points.back();
        obj.isClosed = (first.x == last.x && first.y == last.y) ||
                       (std::abs(first.x - last.x) < 5 && std::abs(first.y - last.y) < 5);

        // 提取颜色
        size_t colorOffset = start + coordStart + coordSize;
        for (size_t i = colorOffset; i + 4 < end; ++i) {
            if (data[i+3] == 0xff) {
                uint8_t r = data[i], g = data[i+1], b = data[i+2];
                if (!((r==0&&g==0&&b==0) || (r==255&&g==255&&b==255) ||
                      (r==0&&g==0&&b==1) || (r==1&&g==0&&b==1))) {
                    if (r > 30 || g > 30 || b > 30) {
                        obj.color = {r, g, b, 255};
                        break;
                    }
                }
            }
        }

        objects.push_back(obj);
    }

    return objects;
}

} // namespace wsd
