/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_RO_BLOCK_CORE_H
#define N71_S3E_RO_BLOCK_CORE_H
#include "n71_s3e_read_series_core.h"
/* A qualification bridge, NOT an unrestricted block driver. The kernel
 * client may submit exactly 0,1,0,1 using four unique bios/CPU buffers.
 * Rejected requests never consume a command, tag or DMA ownership slot. */
struct n71_ro_block_flow {
    unsigned int active,closed,failed,pending,admitted,delivered;
};
struct n71_ro_block_request {
    unsigned long long sector;
    unsigned int is_read,bytes,segments,offset,trusted_bio,trusted_page;
};
static inline int n71_ro_block_mode_valid(unsigned int enabled,
        unsigned int flags,unsigned int identify,unsigned int queues,
        unsigned int delete_queues,unsigned int queue_flags,
        unsigned int single,unsigned int series)
{
    return enabled ? flags==32U && identify && queues && delete_queues &&
        queue_flags==0U && !single && !series : flags==~0U;
}
static inline int n71_ro_block_pair_admissible(const struct n71_ro_block_flow *f,
        const struct n71_ro_block_request *r,unsigned int base)
{
    return n71_read_pair_base_valid(base) && f && r && f->active==1U && !f->closed && !f->failed &&
        !f->pending && f->admitted<4U && f->delivered==f->admitted &&
        r->is_read==1U && r->bytes==4096U && r->segments==1U && !r->offset &&
        r->trusted_bio==1U && r->trusted_page==1U &&
        r->sector==8ULL*n71_read_pair_lba(base,f->admitted);
}
static inline int n71_ro_block_admissible(const struct n71_ro_block_flow *f,
        const struct n71_ro_block_request *r)
{
    return n71_ro_block_pair_admissible(f,r,0U);
}
static inline int n71_ro_block_pair_admit(struct n71_ro_block_flow *f,
        const struct n71_ro_block_request *r,unsigned int base)
{
    if (!n71_ro_block_pair_admissible(f,r,base)) return -1;
    f->pending=1;f->admitted++;
    return 0;
}
static inline int n71_ro_block_admit(struct n71_ro_block_flow *f,
        const struct n71_ro_block_request *r)
{
    if (!n71_ro_block_admissible(f,r)) return -1;
    f->pending=1;f->admitted++;
    return 0;
}
static inline int n71_ro_block_deliver(struct n71_ro_block_flow *f,
        unsigned int step)
{
    if (!f || !f->active || f->closed || f->failed || !f->pending ||
        step>=4U || f->admitted!=step+1U || f->delivered!=step) return -1;
    f->delivered++;f->pending=0;
    return 0;
}
static inline void n71_ro_block_close(struct n71_ro_block_flow *f,int failed)
{
    if (!f) return;
    f->closed=1;f->active=0;f->pending=0;
    if (failed) f->failed=1;
}
static inline int n71_ro_block_flow_complete(const struct n71_ro_block_flow *f)
{
    return f && f->closed && !f->active && !f->pending && !f->failed &&
        f->admitted==4U && f->delivered==4U;
}
/* CPU-only private probe admission; it cannot publish hardware commands. */
static inline int n71_ro_probe_mode_valid(unsigned int enabled,unsigned int block)
{
    return !enabled || block==1U;
}
static inline int n71_ro_probe_request_valid(unsigned int active,
        unsigned int failed,unsigned int step,unsigned int base,
        unsigned long long offset,unsigned long long bytes)
{
    return active==1U && !failed && step<4U &&
        n71_read_pair_base_valid(base) && bytes==4096ULL &&
        offset==4096ULL*n71_read_pair_lba(base,step);
}
#endif
