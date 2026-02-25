# guns library

set(GUNS_SOURCES
    guns.cpp
    gunsfunc.cpp
    shells.cpp
    tracers.cpp
)

add_library(guns STATIC ${GUNS_SOURCES})

target_include_directories(guns PRIVATE
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