# mathlib - header-only math library

add_library(mathlib INTERFACE)

target_include_directories(mathlib INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}
)
