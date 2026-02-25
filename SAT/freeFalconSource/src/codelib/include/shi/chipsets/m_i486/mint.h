
/********************************************************************/
/*  Copyright (C) 1997 MicroProse, Inc. All rights reserved         */
/*                                                                  */
/*  Programs, statements and coded instructions within this file    */
/*  contain unpublished and proprietary information of MicroProse,  */
/*  Inc. and are thus protected by the Federal and International    */
/*  Copyright laws. They may not be copied, duplicated or disclosed */
/*  to third parties in any form, in whole or in part, without the  */
/*  prior written consent of MicroProse, Inc.                       */
/*                                                                  */
/********************************************************************/

#ifndef _MINT_H_
#define _MINT_H_

#define CHIPSET_ID          SHI_CS_m_i486
#define CHIPSET_ID_STR      "Intel i486"
#define CHIPSET_ID_NUM      486

#define CHIPSET_MAX_INT_POW 2     /* See MINT.DOC */

#define CHIPSET_LITTLE_ENDIAN

#include <stdint.h>
typedef int8_t         Int8;
typedef int16_t        Int16;
typedef int32_t        Int32;   // Use fixed-width type for 64-bit compatibility

typedef uint8_t        UInt8;
typedef uint16_t       UInt16;
typedef uint32_t       UInt32;  // Use fixed-width type for 64-bit compatibility

#endif /* _MINT_H_ */

