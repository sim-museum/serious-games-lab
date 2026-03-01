#include <stdio.h>

#include "stdhdr.h"
#include "graphics/include/device.h"
#include "graphics/include/filemem.h"
#include "graphics/include/image.h"
#include "graphics/include/render2d.h"
#include "f4thread.h"
#include "f4find.h"
#include "otwdrive.h"
#include "sinput.h"
#include "dispcfg.h"
#include "stdafx.h" //Wombat778 3-24-04

#include "renderow.h" //Wombat778 3-24-04
#include "dispopts.h" //Wombat778 3-30-04


// ALL RESMGR CODE ADDITIONS START HERE
#define _SI_USE_RES_MGR_ 1

#ifndef _SI_USE_RES_MGR_ // DON'T USE RESMGR

#define SI_HANDLE FILE
#define SI_OPEN   fopen
#define SI_READ   fread
#define SI_CLOSE  fclose
#define SI_SEEK   fseek
#define SI_TELL   ftell

#else // USE RESMGR

#include "cmpclass.h"
extern "C"
{
#include "codelib/resources/reslib/src/resmgr.h"
}

#define SI_HANDLE FILE
#define SI_OPEN   RES_FOPEN
#define SI_READ   RES_FREAD
#define SI_CLOSE  RES_FCLOSE
#define SI_SEEK   RES_FSEEK
#define SI_TELL   RES_FTELL

#endif

#define NUM_FIELDS 5

SimCursor* gpSimCursors;
int gTotalCursors;


