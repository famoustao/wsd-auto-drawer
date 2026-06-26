cmake_minimum_required(VERSION 3.20)
project(WSDAutoDrawer VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

# Qt6
find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)

# 包含 tinyxml2 源码
set(TINYXML2_SRC ${CMAKE_SOURCE_DIR}/third_party/tinyxml2/tinyxml2.cpp)

# 核心库
set(CORE_SRC
    src/wsd_format.cpp
    src/wsd_parser.cpp
    src/wsd_writer.cpp
    src/svg_parser.cpp
    src/converter.cpp
)

set(CORE_HEADERS
    src/wsd_format.h
    src/wsd_parser.h
    src/wsd_writer.h
    src/svg_parser.h
    src/converter.h
)

# GUI 源文件
set(GUI_SRC
    src/gui/mainwindow.cpp
    src/gui/mainwindow.ui
)

set(GUI_HEADERS
    src/gui/mainwindow.h
)

# 可执行文件
add_executable(${PROJECT_NAME}
    src/main.cpp
    ${CORE_SRC}
    ${CORE_HEADERS}
    ${GUI_SRC}
    ${GUI_HEADERS}
    ${TINYXML2_SRC}
)

target_include_directories(${PROJECT_NAME} PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/third_party/tinyxml2
)

target_link_libraries(${PROJECT_NAME} PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
)

# Windows 设置
if(WIN32)
    set_target_properties(${PROJECT_NAME} PROPERTIES
        WIN32_EXECUTABLE TRUE
    )
endif()

# 安装
install(TARGETS ${PROJECT_NAME}
    RUNTIME DESTINATION bin
)
