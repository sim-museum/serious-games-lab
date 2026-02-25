# rwr library

set(RWR_SOURCES
    advancedhts.cpp
    alr56.cpp
    detect.cpp
    easyhts.cpp
    harmpod.cpp
    harmseeker.cpp
    playerrwr.cpp
    rwr.cpp
    tracklst.cpp
    vehrwr.cpp
)

add_library(rwr STATIC ${RWR_SOURCES})

target_include_directories(rwr PRIVATE
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