# campaign library

set(CAMPAIGN_SOURCES
    campaign.cpp
    camphack.cpp
    campmenu.cpp
    cmap.cpp
    cpselect.cpp
    cstores.cpp
    general.cpp
    munition.cpp
    planner.cpp
    priority.cpp
)

add_library(campaign STATIC ${CAMPAIGN_SOURCES})

target_include_directories(campaign PRIVATE
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