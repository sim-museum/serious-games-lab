# camptask library

set(CAMPTASK_SOURCES
    airunit.cpp
    atm.cpp
    battalio.cpp
    brigade.cpp
    division.cpp
    flight.cpp
    gndunit.cpp
    gtm.cpp
    gtmobj.cpp
    manager.cpp
    mission.cpp
    navunit.cpp
    ntm.cpp
    package.cpp
    squadron.cpp
)

add_library(camptask STATIC ${CAMPTASK_SOURCES})

target_include_directories(camptask PRIVATE
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