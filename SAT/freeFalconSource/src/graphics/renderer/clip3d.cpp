/***************************************************************************\
    Clip3D.cpp
    Scott Randolph
    May 24, 1997

    This is a portion of the implemention for Render3D (see Render3D.h)
 These function provide 3D clipping services.
 It is assumed that all 3D coordinates have been transformed such
 that the clipping volume is z >= 1 and -z <= x <= z and -z <= y <= z.
\***************************************************************************/
#include <cISO646>
#include "render3d.h"


//#define DO_NEAR_CLIP_ONLY // Can leave this defined as long as MPR is doing clipping
#define DO_BACKFACE_CULLING



// The use of the global storage defined here intorduces a requirement that only
// one thread at a time do clipping.  If this requirment is unacceptable, this
// storage should become a member of the Render3D class.  Not doing so now
// saves us one pointer indirection per use of this storage (ie: this->)
static const int MAX_VERT_LIST = 10; // (Input verts + num clip planes)
static const int MAX_EXTRA_VERTS = 10; // (2 x Number of clip planes)
static ThreeDVertex extraVerts[MAX_EXTRA_VERTS];// Used to hold temporaty vertices
static int extraVertCount; // created by clipping.


/***************************************************************************\
 Given a list of vertices which make up a fan, clip them to the
 top, bottom, left, right, and near planes.  Then draw the resultant
 polygon.
\***************************************************************************/
void Render3D::ClipAndDraw3DFan(ThreeDVertex** vertPointers, unsigned count, int CullFlag, bool gifPicture, bool terrain, bool sort) //JAM 14Sep03
{
#if defined(FF_LINUX) && defined(FF_LINUX_DEBUG)
    static int clipFanDbg = 0;
    clipFanDbg++;
    bool doDebug = (clipFanDbg <= 20) || (clipFanDbg % 500 == 0);
    if (doDebug)
    {
        fprintf(stderr, "[ClipAndDraw3DFan] ENTER vertPointers=%p count=%d CullFlag=%d (%d)\n",
                (void*)vertPointers, count, CullFlag, clipFanDbg);
        fflush(stderr);
    }
#else
    // Suppress unused variable warnings
    (void)gifPicture;
    bool doDebug = false;
#endif
    ThreeDVertex **v, **p, **lastIn, **nextOut;
    ThreeDVertex **inList, **outList, **temp;
    ThreeDVertex *vertList1[MAX_VERT_LIST]; // Used to hold poly vert pointer lists
    ThreeDVertex *vertList2[MAX_VERT_LIST]; // Used to hold poly vert pointer lists
    DWORD clipTest = 0;

    ShiAssert(vertPointers);
    ShiAssert(count >= 3);

#ifdef FF_LINUX
    if (doDebug)
    {
        fprintf(stderr, "[ClipAndDraw3DFan] Initialize vertex buffers...\n");
        fflush(stderr);
    }
#endif
    // Initialize the vertex buffers
    outList = vertList1;
    lastIn = vertPointers + count;

    for (nextOut = outList; vertPointers < lastIn; nextOut++)
    {
        clipTest or_eq (*vertPointers)->clipFlag;
        *nextOut = (*vertPointers++);
    }
#ifdef FF_LINUX
    if (doDebug)
    {
        fprintf(stderr, "[ClipAndDraw3DFan] clipTest=0x%x, vertices copied\n", clipTest);
        fflush(stderr);
    }
#endif

    ShiAssert(nextOut - outList <= MAX_VERT_LIST);
    inList = vertList2;
    extraVertCount = 0;


    // Clip to the near plane
#ifdef FF_LINUX
    if (doDebug)
    {
        fprintf(stderr, "[ClipAndDraw3DFan] Near clip? %d\n", (clipTest & CLIP_NEAR) != 0);
        fflush(stderr);
    }
#endif
    if (clipTest bitand CLIP_NEAR)
    {
        temp = inList;
        inList = outList;
        outList = temp;
        lastIn = nextOut - 1;
        nextOut = outList;

        for (p = lastIn, v = &inList[0]; v <= lastIn; v++)
        {

            // If the edge between this vert and the previous one crosses the line, trim it
            if (((*p)->clipFlag xor (*v)->clipFlag) bitand CLIP_NEAR)
            {
                ShiAssert(extraVertCount < MAX_EXTRA_VERTS);
                *nextOut = &extraVerts[extraVertCount];
                extraVertCount++;
                IntersectNear(*p, *v, *nextOut);
                clipTest or_eq (*nextOut)->clipFlag;
                nextOut++;
            }

            // If this vert isn't clipped, use it
            if ( not ((*v)->clipFlag bitand CLIP_NEAR))
            {
                *nextOut++ = *v;
            }

            p = v;
        }

        ShiAssert(nextOut - outList <= MAX_VERT_LIST);

        if (nextOut - outList <= 2)  return;

        // NOTE:  We might get to this point and find a polygon is now marked totally clipped
        // since doing the near clip can change the flags and make a vertex appear to have
        // changed sides of the viewer.  We'll ignore this issue since it is quietly handled
        // and would probably cost more to detect than it would save it early termination.
    }


#ifdef DO_BACKFACE_CULLING

    // Note:  we handle only leading and trailing culled triangles.  If
    // a more complicated non-planar polygon with interior triangles culled is
    // presented, too many triangles will get culled.  To handle that case, we'd
    // have to check all triangles instead of stopping after the second reject loop below.
    // If a new set of un-culled triangles was encountered, we'd have to make a new polygon
    // and resubmit it.
#ifdef FF_LINUX
    if (doDebug)
    {
        fprintf(stderr, "[ClipAndDraw3DFan] Backface culling? CullFlag=%d\n", CullFlag);
        fflush(stderr);
    }
#endif
    if (CullFlag)
    {
#ifdef FF_LINUX
        if (doDebug)
        {
            fprintf(stderr, "[ClipAndDraw3DFan] Backface entry: inList=%p outList=%p nextOut=%p\n",
                    (void*)inList, (void*)outList, (void*)nextOut);
            fflush(stderr);
        }
#endif
        temp = inList;
        inList = outList;
        outList = temp;
        lastIn = nextOut - 1;
        nextOut = outList;

#ifdef FF_LINUX
        if (doDebug)
        {
            fprintf(stderr, "[ClipAndDraw3DFan] Backface after swap: inList=%p outList=%p lastIn=%p nextOut=%p\n",
                    (void*)inList, (void*)outList, (void*)lastIn, (void*)nextOut);
            fflush(stderr);
        }
#endif
        // We only support one flavor of clipping right now. The other version would just
        // be this same code repeated with inverted compare signs.
        ShiAssert(CullFlag == CULL_ALLOW_CW);

        // Always copy the vertex at the root of the fan
#ifdef FF_LINUX
        if (doDebug)
        {
            fprintf(stderr, "[ClipAndDraw3DFan] Copying root vertex: *inList=%p\n", (void*)*inList);
            fflush(stderr);
        }
#endif
        *nextOut++ = *inList;

#ifdef FF_LINUX
        if (doDebug)
        {
            int vertCount = (int)(lastIn - inList) + 1;
            fprintf(stderr, "[ClipAndDraw3DFan] Starting backface loop, &inList[1]=%p, vertCount=%d\n",
                    (void*)&inList[1], vertCount);
            fflush(stderr);
        }
#endif
        for (p = &inList[0], v = &inList[1]; v < lastIn; v++)
        {
#ifdef FF_LINUX
            if (doDebug)
            {
                fprintf(stderr, "[ClipAndDraw3DFan] Loop1 iteration: v=%p lastIn=%p\n", (void*)v, (void*)lastIn);
                fflush(stderr);
            }
            // Check for NULL pointers before dereferencing
            if (!*v || !*(v+1) || !*p) {
                fprintf(stderr, "[ClipAndDraw3DFan] ERROR: NULL vertex in backface loop1: *v=%p *(v+1)=%p *p=%p\n",
                        (void*)*v, (void*)*(v+1), (void*)*p);
                fflush(stderr);
                return;  // Avoid crash
            }
#endif
            // Only clockwise triangles are accepted
            // FF_LINUX: Flip._13 = 1.0f reverses screen-space winding; swap < to >
#ifdef FF_LINUX
            if ((((*(v + 1))->y - (*v)->y)) * (((*p)->x - (*v)->x)) >
                (((*(v + 1))->x - (*v)->x)) * (((*p)->y - (*v)->y)))
#else
            if ((((*(v + 1))->y - (*v)->y)) * (((*p)->x - (*v)->x)) <
                (((*(v + 1))->x - (*v)->x)) * (((*p)->y - (*v)->y)))
#endif
            {
                // Accept
                break;
            }
        }

#ifdef FF_LINUX
        // Check bounds before accessing *v
        if (v > lastIn) {
            fprintf(stderr, "[ClipAndDraw3DFan] ERROR: v=%p > lastIn=%p after loop1\n", (void*)v, (void*)lastIn);
            fflush(stderr);
            return;
        }
        if (!*v) {
            fprintf(stderr, "[ClipAndDraw3DFan] ERROR: *v is NULL after backface loop1\n");
            fflush(stderr);
            return;
        }
#endif
        *nextOut++ = *v;

        for (p, v; v < lastIn; v++)
        {
#ifdef FF_LINUX
            // Check for NULL pointers before dereferencing
            if (!*v || !*(v+1) || !*p) {
                fprintf(stderr, "[ClipAndDraw3DFan] ERROR: NULL vertex in backface loop2: *v=%p *(v+1)=%p *p=%p\n",
                        (void*)*v, (void*)*(v+1), (void*)*p);
                fflush(stderr);
                return;  // Avoid crash
            }
#endif
            // Only clockwise triangles are accepted
            // FF_LINUX: Flip._13 = 1.0f reverses screen-space winding; swap >= to <=
#ifdef FF_LINUX
            if ((((*(v + 1))->y - (*v)->y)) * (((*p)->x - (*v)->x)) <=
                (((*(v + 1))->x - (*v)->x)) * (((*p)->y - (*v)->y)))
#else
            if ((((*(v + 1))->y - (*v)->y)) * (((*p)->x - (*v)->x)) >=
                (((*(v + 1))->x - (*v)->x)) * (((*p)->y - (*v)->y)))
#endif
            {
                // Reject
                break;
            }

            *nextOut++ = *(v + 1);
        }

        ShiAssert(nextOut - outList <= MAX_VERT_LIST);

        if (nextOut - outList <= 2)  return;
    }

#endif

    // 2002-04-06 MN if gifPicture is false, then do the other clippings (for terrain and stuff).
    // GifPicture is only locally set to true in the case we draw a celestial object.
    // Sun and Moon GIF's are displayed bad when being clipped by below code.
#ifdef FF_LINUX
    if (doDebug)
    {
        fprintf(stderr, "[ClipAndDraw3DFan] gifPicture=%d, checking clip planes...\n", gifPicture);
        fflush(stderr);
    }
#endif
    if ( not gifPicture)
    {
#ifndef DO_NEAR_CLIP_ONLY

#ifdef FF_LINUX
        if (doDebug)
        {
            fprintf(stderr, "[ClipAndDraw3DFan] Bottom clip? %d\n", (clipTest & CLIP_BOTTOM) != 0);
            fflush(stderr);
        }
#endif
        // Clip to the bottom plane
        if (clipTest bitand CLIP_BOTTOM)
        {
            temp = inList;
            inList = outList;
            outList = temp;
            lastIn = nextOut - 1;
            nextOut = outList;

            for (p = lastIn, v = &inList[0]; v <= lastIn; v++)
            {

                // If the edge between this vert and the previous one crosses the line, trim it
                if (((*p)->clipFlag xor (*v)->clipFlag) bitand CLIP_BOTTOM)
                {
                    ShiAssert(extraVertCount < MAX_EXTRA_VERTS);
                    *nextOut = &extraVerts[extraVertCount];
                    extraVertCount++;
                    IntersectBottom(*p, *v, *nextOut++);
                }

                // If this vert isn't clipped, use it
                if ( not ((*v)->clipFlag bitand CLIP_BOTTOM))
                {
                    *nextOut++ = *v;
                }

                p = v;
            }

            ShiAssert(nextOut - outList <= MAX_VERT_LIST);

            if (nextOut - outList <= 2)  return;
        }


        // Clip to the top plane
        if (clipTest bitand CLIP_TOP)
        {
            temp = inList;
            inList = outList;
            outList = temp;
            lastIn = nextOut - 1;
            nextOut = outList;

            for (p = lastIn, v = &inList[0]; v <= lastIn; v++)
            {

                // If the edge between this vert and the previous one crosses the line, trim it
                if (((*p)->clipFlag xor (*v)->clipFlag) bitand CLIP_TOP)
                {
                    ShiAssert(extraVertCount < MAX_EXTRA_VERTS);
                    *nextOut = &extraVerts[extraVertCount];
                    extraVertCount++;
                    IntersectTop(*p, *v, *nextOut++);
                }

                // If this vert isn't clipped, use it
                if ( not ((*v)->clipFlag bitand CLIP_TOP))
                {
                    *nextOut++ = *v;
                }

                p = v;
            }

            ShiAssert(nextOut - outList <= MAX_VERT_LIST);

            if (nextOut - outList <= 2)  return;
        }


        // Clip to the right plane
        if (clipTest bitand CLIP_RIGHT)
        {
            temp = inList;
            inList = outList;
            outList = temp;
            lastIn = nextOut - 1;
            nextOut = outList;

            for (p = lastIn, v = &inList[0]; v <= lastIn; v++)
            {

                // If the edge between this vert and the previous one crosses the line, trim it
                if (((*p)->clipFlag xor (*v)->clipFlag) bitand CLIP_RIGHT)
                {
                    ShiAssert(extraVertCount < MAX_EXTRA_VERTS);
                    *nextOut = &extraVerts[extraVertCount];
                    extraVertCount++;
                    IntersectRight(*p, *v, *nextOut++);
                }

                // If this vert isn't clipped, use it
                if ( not ((*v)->clipFlag bitand CLIP_RIGHT))
                {
                    *nextOut++ = *v;
                }

                p = v;
            }

            ShiAssert(nextOut - outList <= MAX_VERT_LIST);

            if (nextOut - outList <= 2)  return;
        }


        // Clip to the left plane
        if (clipTest bitand CLIP_LEFT)
        {
            temp = inList;
            inList = outList;
            outList = temp;
            lastIn = nextOut - 1;
            nextOut = outList;

            for (p = lastIn, v = &inList[0]; v <= lastIn; v++)
            {

                // If the edge between this vert and the previous one crosses the line, trim it
                if (((*p)->clipFlag xor (*v)->clipFlag) bitand CLIP_LEFT)
                {
                    ShiAssert(extraVertCount < MAX_EXTRA_VERTS);
                    *nextOut = &extraVerts[extraVertCount];
                    extraVertCount++;
                    IntersectLeft(*p, *v, *nextOut++);
                }

                // If this vert isn't clipped, use it
                if ( not ((*v)->clipFlag bitand CLIP_LEFT))
                {
                    *nextOut++ = *v;
                }

                p = v;
            }

            ShiAssert(nextOut - outList <= MAX_VERT_LIST);

            if (nextOut - outList <= 2)  return;
        }

#endif // DO_NEAR_CLIP_ONLY
    }

    // Finally draw the resultant polygon
    // OW
#if 0
    context.Primitive(MPR_PRM_TRIFAN,
                      MPR_VI_COLOR bitor MPR_VI_TEXTURE,
                      (unsigned short)(nextOut - outList), sizeof(MPRVtxTexClr_t));

    for (v = outList; v < nextOut; v++)
    {
        // ShiAssert ((*v)->q >= -0.001F);

        context.StorePrimitiveVertexData(*v);
    }

#else
#ifdef FF_LINUX
    if (doDebug)
    {
        fprintf(stderr, "[ClipAndDraw3DFan] About to DrawPrimitive, count=%d\n",
                (int)(nextOut - outList));
        fflush(stderr);
    }
#endif
    context.DrawPrimitive(MPR_PRM_TRIFAN, MPR_VI_COLOR bitor MPR_VI_TEXTURE,
                          (unsigned short)(nextOut - outList), (MPRVtxTexClr_t **)outList, terrain); //JAM 14Sep03
#ifdef FF_LINUX
    if (doDebug)
    {
        fprintf(stderr, "[ClipAndDraw3DFan] DrawPrimitive done\n");
        fflush(stderr);
    }
#endif
#endif
}


