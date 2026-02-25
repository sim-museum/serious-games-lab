/*
 * FreeFalcon Linux Port - mmreg.h compatibility
 *
 * Windows Multimedia Registry types - additional format definitions
 */

#ifndef FF_COMPAT_MMREG_H
#define FF_COMPAT_MMREG_H

#ifdef FF_LINUX

#include "compat_mmsystem.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Additional WAVE format tags (from Windows mmreg.h) */
#ifndef WAVE_FORMAT_UNKNOWN
#define WAVE_FORMAT_UNKNOWN                 0x0000
#endif
#ifndef WAVE_FORMAT_PCM
#define WAVE_FORMAT_PCM                     0x0001
#endif
#ifndef WAVE_FORMAT_ADPCM
#define WAVE_FORMAT_ADPCM                   0x0002
#endif
#ifndef WAVE_FORMAT_IEEE_FLOAT
#define WAVE_FORMAT_IEEE_FLOAT              0x0003
#endif
#define WAVE_FORMAT_ALAW                    0x0006
#define WAVE_FORMAT_MULAW                   0x0007
#define WAVE_FORMAT_IMA_ADPCM               0x0011
#define WAVE_FORMAT_GSM610                  0x0031
#define WAVE_FORMAT_MPEG                    0x0050
#define WAVE_FORMAT_MPEGLAYER3              0x0055

/* IMA ADPCM specific structures */
typedef struct imaadpcmwaveformat_tag {
    WAVEFORMATEX wfx;
    WORD         wSamplesPerBlock;
} IMAADPCMWAVEFORMAT;

typedef IMAADPCMWAVEFORMAT* PIMAADPCMWAVEFORMAT;
typedef IMAADPCMWAVEFORMAT* NPIMAADPCMWAVEFORMAT;
typedef IMAADPCMWAVEFORMAT* LPIMAADPCMWAVEFORMAT;

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_MMREG_H */
