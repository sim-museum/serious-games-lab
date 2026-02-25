# FreeFalcon source directory CMakeLists.txt

# Build all libraries first
# Core libraries (no dependencies on other FF libs)
add_subdirectory(compat)          # Compatibility layer (must be first)
add_subdirectory(codelib)         # Code library utilities
add_subdirectory(mathlib)         # Math library (header-only)

# VU2 - Virtual Universe library
add_subdirectory(vu2)

# FalcLib - Core falcon library
add_subdirectory(falclib)

# Graphics subsystem
add_subdirectory(graphics)

# Sound
add_subdirectory(falcsnd)

# Campaign system
add_subdirectory(campaign)

# Simulation subsystem
add_subdirectory(sim)

# UI system
add_subdirectory(ui95)
add_subdirectory(ui95_ext)
add_subdirectory(ui)

# Communications
add_subdirectory(comms)

# Utilities
add_subdirectory(acmi)
if(WIN32)
    add_subdirectory(tools)    # Tools have many incomplete files, Windows-only for now
    add_subdirectory(movie)    # Movie uses Video for Windows APIs
endif()

# Crash handler (Linux will have stub implementation)
add_subdirectory(crashhandler)

# Main executable
add_subdirectory(ffviper)
