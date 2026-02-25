# fcc library

set(FCC_SOURCES
    fccmain.cpp
    grndfcc.cpp
    harmfcc.cpp
    lgbfcc.cpp
    mavfcc.cpp
    mislfcc.cpp
    navfcc.cpp
)

add_library(fcc STATIC ${FCC_SOURCES})

target_include_directories(fcc PRIVATE
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