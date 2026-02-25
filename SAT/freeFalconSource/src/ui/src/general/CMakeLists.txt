# uigeneral library

set(UIGENERAL_SOURCES
    c3dview.cpp
    cbsplist.cpp
    rle.cpp
    targa.cpp
    uihash.cpp
    viewer.cpp
)

add_library(uigeneral STATIC ${UIGENERAL_SOURCES})

target_include_directories(uigeneral PRIVATE
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