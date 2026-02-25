# comms library

set(COMMS_SOURCES
    capi.c
    capibwcontrol.cpp
    capibwfsm.cpp
    comlist.cpp
    rudp.c
    tcp.c
    udp.c
    ws2init.c
)

# Windows-specific networking files (DirectPlay, multicast, protocol enumeration)
if(WIN32)
    list(APPEND COMMS_SOURCES
        comdplay.c
        fndproto.c
        mcast.c
        protofilt.c
        useprot.c
        winverx.c
    )
endif()

add_library(comms STATIC ${COMMS_SOURCES})

target_include_directories(comms PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
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