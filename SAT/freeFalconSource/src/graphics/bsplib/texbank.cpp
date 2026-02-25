/***************************************************************************\
    Context.h
    Miro "Jammer" Torrielli
    10Oct03

 - Begin Major Rewrite
\***************************************************************************/
#include <cISO646>
#include <cstdint>
#include "stdafx.h"
#include <io.h>
#include <fcntl.h>
#include "Utils/lzss.h"
#include "loader.h"
#include "grinline.h"
#include "statestack.h"
#include "objectlod.h"
#include "PalBank.h"
#include "texbank.h"
#include "image.h"
#include "TerrTex.h"
#include "falclib/include/playerop.h"
#include "falclib/include/dispopts.h"
#ifdef FF_LINUX
#include "stdio_compat.h"  // for fopen_nocase
// DDS_FILE_HEADER is defined in ddraw.h for reading DDS files on 64-bit Linux
#endif

// Static data members (used to avoid requiring "this" to be passed to every access function)
int TextureBankClass::nTextures = 0;
TexBankEntry* TextureBankClass::TexturePool = NULL;
TempTexBankEntry* TextureBankClass::TempTexturePool = NULL;
BYTE* TextureBankClass::CompressedBuffer = NULL;
int TextureBankClass::deferredLoadState = 0;
char TextureBankClass::baseName[256];
FileMemMap TextureBankClass::TexFileMap;
#ifdef _DEBUG
int TextureBankClass::textureCount = 0;
#endif
TexFlagsType *TextureBankClass::TexFlags;
BYTE* TextureBankClass::TexBuffer;
DWORD TextureBankClass::TexBufferSize;
bool TextureBankClass::RatedLoad;
short *TextureBankClass::CacheLoad, *TextureBankClass::CacheRelease;
short TextureBankClass::LoadIn, TextureBankClass::LoadOut, TextureBankClass::ReleaseIn, TextureBankClass::ReleaseOut;

DWORD gDebugTextureID;

#ifdef USE_SH_POOLS
extern MEM_POOL gBSPLibMemPool;
#endif

extern bool g_bUseMappedFiles;
int nVer; // Header version


void TextureBankClass::Setup(int nEntries)
{
    // Create our array of texture headers
    nTextures = nEntries;

    if (nEntries)
    {
#ifdef USE_SH_POOLS
        TexturePool = (TexBankEntry *)MemAllocPtr(gBSPLibMemPool, sizeof(TexBankEntry) * nEntries, 0);
        TempTexturePool = (TempTexBankEntry *)MemAllocPtr(gBSPLibMemPool, sizeof(TempTexBankEntry) * nEntries, 0);
#else
        TexturePool = new TexBankEntry[nEntries];
        TempTexturePool = new TempTexBankEntry[nEntries];
#endif

        TexFlags = (TexFlagsType*) malloc(nTextures * sizeof(TexFlagsType));
        memset(TexFlags, 0, nTextures *  sizeof(TexFlagsType));
        // Allocte acche with a little safety margin
        CacheLoad = (short*) malloc(sizeof(short) * (nTextures + CACHE_MARGIN));
        CacheRelease = (short*) malloc(sizeof(short) * (nTextures + CACHE_MARGIN));
    }
    else
    {
        TexturePool = NULL;
        TempTexturePool = NULL;
        TexFlags = NULL;
        TexBuffer = NULL;
        CacheLoad = NULL;
        CacheRelease = NULL;
    }

    RatedLoad = true;
    LoadIn = LoadOut = ReleaseIn = ReleaseOut = 0;
}

void TextureBankClass::Cleanup(void)
{
    // wait for any update on textures
    WaitUpdates();
    // Clean up our array of texture headers
#ifdef USE_SH_POOLS
    MemFreePtr(TexturePool);
    MemFreePtr(TempTexturePool);
#else
    delete[] TexturePool;
    delete[] TempTexturePool;
#endif
    TexturePool = NULL;
    TempTexturePool = NULL;
    nTextures = 0;

    if (TexFlags) free(TexFlags), TexFlags = NULL;

    // Clean up the decompression buffer
#ifdef USE_SH_POOLS
    MemFreePtr(CompressedBuffer);
#else
    delete[] CompressedBuffer;
#endif
    CompressedBuffer = NULL;

    RatedLoad = false;

    if (CacheLoad)  free(CacheLoad), CacheLoad = NULL;

    if (CacheRelease)  free(CacheRelease), CacheRelease = NULL;

    LoadIn = LoadOut = ReleaseIn = ReleaseOut = 0;

    // Close our texture resource file
    if (TexFileMap.IsReady())
    {
        CloseTextureFile();
    }
}

