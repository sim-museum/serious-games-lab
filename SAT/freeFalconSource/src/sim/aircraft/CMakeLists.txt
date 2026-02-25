# aircraft library

set(AIRCRAFT_SOURCES
    acturbulence.cpp
    aircraft.cpp
    aircraftinputs.cpp
    cautions.cpp
    chafflare.cpp
    damage.cpp
    doweapon.cpp
    electrics.cpp
    gloc.cpp
    gndhndl.cpp
    ins.cpp
    surface.cpp
    turbulence.cpp
    virtuals.cpp
)

add_library(aircraft STATIC ${AIRCRAFT_SOURCES})

target_include_directories(aircraft PRIVATE
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