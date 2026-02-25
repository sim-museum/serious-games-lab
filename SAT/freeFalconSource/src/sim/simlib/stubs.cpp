#include "stdhdr.h"
#include "graphics/include/renderow.h"
#include "f4vu.h"

extern "C"
{
    int _CrtDbgReport(int reportType, const char *filename, int linenumber, const char *moduleName, const char *format, ...);
};

int _CrtDbgReport(int reportType, const char *filename, int linenumber, const char *moduleName, const char *format, ...)
{
    char buffer[80];
    int choice = IDRETRY;

    sprintf(buffer, "Assertion at %0d  %s", linenumber, filename);

    while (choice != IDIGNORE)
    {
        choice = MessageBox(NULL, buffer, "Failed:  ",
                            MB_ICONERROR | MB_ABORTRETRYIGNORE | MB_TASKMODAL);

        if (choice == IDABORT)
        {
            exit(-1);
        }
        else if (choice == IDRETRY)
        {
#ifdef FF_LINUX
            __asm__("int $3");
#else
            __asm int 3
#endif
        }
    }

    return (0);

}
