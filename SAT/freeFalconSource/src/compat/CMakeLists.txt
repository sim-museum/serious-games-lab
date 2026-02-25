# Compatibility layer library
# Provides Windows API compatibility for Linux

if(FF_PLATFORM_LINUX)
    # On Linux, we need stub implementations for some Windows functions
    add_library(compat STATIC
        linux_stubs_c.cpp
        linux_stubs.cpp
        d3d_gl.cpp
        openal_dsound.cpp
        ${CMAKE_SOURCE_DIR}/src/utils/lzss.cpp  # FF_LINUX: LZSS compression used by campaign
    )

    target_include_directories(compat PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_SOURCE_DIR}/src  # For utils/lzss.h and utils/LZSSopt.h
    )

    target_compile_definitions(compat PUBLIC FF_LINUX)
else()
    # On Windows, this is a header-only compatibility layer
    add_library(compat INTERFACE)

    target_include_directories(compat INTERFACE
        ${CMAKE_CURRENT_SOURCE_DIR}
    )
endif()
