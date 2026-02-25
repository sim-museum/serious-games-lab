# otwdrive library

set(OTWDRIVE_SOURCES
    access.cpp
    addobj.cpp
    cockpit.cpp
    drawobjs.cpp
    external.cpp
    eyefly.cpp
    menus.cpp
    otwdrive.cpp
    otwlist.cpp
    otwloop.cpp
    padefov.cpp
    padf3.cpp
    padlock.cpp
    radiosubtitle.cpp
    sfx.cpp
    splash.cpp
    trainingscript.cpp
    usrinput.cpp
    vcock.cpp
    vdials.cpp
    xfrm.cpp
)

add_library(otwdrive STATIC ${OTWDRIVE_SOURCES})

target_include_directories(otwdrive PRIVATE
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