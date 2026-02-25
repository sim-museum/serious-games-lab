# airframe library

set(AIRFRAME_SOURCES
    aero.cpp
    afsimple.cpp
    airframe.cpp
    atmos.cpp
    axial.cpp
    cruise.cpp
    engine.cpp
    eom.cpp
    fcs.cpp
    gain.cpp
    gear.cpp
    init.cpp
    limiters.cpp
    meters.cpp
    pitch.cpp
    readin.cpp
    roll.cpp
    supersimple.cpp
    trig.cpp
    trim.cpp
    turbulence.cpp
    yaw.cpp
)

add_library(airframe STATIC ${AIRFRAME_SOURCES})

target_include_directories(airframe PRIVATE
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