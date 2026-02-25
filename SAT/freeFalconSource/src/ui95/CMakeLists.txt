# ui95 library

set(UI95_SOURCES
    canim.cpp
    canimrc.cpp
    cbitmap.cpp
    cblip.cpp
    cbox.cpp
    cbuttons.cpp
    cclock.cpp
    ccolor.cpp
    ccontrol.cpp
    ccursor.cpp
    ccustom.cpp
    ceditbox.cpp
    cfill.cpp
    cfontres.cpp
    cfonts.cpp
    chandler.cpp
    chash.cpp
    chelp.cpp
    cimagerc.cpp
    cline.cpp
    clistbox.cpp
    cmarque.cpp
    cmovie.cpp
    cpanner.cpp
    cparser.cpp
    cpopmgr.cpp
    cpopup.cpp
    cresmgr.cpp
    csclbmp.cpp
    cscroll.cpp
    cslider.cpp
    csndbite.cpp
    csoundrc.cpp
    cstringrc.cpp
    ctext.cpp
    cthook.cpp
    ctile.cpp
    ctree.cpp
    cwindow.cpp
    imagersc.cpp
    ooutput.cpp
    soundrsc.cpp
    stdafx.cpp
    ui95_dd.cpp
)

add_library(ui95 STATIC ${UI95_SOURCES})

target_include_directories(ui95 PRIVATE
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