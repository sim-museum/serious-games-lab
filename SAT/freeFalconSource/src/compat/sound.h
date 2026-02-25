/*
 * FreeFalcon Linux Port - sound.h compatibility
 *
 * Sound system definitions
 */

#ifndef FF_COMPAT_SOUND_H
#define FF_COMPAT_SOUND_H

#ifdef FF_LINUX

#include "mssw.h"
#include "compat_types.h"

/* IMA ADPCM block header - same structure as IMA_BLOCK in psound.h */
typedef struct ImaBlockHeader_tag {
    short iSamp0;           /* First sample value */
    char bStepTableIndex;   /* Step table index */
    char bReserved;         /* Reserved, must be 0 */
} ImaBlockHeader_t;

/* Sound constants - from psound.h */
enum {
    SND_ADPCM_SBLOCK_ALIGN = 1024,   /* IMA ADPCM block alignment for 16-bit stereo */
    SND_ADPCM_MBLOCK_ALIGN = 512,    /* IMA ADPCM block alignment for 16-bit mono */
    SND_WAV_SCHAN = 2,               /* Stereo channels */
    SND_WAV_MCHAN = 1                /* Mono channel */
};

/* MAKELONG macro if not already defined */
#ifndef MAKELONG
#define MAKELONG(a, b) ((LONG)(((WORD)(a)) | ((DWORD)((WORD)(b))) << 16))
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_SOUND_H */
