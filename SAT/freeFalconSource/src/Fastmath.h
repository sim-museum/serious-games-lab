/** Fast Math Functions **/

#ifdef _WIN32
// Windows: use MSVC inline assembly
// Float to 32-bit integer
inline DWORD F_I32(float x)
{
    DWORD r;

    _asm
    {
        fld x
        fistp r
    }

    return r;
}

// Absolute value
inline float F_ABS(float x)
{
    float r;

    _asm
    {
        fld x
        fabs
        fstp r
    }

    return r;
}

#else
// Linux/portable: use standard C functions
#include <math.h>
#include <stdint.h>

// Float to 32-bit integer
inline DWORD F_I32(float x)
{
    return (DWORD)(int32_t)x;
}

// Absolute value
inline float F_ABS(float x)
{
    return fabsf(x);
}

#endif
