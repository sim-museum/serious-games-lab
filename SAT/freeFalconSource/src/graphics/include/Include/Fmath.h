/***************************************************************************\
    fmath.h
    Miro "Jammer" Torrielli
    29Dec03

 Fast Math
\***************************************************************************/

#ifndef _FMATH_H_
#define _FMATH_H_

#ifdef _WIN32
// Windows: use MSVC inline assembly

inline float Sin(float a)
{
    _asm
    {
        fld a;
        fsin;
        fstp a;
    }

    return a;
}

inline float Cos(float a)
{
    _asm
    {
        fld a;
        fcos;
        fstp a;
    }

    return a;
}

inline float FabsF(float f)
{
    _asm
    {
        fld f;
        fabs;
        fstp f;
    }

    return f;
}

inline float SqrtF(float f)
{
    _asm
    {
        fld f;
        fsqrt;
        fstp f;
    }

    return f;
}

inline float Tan(const float a)
{
    _asm
    {
        fld a;
        fptan;
        fstp a;
    }

    return a;
}

inline float Atan(const float o, float a)
{
    _asm
    {
        fld o;
        fld a;
        fpatan;
        fstp a;
    }

    return a;
}

#else
// Linux/portable: use standard math library
#include <math.h>

inline float Sin(float a)
{
    return sinf(a);
}

inline float Cos(float a)
{
    return cosf(a);
}

inline float FabsF(float f)
{
    return fabsf(f);
}

inline float SqrtF(float f)
{
    return sqrtf(f);
}

inline float Tan(const float a)
{
    return tanf(a);
}

inline float Atan(const float o, float a)
{
    return atan2f(o, a);
}

#endif // _WIN32

/*
inline void SinCos(const float a, float *s, float *c)
{
 _asm
 {
 push edx;
 push ebx;
 mov edx,s;
 fld a;
 fsincos;
 mov ebx,c;
 fstp [dword ptr ebx];
 fstp [dword ptr edx];
 pop ebx;
 pop edx;
 }
}
*/

#endif // _FMATH_H_
