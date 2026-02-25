#include <windows.h>
#include "chandler.h"
#include <stdint.h>

#define _IDX_HASH_SIZE_ 10

// MACRO to convert to screen format from TARGA format (0rrrrrgggggbbbbb)
#define COLOR15BIT(color,rs,gs,bs) ((((color >> 10) bitand 0x1f) << rs) bitor (((color >> 5) bitand 0x1f) << gs) bitor (((color) bitand 0x1f) << bs))

extern C_Parser *gMainParser;
extern char FalconUIArtDirectory[];
extern char FalconUIArtThrDirectory[];

#ifdef FF_LINUX
extern "C" FILE* fopen_nocase(const char* filepath, const char* mode);
#endif

void ImageCleanupCB(void *rec)
{
    IMAGE_RSC *data = (IMAGE_RSC*)rec;

    if (data)
    {
        delete data->Header;
        delete data;
    }
}

void C_Resmgr::ConvertToScreen()
{
    IMAGE_RSC *rec = NULL;
    C_HASHNODE *current = NULL;
    long curidx = 0;
    ImageHeader *hdr = NULL;
    WORD *color = NULL;
    long count = 0;

    if ( not Data_ or not Index_)
        return;

    if (reds == 10 and greens == 5 and not blues)
        return;

    rec = (IMAGE_RSC*)Index_->GetFirst(&current, &curidx);

    while (rec)
    {
        if (rec->Header->Type == _RSC_IS_IMAGE_)
        {
            hdr = rec->Header;

            if (hdr->flags bitand _RSC_8_BIT_)
            {
                count = hdr->palettesize;
                color = (WORD*)(Data_ + hdr->paletteoffset);
            }
            else if (hdr->flags bitand _RSC_16_BIT_)
            {
                count = hdr->w * hdr->h;
                color = (WORD*)(Data_ + hdr->imageoffset);
            }
            else
                count = 0;

            while (count--)
            {
                *color = static_cast<short>(COLOR15BIT(*color, reds, greens, blues));

                color++;
            }
        }

        rec = (IMAGE_RSC*)Index_->GetNext(&current, &curidx);
    }
}

C_Resmgr::C_Resmgr()
{
    ID_ = 0;
    Type_ = 0;

    IDTable_ = NULL;
    Index_ = NULL;
    Idx_ = NULL;
    Data_ = NULL;

    name_[0] = 0;

    reds = greens = blues = 0; // OW
}

C_Resmgr::~C_Resmgr()
{
    if (IDTable_ or Index_ or Data_)
        Cleanup();
}

void C_Resmgr::Setup(long ID, char *filename, C_Hash *IDList)
{
    ID_ = ID;
    Type_ = _RSC_MULTIPLE_;
    strcpy(name_, filename);
    IDTable_ = IDList;

    if (IDTable_)
        LoadIndex();
}

void C_Resmgr::Setup(long ID)
{
    ID_ = ID;
    Type_ = _RSC_SINGLE_;
}

void C_Resmgr::Cleanup()
{
    if (IDTable_)
        IDTable_ = NULL;

    if (Index_)
    {
        Index_->Cleanup();
        delete Index_;
        Index_ = NULL;
    }

    if (Idx_)
    {
#ifdef USE_SH_POOLS
        MemFreePtr(Idx_);
#else
        delete[] Idx_;
#endif
        Idx_ = NULL;
    }

    if (Data_)
    {
#ifdef USE_SH_POOLS
        MemFreePtr(Data_);
#else
        delete[] Data_;
#endif
        Data_ = NULL;
    }
}

void C_Resmgr::AddIndex(long ID, IMAGE_RSC *resheader)
{
    if ( not resheader or Type_ == _RSC_MULTIPLE_)
        return;

    if ( not Index_)
    {
        Index_ = new C_Hash;
        Index_->Setup(1);
        Index_->SetFlags(C_BIT_REMOVE);
        Index_->SetCallback(ImageCleanupCB);
    }

    Index_->Add(ID, resheader);
}

