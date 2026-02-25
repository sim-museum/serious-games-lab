# radar library

set(RADAR_SOURCES
    beam.cpp
    beamrider.cpp
    bscope.cpp
    detect.cpp
    gmscope.cpp
    modes.cpp
    radar.cpp
    radar360.cpp
    radaragonly.cpp
    radardigi.cpp
    radardoppler.cpp
    radarmissile.cpp
    radarsuper.cpp
    state.cpp
)

add_library(radar STATIC ${RADAR_SOURCES})

target_include_directories(radar PRIVATE
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