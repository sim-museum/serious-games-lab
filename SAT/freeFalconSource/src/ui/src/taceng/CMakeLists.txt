# uitaceng library

set(UITACENG_SOURCES
    tac_class.cpp
    tac_victory_conditions.cpp
    te_flight.cpp
    te_flow.cpp
    te_list.cpp
    te_map.cpp
    te_setup.cpp
    te_team.cpp
    te_team_victory.cpp
    te_territory_editor.cpp
    te_toolbar.cpp
    te_units.cpp
    ui_taceng.cpp
)

add_library(uitaceng STATIC ${UITACENG_SOURCES})

target_include_directories(uitaceng PRIVATE
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