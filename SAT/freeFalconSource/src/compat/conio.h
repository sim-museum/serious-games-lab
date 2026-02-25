/*
 * FreeFalcon Linux Port - conio.h compatibility
 *
 * This header provides stubs for DOS/Windows console I/O functions.
 * Direct hardware port access (outp, inp) is not available on modern Linux
 * without privileged access, so these are provided as no-ops.
 */

#ifndef FF_COMPAT_CONIO_H
#define FF_COMPAT_CONIO_H

#ifdef FF_LINUX

#include <stdio.h>
#include <stdarg.h>
#include <termios.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================
 * Direct I/O port access stubs
 * These require privileged access on Linux (ioperm/iopl)
 * and are generally not usable, so we provide no-ops
 * ============================================================ */

/* Output byte to I/O port - no-op on Linux */
static inline int _outp(unsigned short port, int value) {
    (void)port;
    (void)value;
    return value;
}

static inline int outp(unsigned short port, int value) {
    return _outp(port, value);
}

/* Output word to I/O port - no-op on Linux */
static inline unsigned short _outpw(unsigned short port, unsigned short value) {
    (void)port;
    (void)value;
    return value;
}

static inline unsigned short outpw(unsigned short port, unsigned short value) {
    return _outpw(port, value);
}

/* Output dword to I/O port - no-op on Linux */
static inline unsigned long _outpd(unsigned short port, unsigned long value) {
    (void)port;
    (void)value;
    return value;
}

static inline unsigned long outpd(unsigned short port, unsigned long value) {
    return _outpd(port, value);
}

/* Input byte from I/O port - no-op on Linux */
static inline int _inp(unsigned short port) {
    (void)port;
    return 0;
}

static inline int inp(unsigned short port) {
    return _inp(port);
}

/* Input word from I/O port - no-op on Linux */
static inline unsigned short _inpw(unsigned short port) {
    (void)port;
    return 0;
}

static inline unsigned short inpw(unsigned short port) {
    return _inpw(port);
}

/* Input dword from I/O port - no-op on Linux */
static inline unsigned long _inpd(unsigned short port) {
    (void)port;
    return 0;
}

static inline unsigned long inpd(unsigned short port) {
    return _inpd(port);
}

/* ============================================================
 * Console keyboard functions
 * ============================================================ */

/* Check if a key has been pressed (non-blocking) */
static inline int _kbhit(void) {
    struct termios oldt, newt;
    int ch;
    int oldf;

    tcgetattr(STDIN_FILENO, &oldt);
    newt = oldt;
    newt.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSANOW, &newt);
    oldf = fcntl(STDIN_FILENO, F_GETFL, 0);
    fcntl(STDIN_FILENO, F_SETFL, oldf | O_NONBLOCK);

    ch = getchar();

    tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
    fcntl(STDIN_FILENO, F_SETFL, oldf);

    if (ch != EOF) {
        ungetc(ch, stdin);
        return 1;
    }

    return 0;
}

static inline int kbhit(void) {
    return _kbhit();
}

/* Get a character without echoing */
static inline int _getch(void) {
    struct termios oldt, newt;
    int ch;
    tcgetattr(STDIN_FILENO, &oldt);
    newt = oldt;
    newt.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSANOW, &newt);
    ch = getchar();
    tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
    return ch;
}

static inline int getch(void) {
    return _getch();
}

/* Get a character with echoing */
static inline int _getche(void) {
    int ch = _getch();
    if (ch != EOF) {
        putchar(ch);
    }
    return ch;
}

static inline int getche(void) {
    return _getche();
}

/* Put a character to console */
static inline int _putch(int c) {
    return putchar(c);
}

static inline int putch(int c) {
    return _putch(c);
}

/* Unget a character */
static inline int _ungetch(int c) {
    return ungetc(c, stdin);
}

static inline int ungetch(int c) {
    return _ungetch(c);
}

/* Console output - just use printf */
static inline int _cprintf(const char *format, ...) {
    va_list args;
    int ret;
    va_start(args, format);
    ret = vprintf(format, args);
    va_end(args);
    return ret;
}

static inline int cprintf(const char *format, ...) {
    va_list args;
    int ret;
    va_start(args, format);
    ret = vprintf(format, args);
    va_end(args);
    return ret;
}

#ifdef __cplusplus
}
#endif

#else /* Windows */
/* On Windows, include the real conio.h */
#include <conio.h>
#endif /* FF_LINUX */

#endif /* FF_COMPAT_CONIO_H */
