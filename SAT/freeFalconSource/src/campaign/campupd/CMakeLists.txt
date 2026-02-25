# campupd library

set(CAMPUPD_SOURCES
    campaign.cpp
    cmpclass.cpp
    cmpevent.cpp
    dogfight.cpp
    gamemgr.cpp
    iaction.cpp
    nofly.cpp
    scores.cpp
    supply.cpp
    tactics.cpp
    update.cpp
    weather.cpp
)

add_library(campupd STATIC ${CAMPUPD_SOURCES})

target_include_directories(campupd PRIVATE
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