// On-disk structure for TempTexBankEntry matching 32-bit Windows format
// This is needed because the file was written on 32-bit Windows where:
// - long is 4 bytes (not 8 bytes like on 64-bit Linux)
// - pointers are 4 bytes (not 8 bytes like on 64-bit)
#pragma pack(push, 1)
struct TempTexBankEntry_OnDisk
{
    int32_t fileOffset;      // 4 bytes (was long on Win32)
    int32_t fileSize;        // 4 bytes (was long on Win32)
    // Texture members (on 32-bit Windows):
    int32_t tex_dimensions;  // 4 bytes
    uint32_t tex_imageData;  // 4 bytes (was void*)
    uint32_t tex_flags;      // 4 bytes (DWORD)
    uint32_t tex_chromaKey;  // 4 bytes (DWORD)
    uint32_t tex_palette;    // 4 bytes (was Palette*)
    uint32_t tex_texHandle;  // 4 bytes (was TextureHandle*)
    int32_t palID;           // 4 bytes
    int32_t refCount;        // 4 bytes
};  // Total: 40 bytes
#pragma pack(pop)

void TextureBankClass::ReadPool(int file, char *basename)
{
    int result;
    int maxCompressedSize;

    ZeroMemory(baseName, sizeof(baseName));
    sprintf(baseName, "%s", basename);

    // Read the number of textures in the pool
    result = read(file, &nTextures, sizeof(nTextures));

    if (nTextures == 0) return;

    // Read the size of the biggest compressed texture in the pool
    result = read(file, &maxCompressedSize, sizeof(maxCompressedSize));

    // HACK - KO.dxh version - Note maxCompressedSize is used for the old BMP
    // textures, not DDS textures.
    nVer = maxCompressedSize;

#ifdef USE_SH_POOLS
    CompressedBuffer = (BYTE *)MemAllocPtr(gBSPLibMemPool, sizeof(BYTE) * maxCompressedSize, 0);
#else
    CompressedBuffer = new BYTE[maxCompressedSize];
#endif
    ShiAssert(CompressedBuffer);

    if (CompressedBuffer)
    {
        ZeroMemory(CompressedBuffer, maxCompressedSize);
    }

    // Setup the pool
    Setup(nTextures);

    // Read using the on-disk 32-bit format structure
    // The file was written on 32-bit Windows with different sizes for long and pointers
    TempTexBankEntry_OnDisk *diskEntries = new TempTexBankEntry_OnDisk[nTextures];
    result = read(file, diskEntries, sizeof(TempTexBankEntry_OnDisk) * nTextures);

    if (result < 0)
    {
        char message[256];
        sprintf(message, "Reading object texture bank: %s", strerror(errno));
        delete[] diskEntries;
        ShiError(message);
    }

    for (int i = 0; i < nTextures; i++)
    {
        // Copy from on-disk format to runtime format
        TempTexturePool[i].fileOffset = diskEntries[i].fileOffset;
        TempTexturePool[i].fileSize = diskEntries[i].fileSize;
        TempTexturePool[i].tex.dimensions = diskEntries[i].tex_dimensions;
        // Note: imageData, palette, and texHandle pointers from file are garbage
        // - they were runtime values when the file was created
        TempTexturePool[i].tex.flags = diskEntries[i].tex_flags;
        TempTexturePool[i].tex.chromaKey = diskEntries[i].tex_chromaKey;
        TempTexturePool[i].palID = diskEntries[i].palID;
        TempTexturePool[i].refCount = diskEntries[i].refCount;
    }

    delete[] diskEntries;

    for (int i = 0; i < nTextures; i++)
    {
        TexturePool[i].fileOffset = TempTexturePool[i].fileOffset;
        TexturePool[i].fileSize = TempTexturePool[i].fileSize;

        TexturePool[i].tex = TempTexturePool[i].tex;
        TexturePool[i].tex.flags or_eq MPR_TI_INVALID;
        TexturePool[i].texN = TempTexturePool[i].tex;
        TexturePool[i].texN.flags or_eq MPR_TI_INVALID;

        if (DisplayOptions.bMipmapping)
        {
            TexturePool[i].tex.flags or_eq MPR_TI_MIPMAP;
            TexturePool[i].texN.flags or_eq MPR_TI_MIPMAP;
        }

        TexturePool[i].palID = 0;//TempTexturePool[i].palID;
        TexturePool[i].refCount = 0;//TempTexturePool[i].refCount;
    }



    OpenTextureFile();
}

