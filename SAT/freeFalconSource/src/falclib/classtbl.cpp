// Use objects in directory ObjectSet0708 with this file.
/*
 * Machine Generated Class Table Constants loader file.
 * NOTE: This file is read only. DO NOT ATTEMPT TO MODIFY IT BY HAND.
 * Generated on 11-August-1999 at 16:28:04
 * Generated from file Access Class Table
 */

#include <windows.h>
#include <stdio.h>
#include "F4vu.h"
#include "ClassTbl.h"
#include "F4Find.h"
#include "entity.h"

#ifdef FF_LINUX
#include <stdint.h>

// On-disk structures matching 32-bit Windows format
// These structures must be packed and use fixed-size types
#pragma pack(push, 1)

// VuEntityType on-disk format (60 bytes on 32-bit Windows)
// The struct is 57 bytes of data + 3 bytes padding to align to 4-byte boundary
struct VuEntityType_OnDisk
{
    uint16_t id_;                    // 2 bytes
    uint16_t collisionType_;         // 2 bytes
    float collisionRadius_;          // 4 bytes (SM_SCALAR)
    uint8_t classInfo_[8];           // 8 bytes (CLASS_NUM_BYTES)
    uint32_t updateRate_;            // 4 bytes (VU_TIME - unsigned long on 32-bit)
    uint32_t updateTolerance_;       // 4 bytes
    float bubbleRange_;              // 4 bytes
    float fineUpdateForceRange_;     // 4 bytes
    float fineUpdateMultiplier_;     // 4 bytes
    uint32_t damageSeed_;            // 4 bytes (VU_DAMAGE - unsigned long on 32-bit)
    int32_t hitpoints_;              // 4 bytes
    uint16_t majorRevisionNumber_;   // 2 bytes
    uint16_t minorRevisionNumber_;   // 2 bytes
    uint16_t createPriority_;        // 2 bytes
    uint8_t managementDomain_;       // 1 byte
    uint8_t transferable_;           // 1 byte
    uint8_t private_;                // 1 byte
    uint8_t tangible_;               // 1 byte
    uint8_t collidable_;             // 1 byte
    uint8_t global_;                 // 1 byte
    uint8_t persistent_;             // 1 byte
    uint8_t _padding[3];             // 3 bytes padding to align to 4-byte boundary
};  // Total: 60 bytes

// Falcon4EntityClassType on-disk format (81 bytes on 32-bit Windows)
struct Falcon4EntityClassType_OnDisk
{
    VuEntityType_OnDisk vuClassData; // 60 bytes
    int16_t visType[7];              // 14 bytes
    int16_t vehicleDataIndex;        // 2 bytes
    uint8_t dataType;                // 1 byte
    uint32_t dataPtr;                // 4 bytes (void* on 32-bit)
};  // Total: 81 bytes

#pragma pack(pop)
#endif // FF_LINUX

extern bool g_bFFDBC;

// Which langauge should we use?
int gLangIDNum = 1;

/*
* Class Table Constant Init Function
*/

