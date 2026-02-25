/*
 * FreeFalcon Linux Port - dlgs.h compatibility stub
 *
 * Windows Common Dialog template defines.
 * Provides minimal definitions needed for compilation.
 */

#ifndef FF_COMPAT_DLGS_H
#define FF_COMPAT_DLGS_H

#ifdef FF_LINUX

/* Common dialog control IDs */
#define ctlFirst    0x0400
#define ctlLast     0x04ff

/* Open/Save dialog control IDs */
#define stc1        0x0440
#define stc2        0x0441
#define stc3        0x0442
#define stc4        0x0443
#define lst1        0x0460
#define lst2        0x0461
#define cmb1        0x0470
#define cmb2        0x0471
#define edt1        0x0480
#define chx1        0x0410
#define pshHelp     0x040E
#define psh1        0x0401
#define psh2        0x0402
#define psh3        0x0403
#define psh4        0x0404
#define psh5        0x0405
#define psh6        0x0406
#define psh7        0x0407
#define psh8        0x0408
#define psh9        0x0409
#define psh10       0x040A
#define psh11       0x040B
#define psh12       0x040C
#define psh13       0x040D
#define psh14       0x040E
#define psh15       0x040F

/* Color dialog control IDs */
#define COLOR_HUESCROLL     700
#define COLOR_SATSCROLL     701
#define COLOR_LUMSCROLL     702
#define COLOR_HUE           703
#define COLOR_SAT           704
#define COLOR_LUM           705
#define COLOR_RED           706
#define COLOR_GREEN         707
#define COLOR_BLUE          708
#define COLOR_CURRENT       709
#define COLOR_RAINBOW       710
#define COLOR_SAVE          711
#define COLOR_ADD           712
#define COLOR_SOLID         713
#define COLOR_TUNE          714
#define COLOR_SCHEMES       715
#define COLOR_ELEMENT       716
#define COLOR_SAMPLES       717
#define COLOR_PALETTE       718
#define COLOR_MIX           719
#define COLOR_BOX1          720
#define COLOR_CUSTOM1       721
#define COLOR_HUEACCEL      723
#define COLOR_SATACCEL      724
#define COLOR_LUMACCEL      725
#define COLOR_REDACCEL      726
#define COLOR_GREENACCEL    727
#define COLOR_BLUEACCEL     728

/* Font dialog control IDs */
#define FONT_SAMPLE         731
#define FONT_FIRSTFONTENTRY 740

/* Print dialog control IDs */
#define PRINT_RANGE_FROM    1152
#define PRINT_RANGE_TO      1153
#define PRINT_COPIES        1154

#endif /* FF_LINUX */
#endif /* FF_COMPAT_DLGS_H */