void TextureBankClass::FreeCompressedBuffer()
{
#ifdef USE_SH_POOLS
    MemFreePtr(CompressedBuffer);
#else
    delete[] CompressedBuffer;
#endif

    CompressedBuffer = NULL;
}

void TextureBankClass::AllocCompressedBuffer(int maxCompressedSize)
{
#ifdef USE_SH_POOLS
    CompressedBuffer = (BYTE *)MemAllocPtr(gBSPLibMemPool, sizeof(BYTE) * maxCompressedSize, 0);
#else
    CompressedBuffer = new BYTE[maxCompressedSize];
#endif

    ShiAssert(CompressedBuffer);

    if (CompressedBuffer)
    {
        ZeroMemory(CompressedBuffer, maxCompressedSize);
    }
}

void TextureBankClass::OpenTextureFile()
{
    char filename[_MAX_PATH];

    ShiAssert( not TexFileMap.IsReady());

    strcpy(filename, baseName);
    strcat(filename, ".TEX");

    if ( not TexFileMap.Open(filename, FALSE, not g_bUseMappedFiles))
    {
        char message[256];
        sprintf(message, "Failed to open object texture file %s\n", filename);
        ShiError(message);
    }
}

void TextureBankClass::CloseTextureFile(void)
{
    TexFileMap.Close();
}

void TextureBankClass::Reference(int id)
{
    int  isLoaded;

    gDebugTextureID = id;

    ShiAssert(IsValidIndex(id));

    // Get our reference to this texture recorded to ensure it doesn't disappear out from under us
    //EnterCriticalSection(&ObjectLOD::cs_ObjectLOD);

    isLoaded = TexturePool[id].refCount;
    ShiAssert(isLoaded >= 0);
    TexturePool[id].refCount++;

    // If we already have the data, just verify that fact. Otherwise, load it.
    if (isLoaded)
    {
        ;
    }
    else
    {
        ShiAssert(TexFileMap.IsReady());
        ShiAssert(CompressedBuffer);
        if(TexturePool[id].tex.imageData not_eq NULL)
            return;
        ShiAssert(TexturePool[id].tex.TexHandle() == NULL);

        // Get the palette pointer
        // would be great if we could set a flag saying this palette comes from bank...
        // but since we cannot add anything to texture structure (because Jammer read them
        // directly from file instead of from a method) I make the check when releasing
        // the palette.
        TexturePool[id].tex.SetPalette(&ThePaletteBank.PalettePool[TexturePool[id].palID]);
        ShiAssert(TexturePool[id].tex.GetPalette());
        TexturePool[id].tex.GetPalette()->Reference();

        // Mark for the request if not already marked
        if ( not TexFlags[id].OnOrder)
        {
            TexFlags[id].OnOrder = true;
            // put into load cache
            CacheLoad[LoadIn++] = id;

            // Ring the pointer
            if (LoadIn >= (nTextures + CACHE_MARGIN)) LoadIn = 0;

            // Kick the Loader
            TheLoader.WakeUp();

        }

    }

    gDebugTextureID = -1;

}

// Calls to this func are enclosed in the critical section cs_ObjectLOD by ObjectLOD::Unload()
void TextureBankClass::Release(int id)
{
    ShiAssert(IsValidIndex(id));
    ShiAssert(TexturePool[id].refCount > 0);

    // RED - no reference, no party... 
    if ( not TexturePool[id].refCount) 
        return;

    TexturePool[id].refCount--;

    if (TexturePool[id].refCount == 0)
    {
        if ( not TexFlags[id].OnRelease)
        {
            TexFlags[id].OnRelease = true;
            // put into load cache
            CacheRelease[ReleaseIn++] = id;

            // Ring the pointer
            if (ReleaseIn >= (nTextures + CACHE_MARGIN)) ReleaseIn = 0;

            // Kick the Loader
            TheLoader.WakeUp();
        }
    }
}

