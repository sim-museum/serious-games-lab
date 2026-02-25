# acmi library

set(ACMI_SOURCES
    src/acmicam.cpp
    src/acmihash.cpp
    src/acmiloop.cpp
    src/acmirec.cpp
    src/acmitape.cpp
    src/acmiui.cpp
    src/acmiview.cpp
    # These are inline implementation files that are #included from headers, not standalone sources
    # src/include/acmcminl.cpp
    # src/include/acmtpinl.cpp
    # src/include/acmvwinl.cpp
)

add_library(acmi STATIC ${ACMI_SOURCES})

target_include_directories(acmi PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/src/include
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