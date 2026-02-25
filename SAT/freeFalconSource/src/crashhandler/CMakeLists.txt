# crashhandler library

if(WIN32)
    set(CRASHHANDLER_SOURCES
        allocandfillprocessmodulelist.cpp
        bsufunctions.cpp
        crashhandler.cpp
        diagassert.cpp
        getloadedmodules.cpp
        hookimportedfunctionbyname.cpp
        isnt.cpp
        memdumpervalidator.cpp
        nt4processinfo.cpp
        pch.cpp
        tlhelpprocessinfo.cpp
    )
else()
    # Linux uses a stub implementation
    set(CRASHHANDLER_SOURCES
        crashhandler_linux.cpp
    )
endif()

add_library(crashhandler STATIC ${CRASHHANDLER_SOURCES})

target_include_directories(crashhandler PRIVATE
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