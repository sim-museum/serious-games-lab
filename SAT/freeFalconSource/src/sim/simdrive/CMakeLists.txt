# simdrive library

set(SIMDRIVE_SOURCES
    finders.cpp
    rtloop.cpp
    simatc.cpp
    simdrive.cpp
    simvucb.cpp
)

add_library(simdrive STATIC ${SIMDRIVE_SOURCES})

target_include_directories(simdrive PRIVATE
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