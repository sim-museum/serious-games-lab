# vu2 library

set(VU2_SOURCES
    src/vu.cpp
    # src/vu_anti_database.cpp  # Disabled - VuAntiDatabase class is #if 0'd in vucoll.h
    src/vu_association_filter.cpp
    src/vu_bi_key_filter.cpp
    src/vu_collection_manager.cpp
    src/vu_database.cpp
    src/vu_database_iterator.cpp
    # src/vu_fifo_queue.cpp     # Disabled - VuFifoQueue class is #if 0'd in vucoll.h
    src/vu_filter.cpp
    src/vu_filtered_hash_table.cpp
    src/vu_filtered_list.cpp
    src/vu_full_grid_iterator.cpp
    src/vu_gc.cpp
    src/vu_grid_iterator.cpp
    src/vu_grid_tree.cpp
    src/vu_hash_iterator.cpp
    src/vu_hash_table.cpp
    # src/vu_id.cpp         # Disabled - VU_ID methods already defined inline in vutypes.h
    src/vu_iterator.cpp
    src/vu_key_filter.cpp
    # src/vu_lifo_queue.cpp     # Disabled - VuLifoQueue class is #if 0'd in vucoll.h
    src/vu_line_iterator.cpp
    src/vu_linked_list.cpp
    src/vu_list_iterator.cpp
    src/vu_list_mucky_iterator.cpp
    src/vu_mf.cpp
    src/vu_mq.cpp
    src/vu_nat.cpp
    src/vu_opaque_filter.cpp
    src/vu_ordered_list.cpp
    src/vu_rb_iterator.cpp
    # src/vu_rb_node.cpp   # Disabled - VuRBNode class removed when VU_ALL_FILTERED=1
    src/vu_rb_tree.cpp
    # src/vu_session_id.cpp  # Disabled - VU_SESSION_ID methods already defined inline in vutypes.h
    src/vu_standard_filter.cpp
    src/vu_thread.cpp
    src/vu_transmission_filter.cpp
    src/vu_type_filter.cpp
    # src/vu_update_counter.cpp  # Disabled - VU_UPDATE_COUNTER class not defined anywhere
    src/vucoll.cpp
    src/vudriver.cpp
    src/vuentity.cpp
    src/vuevent.cpp
    src/vusessn.cpp
)

add_library(vu2 STATIC ${VU2_SOURCES})

target_include_directories(vu2 PRIVATE
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
    ${FF_SRC_DIR}/comms
)