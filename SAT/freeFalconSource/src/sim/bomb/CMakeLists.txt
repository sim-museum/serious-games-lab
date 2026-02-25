# bomb library

set(BOMB_SOURCES
    bombfunc.cpp
    bombmain.cpp
    chaffmain.cpp
    debrismain.cpp
    flaremain.cpp
    lau.cpp
    readin.cpp
)

add_library(bomb STATIC ${BOMB_SOURCES})

target_include_directories(bomb PRIVATE
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