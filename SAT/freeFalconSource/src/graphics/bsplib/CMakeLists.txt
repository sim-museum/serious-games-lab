# bsplib library

set(BSPLIB_SOURCES
    bspnodes.cpp
    colorbank.cpp
    objectinstance.cpp
    objectlod.cpp
    objectparent.cpp
    palbank.cpp
    polylib.cpp
    polylibclip.cpp
    polylibdraw.cpp
    polylibrestore.cpp
    scripts.cpp
    statestack.cpp
    stdafx.cpp
    texbank.cpp
    xobjectlod.cpp
)

add_library(bsplib STATIC ${BSPLIB_SOURCES})

target_include_directories(bsplib PRIVATE
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