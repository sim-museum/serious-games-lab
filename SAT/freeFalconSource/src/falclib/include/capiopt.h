#ifndef CAPIOPT_H
#define CAPIOPT_H

/*  Application defined data, etc */

/* comment/uncomment this as wished */
/* #define DEBUG_COMMS  */

// LOAD_DLLS causes DLL loading via GetProcAddress for Winsock functions
// On Linux, we use direct BSD socket function assignments instead
#ifndef FF_LINUX
#define LOAD_DLLS
#endif

//#define CAPI_DEBUG
//#define DEBUG_RECEIVE
//#define DEBUG_SEND

//#define CAPI_NET_DEBUG_FEATURES

// compression stuff
#include "utils/Lzss.h"
#define ComAPICompress LZSS_Compress
#define ComAPIDecompress LZSS_Expand


#endif