void TextureBankClass::ReadImageData(int id, bool forceNoDDS)
{
    int retval;
    int size;
    BYTE *cdata;
    //sfr: added for more control
    int cdataSize;


    ShiAssert(TexturePool[id].refCount);

    if ( not forceNoDDS and DisplayOptions.m_texMode == DisplayOptionsClass::TEX_MODE_DDS)
    {
        ReadImageDDS(id);
        ReadImageDDSN(id);
        return;
    }

    if (g_bUseMappedFiles)
    {
        cdata = TexFileMap.GetData(TexturePool[id].fileOffset, TexturePool[id].fileSize);
        cdataSize = TexturePool[id].fileSize - TexturePool[id].fileOffset;
        ShiAssert(cdata);
    }
    else
    {
        if ( not TexFileMap.ReadDataAt(TexturePool[id].fileOffset, CompressedBuffer, TexturePool[id].fileSize))
        {
            char message[120];
            sprintf(message, "%s: Bad object texture seek (%0d)", strerror(errno), TexturePool[id].fileOffset);
            ShiError(message);
        }

        cdata = CompressedBuffer;
        //sfr: in this case, im not sure size is this
        // FRB - fileOffset - fileOffset ????
        //cdataSize = TexturePool[id].fileOffset - TexturePool[id].fileOffset;
        cdataSize = TexturePool[id].fileSize - TexturePool[id].fileOffset;
    }

    // Allocate memory for the new texture
    size = TexturePool[id].tex.dimensions;
    size = size * size;

    TexturePool[id].tex.imageData = glAllocateMemory(size, FALSE);
    ShiAssert(TexturePool[id].tex.imageData);

    // Uncompress the data into the texture structure
    //sfr: using new cdataSize for control
    retval = LZSS_Expand(cdata, cdataSize, (BYTE*)TexturePool[id].tex.imageData, size);
    ShiAssert(retval == TexturePool[id].fileSize);

#ifdef _DEBUG
    textureCount++;
#endif
}

void TextureBankClass::SetDeferredLoad(BOOL state)
{
    LoaderQ *request;

    // Allocate space for the async request
    request = new LoaderQ;

    if ( not request)
        ShiError("Failed to allocate memory for a object texture load state change request");

    // Build the data transfer request to get the required object data
    request->filename = NULL;
    request->fileoffset = 0;
    request->callback = LoaderCallBack;
    request->parameter = (void*)state;

    // Submit the request to the asynchronous loader
    TheLoader.EnqueueRequest(request);
}

void TextureBankClass::LoaderCallBack(LoaderQ* request)
{
    BOOL state = (int)request->parameter;

    //EnterCriticalSection(&ObjectLOD::cs_ObjectLOD);

    // If we're turning deferred loads off, go back and do all the loads we held up
    if (deferredLoadState and not state)
    {
        DWORD Count = 5;

        // Check each texture
        for (int id = 0; id < nTextures; id++)
        {
            // See if it is in use
            if (TexturePool[id].refCount)

                // This one is in use. Is it already loaded?
                if (/* not TexturePool[id].tex.imageData and */ not TexturePool[id].tex.TexHandle())
                {

                    // Nope, go get it.
                    if ( not TexturePool[id].tex.imageData) ReadImageData(id);
#ifndef FF_LINUX
                    // FF_LINUX: Skip CreateTexture() - this runs on Loader thread with no GL context.
                    // Textures will be created lazily in GetHandle() on the rendering thread.
                    TexturePool[id].tex.CreateTexture();
#endif
                    Count--;
                    //TexturePool[id].tex.FreeImage();
                }

            if ( not Count) break;
        }
    }

    // Now store the new state
    deferredLoadState = state;

    //LeaveCriticalSection(&ObjectLOD::cs_ObjectLOD);

    // Free the request queue entry
    delete request;
}

void TextureBankClass::FlushHandles(void)
{
    int id;

    for (id = 0; id < nTextures; id++)
    {
        ShiAssert(TexturePool[id].refCount == 0);

        while (TexturePool[id].refCount > 0)
        {
            Release(id);
        }
    }

    WaitUpdates();
}

void TextureBankClass::Select(int id)
{
}


void TextureBankClass::SelectHandle(intptr_t TexHandle)
{
    TheStateStack.context->SelectTexture1(TexHandle);
}


BOOL TextureBankClass::IsValidIndex(int id)
{
    return((id >= 0) and (id < nTextures));
}

