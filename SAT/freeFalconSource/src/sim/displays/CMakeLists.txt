# displays library

set(DISPLAYS_SOURCES
    blankmfd.cpp
    bombsms.cpp
    datainput.cpp
    drawable.cpp
    dtemfd.cpp
    flcsmfd.cpp
    flirmfd.cpp
    gndhud.cpp
    gunhud.cpp
    gunsms.cpp
    hadmfd.cpp
    helpers.cpp
    hud.cpp
    invsms.cpp
    lantirn.cpp
    lantmfd.cpp
    menumfd.cpp
    mfd.cpp
    mislhud.cpp
    mslsms.cpp
    navhud.cpp
    sms.cpp
    smsdraw.cpp
    testmfd.cpp
    tgpmfd.cpp
    wpnmfd.cpp
)

add_library(displays STATIC ${DISPLAYS_SOURCES})

target_include_directories(displays PRIVATE
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