inline void InterpolateColorAndTex(ThreeDVertex *v1, ThreeDVertex *v2, ThreeDVertex *v, float t)
{
    // Compute the interpolated color and texture coordinates
    v->r = v1->r + t * (v2->r - v1->r);
    v->g = v1->g + t * (v2->g - v1->g);
    v->b = v1->b + t * (v2->b - v1->b);
    v->a = v1->a + t * (v2->a - v1->a);

    v->u = v1->u + t * (v2->u - v1->u);
    v->v = v1->v + t * (v2->v - v1->v);
    v->q = v->csZ * Q_SCALE; // Need to preserve scaling to 16.16
}


// Intersect edge with z=near plane
// This function is expected to be called first in the clipping chain
void Render3D::IntersectNear(ThreeDVertex *v1, ThreeDVertex *v2, ThreeDVertex *v)
{
    float x, y, z, t;

    // Compute the parametric location of the intersection of the edge and the clip plane
    t = (NEAR_CLIP - v1->csZ) / (v2->csZ - v1->csZ);
    ShiAssert((t >= -0.001f) and (t <= 1.001f));

    // Compute the camera space intersection point
    v->csZ = z = NEAR_CLIP;
    v->csX = x = v1->csX + t * (v2->csX - v1->csX);
    v->csY = y = v1->csY + t * (v2->csY - v1->csY);


    // Compute the interpolated color and texture coordinates
    InterpolateColorAndTex(v1, v2, v, t);

    // Now determine if the point is out to the sides
    v->clipFlag  = GetHorizontalClipFlags(x, z);
    v->clipFlag or_eq GetVerticalClipFlags(y, z);

    // Compute the screen space coordinates of the new point
    register float OneOverZ = 1.0f / z;
    v->x = viewportXtoPixel(x * OneOverZ);
    v->y = viewportYtoPixel(y * OneOverZ);
}


