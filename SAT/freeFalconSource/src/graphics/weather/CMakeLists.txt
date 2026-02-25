# weather library

set(WEATHER_SOURCES
    real2dcloud.cpp
    real3dcloud.cpp
    realweather.cpp
    star.cpp
    tod.cpp
)

add_library(weather STATIC ${WEATHER_SOURCES})

target_include_directories(weather PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${FF_SRC_DIR}
    ${FF_SRC_DIR}/include
    ${FF_SRC_DIR}/falclib/include
    ${FF_SRC_DIR}/codelib/include
    ${FF_SRC_DIR}/vu2/include
    ${FF_SRC_DIR}/sim/include
    ${FF_SRC_DIR}/campaign/include
    ${FF_SRC_DIR}/ui/include
    ${FF_SRC_DIR}/graphics/include
)