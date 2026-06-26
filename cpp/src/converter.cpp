#include "converter.h"
#include "svg_parser.h"
#include "wsd_parser.h"
#include "wsd_writer.h"
#include <fstream>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <climits>

namespace converter {

void svgToWsd(const std::string& templatePath, const std::string& svgInput, const std::string& wsdOutput) {
    svg::Parser parser;
    auto objects = parser.parse(svgInput);

    wsd::Writer writer;
    writer.writeWithTemplate(templatePath, objects, wsdOutput);
}

void wsdToSvg(const std::string& input, const std::string& output) {
    wsd::Parser parser;
    auto objects = parser.parse(input);

    if (objects.empty()) return;

    int16_t minX = INT16_MAX, maxX = INT16_MIN;
    int16_t minY = INT16_MAX, maxY = INT16_MIN;
    for (const auto& obj : objects) {
        for (const auto& pt : obj.points) {
            minX = std::min(minX, pt.x);
            maxX = std::max(maxX, pt.x);
            minY = std::min(minY, pt.y);
            maxY = std::max(maxY, pt.y);
        }
    }

    double scale = 0.1;
    double offsetX = -minX * scale + 10;
    double offsetY = -minY * scale + 10;
    double width = (maxX - minX) * scale + 20;
    double height = (maxY - minY) * scale + 20;

    std::ofstream file(output);
    file << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
    file << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width
         << "\" height=\"" << height << "\" viewBox=\"0 0 " << width << " " << height << "\">\n";
    file << "  <rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n";

    for (size_t i = 0; i < objects.size(); ++i) {
        const auto& obj = objects[i];
        if (obj.points.size() < 2) continue;

        char colorStr[8];
        std::snprintf(colorStr, sizeof(colorStr), "#%02x%02x%02x",
                      obj.color.r, obj.color.g, obj.color.b);

        file << "  <path d=\"M ";
        for (size_t j = 0; j < obj.points.size(); ++j) {
            double x = obj.points[j].x * scale + offsetX;
            double y = obj.points[j].y * scale + offsetY;
            if (j > 0) file << " L ";
            file << x << " " << y;
        }
        file << "\" fill=\"none\" stroke=\"" << colorStr
             << "\" stroke-width=\"0.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\" id=\"path_"
             << i << "\"/>\n";
    }

    file << "</svg>\n";
    file.close();
}

} // namespace converter
