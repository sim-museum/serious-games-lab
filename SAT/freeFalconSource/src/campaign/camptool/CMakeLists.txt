# camptool library

set(CAMPTOOL_SOURCES
    campdriv.cpp
    camptask/airunit.cpp
    camptask/atm.cpp
    camptask/battalio.cpp
    camptask/brigade.cpp
    camptask/division.cpp
    camptask/flight.cpp
    camptask/gndunit.cpp
    camptask/gtm.cpp
    camptask/gtmobj.cpp
    camptask/manager.cpp
    camptask/mission.cpp
    camptask/navunit.cpp
    camptask/ntm.cpp
    camptask/package.cpp
    camptask/squadron.cpp
    convert.cpp
    dialog.cpp
    display.cpp
    unitdlg.cpp
    wingraph.cpp
)

add_library(camptool STATIC ${CAMPTOOL_SOURCES})

target_include_directories(camptool PRIVATE
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