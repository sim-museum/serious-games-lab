/*
 * FreeFalcon Linux Port - D3DX Math stub
 */

#ifndef FF_COMPAT_D3DXMATH_H
#define FF_COMPAT_D3DXMATH_H

#ifdef FF_LINUX

#include "d3d.h"
#include <math.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* D3DX Math types - extending D3D types */
/* These may already be defined in d3dtypes.h or d3d.h */
#ifndef D3DXVECTOR3_DEFINED
typedef D3DMATRIX D3DXMATRIX;
typedef D3DVECTOR D3DXVECTOR3;
#define D3DXVECTOR3_DEFINED
#endif

typedef struct D3DXVECTOR2 {
    float x, y;
} D3DXVECTOR2;

typedef struct D3DXVECTOR4 {
    float x, y, z, w;
} D3DXVECTOR4;

typedef struct D3DXQUATERNION {
    float x, y, z, w;
} D3DXQUATERNION;

typedef struct D3DXPLANE {
    float a, b, c, d;
} D3DXPLANE;

/* D3DX Math functions - stubs */
#ifndef D3DXMatrixIdentity_DEFINED
static inline D3DXMATRIX* D3DXMatrixIdentity(D3DXMATRIX* pOut) {
    if (pOut) {
        memset(pOut, 0, sizeof(D3DXMATRIX));
        pOut->_11 = pOut->_22 = pOut->_33 = pOut->_44 = 1.0f;
    }
    return pOut;
}
#define D3DXMatrixIdentity_DEFINED
#endif

static inline D3DXMATRIX* D3DXMatrixTranslation(D3DXMATRIX* pOut, float x, float y, float z) {
    D3DXMatrixIdentity(pOut);
    if (pOut) {
        pOut->_41 = x;
        pOut->_42 = y;
        pOut->_43 = z;
    }
    return pOut;
}

static inline D3DXMATRIX* D3DXMatrixScaling(D3DXMATRIX* pOut, float sx, float sy, float sz) {
    if (pOut) {
        memset(pOut, 0, sizeof(D3DXMATRIX));
        pOut->_11 = sx;
        pOut->_22 = sy;
        pOut->_33 = sz;
        pOut->_44 = 1.0f;
    }
    return pOut;
}

static inline D3DXMATRIX* D3DXMatrixMultiply(D3DXMATRIX* pOut, const D3DXMATRIX* pM1, const D3DXMATRIX* pM2) {
    if (pOut && pM1 && pM2) {
        D3DXMATRIX tmp;
        for (int i = 0; i < 4; i++) {
            for (int j = 0; j < 4; j++) {
                tmp.mat[i][j] = pM1->mat[i][0] * pM2->mat[0][j] +
                                pM1->mat[i][1] * pM2->mat[1][j] +
                                pM1->mat[i][2] * pM2->mat[2][j] +
                                pM1->mat[i][3] * pM2->mat[3][j];
            }
        }
        *pOut = tmp;
    }
    return pOut;
}

static inline D3DXMATRIX* D3DXMatrixRotationX(D3DXMATRIX* pOut, float angle) {
    if (pOut) {
        float s = sinf(angle);
        float c = cosf(angle);
        memset(pOut, 0, sizeof(D3DXMATRIX));
        pOut->_11 = 1.0f;
        pOut->_22 = c;
        pOut->_23 = s;
        pOut->_32 = -s;
        pOut->_33 = c;
        pOut->_44 = 1.0f;
    }
    return pOut;
}

static inline D3DXMATRIX* D3DXMatrixRotationY(D3DXMATRIX* pOut, float angle) {
    if (pOut) {
        float s = sinf(angle);
        float c = cosf(angle);
        memset(pOut, 0, sizeof(D3DXMATRIX));
        pOut->_11 = c;
        pOut->_13 = -s;
        pOut->_22 = 1.0f;
        pOut->_31 = s;
        pOut->_33 = c;
        pOut->_44 = 1.0f;
    }
    return pOut;
}

static inline D3DXMATRIX* D3DXMatrixRotationZ(D3DXMATRIX* pOut, float angle) {
    if (pOut) {
        float s = sinf(angle);
        float c = cosf(angle);
        memset(pOut, 0, sizeof(D3DXMATRIX));
        pOut->_11 = c;
        pOut->_12 = s;
        pOut->_21 = -s;
        pOut->_22 = c;
        pOut->_33 = 1.0f;
        pOut->_44 = 1.0f;
    }
    return pOut;
}

/* D3DXMatrixPerspectiveFovLH - left-handed perspective projection matrix */
static inline D3DXMATRIX* D3DXMatrixPerspectiveFovLH(D3DXMATRIX* pOut, float fovy, float aspect, float zn, float zf) {
    if (!pOut) return NULL;
    float yScale = 1.0f / tanf(fovy / 2.0f);
    float xScale = yScale / aspect;

    memset(pOut, 0, sizeof(D3DXMATRIX));
    pOut->_11 = xScale;
    pOut->_22 = yScale;
    pOut->_33 = zf / (zf - zn);
    pOut->_34 = 1.0f;
    pOut->_43 = -zn * zf / (zf - zn);
    return pOut;
}