BOOL CreateSimCursors()
{
    SI_HANDLE* pCursorFile;
    char pFileName[MAX_PATH] = "";
    char pFilePath[MAX_PATH] = "";
    BOOL Result = TRUE;
    int i;

    sprintf(pFilePath, "%s%s%s", FalconDataDirectory, SIM_CURSOR_DIR, SIM_CURSOR_FILE);
#ifdef FF_LINUX
    fprintf(stderr, "[CreateSimCursors] Trying to open: %s\n", pFilePath);
#endif
    pCursorFile = SI_OPEN(pFilePath, "r");

    if (pCursorFile == NULL)
    {
#ifdef FF_LINUX
        fprintf(stderr, "[CreateSimCursors] FAILED to open cursor file: %s\n", pFilePath);
#endif
        return (FALSE);
    }

    if (fscanf(pCursorFile, "%d", &gTotalCursors) not_eq 1)
    {
#ifdef FF_LINUX
        fprintf(stderr, "[CreateSimCursors] FAILED to read cursor count\n");
#endif
        return(FALSE);
    }

    gpSimCursors = new SimCursor[gTotalCursors];

    for (i = 0; i < gTotalCursors; i++)
    {
        // Note, the %hu is to read in unsigned shorts instead of unsigned ints
        if (fscanf(pCursorFile, "\t%hu %hu %hu %hu %s\n", &gpSimCursors[i].Width, &gpSimCursors[i].Height,
                   &gpSimCursors[i].xHotspot, &gpSimCursors[i].yHotspot, pFileName) not_eq NUM_FIELDS)
        {
            return(FALSE);
        }

        gpSimCursors[i].CursorBuffer = new ImageBuffer;

        sprintf(pFilePath, "%s%s%s", FalconDataDirectory, SIM_CURSOR_DIR, pFileName);

        gpSimCursors[i].CursorBuffer->Setup(&FalconDisplay.theDisplayDevice, gpSimCursors[i].Width, gpSimCursors[i].Height, SystemMem, None);
        gpSimCursors[i].CursorBuffer->SetChromaKey(0xFFFF0000);

        // OW FIXME: fix it :)
#if 1 // This avoids using MPR since the bitmap function is broken at the moment...  SCR 5/14/98
        int r, c;
        BYTE *p;
        void *imgPtr;

        int result;
        CImageFileMemory  texFile;

        // Make sure we recognize this file type
        texFile.imageType = CheckImageType(pFilePath);
        ShiAssert(texFile.imageType not_eq IMAGE_TYPE_UNKNOWN);

        // Open the input file
        result = texFile.glOpenFileMem(pFilePath);
#ifdef FF_LINUX
        if (result != 1) {
            fprintf(stderr, "[CreateSimCursors] Failed to open cursor image: %s\n", pFilePath);
            gpSimCursors[i].CursorBuffer->Unlock();
            continue;
        }
#else
        ShiAssert(result == 1);
#endif

        // Read the image data (note that ReadTextureImage will close texFile for us)
        texFile.glReadFileMem();
        result = ReadTextureImage(&texFile);

        if (result not_eq GOOD_READ)
        {
#ifdef FF_LINUX
            fprintf(stderr, "[CreateSimCursors] Failed to read cursor bitmap: %s\n", pFilePath);
            continue;
#else
            ShiError("Failed to read bitmap.  CD Error?");
#endif
        }

#ifdef FF_LINUX
        if (!texFile.image.palette || !texFile.image.image) {
            fprintf(stderr, "[CreateSimCursors] Cursor image missing palette/data: %s\n", pFilePath);
            continue;
        }
#else
        ShiAssert(texFile.image.palette);
#endif
        ShiAssert(texFile.image.width == gpSimCursors[i].Width);
        ShiAssert(texFile.image.height == gpSimCursors[i].Height);

        // Convert from palettized to screen format
        p = texFile.image.image;
        imgPtr = gpSimCursors[i].CursorBuffer->Lock();

        switch (gpSimCursors[i].CursorBuffer->PixelSize())
        {
            case 2:
            {
                for (r = 0; r < gpSimCursors[i].Height; r++)
                {
                    for (c = 0; c < gpSimCursors[i].Width; c++)
                    {
                        *(WORD*)gpSimCursors[i].CursorBuffer->Pixel(imgPtr, r, c) = gpSimCursors[i].CursorBuffer->Pixel32toPixel16(texFile.image.palette[*p++]);
                    }
                }

                break;
            }

            case 4:
            {
                for (r = 0; r < gpSimCursors[i].Height; r++)
                {
                    for (c = 0; c < gpSimCursors[i].Width; c++)
                    {
                        *(DWORD*)gpSimCursors[i].CursorBuffer->Pixel(imgPtr, r, c) = gpSimCursors[i].CursorBuffer->Pixel32toPixel32(texFile.image.palette[*p++]);
                    }
                }

                break;
            }

            default:
                ShiAssert(false);
        }

        gpSimCursors[i].CursorBuffer->Unlock();

        //Wombat778 3-24-04 If rendered cursor is on, read the mouse cursor as a texture.
        if (DisplayOptions.bRender2DCockpit)
        {
            gpSimCursors[i].CursorRenderBuffer = texFile.image.image;

            try
            {
                const DWORD dwMaxTextureWidth = OTWDriver.OTWImage->GetDisplayDevice()->GetDefaultRC()->m_pD3DHWDeviceDesc->dwMaxTextureWidth;
                const DWORD dwMaxTextureHeight = OTWDriver.OTWImage->GetDisplayDevice()->GetDefaultRC()->m_pD3DHWDeviceDesc->dwMaxTextureHeight;
                gpSimCursors[i].CursorRenderPalette = new PaletteHandle(OTWDriver.OTWImage->GetDisplayDevice()->GetDefaultRC()->m_pDD, 32, 256);

                if ( not gpSimCursors[i].CursorRenderPalette)
                    throw _com_error(E_OUTOFMEMORY);

                // Check if we can use a single texture
                if (dwMaxTextureWidth >= gpSimCursors[i].Width and dwMaxTextureHeight >= gpSimCursors[i].Height)
                {
                    TextureHandle *pTex = new TextureHandle;

                    if ( not pTex)
                        throw _com_error(E_OUTOFMEMORY);

                    gpSimCursors[i].CursorRenderPalette->AttachToTexture(pTex);

                    if ( not pTex->Create("CPHsi", MPR_TI_PALETTE bitor MPR_TI_CHROMAKEY, 8, gpSimCursors[i].Width, gpSimCursors[i].Height))
                        throw _com_error(E_FAIL);

                    if ( not pTex->Load(0, 0xFFFF0000, (BYTE*) gpSimCursors[i].CursorRenderBuffer, true, true)) // soon to be re-loaded by CPSurface::Translate3D
                        throw _com_error(E_FAIL);

                    gpSimCursors[i].CursorRenderTexture.push_back(pTex);

                    gpSimCursors[i].CursorRenderPalette->Load(MPR_TI_PALETTE, 32, 0, 256, (BYTE*) texFile.image.palette);
                }

            }
            catch (_com_error e)
            {
                MonoPrint("CreateSimCursors - Error 0x%X (%s)\n", e.Error(), e.ErrorMessage());
            }

        }
        // Release the raw image data
        else
        {
            glReleaseMemory((char*)texFile.image.image);
        }

        glReleaseMemory((char*)texFile.image.palette);
#else
        Render2D CursorRenderer;
        CursorRenderer.Setup(gpSimCursors[i].CursorBuffer);
        CursorRenderer.StartFrame();
        CursorRenderer.ClearFrame();
        CursorRenderer.Render2DBitmap(0, 0, 0, 0, gpSimCursors[i].Width, gpSimCursors[i].Height, pFilePath);
        CursorRenderer.FinishFrame();
        CursorRenderer.SetColor(0xff00ff00);
        CursorRenderer.Cleanup();
#endif



    }


    SI_CLOSE(pCursorFile);

#ifdef FF_LINUX
    fprintf(stderr, "[CreateSimCursors] Loaded %d cursors from %s\n", gTotalCursors, pFilePath);
#endif

    return(Result);
}


