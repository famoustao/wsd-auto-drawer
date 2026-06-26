#pragma once
#include <vector>
#include <cstdint>
#include <string>

namespace wsd {

struct Point {
    int16_t x;
    int16_t y;
};

struct Color {
    uint8_t r = 0;
    uint8_t g = 0;
    uint8_t b = 0;
    uint8_t a = 255;
};

struct Object {
    std::vector<Point> points;
    Color color;
    bool isClosed = false;
};

struct FileHeader {
    static constexpr const char* MAGIC = "WSTUDIO7";
    static constexpr uint8_t VERSION = 7;
};

// 对象头模板 (41字节)
extern const uint8_t OBJECT_HEADER[41];

} // namespace wsd
