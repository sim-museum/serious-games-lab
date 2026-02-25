# hdigi library

set(HDIGI_SOURCES
    actions.cpp
    cavoid.cpp
    digimain.cpp
    dlogic.cpp
    engage.cpp
    flitlead.cpp
    gengage.cpp
    ground.cpp
    gunsjink.cpp
    h_actions.cpp
    h_cavoid.cpp
    h_digimain.cpp
    h_dlogic.cpp
    h_engage.cpp
    h_flitlead.cpp
    h_gengage.cpp
    h_gunsjink.cpp
    h_landme.cpp
    h_mdefeat.cpp
    h_mengage.cpp
    h_mnvers.cpp
    h_randp.cpp
    h_sfusion.cpp
    h_waypoint.cpp
    h_wingman.cpp
    landme.cpp
    mdefeat.cpp
    mengage.cpp
    # mnvers.cpp - removed: h_mnvers.cpp defines the same HeliBrain methods
    randp.cpp
    sfusion.cpp
    waypoint.cpp
    wingman.cpp
)

add_library(hdigi STATIC ${HDIGI_SOURCES})

target_include_directories(hdigi PRIVATE
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