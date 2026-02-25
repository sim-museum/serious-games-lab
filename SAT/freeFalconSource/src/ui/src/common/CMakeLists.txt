# common library

set(COMMON_SOURCES
    ato.cpp
    common.cpp
    events.cpp
    filters.cpp
    gps.cpp
    icondefs.cpp
    missions.cpp
    oob.cpp
    printer.cpp
    targets.cpp
    teamdata.cpp
    units.cpp
    urefresh.cpp
    waypoint.cpp
)

add_library(common STATIC ${COMMON_SOURCES})

target_include_directories(common PRIVATE
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