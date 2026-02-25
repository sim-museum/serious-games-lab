# uicomms library

set(UICOMMS_SOURCES
    cpcomms.cpp
    cphoneb.cpp
    dfcomms.cpp
    info.cpp
    phonebk.cpp
    queue.cpp
    remotelb.cpp
    serverbrowser.cpp
    stats.cpp
    ui_comms.cpp
    uicomms.cpp
)

add_library(uicomms STATIC ${UICOMMS_SOURCES})

target_include_directories(uicomms PRIVATE
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