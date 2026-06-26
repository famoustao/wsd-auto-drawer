#ifdef _WIN32
#define _USE_MATH_DEFINES
#endif
#include "svg_parser.h"
#include "tinyxml2.h"
#include <fstream>
#include <sstream>
#include <cmath>
#include <cctype>

namespace svg {

static wsd::Color parseColor(const char* colorStr) {
    wsd::Color c{0, 0, 0, 255};
    if (!colorStr) return c;
    std::string s(colorStr);
    if (s.empty() || s == "none") return c;

    if (s[0] == '#') {
        if (s.size() == 7) {
            c.r = static_cast<uint8_t>(std::stoi(s.substr(1, 2), nullptr, 16));
            c.g = static_cast<uint8_t>(std::stoi(s.substr(3, 2), nullptr, 16));
            c.b = static_cast<uint8_t>(std::stoi(s.substr(5, 2), nullptr, 16));
        }
    }
    return c;
}

static std::vector<std::string> tokenizePath(const std::string& d) {
    std::vector<std::string> tokens;
    std::string current;
    for (size_t i = 0; i < d.size(); ++i) {
        char ch = d[i];
        if (std::isspace(ch) || ch == ',') {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
        } else if (std::isalpha(ch)) {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
            tokens.push_back(std::string(1, ch));
        } else {
            current += ch;
        }
    }
    if (!current.empty()) tokens.push_back(current);
    return tokens;
}

static void sampleCubicBezier(const wsd::Point& p0, const wsd::Point& p1,
                               const wsd::Point& p2, const wsd::Point& p3,
                               std::vector<wsd::Point>& out, int steps = 8) {
    for (int i = 1; i <= steps; ++i) {
        double t = i / double(steps);
        double t2 = t * t, t3 = t2 * t;
        double x = (1 - 3*t + 3*t2 - t3) * p0.x + (3*t - 6*t2 + 3*t3) * p1.x
                 + (3*t2 - 3*t3) * p2.x + t3 * p3.x;
        double y = (1 - 3*t + 3*t2 - t3) * p0.y + (3*t - 6*t2 + 3*t3) * p1.y
                 + (3*t2 - 3*t3) * p2.y + t3 * p3.y;
        out.push_back({static_cast<int16_t>(std::lround(x)),
                       static_cast<int16_t>(std::lround(y))});
    }
}

static void sampleQuadraticBezier(const wsd::Point& p0, const wsd::Point& p1,
                                   const wsd::Point& p2,
                                   std::vector<wsd::Point>& out, int steps = 6) {
    for (int i = 1; i <= steps; ++i) {
        double t = i / double(steps);
        double t2 = t * t;
        double x = (1 - 2*t + t2) * p0.x + (2*t - 2*t2) * p1.x + t2 * p2.x;
        double y = (1 - 2*t + t2) * p0.y + (2*t - 2*t2) * p1.y + t2 * p2.y;
        out.push_back({static_cast<int16_t>(std::lround(x)),
                       static_cast<int16_t>(std::lround(y))});
    }
}

std::vector<wsd::Object> Parser::parse(const std::string& filepath) {
    std::vector<wsd::Object> objects;

    tinyxml2::XMLDocument doc;
    if (doc.LoadFile(filepath.c_str()) != tinyxml2::XML_SUCCESS) {
        return objects;
    }

    auto* root = doc.RootElement();
    if (!root) return objects;

    // 查找所有 path 元素
    for (auto* elem = root->FirstChildElement(); elem; elem = elem->NextSiblingElement()) {
        if (std::string(elem->Name()) != "path") {
            // 递归查找子元素中的 path
            for (auto* child = elem->FirstChildElement("path"); child; child = child->NextSiblingElement("path")) {
                const char* d = child->Attribute("d");
                if (!d) continue;

                wsd::Object obj;
                obj.color = parseColor(child->Attribute("stroke"));
                const char* fill = child->Attribute("fill");
                obj.isClosed = (fill && std::string(fill) != "none") ||
                               (std::string(d).find('Z') != std::string::npos) ||
                               (std::string(d).find('z') != std::string::npos);

                auto tokens = tokenizePath(d);
                double curX = 0, curY = 0, startX = 0, startY = 0;
                char cmd = 0;
                size_t i = 0;

                while (i < tokens.size()) {
                    if (tokens[i].size() == 1 && std::isalpha(tokens[i][0])) {
                        cmd = tokens[i][0];
                        ++i;
                    }

                    if (i >= tokens.size()) break;

                    switch (cmd) {
                    case 'M': {
                        curX = std::stod(tokens[i++]);
                        curY = std::stod(tokens[i++]);
                        startX = curX; startY = curY;
                        obj.points.push_back({static_cast<int16_t>(std::lround(curX)),
                                              static_cast<int16_t>(std::lround(curY))});
                        cmd = 'L';
                        break;
                    }
                    case 'm': {
                        curX += std::stod(tokens[i++]);
                        curY += std::stod(tokens[i++]);
                        startX = curX; startY = curY;
                        obj.points.push_back({static_cast<int16_t>(std::lround(curX)),
                                              static_cast<int16_t>(std::lround(curY))});
                        cmd = 'l';
                        break;
                    }
                    case 'L': {
                        curX = std::stod(tokens[i++]);
                        curY = std::stod(tokens[i++]);
                        obj.points.push_back({static_cast<int16_t>(std::lround(curX)),
                                              static_cast<int16_t>(std::lround(curY))});
                        break;
                    }
                    case 'l': {
                        curX += std::stod(tokens[i++]);
                        curY += std::stod(tokens[i++]);
                        obj.points.push_back({static_cast<int16_t>(std::lround(curX)),
                                              static_cast<int16_t>(std::lround(curY))});
                        break;
                    }
                    case 'H': curX = std::stod(tokens[i++]); obj.points.push_back({static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))}); break;
                    case 'h': curX += std::stod(tokens[i++]); obj.points.push_back({static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))}); break;
                    case 'V': curY = std::stod(tokens[i++]); obj.points.push_back({static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))}); break;
                    case 'v': curY += std::stod(tokens[i++]); obj.points.push_back({static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))}); break;
                    case 'C': {
                        double x1 = std::stod(tokens[i++]);
                        double y1 = std::stod(tokens[i++]);
                        double x2 = std::stod(tokens[i++]);
                        double y2 = std::stod(tokens[i++]);
                        double x = std::stod(tokens[i++]);
                        double y = std::stod(tokens[i++]);
                        wsd::Point p0{static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))};
                        wsd::Point cp1{static_cast<int16_t>(std::lround(x1)), static_cast<int16_t>(std::lround(y1))};
                        wsd::Point cp2{static_cast<int16_t>(std::lround(x2)), static_cast<int16_t>(std::lround(y2))};
                        wsd::Point p3{static_cast<int16_t>(std::lround(x)), static_cast<int16_t>(std::lround(y))};
                        sampleCubicBezier(p0, cp1, cp2, p3, obj.points);
                        curX = x; curY = y;
                        break;
                    }
                    case 'c': {
                        double x1 = curX + std::stod(tokens[i++]);
                        double y1 = curY + std::stod(tokens[i++]);
                        double x2 = curX + std::stod(tokens[i++]);
                        double y2 = curY + std::stod(tokens[i++]);
                        double x = curX + std::stod(tokens[i++]);
                        double y = curY + std::stod(tokens[i++]);
                        wsd::Point p0{static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))};
                        wsd::Point cp1{static_cast<int16_t>(std::lround(x1)), static_cast<int16_t>(std::lround(y1))};
                        wsd::Point cp2{static_cast<int16_t>(std::lround(x2)), static_cast<int16_t>(std::lround(y2))};
                        wsd::Point p3{static_cast<int16_t>(std::lround(x)), static_cast<int16_t>(std::lround(y))};
                        sampleCubicBezier(p0, cp1, cp2, p3, obj.points);
                        curX = x; curY = y;
                        break;
                    }
                    case 'Q': {
                        double x1 = std::stod(tokens[i++]);
                        double y1 = std::stod(tokens[i++]);
                        double x = std::stod(tokens[i++]);
                        double y = std::stod(tokens[i++]);
                        wsd::Point p0{static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))};
                        wsd::Point cp{static_cast<int16_t>(std::lround(x1)), static_cast<int16_t>(std::lround(y1))};
                        wsd::Point p2{static_cast<int16_t>(std::lround(x)), static_cast<int16_t>(std::lround(y))};
                        sampleQuadraticBezier(p0, cp, p2, obj.points);
                        curX = x; curY = y;
                        break;
                    }
                    case 'q': {
                        double x1 = curX + std::stod(tokens[i++]);
                        double y1 = curY + std::stod(tokens[i++]);
                        double x = curX + std::stod(tokens[i++]);
                        double y = curY + std::stod(tokens[i++]);
                        wsd::Point p0{static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))};
                        wsd::Point cp{static_cast<int16_t>(std::lround(x1)), static_cast<int16_t>(std::lround(y1))};
                        wsd::Point p2{static_cast<int16_t>(std::lround(x)), static_cast<int16_t>(std::lround(y))};
                        sampleQuadraticBezier(p0, cp, p2, obj.points);
                        curX = x; curY = y;
                        break;
                    }
                    case 'Z':
                    case 'z': {
                        if (!obj.points.empty()) {
                            obj.points.push_back(obj.points.front());
                        }
                        curX = startX; curY = startY;
                        break;
                    }
                    default:
                        ++i;
                        break;
                    }
                }

                if (obj.points.size() >= 2) {
                    objects.push_back(obj);
                }
            }
            continue;
        }

        const char* d = elem->Attribute("d");
        if (!d) continue;

        wsd::Object obj;
        obj.color = parseColor(elem->Attribute("stroke"));
        const char* fill = elem->Attribute("fill");
        obj.isClosed = (fill && std::string(fill) != "none") ||
                       (std::string(d).find('Z') != std::string::npos) ||
                       (std::string(d).find('z') != std::string::npos);

        auto tokens = tokenizePath(d);
        double curX = 0, curY = 0, startX = 0, startY = 0;
        char cmd = 0;
        size_t i = 0;

        while (i < tokens.size()) {
            if (tokens[i].size() == 1 && std::isalpha(tokens[i][0])) {
                cmd = tokens[i][0];
                ++i;
            }

            if (i >= tokens.size()) break;

            switch (cmd) {
            case 'M': {
                curX = std::stod(tokens[i++]);
                curY = std::stod(tokens[i++]);
                startX = curX; startY = curY;
                obj.points.push_back({static_cast<int16_t>(std::lround(curX)),
                                      static_cast<int16_t>(std::lround(curY))});
                cmd = 'L';
                break;
            }
            case 'm': {
                curX += std::stod(tokens[i++]);
                curY += std::stod(tokens[i++]);
                startX = curX; startY = curY;
                obj.points.push_back({static_cast<int16_t>(std::lround(curX)),
                                      static_cast<int16_t>(std::lround(curY))});
                cmd = 'l';
                break;
            }
            case 'L': {
                curX = std::stod(tokens[i++]);
                curY = std::stod(tokens[i++]);
                obj.points.push_back({static_cast<int16_t>(std::lround(curX)),
                                      static_cast<int16_t>(std::lround(curY))});
                break;
            }
            case 'l': {
                curX += std::stod(tokens[i++]);
                curY += std::stod(tokens[i++]);
                obj.points.push_back({static_cast<int16_t>(std::lround(curX)),
                                      static_cast<int16_t>(std::lround(curY))});
                break;
            }
            case 'H': curX = std::stod(tokens[i++]); obj.points.push_back({static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))}); break;
            case 'h': curX += std::stod(tokens[i++]); obj.points.push_back({static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))}); break;
            case 'V': curY = std::stod(tokens[i++]); obj.points.push_back({static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))}); break;
            case 'v': curY += std::stod(tokens[i++]); obj.points.push_back({static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))}); break;
            case 'C': {
                double x1 = std::stod(tokens[i++]);
                double y1 = std::stod(tokens[i++]);
                double x2 = std::stod(tokens[i++]);
                double y2 = std::stod(tokens[i++]);
                double x = std::stod(tokens[i++]);
                double y = std::stod(tokens[i++]);
                wsd::Point p0{static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))};
                wsd::Point cp1{static_cast<int16_t>(std::lround(x1)), static_cast<int16_t>(std::lround(y1))};
                wsd::Point cp2{static_cast<int16_t>(std::lround(x2)), static_cast<int16_t>(std::lround(y2))};
                wsd::Point p3{static_cast<int16_t>(std::lround(x)), static_cast<int16_t>(std::lround(y))};
                sampleCubicBezier(p0, cp1, cp2, p3, obj.points);
                curX = x; curY = y;
                break;
            }
            case 'c': {
                double x1 = curX + std::stod(tokens[i++]);
                double y1 = curY + std::stod(tokens[i++]);
                double x2 = curX + std::stod(tokens[i++]);
                double y2 = curY + std::stod(tokens[i++]);
                double x = curX + std::stod(tokens[i++]);
                double y = curY + std::stod(tokens[i++]);
                wsd::Point p0{static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))};
                wsd::Point cp1{static_cast<int16_t>(std::lround(x1)), static_cast<int16_t>(std::lround(y1))};
                wsd::Point cp2{static_cast<int16_t>(std::lround(x2)), static_cast<int16_t>(std::lround(y2))};
                wsd::Point p3{static_cast<int16_t>(std::lround(x)), static_cast<int16_t>(std::lround(y))};
                sampleCubicBezier(p0, cp1, cp2, p3, obj.points);
                curX = x; curY = y;
                break;
            }
            case 'Q': {
                double x1 = std::stod(tokens[i++]);
                double y1 = std::stod(tokens[i++]);
                double x = std::stod(tokens[i++]);
                double y = std::stod(tokens[i++]);
                wsd::Point p0{static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))};
                wsd::Point cp{static_cast<int16_t>(std::lround(x1)), static_cast<int16_t>(std::lround(y1))};
                wsd::Point p2{static_cast<int16_t>(std::lround(x)), static_cast<int16_t>(std::lround(y))};
                sampleQuadraticBezier(p0, cp, p2, obj.points);
                curX = x; curY = y;
                break;
            }
            case 'q': {
                double x1 = curX + std::stod(tokens[i++]);
                double y1 = curY + std::stod(tokens[i++]);
                double x = curX + std::stod(tokens[i++]);
                double y = curY + std::stod(tokens[i++]);
                wsd::Point p0{static_cast<int16_t>(std::lround(curX)), static_cast<int16_t>(std::lround(curY))};
                wsd::Point cp{static_cast<int16_t>(std::lround(x1)), static_cast<int16_t>(std::lround(y1))};
                wsd::Point p2{static_cast<int16_t>(std::lround(x)), static_cast<int16_t>(std::lround(y))};
                sampleQuadraticBezier(p0, cp, p2, obj.points);
                curX = x; curY = y;
                break;
            }
            case 'Z':
            case 'z': {
                if (!obj.points.empty()) {
                    obj.points.push_back(obj.points.front());
                }
                curX = startX; curY = startY;
                break;
            }
            default:
                ++i;
                break;
            }
        }

        if (obj.points.size() >= 2) {
            objects.push_back(obj);
        }
    }

    return objects;
}

} // namespace svg
