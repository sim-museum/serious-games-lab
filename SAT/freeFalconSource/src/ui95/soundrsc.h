#ifndef _SOUND_RSC_H_
#define _SOUND_RSC_H_

#include <stdint.h>

//
// This class is TIED to the C_Resmgr class (which holds the actual sound data)
//
// (So you need both to actually be able to play a sound)
//

// First item MUST be     short Type
// NOTE: Must use int32_t for all "long" fields to match Windows 32-bit binary file format
class SoundHeader
{
#ifdef USE_SH_POOLS
public:
    // Overload new/delete to use a SmartHeap pool
    void *operator new(size_t size)
    {
        return MemAllocPtr(UI_Pools[UI_SOUND_POOL], size, FALSE);
    };
    void operator delete(void *mem)
    {
        if (mem) MemFreePtr(mem);
    };
#endif
public:
    int32_t Type;         // Must be 32-bit for binary file compatibility
    char    ID[32];
    int32_t flags;        // Must be 32-bit for binary file compatibility
    int16_t Channels;
    int16_t SoundType;
    int32_t offset;       // Must be 32-bit for binary file compatibility
    int32_t headersize;   // Must be 32-bit for binary file compatibility
};

class SOUND_RSC
{
#ifdef USE_SH_POOLS
public:
    // Overload new/delete to use a SmartHeap pool
    void *operator new(size_t size)
    {
        return MemAllocPtr(UI_Pools[UI_SOUND_POOL], size, FALSE);
    };
    void operator delete(void *mem)
    {
        if (mem) MemFreePtr(mem);
    };
#endif
public:
    long ID;
    C_Resmgr *Owner;
    SoundHeader *Header;

    BOOL Play(int Stream);
    BOOL Loop(int Stream);
    BOOL Stream(int Stream);
};

#endif
