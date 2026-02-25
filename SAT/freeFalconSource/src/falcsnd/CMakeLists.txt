# falcsnd library

set(FALCSND_SOURCES
    adpcm.cpp
    falcvoice.cpp
    fsound.cpp
    imadpcm.cpp
    lhsp.cpp
    mlrvoice.cpp
    mlrvoicehandle.cpp
    msima.cpp
    psound.cpp
    silence.cpp
    soundfx.cpp
    transprt.cpp
    voicefilter.cpp
    voicemanager.cpp
    voicemapper.cpp
    winampfrontend.cpp
)

add_library(falcsnd STATIC ${FALCSND_SOURCES})

target_include_directories(falcsnd PRIVATE
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