void TextureBankClass::RestoreAll()
{
#ifdef FF_LINUX
    // FF_LINUX: Retry texture creation for entries loaded by the Loader thread
    // before DeviceDependentGraphicsSetup() set the DXContext (rc).
    // These entries have imageData but no texHandle because CreateTexture() failed
    // when rc was NULL.
    if ( not Texture::IsSetup()) return;

    int retryCount = 0, successCount = 0;
    for (int id = 0; id < nTextures; id++)
    {
        if (TexturePool[id].refCount > 0 &&
            TexturePool[id].tex.imageData != NULL &&
            TexturePool[id].tex.TexHandle() == 0)
        {
            retryCount++;
            if (TexturePool[id].tex.CreateTexture())
            {
                successCount++;
            }
        }
    }
    if (retryCount > 0)
    {
        fprintf(stderr, "[RestoreAll] Retried %d textures, %d succeeded\n", retryCount, successCount);
        fflush(stderr);
    }
#endif
}

void TextureBankClass::SyncDDSTextures(bool bForce)
{
    char szFile[256];
    FILE *fp;

    ShiAssert(TexturePool);

    CreateDirectory(baseName, NULL);

    for (DWORD id = 0; id < (DWORD)nTextures; id++)
    {
#ifdef FF_LINUX
        sprintf(szFile, "%s/%d.dds", baseName, id);
        fp = fopen_nocase(szFile, "rb");
#else
        sprintf(szFile, "%s\\%d.dds", baseName, id);
        fp = fopen(szFile, "rb");
#endif

        if ( not fp or bForce)
        {
            if (fp)
                fclose(fp);

            UnpackPalettizedTexture(id);
        }
        else
            fclose(fp);

        TexturePool[id].tex.flags or_eq MPR_TI_DDS;
        TexturePool[id].tex.flags and_eq compl MPR_TI_PALETTE;
        TexturePool[id].texN.flags or_eq MPR_TI_DDS;
        TexturePool[id].texN.flags and_eq compl MPR_TI_PALETTE;
    }
}

void TextureBankClass::UnpackPalettizedTexture(DWORD id)
{
    char szFile[256];

    CreateDirectory(baseName, NULL);

    if (TexturePool[id].tex.dimensions > 0)
    {
        //sfr: (see my comment regarding palette origin above)
        TexturePool[id].tex.SetPalette(&ThePaletteBank.PalettePool[TexturePool[id].palID]);
        ShiAssert(TexturePool[id].tex.GetPalette());
        TexturePool[id].tex.GetPalette()->Reference();

        ReadImageData(id, true);
#ifdef FF_LINUX
        sprintf(szFile, "%s/%d", baseName, id);
#else
        sprintf(szFile, "%s\\%d", baseName, id);
#endif
        TexturePool[id].tex.DumpImageToFile(szFile, TexturePool[id].palID);
        Release(id);
    }
    else
    {
#ifdef FF_LINUX
        sprintf(szFile, "%s/%d.dds", baseName, id);
#else
        sprintf(szFile, "%s\\%d.dds", baseName, id);
#endif
        FILE* fp = fopen(szFile, "wb");
        fclose(fp);
    }
}



