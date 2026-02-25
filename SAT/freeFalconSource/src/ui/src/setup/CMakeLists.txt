# uisetup library

set(UISETUP_SOURCES
    controltab.cpp
    graphicstab.cpp
    keydescrips.cpp
    simoptn.cpp
    simtab.cpp
    soundtab.cpp
    ui_setup.cpp
)

add_library(uisetup STATIC ${UISETUP_SOURCES})

target_include_directories(uisetup PRIVATE
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