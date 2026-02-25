/*
 * FreeFalcon Linux Port - COM definitions stub
 *
 * This provides minimal COM smart pointer stubs.
 */

#ifndef FF_COMPAT_COMDEF_H
#define FF_COMPAT_COMDEF_H

#ifdef FF_LINUX

#include "compat_types.h"
#include <cstring>

/* _com_error stub */
class _com_error {
public:
    _com_error(HRESULT hr) : m_hr(hr) {}
    HRESULT Error() const { return m_hr; }
    const char* ErrorMessage() const { return "COM Error"; }
private:
    HRESULT m_hr;
};

/* _bstr_t stub */
class _bstr_t {
public:
    _bstr_t() : m_str(nullptr) {}
    _bstr_t(const char* s) : m_str(nullptr) {
        if (s) {
            m_str = new char[strlen(s) + 1];
            strcpy(m_str, s);
        }
    }
    _bstr_t(const _bstr_t& other) : m_str(nullptr) {
        if (other.m_str) {
            m_str = new char[strlen(other.m_str) + 1];
            strcpy(m_str, other.m_str);
        }
    }
    ~_bstr_t() { delete[] m_str; }
    _bstr_t& operator=(const _bstr_t& other) {
        if (this != &other) {
            delete[] m_str;
            m_str = nullptr;
            if (other.m_str) {
                m_str = new char[strlen(other.m_str) + 1];
                strcpy(m_str, other.m_str);
            }
        }
        return *this;
    }
    operator const char*() const { return m_str ? m_str : ""; }
    operator char*() const { return m_str; }  /* Allow LPSTR cast */
    unsigned int length() const { return m_str ? (unsigned int)strlen(m_str) : 0; }
private:
    char* m_str;
};

/* _variant_t stub */
class _variant_t {
public:
    _variant_t() {}
    _variant_t(long val) { (void)val; }
    _variant_t(const char* s) { (void)s; }
};

#endif /* FF_LINUX */
#endif /* FF_COMPAT_COMDEF_H */
