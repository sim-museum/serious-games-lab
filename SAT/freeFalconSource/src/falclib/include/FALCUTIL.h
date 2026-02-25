#ifndef _FALCUTIL_H
#define _FALCUTIL_H

/*
 * min/max macros - on Linux with C++, use std::min/std::max instead
 * These macros conflict with the C++ standard library template functions
 */
#if defined(FF_LINUX) && defined(__cplusplus)
#include <algorithm>
using std::min;
using std::max;
#else
#ifndef max
#define max(a,b) ((a) > (b) ? (a) : (b))
#endif

#ifndef min
#define min(a,b) ((a) < (b) ? (a) : (b))
#endif
#endif

#endif
