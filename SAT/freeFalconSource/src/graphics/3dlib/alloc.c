#include <cISO646>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include "alloc.h"
#include "xmmintrin.h"

#ifdef FF_LINUX
#include "ffviper/ff_linux_debug.h"
extern unsigned long g_RenderFrameCount;
// Track allocation statistics
static unsigned long g_AllocBlockCount = 0;
static unsigned long g_AllocTotalAllocated = 0;
static unsigned long g_AllocCurrentUsed = 0;
#endif

#define ALIGN_BYTES 8
#define ALLOC_BLOCK_SIZE (64*1024)

typedef struct alloc_block_s
{
    struct alloc_block_s *next;
    char *start, *end, *free;
}
alloc_block_t;

typedef struct alloc_hdr_s
{
    alloc_block_t *first, *curr;
}
alloc_hdr_t;

static alloc_hdr_t *root = 0UL;

char *AllocSetToAlignment(char *c)
{
    // FF_LINUX: Use uintptr_t instead of unsigned int to avoid pointer truncation on 64-bit
    uintptr_t i = (uintptr_t)c;
    i = (i + ALIGN_BYTES - 1) & ~(uintptr_t)(ALIGN_BYTES - 1);
    return(char*)i;
}

alloc_handle_t *AllocInit(void)
{
    alloc_hdr_t *hdr;
    alloc_block_t *blk;
    blk = (alloc_block_t *)malloc(sizeof(alloc_block_t));
    blk->next = 0UL;
    blk->start = (char *)malloc(ALLOC_BLOCK_SIZE + ALIGN_BYTES - 1);
    blk->free = AllocSetToAlignment(blk->start);
    blk->end = blk->start + ALLOC_BLOCK_SIZE;
    hdr = (alloc_hdr_t *)malloc(sizeof(alloc_hdr_t));
    hdr->first =
        hdr->curr = blk;
    root = hdr;
    return(alloc_handle_t *)root;
}

alloc_handle_t *AllocSetPool(alloc_handle_t *new)
{
    alloc_handle_t *old;
    old = (alloc_handle_t *)root;
    root = (alloc_hdr_t *)new;
    return old;
}

char *Alloc(int size)
{
    alloc_block_t *blk;
    char *mem;

#ifdef FF_LINUX
    // Safety check for NULL root
    if (!root) {
        FF_DEBUG_RENDER("Alloc ERROR: root is NULL!\n");
        return NULL;
    }
#endif

    blk = root->curr;
    size = (size + ALIGN_BYTES - 1) bitand -ALIGN_BYTES;
    mem = blk->free;
    blk->free += size;

#ifdef FF_LINUX
    g_AllocTotalAllocated += size;
    g_AllocCurrentUsed += size;
#endif

    // FF_LINUX: Use uintptr_t instead of unsigned int for 64-bit pointer comparison
    if ((uintptr_t)(blk->free) > (uintptr_t)(blk->end))
    {
        if (blk->next not_eq 0UL)
        {
            blk = blk->next;
            blk->free = AllocSetToAlignment(blk->start);
        }
        else
        {
#ifdef FF_LINUX
            g_AllocBlockCount++;
            FF_DEBUG_RENDER_FRAME(g_RenderFrameCount, "  Alloc: new block #%lu (total %lu KB)\n",
                                  g_AllocBlockCount, g_AllocBlockCount * 64);
#endif
            blk->next = (alloc_block_t *)malloc(sizeof(alloc_block_t));
            blk = blk->next;
            blk->next = 0UL;
            blk->start = (char *)malloc(ALLOC_BLOCK_SIZE + ALIGN_BYTES - 1);
            blk->end = blk->start + ALLOC_BLOCK_SIZE;
            blk->free = AllocSetToAlignment(blk->start);
#ifdef FF_LINUX
            if (!blk->start) {
                FF_DEBUG_RENDER("Alloc ERROR: malloc failed for new block!\n");
            }
#endif
        }

        mem = blk->free;
        blk->free = mem + size;
        root->curr = blk;
    }

    return mem;
}

void AllocDiscard(char *last)
{
    alloc_block_t *blk;
    blk = root->curr;
    blk->free = last;
}

void AllocResetPool(void)
{
#ifdef FF_LINUX
    // Report memory usage statistics before reset (every 100 frames to reduce spam)
    if (g_RenderFrameCount % 100 == 0) {
        FF_DEBUG_RENDER_FRAME(g_RenderFrameCount, "  AllocResetPool: used=%lu KB, blocks=%lu\n",
                              g_AllocCurrentUsed / 1024, g_AllocBlockCount > 0 ? g_AllocBlockCount : 1);
    }
    g_AllocCurrentUsed = 0;
#endif
    root->curr = root->first;
    root->curr->free = root->curr->start;
}

void AllocFreePool(void)
{
    alloc_block_t *next, *curr;
    curr = root->first;

    while (curr not_eq NULL)
    {
        next = curr->next;
        free(curr->start);
        free((char *)curr);
        curr = next;
    }

    free((char *)root);
    root = NULL;
}
