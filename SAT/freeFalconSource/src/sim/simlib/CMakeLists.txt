# simlib library

set(SIMLIB_SOURCES
    datafile.cpp
    file.cpp
    geometry.cpp
    handoff.cpp
    io.cpp
    math.cpp
    memory.cpp
    message.cpp
    ownresult.cpp
    pilotinputs.cpp
    resstub.c
    sensclas.cpp
    simbase.cpp
    simfiltr.cpp
    simmover.cpp
    simobj.cpp
    simstatic.cpp
    simveh.cpp
    simvudrv.cpp
    simweapn.cpp
    stubs.cpp
    timer.cpp
    vehdef.cpp
    wpnstatn.cpp
)

add_library(simlib STATIC ${SIMLIB_SOURCES})

target_include_directories(simlib PRIVATE
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