// Intersect edge with y=z plane
// This function is expected to be called second in the clipping chain
// (ie: after near clip, but before all the others)
void Render3D::IntersectBottom(ThreeDVertex *v1, ThreeDVertex *v2, ThreeDVertex *v)
{
    float x, y, z, t;
    float dx, dy, dz;

    // Compute the parametric location of the intersection of the edge and the clip plane
    dx = v2->csX - v1->csX;
    dy = v2->csY - v1->csY;
    dz = v2->csZ - v1->csZ;
    t = (v1->csY - v1->csZ) / (dz - dy);
    ShiAssert((t >= -0.001f) and (t <= 1.001f));

    // Compute the camera space intersection point
    v->csZ = z = v1->csZ + t * (dz);
    v->csX = x = v1->csX + t * (dx); // Note: either dx or dy is used only once, so could
    v->csY = y = v1->csY + t * (dy); // be avoided, but this way, the code is more standardized...


    // Compute the interpolated color and texture coordinates
    InterpolateColorAndTex(v1, v2, v, t);

    // Now determine if the point is out to the sides
    v->clipFlag  = GetHorizontalClipFlags(x, z);

    // Compute the screen space coordinates of the new point
    register float OneOverZ = 1.0f / z;
    v->x = viewportXtoPixel(x * OneOverZ);
    v->y = viewportYtoPixel(y * OneOverZ);
}


