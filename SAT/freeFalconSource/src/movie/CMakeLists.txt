# movie library

set(MOVIE_SOURCES
    avimovie.c
    avimovie.cpp
    riffio.c
    riffio.cpp
    surface.c
    surface.cpp
    test.c
    test.cpp
)

add_library(movie STATIC ${MOVIE_SOURCES})

target_include_directories(movie PRIVATE
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