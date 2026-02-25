/*
 * FreeFalcon Linux Port - Debug Configuration
 *
 * Control debug output for the Linux port.
 * Define FF_LINUX_DEBUG to enable verbose debug output.
 * For production builds, leave FF_LINUX_DEBUG undefined.
 */

#ifndef FF_LINUX_DEBUG_H
#define FF_LINUX_DEBUG_H

#ifdef __cplusplus
#include <cstdio>
#else
#include <stdio.h>
#endif

// Uncomment the following line to enable debug output:
// #define FF_LINUX_DEBUG

// Uncomment the following line to enable RENDER debug output (very verbose):
// #define FF_LINUX_DEBUG_RENDER

#ifdef FF_LINUX_DEBUG
    // Debug output enabled - print to stderr
    #define FF_DEBUG(fmt, ...) fprintf(stderr, fmt, ##__VA_ARGS__)
    #define FF_DEBUG_JOYSTICK(fmt, ...) fprintf(stderr, "[JOYSTICK] " fmt, ##__VA_ARGS__)
    #define FF_DEBUG_INIT(fmt, ...) fprintf(stderr, "[INIT] " fmt, ##__VA_ARGS__)
    #define FF_DEBUG_CLEANUP(fmt, ...) fprintf(stderr, "[CLEANUP] " fmt, ##__VA_ARGS__)
    #define FF_DEBUG_UI(fmt, ...) fprintf(stderr, "[UI] " fmt, ##__VA_ARGS__)
    #define FF_DEBUG_INPUT(fmt, ...) fprintf(stderr, "[INPUT] " fmt, ##__VA_ARGS__)
    #define FF_DEBUG_FLUSH() fflush(stderr)
#else
    // Debug output disabled - compile to nothing
    #define FF_DEBUG(fmt, ...) do {} while(0)
    #define FF_DEBUG_JOYSTICK(fmt, ...) do {} while(0)
    #define FF_DEBUG_INIT(fmt, ...) do {} while(0)
    #define FF_DEBUG_CLEANUP(fmt, ...) do {} while(0)
    #define FF_DEBUG_UI(fmt, ...) do {} while(0)
    #define FF_DEBUG_INPUT(fmt, ...) do {} while(0)
    #define FF_DEBUG_FLUSH() do {} while(0)
#endif

// Render pipeline debug - controlled separately due to high volume
// Only log first N frames, then every Mth frame to reduce spam
#define FF_RENDER_DEBUG_FIRST_FRAMES 500
#define FF_RENDER_DEBUG_SAMPLE_INTERVAL 100

#ifdef FF_LINUX_DEBUG_RENDER
    // Always log unconditionally
    #define FF_DEBUG_RENDER(fmt, ...) fprintf(stderr, "[RENDER] " fmt, ##__VA_ARGS__)
    // Frame-gated logging - only log first N frames, then every Mth frame
    #define FF_DEBUG_RENDER_FRAME(frame, fmt, ...) do { \
        unsigned long _f = (unsigned long)(frame); \
        if (_f <= FF_RENDER_DEBUG_FIRST_FRAMES || (_f % FF_RENDER_DEBUG_SAMPLE_INTERVAL) == 0) { \
            fprintf(stderr, "[RENDER:%lu] " fmt, _f, ##__VA_ARGS__); \
        } \
    } while(0)
    #define FF_DEBUG_RENDER_FLUSH() fflush(stderr)
#else
    #define FF_DEBUG_RENDER(fmt, ...) do {} while(0)
    #define FF_DEBUG_RENDER_FRAME(frame, fmt, ...) do {} while(0)
    #define FF_DEBUG_RENDER_FLUSH() do {} while(0)
#endif

// Error output - always enabled (for actual errors)
#define FF_ERROR(fmt, ...) fprintf(stderr, "[ERROR] " fmt, ##__VA_ARGS__)

// Info output - for important non-debug messages (startup info, etc.)
// Can be disabled by defining FF_LINUX_QUIET
#ifndef FF_LINUX_QUIET
    #define FF_INFO(fmt, ...) printf(fmt, ##__VA_ARGS__)
#else
    #define FF_INFO(fmt, ...) do {} while(0)
#endif

#endif // FF_LINUX_DEBUG_H