/* D3DXMatrixPerspectiveFovRH - right-handed perspective projection matrix */
static inline D3DXMATRIX* D3DXMatrixPerspectiveFovRH(D3DXMATRIX* pOut, float fovy, float aspect, float zn, float zf) {
    if (!pOut) return NULL;
    float yScale = 1.0f / tanf(fovy / 2.0f);
    float xScale = yScale / aspect;

    memset(pOut, 0, sizeof(D3DXMATRIX));
    pOut->_11 = xScale;
    pOut->_22 = yScale;
    pOut->_33 = zf / (zn - zf);
    pOut->_34 = -1.0f;
    pOut->_43 = zn * zf / (zn - zf);
    return pOut;
}

/* D3DXMatrixPerspectiveFov - alias for LH version */
#define D3DXMatrixPerspectiveFov D3DXMatrixPerspectiveFovLH

/* D3DXMatrixLookAtLH - left-handed view matrix */
static inline D3DXMATRIX* D3DXMatrixLookAtLH(D3DXMATRIX* pOut, const D3DXVECTOR3* pEye, const D3DXVECTOR3* pAt, const D3DXVECTOR3* pUp) {
    if (!pOut || !pEye || !pAt || !pUp) return NULL;

    /* Calculate forward (z), right (x), and up (y) vectors */
    D3DXVECTOR3 zaxis = { pAt->x - pEye->x, pAt->y - pEye->y, pAt->z - pEye->z };
    float len = sqrtf(zaxis.x * zaxis.x + zaxis.y * zaxis.y + zaxis.z * zaxis.z);
    if (len > 0) { zaxis.x /= len; zaxis.y /= len; zaxis.z /= len; }

    /* xaxis = cross(up, zaxis) */
    D3DXVECTOR3 xaxis = {
        pUp->y * zaxis.z - pUp->z * zaxis.y,
        pUp->z * zaxis.x - pUp->x * zaxis.z,
        pUp->x * zaxis.y - pUp->y * zaxis.x
    };
    len = sqrtf(xaxis.x * xaxis.x + xaxis.y * xaxis.y + xaxis.z * xaxis.z);
    if (len > 0) { xaxis.x /= len; xaxis.y /= len; xaxis.z /= len; }

    /* yaxis = cross(zaxis, xaxis) */
    D3DXVECTOR3 yaxis = {
        zaxis.y * xaxis.z - zaxis.z * xaxis.y,
        zaxis.z * xaxis.x - zaxis.x * xaxis.z,
        zaxis.x * xaxis.y - zaxis.y * xaxis.x
    };

    pOut->_11 = xaxis.x;  pOut->_12 = yaxis.x;  pOut->_13 = zaxis.x;  pOut->_14 = 0.0f;
    pOut->_21 = xaxis.y;  pOut->_22 = yaxis.y;  pOut->_23 = zaxis.y;  pOut->_24 = 0.0f;
    pOut->_31 = xaxis.z;  pOut->_32 = yaxis.z;  pOut->_33 = zaxis.z;  pOut->_34 = 0.0f;
    pOut->_41 = -(xaxis.x * pEye->x + xaxis.y * pEye->y + xaxis.z * pEye->z);
    pOut->_42 = -(yaxis.x * pEye->x + yaxis.y * pEye->y + yaxis.z * pEye->z);
    pOut->_43 = -(zaxis.x * pEye->x + zaxis.y * pEye->y + zaxis.z * pEye->z);
    pOut->_44 = 1.0f;
    return pOut;
}

static inline float D3DXVec3Length(const D3DXVECTOR3* pV) {
    if (!pV) return 0.0f;
    return sqrtf(pV->x * pV->x + pV->y * pV->y + pV->z * pV->z);
}

static inline D3DXVECTOR3* D3DXVec3Normalize(D3DXVECTOR3* pOut, const D3DXVECTOR3* pV) {
    if (pOut && pV) {
        float len = D3DXVec3Length(pV);
        if (len > 0.0f) {
            pOut->x = pV->x / len;
            pOut->y = pV->y / len;
            pOut->z = pV->z / len;
        }
    }
    return pOut;
}

static inline float D3DXVec3Dot(const D3DXVECTOR3* pV1, const D3DXVECTOR3* pV2) {
    if (!pV1 || !pV2) return 0.0f;
    return pV1->x * pV2->x + pV1->y * pV2->y + pV1->z * pV2->z;
}

static inline D3DXVECTOR3* D3DXVec3Cross(D3DXVECTOR3* pOut, const D3DXVECTOR3* pV1, const D3DXVECTOR3* pV2) {
    if (pOut && pV1 && pV2) {
        pOut->x = pV1->y * pV2->z - pV1->z * pV2->y;
        pOut->y = pV1->z * pV2->x - pV1->x * pV2->z;
        pOut->z = pV1->x * pV2->y - pV1->y * pV2->x;
    }
    return pOut;
}

#ifdef __cplusplus
}
#endif

#endif /* FF_LINUX */
#endif /* FF_COMPAT_D3DXMATH_H */