void InitClassTableAndData(char *name, char *objset)
{
    FILE* filePtr;
    char  fileName[MAX_PATH];

    if (stricmp(objset, "objects") not_eq 0)
    {
        //Check for correct object data version
        ShiAssert(stricmp("ObjectSet0708", objset) == 0);
    }

#ifdef FF_LINUX
    sprintf(fileName, "%s/%s.ini", FalconObjectDataDir, name);
#else
    sprintf(fileName, "%s\\%s.ini", FalconObjectDataDir, name);
#endif

    gLangIDNum = GetPrivateProfileInt("Lang", "Id", 0, fileName);

    filePtr = OpenCampFile(name, "ct", "rb");

    if (filePtr)
    {
        //fread (&NumEntities, sizeof (short), 1, filePtr);
        // FF - DB Control
        //fseek(filePtr, 0, SEEK_SET);
        fread(&NumEntities, sizeof(short), 1, filePtr);
        fseek(filePtr, 0, SEEK_SET);

        if (NumEntities == 0)
            g_bFFDBC = true;

        // FF - DB Control
        if (g_bFFDBC)
        {
            // FF - get real count of entries
            short iknt = 0;
            fseek(filePtr, 0, SEEK_END);
            fseek(filePtr, -2, SEEK_CUR);
            fread(&iknt, sizeof(short), 1, filePtr);
            fseek(filePtr, 0, SEEK_SET);
            // Move pointer past the 0 entries
            fread(&NumEntities, sizeof(short), 1, filePtr);

            if (NumEntities == 0)
                NumEntities = iknt;
        }
        else
        {
            fseek(filePtr, 0, SEEK_SET);
            fread(&NumEntities, sizeof(short), 1, filePtr);
        }

        Falcon4ClassTable = new Falcon4EntityClassType[NumEntities];

#ifdef FF_LINUX
        // Read using on-disk 32-bit structure format, then convert to 64-bit runtime format
        Falcon4EntityClassType_OnDisk* tempTable = new Falcon4EntityClassType_OnDisk[NumEntities];
        fread(tempTable, sizeof(Falcon4EntityClassType_OnDisk), NumEntities, filePtr);

        // Convert from on-disk format to runtime format
        for (int i = 0; i < NumEntities; i++)
        {
            // Copy VuEntityType fields
            Falcon4ClassTable[i].vuClassData.id_ = tempTable[i].vuClassData.id_;
            Falcon4ClassTable[i].vuClassData.collisionType_ = tempTable[i].vuClassData.collisionType_;
            Falcon4ClassTable[i].vuClassData.collisionRadius_ = tempTable[i].vuClassData.collisionRadius_;
            memcpy(Falcon4ClassTable[i].vuClassData.classInfo_, tempTable[i].vuClassData.classInfo_, 8);
            Falcon4ClassTable[i].vuClassData.updateRate_ = tempTable[i].vuClassData.updateRate_;
            Falcon4ClassTable[i].vuClassData.updateTolerance_ = tempTable[i].vuClassData.updateTolerance_;
            Falcon4ClassTable[i].vuClassData.bubbleRange_ = tempTable[i].vuClassData.bubbleRange_;
            Falcon4ClassTable[i].vuClassData.fineUpdateForceRange_ = tempTable[i].vuClassData.fineUpdateForceRange_;
            Falcon4ClassTable[i].vuClassData.fineUpdateMultiplier_ = tempTable[i].vuClassData.fineUpdateMultiplier_;
            Falcon4ClassTable[i].vuClassData.damageSeed_ = tempTable[i].vuClassData.damageSeed_;
            Falcon4ClassTable[i].vuClassData.hitpoints_ = tempTable[i].vuClassData.hitpoints_;
            Falcon4ClassTable[i].vuClassData.majorRevisionNumber_ = tempTable[i].vuClassData.majorRevisionNumber_;
            Falcon4ClassTable[i].vuClassData.minorRevisionNumber_ = tempTable[i].vuClassData.minorRevisionNumber_;
            Falcon4ClassTable[i].vuClassData.createPriority_ = tempTable[i].vuClassData.createPriority_;
            Falcon4ClassTable[i].vuClassData.managementDomain_ = tempTable[i].vuClassData.managementDomain_;
            Falcon4ClassTable[i].vuClassData.transferable_ = tempTable[i].vuClassData.transferable_;
            Falcon4ClassTable[i].vuClassData.private_ = tempTable[i].vuClassData.private_;
            Falcon4ClassTable[i].vuClassData.tangible_ = tempTable[i].vuClassData.tangible_;
            Falcon4ClassTable[i].vuClassData.collidable_ = tempTable[i].vuClassData.collidable_;
            Falcon4ClassTable[i].vuClassData.global_ = tempTable[i].vuClassData.global_;
            Falcon4ClassTable[i].vuClassData.persistent_ = tempTable[i].vuClassData.persistent_;

            // Copy other Falcon4EntityClassType fields
            memcpy(Falcon4ClassTable[i].visType, tempTable[i].visType, sizeof(tempTable[i].visType));
            Falcon4ClassTable[i].vehicleDataIndex = tempTable[i].vehicleDataIndex;
            Falcon4ClassTable[i].dataType = tempTable[i].dataType;
            // dataPtr is stored as an index/offset, convert uint32_t to void*
            Falcon4ClassTable[i].dataPtr = (void*)(intptr_t)tempTable[i].dataPtr;
        }

        delete[] tempTable;
#else
        fread(Falcon4ClassTable, sizeof(Falcon4EntityClassType), NumEntities, filePtr);
#endif
        fclose(filePtr);
    }
    else
    {
        Falcon4ClassTable = NULL;
    }
}
