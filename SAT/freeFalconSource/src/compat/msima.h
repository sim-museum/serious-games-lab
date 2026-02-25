/*
 * FreeFalcon Linux Port - msima.h compatibility
 *
 * IMA ADPCM codec definitions for Miles Sound System compatibility
 */

#ifndef FF_COMPAT_MSIMA_H
#define FF_COMPAT_MSIMA_H

#ifdef FF_LINUX

#include "mssw.h"

/* IMA ADPCM block header structure */
typedef struct {
    S16 iSamp0;          /* First sample value */
    U8  bStepTableIndex; /* Step table index */
    U8  bReserved;       /* Reserved, must be 0 */
} IMA_ADPCM_BLOCKHEADER;

/* Block alignment for different formats */
#define IMA_ADPCM_BLOCKALIGNMENT_S16 2048  /* Stereo 16-bit */
#define IMA_ADPCM_BLOCKALIGNMENT_M16 1024  /* Mono 16-bit */

/* Print/debug macros */
#ifndef BOF_PRINT
#define BOF_PRINT(x)
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* IMA ADPCM decoding functions - implemented in imadpcm.cpp */
long ImaDecodeS16(S8 *sBuff, S8 *dBuff, S32 bufferLength);
long ImaDecodeM16(char *sBuff, char *dBuff, long bufferLength);

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_MSIMA_H */
