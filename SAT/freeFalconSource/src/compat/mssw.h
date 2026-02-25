/*
 * FreeFalcon Linux Port - mssw.h compatibility
 *
 * Miles Sound System types and definitions - stubs for Linux
 */

#ifndef FF_COMPAT_MSSW_H
#define FF_COMPAT_MSSW_H

#ifdef FF_LINUX

#include <stdint.h>

/* Miles Sound System basic types */
typedef int8_t   S8;
typedef int16_t  S16;
typedef int32_t  S32;
typedef uint8_t  U8;
typedef uint16_t U16;
typedef uint32_t U32;

/* Floating point types */
typedef float    F32;
typedef double   F64;

/* Boolean type */
typedef int32_t  AILBOOL;

/* Pointer types */
typedef void*    HDIGDRIVER;
typedef void*    HMDIDRIVER;
typedef void*    HSAMPLE;
typedef void*    HSTREAM;
typedef void*    HDLSFILE;
typedef void*    AILPROVIDER;
typedef void*    AILPROVINSTANCE;
typedef void*    H3DPOBJECT;
typedef void*    H3DSAMPLE;

/* Miles Sound API stubs - these will all return failure or do nothing */

#define AIL_startup() (0)
#define AIL_shutdown()

#define AIL_set_redist_directory(dir)
#define AIL_waveOutOpen(hDigDriver, device, rate, bits, channels) (0)
#define AIL_waveOutClose(hDigDriver)

#define AIL_allocate_sample_handle(hDigDriver) ((HSAMPLE)NULL)
#define AIL_release_sample_handle(hSample)
#define AIL_init_sample(hSample)
#define AIL_set_sample_file(hSample, data, loop) (0)
#define AIL_start_sample(hSample)
#define AIL_stop_sample(hSample)
#define AIL_sample_status(hSample) (0)
#define AIL_set_sample_volume(hSample, vol)
#define AIL_set_sample_pan(hSample, pan)
#define AIL_set_sample_playback_rate(hSample, rate)
#define AIL_set_sample_loop_count(hSample, count)

/* Status values */
#define SMP_FREE        0
#define SMP_DONE        1
#define SMP_PLAYING     2
#define SMP_STOPPED     3

#endif /* FF_LINUX */
#endif /* FF_COMPAT_MSSW_H */
