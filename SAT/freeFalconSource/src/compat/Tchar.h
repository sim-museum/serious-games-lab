/*
 * FreeFalcon Linux Port - tchar.h compatibility
 *
 * Windows TCHAR (Unicode/ANSI compatibility) replacement.
 * We assume ANSI (single-byte) mode on Linux.
 */

#ifndef FF_COMPAT_TCHAR_H
#define FF_COMPAT_TCHAR_H

#ifdef FF_LINUX

#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <stdarg.h>

/* TCHAR type - always char on Linux (ANSI mode) */
typedef char TCHAR;
typedef char _TCHAR;  /* Underscore variant */
typedef char* LPTSTR;
typedef const char* LPCTSTR;

/* Generic text macros */
#define _T(x)       x
#define _TEXT(x)    x
#define TEXT(x)     x

/* String functions - map to standard C functions */
#define _tcslen     strlen
#define _tcsclen    strlen  /* Character count - same as _tcslen for ANSI builds */
#define _tcscpy     strcpy
#define _tcsncpy    strncpy
#define _tcscat     strcat
#define _tcsncat    strncat
#define _tcscmp     strcmp
#define _tcsncmp    strncmp
#define _tcsicmp    strcasecmp
#define _tcsnicmp   strncasecmp
#define _tcsncicmp  strncasecmp
#define _tcschr     strchr
#define _tcsrchr    strrchr
#define _tcsstr     strstr
#define _tcspbrk    strpbrk
#define _tcstok     strtok
#define _tcsspn     strspn
#define _tcscspn    strcspn
#define _tcsdup     strdup

/* Printf functions */
#define _tprintf    printf
#define _ftprintf   fprintf
#define _stprintf   sprintf
#define _sntprintf  snprintf
#define _vtprintf   vprintf
#define _vftprintf  vfprintf
#define _vstprintf  vsprintf
#define _vsntprintf vsnprintf

/* Scanf functions */
#define _tscanf     scanf
#define _ftscanf    fscanf
#define _stscanf    sscanf

/* File functions */
#define _tfopen     fopen
#define _tfreopen   freopen
#define _tfgets     fgets
#define _tfputs     fputs
#define _tputc      putc
#define _tgetc      getc
#define _tungetc    ungetc

/* Path functions */
#define _tfullpath(abs, rel, maxlen)  realpath(rel, abs)
#define _tmakepath  _makepath
#define _tsplitpath _splitpath

/* File functions */
#define _trename    rename
#define _tremove    remove
#define _taccess    access

/* Conversion functions */
#define _ttoi       atoi
#define _ttol       atol
#define _ttof       atof
#define _tcstol     strtol
#define _tcstoul    strtoul
#define _tcstod     strtod

/* Character functions */
#define _totlower   tolower
#define _totupper   toupper
#define _istalpha   isalpha
#define _istdigit   isdigit
#define _istalnum   isalnum
#define _istspace   isspace
#define _istpunct   ispunct
#define _istcntrl   iscntrl
#define _istprint   isprint
#define _istgraph   isgraph
#define _istupper   isupper
#define _istlower   islower
#define _istxdigit  isxdigit

/* Main function */
#define _tmain      main
#define _targv      argv

#endif /* FF_LINUX */
#endif /* FF_COMPAT_TCHAR_H */
