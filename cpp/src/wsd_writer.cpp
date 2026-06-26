#include "wsd_writer.h"
#include <fstream>
#include <cstring>

namespace wsd {

void Writer::write(const std::string& filepath, const std::vector<Object>& objects) {
    std::ofstream file(filepath, std::ios::binary);
    if (!file) return;

    // 文件头
    file.put(0x00);
    file.write(FileHeader::MAGIC, 8);
    file.put(FileHeader::VERSION);

    // 字体表填充
    file.write(reinterpret_cast<const char*>(OBJECT_HEADER), 41);
    char padding[100] = {0};
    file.write(padding, 100);

    // 写入对象
    for (const auto& obj : objects) {
        // 对象头
        file.write(reinterpret_cast<const char*>(OBJECT_HEADER), 41);

        // 点数 (大端序)
        uint16_t count = static_cast<uint16_t>(obj.points.size());
        file.put(static_cast<char>((count >> 8) & 0xFF));
        file.put(static_cast<char>(count & 0xFF));

        // 填充
        file.put(0x00);

        // 坐标
        for (const auto& pt : obj.points) {
            file.write(reinterpret_cast<const char*>(&pt.x), 2);
            file.put(0x00); file.put(0x00);
            file.write(reinterpret_cast<const char*>(&pt.y), 2);
            file.put(0x00); file.put(0x00);
        }

        // 颜色 ARGB
        file.put(static_cast<char>(obj.color.r));
        file.put(static_cast<char>(obj.color.g));
        file.put(static_cast<char>(obj.color.b));
        file.put(static_cast<char>(obj.color.a));

        // 对象尾
        file.put(0x00); file.put(0x00);
    }

    // 文件尾
    char tail[20] = {0};
    file.write(tail, 20);
    file.close();
}

} // namespace wsd
