# resmgr library

set(RESMGR_SOURCES
    src/inflate.c
    src/resmgr.c
    src/test.c
    src/unzip.c
)

add_library(resmgr STATIC ${RESMGR_SOURCES})

target_include_directories(resmgr PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${FF_SRC_DIR}
    ${FF_SRC_DIR}/include
    ${FF_SRC_DIR}/falclib/include
    ${FF_SRC_DIR}/codelib/include
    ${FF_SRC_DIR}/codelib/tools/lists
    ${FF_SRC_DIR}/vu2/include
    ${FF_SRC_DIR}/sim/include
    ${FF_SRC_DIR}/campaign/include
    ${FF_SRC_DIR}/ui/include
    ${FF_SRC_DIR}/graphics/include
)