FILE *C_Resmgr::OpenResFile(const char *name, const char *sfx, const char *mode)
{
    char filename[MAX_PATH];
    FILE *fp;

#ifdef FF_LINUX
    // Linux: use forward slashes and case-insensitive file open
    // Also need to convert any backslashes in 'name' to forward slashes
    char normalizedName[MAX_PATH];
    strncpy(normalizedName, name, sizeof(normalizedName) - 1);
    normalizedName[sizeof(normalizedName) - 1] = '\0';
    for (char* p = normalizedName; *p; p++) {
        if (*p == '\\') *p = '/';
    }

    // Strip leading "art/" from name if directory already ends with "/art"
    const char* adjustedName = normalizedName;
    size_t dirLen = strlen(FalconUIArtThrDirectory);
    bool thrDirEndsWithArt = (dirLen >= 4 &&
        strcmp(FalconUIArtThrDirectory + dirLen - 4, "/art") == 0);

    if (thrDirEndsWithArt &&
        (normalizedName[0] == 'a' || normalizedName[0] == 'A') &&
        (normalizedName[1] == 'r' || normalizedName[1] == 'R') &&
        (normalizedName[2] == 't' || normalizedName[2] == 'T') &&
        normalizedName[3] == '/') {
        adjustedName = normalizedName + 4;  // Skip "art/"
    }

    snprintf(filename, sizeof(filename), "%s/%s.%s", FalconUIArtThrDirectory, adjustedName, sfx);
    if ((fp = fopen_nocase(filename, mode)) != NULL)
        return fp;

    // Try main directory too, adjusting for art suffix similarly
    dirLen = strlen(FalconUIArtDirectory);
    bool mainDirEndsWithArt = (dirLen >= 4 &&
        strcmp(FalconUIArtDirectory + dirLen - 4, "/art") == 0);

    adjustedName = normalizedName;
    if (mainDirEndsWithArt &&
        (normalizedName[0] == 'a' || normalizedName[0] == 'A') &&
        (normalizedName[1] == 'r' || normalizedName[1] == 'R') &&
        (normalizedName[2] == 't' || normalizedName[2] == 'T') &&
        normalizedName[3] == '/') {
        adjustedName = normalizedName + 4;
    }

    snprintf(filename, sizeof(filename), "%s/%s.%s", FalconUIArtDirectory, adjustedName, sfx);
    return fopen_nocase(filename, mode);
#else
    snprintf(filename, sizeof(filename), "%s\\%s.%s", FalconUIArtThrDirectory, name, sfx);

    if ((fp = fopen(filename, mode)) not_eq NULL)
        return fp;

    snprintf(filename, sizeof(filename), "%s\\%s.%s", FalconUIArtDirectory, name, sfx);
    return fopen(filename, mode);
#endif
}


