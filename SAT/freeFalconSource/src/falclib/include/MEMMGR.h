/*
 *  MODULE:  MEMMGR.H
 *
 *  PURPOSE: Memory Management Functions header.
 *
 *  (c) 1994, 1995, 1996 Spectrum Holobyte.
 */

#ifndef __MEMMGR_H__
#define __MEMMGR_H__

#ifdef __cplusplus
extern "C" {
#endif

/* Memory cookie counts - must be at least 1 */
#ifndef COOKIE_COUNT_HEAD
#define COOKIE_COUNT_HEAD    1
#endif

#ifndef COOKIE_COUNT_TAIL
#define COOKIE_COUNT_TAIL    1
#endif

/* Magic cookie values for memory corruption detection */
#define MAGIC_COOKIE_HEAD    0xDEADBEEF
#define MAGIC_COOKIE_TAIL    0xBEEFDEAD
#define MAGIC_COOKIE_FREE    0xFEEDFACE

/* Export/import macros */
#ifdef MEM_STATIC_LIB
#define MEM_EXPORT
#else
#ifdef MEM_DLL
#define MEM_EXPORT __declspec(dllexport)
#else
#define MEM_EXPORT
#endif
#endif

/* Memory type definitions */
typedef unsigned char* memANY_PTR;
typedef char*          memCHAR_PTR;
typedef int*           memINT_PTR;
typedef unsigned char  memBYTE;
typedef int            memBOOL;

/* Debug macro - define to no-op if not defined elsewhere */
#ifndef DBG
#  define DBG(a)       a
#endif

#ifndef PF
#  define PF           printf
#endif

/* Include stddef.h for size_t */
#include <stddef.h>

/* Function prototypes */
MEM_EXPORT void* MEMMalloc(long req_size, char *name, char *filename, int linenum);
MEM_EXPORT unsigned char MEMFree(void *ptr, char *filename, int linenum);
MEM_EXPORT void MEMDump(void);
MEM_EXPORT long MEMAvail(void);
MEM_EXPORT int MEMSanity(void);
MEM_EXPORT int MEMFindCount(void);
MEM_EXPORT void MEMFindEqual(size_t size);
MEM_EXPORT void MEMFindMin(size_t size);
MEM_EXPORT void MEMFindMax(size_t size);
MEM_EXPORT int MEMFindName(char *name);
MEM_EXPORT void MEMFindUsage(void);
MEM_EXPORT char* MEMStrDup(const char *s, char *filename, int linenum);

/* Debug macros - define USE_MEM_MANAGER to enable memory tracking */
#ifdef USE_MEM_MANAGER
#define malloc(s)       MEMMalloc((s), "malloc", __FILE__, __LINE__)
#define calloc(n,s)     MEMMalloc((n)*(s), "calloc", __FILE__, __LINE__)
#define free(p)         MEMFree((p), __FILE__, __LINE__)
#define strdup(s)       MEMStrDup((s), __FILE__, __LINE__)
#else
/* Standard library functions */
#include <stdlib.h>
#include <string.h>
#endif

#ifdef __cplusplus
}
#endif

#endif /* __MEMMGR_H__ */
