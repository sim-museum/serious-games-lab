# missile library

set(MISSILE_SOURCES
    accel.cpp
    aero.cpp
    apprch.cpp
    atmos.cpp
    engine.cpp
    eom.cpp
    fcs.cpp
    flight.cpp
    gains.cpp
    guidance.cpp
    init1.cpp
    init2.cpp
    launch.cpp
    mavdisp.cpp
    misldisp.cpp
    missfunc.cpp
    missmain.cpp
    msltrail.cpp
    pitch.cpp
    readin.cpp
    seeker.cpp
    status.cpp
    target.cpp
    trig.cpp
    yaw.cpp
)

add_library(missile STATIC ${MISSILE_SOURCES})

target_include_directories(missile PRIVATE
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