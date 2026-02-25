#include "graphics/include/grinline.h"
#include "graphics/include/renderow.h"

#include "cpmanager.h"
#include "cpgauge.h"
#include "otwdrive.h"


CPGauge::CPGauge(ObjectInitStr* BaseInitData, CPGaugeInitStruct *GaugeInitData) : CPObject(BaseInitData)
{

    mWidthTapeBitmap = GaugeInitData->widthTapeBitmap;
    mHeightTapeBitmap = GaugeInitData->heightTapeBitmap;
    mMaxTapeValue = GaugeInitData->maxTapeValue;
    mMaxValPosition = GaugeInitData->maxValPosition;
    mMinTapeValue = GaugeInitData->minTapeValue;
    mMinValPosition = GaugeInitData->minValPosition;
    mpTapeBitmapHandle = GaugeInitData->TapeBitmapHandle;

    mpBackgroundBitmapHandle = NULL;
    mCurrentVal = 60000.0F;
}

CPGauge::~CPGauge()
{
    glReleaseMemory(mpTapeBitmapHandle);
}

void CPGauge::Exec(void)
{
    CPObject::Exec();
    SetDirtyFlag(); //VWF FOR NOW
}

void CPGauge::DrawTape(float Value, int x, int y, BOOL WrapAroundOn)
{
    float PixelSlope;
    float PixelIntercept;
    float TapePosition;
    int UpperSrcBound;
    int LowerSrcBound;
    int UpperDestBound;
    int LowerDestBound;

    // Determine how many pixels represent a unit, (units/pixel)
    PixelSlope = (mMaxValPosition - mMinValPosition) / (mMaxTapeValue - mMinTapeValue);
    PixelIntercept = mMaxValPosition - (PixelSlope * mMaxTapeValue);

    // Limit the current value
    if (Value > mMaxTapeValue)
    {
        Value = mMaxTapeValue;
    }
    else if (Value < mMinTapeValue)
    {
        Value = mMinTapeValue;
    }

    // Find the tape position
    TapePosition = (PixelSlope * Value) + PixelIntercept;

    UpperSrcBound = (int) TapePosition - (mHeight / 2);
    LowerSrcBound = (int) TapePosition + (mHeight / 2);

    // Determine where the blit should go
    if (UpperSrcBound < 0)
    {
        UpperDestBound = -UpperSrcBound;
        UpperSrcBound = 0;
    }
    else if (LowerSrcBound > mHeightTapeBitmap)
    {
        LowerDestBound = mHeight - (LowerSrcBound - mHeightTapeBitmap);
        LowerSrcBound  = mHeightTapeBitmap;
    }
    else
    {
        UpperDestBound = 0;
        LowerDestBound = mHeight;
    }

    OTWDriver.renderer->StartDraw();
    OTWDriver.renderer->Render2DBitmap(0, UpperSrcBound, x, y + mpParent->myPanelOffset, mWidthTapeBitmap, mHeight, mWidthTapeBitmap, mpTapeBitmapHandle);
    OTWDriver.renderer->EndDraw();
}

void CPGauge::Display(Render2D *pCockpitRenderer, BOOL RedrawObject)
{
    // Move to the Gauge location
    if (!mDirtyFlag)
    {
        return;
    }

    CPObject::DisplayBlit();

    mDirtyFlag = FALSE;
}