void CleanupSimCursors()
{
    int i;

    for (i = 0; i < gTotalCursors; i++)
    {
        if (gpSimCursors[i].CursorBuffer)
        {
            gpSimCursors[i].CursorBuffer->Cleanup();
            delete(gpSimCursors[i].CursorBuffer);
        }

        gpSimCursors[i].CursorBuffer = NULL;

        //Wombat778 3-24-04 if the rendered cursor has been used, delete it
        if (DisplayOptions.bRender2DCockpit)
        {
            for (unsigned int i2 = 0; i2 < gpSimCursors[i].CursorRenderTexture.size(); i2++) delete gpSimCursors[i].CursorRenderTexture[i2];

            gpSimCursors[i].CursorRenderTexture.clear();
            glReleaseMemory(gpSimCursors[i].CursorRenderBuffer);

            if (gpSimCursors[i].CursorRenderPalette) //Wombat78 5-14-04 avoid a possible ctd
                delete gpSimCursors[i].CursorRenderPalette;

            gpSimCursors[i].CursorRenderBuffer = NULL;
            gpSimCursors[i].CursorRenderPalette = NULL;
        }
    }

    delete [] gpSimCursors;
    gTotalCursors = 0;
}


void ClipAndDrawCursor(int displayWidth, int displayHeight)
{

    RECT CursorSrc;
    RECT CursorDest;

    if (gSelectedCursor < 0 or gSelectedCursor >= gTotalCursors)
    {
        return;
    }

    CursorSrc.top = 0;
    CursorSrc.left = 0;
    CursorSrc.bottom = gpSimCursors[gSelectedCursor].Height;
    CursorSrc.right = gpSimCursors[gSelectedCursor].Width;

    CursorDest.top = gyPos - gpSimCursors[gSelectedCursor].yHotspot;
    CursorDest.left = gxPos - gpSimCursors[gSelectedCursor].xHotspot;
    CursorDest.bottom = CursorDest.top + gpSimCursors[gSelectedCursor].Height;
    CursorDest.right = CursorDest.left + gpSimCursors[gSelectedCursor].Width;

    gyLast = gyPos;
    gxLast = gxPos;

    if (CursorDest.top < 0)
    {
        // Clipping necessary for the swap compose
        CursorSrc.top -= CursorDest.top;
        CursorDest.top = 0;
    }

    if (CursorDest.left < 0)
    {
        CursorSrc.left -= CursorDest.left;
        CursorDest.left = 0;
    }

    if (CursorDest.right > displayWidth - 1)
    {
        CursorSrc.right -= (CursorDest.right - displayWidth + 1);
        CursorDest.right = displayWidth - 1;
    }

    if (CursorDest.bottom > displayHeight - 1)
    {
        CursorSrc.bottom -= (CursorDest.bottom - displayHeight + 1);
        CursorDest.bottom = displayHeight - 1;
    }

    if ( not DisplayOptions.bRender2DCockpit)
        OTWDriver.OTWImage->ComposeTransparent(gpSimCursors[gSelectedCursor].CursorBuffer, &CursorSrc, &CursorDest);
    else
    {
        //Wombat778 3-24-04  If rendered cursor is enabled, dont blit, but render it instead

        OTWDriver.renderer->StartDraw();
        OTWDriver.renderer->CenterOriginInViewport();
        OTWDriver.renderer->SetViewport(-1.0, 1.0, 1.0, -1.0);

        TextureHandle *pTex = gpSimCursors[gSelectedCursor].CursorRenderTexture[0];
        // Setup vertices
        float fStartU = 0;
        float fMaxU = (float) pTex->m_nWidth / (float) pTex->m_nActualWidth;
        fMaxU -= fStartU;
        float fStartV = 0;
        float fMaxV = (float) pTex->m_nHeight / (float) pTex->m_nActualHeight;
        fMaxV -= fStartV;

        TwoDVertex pVtx[4];
        ZeroMemory(pVtx, sizeof(pVtx));

        pVtx[0].x = (float)CursorDest.left;
        pVtx[0].y = (float)CursorDest.top;
        pVtx[0].u = fStartU;
        pVtx[0].v = fStartV;
        pVtx[0].r = pVtx[0].g = pVtx[0].b = pVtx[0].a = 1.0f;
        pVtx[1].x = (float)CursorDest.right;
        pVtx[1].y = (float)CursorDest.top;
        pVtx[1].u = fMaxU;
        pVtx[1].v = fStartV;
        pVtx[1].r = pVtx[1].g = pVtx[1].b = pVtx[1].a = 1.0f;
        pVtx[2].x = (float)CursorDest.right;
        pVtx[2].y = (float)CursorDest.bottom;
        pVtx[2].u = fMaxU;
        pVtx[2].v = fMaxV;
        pVtx[2].r = pVtx[2].g = pVtx[2].b = pVtx[2].a = 1.0f;
        pVtx[3].x = (float)CursorDest.left;
        pVtx[3].y = (float)CursorDest.bottom;
        pVtx[3].u = fStartU;
        pVtx[3].v = fMaxV;
        pVtx[3].r = pVtx[3].g = pVtx[3].b = pVtx[3].a = 1.0f;


        OTWDriver.renderer->context.RestoreState(STATE_ALPHA_TEXTURE_NOFILTER);
        OTWDriver.renderer->context.SelectTexture1((intptr_t) pTex);
        OTWDriver.renderer->context.DrawPrimitive(MPR_PRM_TRIFAN, MPR_VI_COLOR bitor MPR_VI_TEXTURE, 4, pVtx, sizeof(pVtx[0]));
        OTWDriver.renderer->EndDraw();

        //Wombat778 3-24-04 end
    }

}