void C_Resmgr::LoadIndex()
{
    char buffer[MAX_PATH] = {0};
    FILE *fp = NULL;
    long recID = 0;
    int32_t size = 0;  // Must be 32-bit for Windows binary file format
    int32_t *rectype = NULL;
    char *ptr = NULL;
    IMAGE_RSC *irec = NULL;
    SOUND_RSC *srec = NULL;
    FLAT_RSC  *frec = NULL;

    strcpy(buffer, name_);
    strcat(buffer, ".idx");

    fp = OpenResFile(name_, "idx", "rb");

    if ( not fp)
    {
        MonoPrint("Error opening index file (%s)\n", buffer);
        return;
    }

    fread(&size, sizeof(int32_t), 1, fp);

    if ( not size)
    {
        fclose(fp);
        return;
    }

    {
        int32_t version;
        fread(&version, sizeof(int32_t), 1, fp);
        ResIndexVersion_ = version;
    }

    if (Index_)
    {
        Index_->Cleanup();
        delete Index_;
    }

    Index_ = new C_Hash;
    Index_->Setup(_IDX_HASH_SIZE_);
    Index_->SetFlags(C_BIT_REMOVE);
    Index_->SetCallback(NULL);

#ifdef USE_SH_POOLS
    Idx_ = (char*)MemAllocPtr(UI_Pools[UI_ART_POOL], sizeof(char) * (size), FALSE);
#else
    Idx_ = new char[size];
#endif

    if ( not Idx_)
    {
        fclose(fp);
        Index_->Cleanup();
        delete Index_;
        Index_ = NULL;
        return;
    }

    fread(Idx_, size, 1, fp);
    fclose(fp);

    ptr = Idx_;

    while (ptr and size)
    {
        rectype = (int32_t *)ptr;

        switch (*rectype)
        {
            case _RSC_IS_IMAGE_:
                irec = new IMAGE_RSC;
                irec->Header = (ImageHeader*)ptr;
                irec->Owner = this;

                recID = IDTable_->FindTextID(irec->Header->ID);

                if (recID >= 0)
                {
                    irec->ID = recID;

                    if (Index_->Find(recID))
                    {
                        MonoPrint("ERROR: %s already in Index\n", irec->Header->ID);
                        delete irec;
                    }
                    else
                        Index_->Add(recID, irec);
                }
                else
                {
                    gMainParser->AddNewID(irec->Header->ID, 100);
                    recID = IDTable_->FindTextID(irec->Header->ID);

                    if (recID)
                    {
                        irec->ID = recID;

                        if (Index_->Find(recID))
                        {
                            MonoPrint("ERROR: %s already in Index\n", irec->Header->ID);
                            delete irec;
                        }
                        else
                            Index_->Add(recID, irec);
                    }
                }

                size -= sizeof(ImageHeader);
                ptr += sizeof(ImageHeader);
                break;

            case _RSC_IS_SOUND_:
                srec = new SOUND_RSC;
                srec->Header = (SoundHeader*)ptr;
                srec->Owner = this;

                recID = IDTable_->FindTextID(srec->Header->ID);

                if (recID >= 0)
                {
                    srec->ID = recID;

                    if (Index_->Find(recID))
                    {
                        MonoPrint("ERROR: %s already in Index\n", frec->Header->ID);
                        delete srec;
                    }
                    else
                        Index_->Add(recID, srec);
                }
                else
                {
                    gMainParser->AddNewID(srec->Header->ID, 50);
                    recID = IDTable_->FindTextID(srec->Header->ID);

                    if (recID)
                    {
                        srec->ID = recID;

                        if (Index_->Find(recID))
                        {
                            MonoPrint("ERROR: %s already in Index\n", srec->Header->ID);
                            delete srec;
                        }
                        else
                            Index_->Add(recID, srec);
                    }
                }

                size -= sizeof(SoundHeader);
                ptr += sizeof(SoundHeader);
                break;

            case _RSC_IS_FLAT_:
                frec = new FLAT_RSC;
                frec->Header = (FlatHeader*)ptr;
                frec->Owner = this;

                recID = IDTable_->FindTextID(frec->Header->ID);

                if (recID >= 0)
                {
                    frec->ID = recID;

                    if (Index_->Find(recID))
                    {
                        MonoPrint("ERROR: %s already in Index\n", frec->Header->ID);
                        delete frec;
                    }
                    else
                        Index_->Add(recID, frec);
                }
                else
                {
                    gMainParser->AddNewID(frec->Header->ID, 50);
                    recID = IDTable_->FindTextID(frec->Header->ID);

                    if (recID)
                    {
                        frec->ID = recID;

                        if (Index_->Find(recID))
                        {
                            MonoPrint("ERROR: %s already in Index\n", frec->Header->ID);
                            delete frec;
                        }
                        else
                            Index_->Add(recID, frec);
                    }
                }

                size -= sizeof(FlatHeader);
                ptr += sizeof(FlatHeader);
                break;

            default:
                ptr = NULL;
                size = 0;
                break;
        }
    }
}

void C_Resmgr::LoadData()
{
    int32_t size;  // Must be 32-bit for Windows binary file format
    FILE *fp;
    char buffer[MAX_PATH];

    if ( not Index_)
        return;

    if (Data_)
        delete Data_;

    strcpy(buffer, name_);
    strcat(buffer, ".rsc");

    fp = OpenResFile(name_, "rsc", "rb");

    if ( not fp)
    {
        MonoPrint("Error: Can't open Datafile (%s)\n", buffer);
        return;
    }

    fread(&size, sizeof(int32_t), 1, fp);

    if ( not size)
    {
        fclose(fp);
        return;
    }

    {
        int32_t version;
        fread(&version, sizeof(int32_t), 1, fp);
        ResDataVersion_ = version;
    }
    // F4Assert(ResIndexVersion_ == ResDataVersion_); // MLR 1/21/2004 - This Asserts every time, so obviously it serves no purpose.

#ifdef USE_SH_POOLS
    Data_ = (char*)MemAllocPtr(UI_Pools[UI_ART_POOL], sizeof(char) * (size), FALSE);
#else
    Data_ = new char[size];
#endif

    if (Data_)
        fread(Data_, size, 1, fp);
    else
        MonoPrint("Error allocating (%1ld) bytes for Datafile\n", size);

    fclose(fp);

    if (Data_)
        ConvertToScreen();
}

void C_Resmgr::UnloadData()
{
    if (Data_)
    {
        delete Data_;
        Data_ = NULL;
    }
}

