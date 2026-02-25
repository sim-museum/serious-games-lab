# FreeFalcon - Cross-platform CMake build system
# This is the Linux port of the FreeFalcon flight simulator
cmake_minimum_required(VERSION 3.16)
project(FreeFalcon VERSION 6.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug CACHE STRING "Build type" FORCE)
endif()

# Options
option(FF_USE_SDL2 "Use SDL2 for window/input/audio" ON)
option(FF_USE_OPENGL "Use OpenGL for rendering" ON)
option(FF_USE_OPENAL "Use OpenAL for 3D audio" ON)

# Platform detection
if(WIN32)
    set(FF_PLATFORM_WINDOWS TRUE)
    add_compile_definitions(WIN32 _WINDOWS)
elseif(UNIX AND NOT APPLE)
    set(FF_PLATFORM_LINUX TRUE)
    add_compile_definitions(FF_LINUX)
    # Force-include the compat types header for all source files
    add_compile_options(-include ${CMAKE_CURRENT_SOURCE_DIR}/src/compat/compat_types.h)
elseif(APPLE)
    set(FF_PLATFORM_MACOS TRUE)
    add_compile_definitions(FF_MACOS)
endif()

# Compiler flags
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(
        -Wall
        -Wno-unused-variable
        -Wno-unused-but-set-variable
        -Wno-sign-compare
        -Wno-parentheses
        -Wno-missing-braces
        -Wno-switch
        -Wno-write-strings
        -Wno-narrowing
        # Relaxed warnings for legacy code
        -Wno-format-security
        -Wno-format
        -fpermissive
    )

    # Debug flags
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        add_compile_options(-g -O0)
        add_compile_definitions(_DEBUG)
    else()
        add_compile_options(-O2)
        add_compile_definitions(NDEBUG)
    endif()
endif()

# Common preprocessor definitions (matching VS project)
add_compile_definitions(
    STRICT
    _CRT_NONSTDC_NO_DEPRECATE
    _CRT_SECURE_NO_WARNINGS
)

# Find required packages for Linux
if(FF_PLATFORM_LINUX)
    # SDL2
    if(FF_USE_SDL2)
        find_package(SDL2 QUIET)
        find_package(SDL2_image QUIET)
        find_package(SDL2_mixer QUIET)
        if(NOT SDL2_FOUND)
            message(WARNING "SDL2 not found - install with: sudo apt install libsdl2-dev")
        endif()
    endif()

    # OpenGL
    if(FF_USE_OPENGL)
        find_package(OpenGL QUIET)
        find_package(GLEW QUIET)
        if(NOT OPENGL_FOUND)
            message(WARNING "OpenGL not found - install with: sudo apt install libgl-dev")
        endif()
        if(NOT GLEW_FOUND)
            message(WARNING "GLEW not found - install with: sudo apt install libglew-dev")
        endif()
    endif()

    # OpenAL
    if(FF_USE_OPENAL)
        find_package(OpenAL QUIET)
        if(NOT OPENAL_FOUND)
            message(WARNING "OpenAL not found - install with: sudo apt install libopenal-dev")
        endif()
    endif()

    # Threads
    find_package(Threads REQUIRED)
endif()

# Source directory
set(FF_SRC_DIR ${CMAKE_SOURCE_DIR}/src)

# Global include directories
include_directories(
    ${FF_SRC_DIR}
    ${FF_SRC_DIR}/compat          # Our compatibility headers
    ${FF_SRC_DIR}/include
    ${FF_SRC_DIR}/falclib/include
    ${FF_SRC_DIR}/codelib/include
    ${FF_SRC_DIR}/vu2/include
    ${FF_SRC_DIR}/sim/include
    ${FF_SRC_DIR}/campaign/include
    ${FF_SRC_DIR}/ui/include
    ${FF_SRC_DIR}/graphics/include
    ${FF_SRC_DIR}/amd/inc
    ${FF_SRC_DIR}/comms
)

# Platform-specific includes (only if packages found)
if(FF_PLATFORM_LINUX)
    if(SDL2_FOUND)
        include_directories(${SDL2_INCLUDE_DIRS})
    endif()
    if(OPENGL_FOUND)
        include_directories(${OPENGL_INCLUDE_DIR})
    endif()
    if(GLEW_FOUND)
        include_directories(${GLEW_INCLUDE_DIRS})
    endif()
    if(OPENAL_FOUND)
        include_directories(${OPENAL_INCLUDE_DIR})
    endif()
endif()

# Add subdirectories (libraries first, then executable)
add_subdirectory(src)