void TextureBankClass::ReadImageDDS(DWORD id)
{
    DWORD dwSize, dwMagic;
    char szFile[256];
    FILE *fp;

    TexturePool[id].tex.flags = MPR_TI_DDS;
    TexturePool[id].tex.flags and_eq compl MPR_TI_PALETTE;

#ifdef FF_LINUX
    sprintf(szFile, "%s/%d.dds", baseName, id);
    fp = fopen_nocase(szFile, "rb");
#else
    sprintf(szFile, "%s\\%d.dds", baseName, id);
    fp = fopen(szFile, "rb");
#endif

    // RV - RED - Avoid CTD if a missing texture
    if ( not fp) return;

    fread(&dwMagic, 1, sizeof(DWORD), fp);
    ShiAssert(dwMagic == MAKEFOURCC('D', 'D', 'S', ' '));

    // Read first compressed mipmap
#ifdef FF_LINUX
    // FF_LINUX: Use fixed 124-byte DDS header struct to avoid 64-bit pointer
    // size mismatch in DDSURFACEDESC2 (which has LPVOID lpSurface = 8 bytes)
    DDS_FILE_HEADER ddsd;
    memset(&ddsd, 0, sizeof(ddsd));
    fread(&ddsd, 1, sizeof(DDS_FILE_HEADER), fp);
#else
    DDSURFACEDESC2 ddsd;
    fread(&ddsd, 1, sizeof(DDSURFACEDESC2), fp);
#endif

    // MLR 1/25/2004 - Little kludge so FF can read DDS files made by dxtex
    if (ddsd.dwLinearSize == 0)
    {
        if (ddsd.ddpfPixelFormat.dwFourCC == MAKEFOURCC('D', 'X', 'T', '3') or
            ddsd.ddpfPixelFormat.dwFourCC == MAKEFOURCC('D', 'X', 'T', '5'))
        {
            ddsd.dwLinearSize = ddsd.dwWidth * ddsd.dwWidth;
            ddsd.dwFlags or_eq DDSD_LINEARSIZE;
        }

        if (ddsd.ddpfPixelFormat.dwFourCC == MAKEFOURCC('D', 'X', 'T', '1'))
        {
            ddsd.dwLinearSize = ddsd.dwWidth * ddsd.dwWidth / 2;
            ddsd.dwFlags or_eq DDSD_LINEARSIZE;
        }
    }


    ShiAssert(ddsd.dwFlags bitand DDSD_LINEARSIZE)


    switch (ddsd.ddpfPixelFormat.dwFourCC)
    {
        case MAKEFOURCC('D', 'X', 'T', '1'):
            TexturePool[id].tex.flags or_eq MPR_TI_DXT1;
            break;

        case MAKEFOURCC('D', 'X', 'T', '3'):
            TexturePool[id].tex.flags or_eq MPR_TI_DXT3;
            break;

        case MAKEFOURCC('D', 'X', 'T', '5'):
            TexturePool[id].tex.flags or_eq MPR_TI_DXT5;
            break;

        default:
#ifdef FF_LINUX
            fprintf(stderr, "[ReadImageDDS] Unknown FourCC 0x%08x for texture %d, skipping\n",
                    ddsd.ddpfPixelFormat.dwFourCC, id);
            fclose(fp);
            return;
#else
            ShiAssert(false);
#endif
    }

    switch (ddsd.dwWidth)
    {
        case 16:
            TexturePool[id].tex.flags or_eq MPR_TI_16;
            break;

        case 32:
            TexturePool[id].tex.flags or_eq MPR_TI_32;
            break;

        case 64:
            TexturePool[id].tex.flags or_eq MPR_TI_64;
            break;

        case 128:
            TexturePool[id].tex.flags or_eq MPR_TI_128;
            break;

        case 256:
            TexturePool[id].tex.flags or_eq MPR_TI_256;
            break;

        case 512:
            TexturePool[id].tex.flags or_eq MPR_TI_512;
            break;

        case 1024:
            TexturePool[id].tex.flags or_eq MPR_TI_1024;
            break;

        case 2048:
            TexturePool[id].tex.flags or_eq MPR_TI_2048;
            break;

        default:
#ifdef FF_LINUX
            fprintf(stderr, "[ReadImageDDS] Unknown width %d for texture %d, skipping\n",
                    ddsd.dwWidth, id);
            fclose(fp);
            return;
#else
            ShiAssert(false);
#endif
    }

    dwSize = ddsd.dwLinearSize;
    TexturePool[id].tex.imageData = (BYTE *)glAllocateMemory(dwSize, FALSE);
    fread(TexturePool[id].tex.imageData, 1, dwSize, fp);

    TexturePool[id].tex.dimensions = dwSize;

    fclose(fp);

#ifdef _DEBUG
    textureCount++;
#endif
}

