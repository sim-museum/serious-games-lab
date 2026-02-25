# helo library

set(HELO_SOURCES
    chafflare.cpp
    damage.cpp
    doweapon.cpp
    h_damage.cpp
    h_doweapon.cpp
    h_inputs.cpp
    helimain.cpp
    helimm.cpp
    inputs.cpp
)

add_library(helo STATIC ${HELO_SOURCES})

target_include_directories(helo PRIVATE
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