// Intersect edge with -y=z plane
// This function is expected to be called third in the clipping chain
// (ie: after bottom clipping, but before horizontal)
void Render3D::IntersectTop(ThreeDVertex *v1, ThreeDVertex *v2, ThreeDVertex *v)
{
    float x, y, z, t;
    float dx, dy, dz;

    // Compute the parametric location of the intersection of the edge and the clip plane
    dx = v2->csX - v1->csX;
    dy = v2->csY - v1->csY;
    dz = v2->csZ - v1->csZ;
    t = (v1->csZ + v1->csY) / (-dz - dy);
    ShiAssert((t >= -0.001f) and (t <= 1.001f));

    // Compute the camera space intersection point
    v->csZ = z = v1->csZ + t * (dz);
    v->csX = x = v1->csX + t * (dx); // Note: either dx or dy is used only once, so could
    v->csY = y = v1->csY + t * (dy); // be avoided, but this way, the code is more standardized...


    // Compute the interpolated color and texture coordinates
    InterpolateColorAndTex(v1, v2, v, t);

    // Now determine if the point is out to the sides
    v->clipFlag  = GetHorizontalClipFlags(x, z);

    // Compute the screen space coordinates of the new point
    register float OneOverZ = 1.0f / z;
    v->x = viewportXtoPixel(x * OneOverZ);
    v->y = viewportYtoPixel(y * OneOverZ);
}


