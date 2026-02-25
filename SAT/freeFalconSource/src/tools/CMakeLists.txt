# tools library

set(TOOLS_SOURCES
    bexpand/bexpand.cpp
    checksum/filelist.c
    checksum/md5c.c
    checksum/mddriver.c
    checksum/mdxhl.c
    eventmkr/eventmkr.cpp
    eventreader/eventreader.cpp
    eventreader/eventreaderdlg.cpp
    eventreader/stdafx.cpp
    fontmunge/font_raw.cpp
    fontmunge/fontres.cpp
    isbad/isbad.cpp
    makethr/makethr.cpp
    misstest/main.cpp
    misstest/stubs.cpp
    missvis/database.cpp
    missvis/linelist.cpp
    missvis/sim.cpp
    missvis/visualizer.cpp
    mono/debuggr.cpp
    mono/monodraw.cpp
    strcheck/fileio.cpp
    strcheck/main.cpp
    tacref/txt2bin/convert.cpp
    tactool/tactool.cpp
    ui_tools/addcode.cpp
    ui_tools/ascii.c
    ui_tools/decode.cpp
    ui_tools/delta.c
    ui_tools/flatrsc.cpp
    ui_tools/font_raw.cpp
    ui_tools/fontres.cpp
    ui_tools/genascii/genascii.cpp
    ui_tools/genids.cpp
    ui_tools/hash.cpp
    ui_tools/hexdump.c
    ui_tools/imagersc.cpp
    ui_tools/makeanim.c
    ui_tools/patchf4.cpp
    ui_tools/raw_font.cpp
    ui_tools/savefont.cpp
    ui_tools/soundrsc.cpp
    ui_tools/toupper.c
)

add_library(tools STATIC ${TOOLS_SOURCES})

target_include_directories(tools PRIVATE
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