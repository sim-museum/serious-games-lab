# uidogfight library

set(UIDOGFIGHT_SOURCES
    dfscores.cpp
    dogfight.cpp
    dogmenus.cpp
)

add_library(uidogfight STATIC ${UIDOGFIGHT_SOURCES})

target_include_directories(uidogfight PRIVATE
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