// Intersect edge with x=z plane
// This function is expected to be called fourth in the clipping chain
// (ie: after vertical clipping is complete, but before the other side is done)
void Render3D::IntersectRight(ThreeDVertex *v1, ThreeDVertex *v2, ThreeDVertex *v)
{
    float x, y, z, t;
    float dx, dy, dz;

    // Compute the parametric location of the intersection of the edge and the clip plane
    dx = v2->csX - v1->csX;
    dy = v2->csY - v1->csY;
    dz = v2->csZ - v1->csZ;
    t = (v1->csX - v1->csZ) / (dz - dx);
    ShiAssert((t >= -0.001f) and (t <= 1.001f));

    // Compute the camera space intersection point
    v->csZ = z = v1->csZ + t * (dz);
    v->csX = x = v1->csX + t * (dx); // Note: either dx or dy is used only once, so could
    v->csY = y = v1->csY + t * (dy); // be avoided, but this way, the code is more standardized...


    // Compute the interpolated color and texture coordinates
    InterpolateColorAndTex(v1, v2, v, t);

    // Now determine if the point is out to the sides
    // (this point MUST be on screen because all that is left is Left edge clipping,
    // and this point is onthe right).
    v->clipFlag = ON_SCREEN;

    // Compute the screen space coordinates of the new point
    register float OneOverZ = 1.0f / z;
    v->x = viewportXtoPixel(x * OneOverZ);
    v->y = viewportYtoPixel(y * OneOverZ);
}


