# Graphics utils library (renamed to avoid system conflict)

set(GFX_UTILS_SOURCES
    loader.cpp
    matrix.cpp
    setup.cpp
    timemgr.cpp
)

add_library(gfx_utils STATIC ${GFX_UTILS_SOURCES})

target_include_directories(gfx_utils PRIVATE
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