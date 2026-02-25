# digi library

set(DIGI_SOURCES
    actions.cpp
    autopilot.cpp
    bvrengage.cpp
    cavoid.cpp
    digifunc.cpp
    digimain.cpp
    dlogic.cpp
    facbrain.cpp
    flitlead.cpp
    formdata.cpp
    gengage.cpp
    gndattck.cpp
    ground.cpp
    gunsjink.cpp
    handlethreat.cpp
    landme.cpp
    mdefeat.cpp
    mengage.cpp
    merge.cpp
    mnvers.cpp
    randp.cpp
    refuel.cpp
    separate.cpp
    sfusion.cpp
    simbrain.cpp
    tankbrn.cpp
    targeting.cpp
    waypoint.cpp
    wingactions.cpp
    wingai.cpp
    winglogic.cpp
    wingman.cpp
    wingmnvers.cpp
    wingorder.cpp
    wingradio.cpp
    wvrengage.cpp
)

add_library(digi STATIC ${DIGI_SOURCES})

target_include_directories(digi PRIVATE
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