void TextureBankClass::ReadImageDDSN(DWORD id)
{
    DWORD dwSize, dwMagic;
    char szFile[256];
    FILE *fp;

#ifdef FF_LINUX
    sprintf(szFile, "%s/%dN.dds", baseName, id);
    fp = fopen_nocase(szFile, "rb");
#else
    sprintf(szFile, "%s\\%dN.dds", baseName, id);
    fp = fopen(szFile, "rb");
#endif

    if ( not fp)
    {
        return;
    }

    TexturePool[id].texN.flags or_eq MPR_TI_DDS;
    TexturePool[id].texN.flags and_eq compl MPR_TI_PALETTE;
    TexturePool[id].texN.flags and_eq compl MPR_TI_INVALID;

    fread(&dwMagic, 1, sizeof(DWORD), fp);
    ShiAssert(dwMagic == MAKEFOURCC('D', 'D', 'S', ' '));

    // Read first compressed mipmap
#ifdef FF_LINUX
    DDS_FILE_HEADER ddsd;
    memset(&ddsd, 0, sizeof(ddsd));
    fread(&ddsd, 1, sizeof(DDS_FILE_HEADER), fp);
#else
    DDSURFACEDESC2 ddsd;
    fread(&ddsd, 1, sizeof(DDSURFACEDESC2), fp);
#endif

    // MLR 1/25/2004 - Little kludge so FF can read DDS files made by dxtex
    if (ddsd.dwLinearSize == 0)
    {
        if (ddsd.ddpfPixelFormat.dwFourCC == MAKEFOURCC('D', 'X', 'T', '3') or
            ddsd.ddpfPixelFormat.dwFourCC == MAKEFOURCC('D', 'X', 'T', '5'))
        {
            ddsd.dwLinearSize = ddsd.dwWidth * ddsd.dwWidth;
            ddsd.dwFlags or_eq DDSD_LINEARSIZE;
        }

        if (ddsd.ddpfPixelFormat.dwFourCC == MAKEFOURCC('D', 'X', 'T', '1'))
        {
            ddsd.dwLinearSize = ddsd.dwWidth * ddsd.dwWidth / 2;
            ddsd.dwFlags or_eq DDSD_LINEARSIZE;
        }
    }

    ShiAssert(ddsd.dwFlags bitand DDSD_LINEARSIZE)

    switch (ddsd.ddpfPixelFormat.dwFourCC)
    {
        case MAKEFOURCC('D', 'X', 'T', '1'):
            TexturePool[id].texN.flags or_eq MPR_TI_DXT1;
            break;

        case MAKEFOURCC('D', 'X', 'T', '3'):
            TexturePool[id].tex.flags or_eq MPR_TI_DXT3;
            break;

        case MAKEFOURCC('D', 'X', 'T', '5'):
            TexturePool[id].texN.flags or_eq MPR_TI_DXT5;
            break;

        default:
            ShiAssert(false);
    }

    switch (ddsd.dwWidth)
    {
        case 16:
            TexturePool[id].texN.flags or_eq MPR_TI_16;
            break;

        case 32:
            TexturePool[id].texN.flags or_eq MPR_TI_32;
            break;

        case 64:
            TexturePool[id].texN.flags or_eq MPR_TI_64;
            break;

        case 128:
            TexturePool[id].texN.flags or_eq MPR_TI_128;
            break;

        case 256:
            TexturePool[id].texN.flags or_eq MPR_TI_256;
            break;

        case 512:
            TexturePool[id].texN.flags or_eq MPR_TI_512;
            break;

        case 1024:
            TexturePool[id].texN.flags or_eq MPR_TI_1024;
            break;

        case 2048:
            TexturePool[id].texN.flags or_eq MPR_TI_2048;
            break;

        default:
            ShiAssert(false);
    }

    dwSize = ddsd.dwLinearSize;
    TexturePool[id].texN.imageData = (BYTE *)glAllocateMemory(dwSize, FALSE);
    fread(TexturePool[id].texN.imageData, 1, dwSize, fp);

    TexturePool[id].texN.dimensions = dwSize;

    fclose(fp);

#ifdef _DEBUG
    textureCount++;
#endif
}

void TextureBankClass::RestoreTexturePool()
{
    for (int i = 0; i < nTextures; i++)
    {
        TexturePool[i].fileOffset = TempTexturePool[i].fileOffset;
        TexturePool[i].fileSize = TempTexturePool[i].fileSize;
        TexturePool[i].tex = TempTexturePool[i].tex;
        TexturePool[i].texN = TempTexturePool[i].tex;
        TexturePool[i].palID = TempTexturePool[i].palID;
        TexturePool[i].refCount = TempTexturePool[i].refCount;
    }
}



// FF_LINUX: Diagnostic counters for GetHandle results
#ifdef FF_LINUX
static int g_ghOK = 0;         // Returned valid handle
static int g_ghLazy = 0;       // Lazy-created handle
static int g_ghNoImage = 0;    // No imageData (loader not done)
static int g_ghCreateFail = 0; // CreateTexture failed
static int g_ghRelease = 0;    // OnRelease flag set
static int g_ghInvalid = 0;    // Invalid index

extern "C" void FF_GetHandleStats(int* ok, int* lazy, int* noImage, int* createFail, int* release, int* invalid) {
    *ok = g_ghOK; *lazy = g_ghLazy; *noImage = g_ghNoImage;
    *createFail = g_ghCreateFail; *release = g_ghRelease; *invalid = g_ghInvalid;
}
extern "C" void FF_GetHandleStatsReset() {
    g_ghOK = g_ghLazy = g_ghNoImage = g_ghCreateFail = g_ghRelease = g_ghInvalid = 0;
}
#endif

