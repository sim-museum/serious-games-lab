# feature library

set(FEATURE_SOURCES
    atcbrain.cpp
    damage.cpp
    # feature.cpp - removed: simfeature.cpp is the more complete version with same class definitions
    simfeature.cpp
)

add_library(feature STATIC ${FEATURE_SOURCES})

target_include_directories(feature PRIVATE
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