// Intersect edge with -x=z plane
// This function is expected to be called fifth in the clipping chain
// (ie: last)
void Render3D::IntersectLeft(ThreeDVertex *v1, ThreeDVertex *v2, ThreeDVertex *v)
{
    float x, y, z, t;
    float dx, dy, dz;

    // Compute the parametric location of the intersection of the edge and the clip plane
    dx = v2->csX - v1->csX;
    dy = v2->csY - v1->csY;
    dz = v2->csZ - v1->csZ;
    t = (v1->csZ + v1->csX) / (-dz - dx);
    ShiAssert((t >= -0.001f) and (t <= 1.001f));

    // Compute the camera space intersection point
    v->csZ = z = v1->csZ + t * (dz);
    v->csX = x = v1->csX + t * (dx); // Note: either dx or dy is used only once, so could
    v->csY = y = v1->csY + t * (dy); // be avoided, but this way, the code is more standardized...


    // Compute the interpolated color and texture coordinates
    InterpolateColorAndTex(v1, v2, v, t);

    // Now determine if the point is out to the sides
    // (this point MUST be on screen because we've done all clipping at this point
    v->clipFlag = ON_SCREEN;

    // Compute the screen space coordinates of the new point
    register float OneOverZ = 1.0f / z;
    v->x = viewportXtoPixel(x * OneOverZ);
    v->y = viewportYtoPixel(y * OneOverZ);
}
