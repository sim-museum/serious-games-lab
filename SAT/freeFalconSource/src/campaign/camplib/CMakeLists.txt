# camplib library

set(CAMPLIB_SOURCES
    aiinput.cpp
    asearch.cpp
    atcbrain.cpp
    campbase.cpp
    campcell.cpp
    camplist.cpp
    campterr.cpp
    campwp.cpp
    cmpradar.cpp
    feature.cpp
    find.cpp
    listadt.cpp
    loadout.cpp
    name.cpp
    objectiv.cpp
    path.cpp
    persist.cpp
    ptdata.cpp
    relation.cpp
    team.cpp
    unit.cpp
    vehicle.cpp
)

add_library(camplib STATIC ${CAMPLIB_SOURCES})

target_include_directories(camplib PRIVATE
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