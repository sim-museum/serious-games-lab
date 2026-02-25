# icp library

set(ICP_SOURCES
    icp.cpp
    icpalow.cpp
    icpbackup.cpp
    icpcni.cpp
    icpcniswitch.cpp
    icpcomm.cpp
    icpcrus.cpp
    icpdlink.cpp
    icpenter.cpp
    icpfack.cpp
    icpiff.cpp
    icpils.cpp
    icplist.cpp
    icpmark.cpp
    icpmisc.cpp
    icpmiscfuncs.cpp
    icpnumbers.cpp
    icpstpt.cpp
    magvar.c
    scratchpad.cpp
)

add_library(icp STATIC ${ICP_SOURCES})

target_include_directories(icp PRIVATE
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