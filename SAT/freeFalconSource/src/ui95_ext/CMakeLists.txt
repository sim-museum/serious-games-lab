# ui95_ext library

set(UI95_EXT_SOURCES
    cbeye.cpp
    cdogflt.cpp
    cdrawlst.cpp
    centity.cpp
    cfeature.cpp
    cflight.cpp
    chistory.cpp
    cicons.cpp
    clevel.cpp
    cmapmvr.cpp
    cmission.cpp
    cpackage.cpp
    cpilot.cpp
    cplayer.cpp
    csquad.cpp
    cthreat.cpp
    cvictory.cpp
    cwaypnt.cpp
    stdafx.cpp
)

add_library(ui95_ext STATIC ${UI95_EXT_SOURCES})

target_include_directories(ui95_ext PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${FF_SRC_DIR}
    ${FF_SRC_DIR}/include
    ${FF_SRC_DIR}/falclib/include
    ${FF_SRC_DIR}/codelib/include
    ${FF_SRC_DIR}/vu2/include
    ${FF_SRC_DIR}/sim/include
    ${FF_SRC_DIR}/campaign/include
    ${FF_SRC_DIR}/ui/include
    ${FF_SRC_DIR}/ui95
    ${FF_SRC_DIR}/graphics/include
)