intptr_t TextureBankClass::GetHandle(DWORD id)
{
    // if already on release, avoid using or requesting it
    if (TexFlags[id].OnRelease) {
#ifdef FF_LINUX
        g_ghRelease++;
#endif
        return 0;
    }

    // if the Handle is present, return it
    if (IsValidIndex(id) and TexturePool[id].tex.TexHandle()) {
#ifdef FF_LINUX
        g_ghOK++;
#endif
        return TexturePool[id].tex.TexHandle();
    }

#ifdef FF_LINUX
    // FF_LINUX: Lazy GL texture creation. The Loader thread loaded image data from disk
    // but couldn't call CreateTexture() because it has no OpenGL context. Now that we're
    // on the rendering thread (which owns the GL context), create the texture.
    if (IsValidIndex(id) and TexturePool[id].tex.imageData and Texture::IsSetup())
    {
        TexturePool[id].tex.CreateTexture();
        if (TexturePool[id].tex.TexHandle()) {
            g_ghLazy++;
            return TexturePool[id].tex.TexHandle();
        }
        g_ghCreateFail++;
        return 0;
    }

    if (!IsValidIndex(id)) {
        g_ghInvalid++;
    } else {
        g_ghNoImage++;
    }
#endif

    // return  a null pointer that means BLANK SURFACE
    return 0;
}



// RED - This function manages to load and create requested textures
bool TextureBankClass::UpdateBank(void)
{
    DWORD id;


    // till when data to update into caches
    while (LoadIn not_eq LoadOut or ReleaseIn not_eq ReleaseOut)
    {

        // check for textures to be released
        if (ReleaseIn not_eq ReleaseOut)
        {
            // get the 1st texture Id from cache
            id = CacheRelease[ReleaseOut++];

            // if not an order again, and no Referenced, release it
            if ( not TexFlags[id].OnOrder and not TexturePool[id].refCount and TexFlags[id].OnRelease) TexturePool[id].tex.FreeAll();

            // clear flag, in any case
            TexFlags[id].OnRelease = false;

            // ring the pointer
            if (ReleaseOut >= (nTextures + CACHE_MARGIN)) ReleaseOut = 0;

            // if any action, terminate here
            if (RatedLoad) return true;
        }

        // check for textures to be loaded
        if (LoadIn not_eq LoadOut)
        {
            // get the 1st texture Id from cache
            id = CacheLoad[LoadOut++];

            // if Texture not yet loaded, load it
            if ( not TexturePool[id].tex.imageData) ReadImageData(id);

            // if Texture not yet created, create it
#ifdef FF_LINUX
            // FF_LINUX: Skip CreateTexture() here - this function is called from the
            // Loader thread which has no OpenGL context. GL texture creation will happen
            // lazily in GetHandle() when called from the rendering thread.
            // Only load image data on the Loader thread.
#else
            if ( not TexturePool[id].tex.TexHandle())
            {
                TexturePool[id].tex.CreateTexture();
            }
#endif

            // clear flag, in any case
            TexFlags[id].OnOrder = false;

            // ring the pointer
            if (LoadOut >= (nTextures + CACHE_MARGIN)) LoadOut = 0;

            // if any action, terminate here
            if (RatedLoad) return true;
        }

    }

    // if here, nothing done, back is up to date
    return false;
}


void TextureBankClass::WaitUpdates(void)
{
    // if no data to wait, exit here
    if (LoadIn == LoadOut and ReleaseIn == ReleaseOut) return;

    // Pause the Loader...
    TheLoader.SetPause(true);

    while ( not TheLoader.Paused());

    // Not slow loading
    RatedLoad = false;

    // Parse all objects till any opration to do
    while (UpdateBank());

    // Restore rated loading
    RatedLoad = true;
    // Run the Loader again
    TheLoader.SetPause(false);
}


void TextureBankClass::CreateCallBack(LoaderQ* request)
{
}


void TextureBankClass::ReferenceTexSet(DWORD *TexList, DWORD Nr)
{
    while (Nr--) 
    {
        Reference(*TexList);
        TexList++;
    }
}

void TextureBankClass::ReleaseTexSet(DWORD *TexList, DWORD Nr)
{
    while (Nr--) 
    {
        Release(*TexList);
        TexList++;
    }
}
