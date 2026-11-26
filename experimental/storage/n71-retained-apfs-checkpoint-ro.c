// SPDX-License-Identifier: GPL-2.0-only
/* CPU-only observation of an already accepted, closed and pinned owner.
 * Never calls owner routines, writes owner targets, maps I/O or submits commands.
 * One additional ordinary module reference is acquired and retained.
 * Host must attest owner SHA614de1... from the accepted APFS epoch and live symbols.
 * Every acquired owner reference stays retained, including error paths. */
#include <linux/module.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/mm.h>
#include <linux/vmalloc.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/bio.h>
#include <linux/blkdev.h>
#include <linux/completion.h>
#include <linux/kthread.h>
#include <linux/spinlock.h>
#include <linux/delay.h>
#include "../port0/n71_s3e_ro_block_core.h"
#include "n71-apfs-checkpoint-core.h"
#define OWNER_NAME "n71_s3e_p0_asserted_reset_rootstart"
/* Exact field declaration copied from the pinned owner's anonymous object.
 * The ELF OBJECT symbol is 176 bytes, with target[] at offset48. */
struct n71_retained_owner {
 struct gendisk *disk;
 struct bio *bio[4],*pending_bio;
 void *target[4];
 struct task_struct *client;
 struct completion request_ready;
 spinlock_t lock;
 struct n71_ro_block_flow flow;
 unsigned int rejected,client_completed;
 int major,client_rc;
 bool prepared,registered,removed,pairs_equal,passed;
};
static bool armed,owner_hash_attested;
static unsigned long owner_module_addr,owner_state_addr;
static unsigned long long partition_blocks;
module_param(partition_blocks,ullong,0400);
module_param(armed,bool,0400);
module_param(owner_hash_attested,bool,0400);
module_param(owner_module_addr,ulong,0400);
module_param(owner_state_addr,ulong,0400);
MODULE_PARM_DESC(owner_hash_attested,"host verified exact retained owner module SHA256, source ABI, boot and symbol addresses; never use guessed addresses");
/* Walk only CPU page tables; reject invalid/non-RAM backing before copying
 * module metadata. The execution protocol independently pins live symbols. */
static bool n71_module_ram(unsigned long addr,size_t bytes)
{
 unsigned long at,end;
 if(!addr||!bytes||addr>ULONG_MAX-(bytes-1)||
    !is_vmalloc_or_module_addr((void *)addr)||
    !is_vmalloc_or_module_addr((void *)(addr+bytes-1)))return false;
 end=(addr+bytes-1)&PAGE_MASK;
 for(at=addr&PAGE_MASK;;at+=PAGE_SIZE) {
  struct page *p=vmalloc_to_page((void *)at);
  if(!p||!pfn_valid(page_to_pfn(p))||PageReserved(p)||PageSlab(p))return false;
  if(at==end)break;
 }
 return true;
}
static bool n71_owner_closed(const struct n71_retained_owner *s)
{
 unsigned i;
 if(s->disk||s->pending_bio||s->client||s->major||s->client_rc||s->rejected||
    s->client_completed!=4||!s->prepared||!s->registered||!s->removed||
    !s->pairs_equal||!s->passed||!n71_ro_block_flow_complete(&s->flow))return false;
 for(i=0;i<4;i++)if(s->bio[i])return false;
 return true;
}
static int __init n71_retained_checkpoint_init(void)
{
 struct module *meta=NULL,*owner=(struct module *)owner_module_addr;
 struct n71_retained_owner before,after;
 struct n71_apfs_checkpoint_result observed;
 unsigned char *copies=NULL;
 unsigned int i,j;
 int rc=-EPERM;
 bool owner_ref_held=false;
 BUILD_BUG_ON(sizeof(struct n71_retained_owner)!=176);
 BUILD_BUG_ON(offsetof(struct n71_retained_owner,target)!=48);
 BUILD_BUG_ON(PAGE_SIZE!=16384);
 if(!armed){pr_info("n71-retained-apfs: INERT\n");return 0;}
 if(partition_blocks<2ULL||partition_blocks>15625000ULL||
    !owner_hash_attested||!n71_module_ram(owner_module_addr,sizeof(*owner)))goto out;
 meta=kzalloc(sizeof(*meta),GFP_KERNEL);
 if(!meta){rc=-ENOMEM;goto out;}
 if(copy_from_kernel_nofault(meta,owner,sizeof(*meta))||
    strncmp(meta->name,OWNER_NAME,MODULE_NAME_LEN)||meta->state!=MODULE_STATE_LIVE||
    !n71_cpu_range_inside(owner_module_addr,sizeof(*owner),
       (unsigned long)meta->mem[MOD_DATA].base,meta->mem[MOD_DATA].size)||
    !n71_cpu_range_inside(owner_state_addr,sizeof(before),
       (unsigned long)meta->mem[MOD_DATA].base,meta->mem[MOD_DATA].size)||
    !n71_module_ram(owner_state_addr,sizeof(before)))goto out;
 /* Held intentionally; neither success nor failure authorizes owner release. */
 if(!try_module_get(owner))goto out;
 owner_ref_held=true;
 if(copy_from_kernel_nofault(&before,(void *)owner_state_addr,sizeof(before))||
    !n71_owner_closed(&before))goto out;
 for(i=0;i<4;i++) {
  unsigned long a=(unsigned long)before.target[i];struct page *p;
  if(!a||(a&~PAGE_MASK)||!virt_addr_valid((void *)a))goto out;
  p=virt_to_page((void *)a);
  if(PageReserved(p)||PageSlab(p)||PageTail(p)||page_count(p)<1)goto out;
  for(j=0;j<i;j++)if(before.target[i]==before.target[j])goto out;
 }
 copies=kvzalloc(8*PAGE_SIZE,GFP_KERNEL);
 if(!copies){rc=-ENOMEM;goto out;}
 for(i=0;i<4;i++)if(copy_from_kernel_nofault(copies+i*PAGE_SIZE,
                                         before.target[i],PAGE_SIZE))goto out;
 msleep(50);
 for(i=0;i<4;i++)if(copy_from_kernel_nofault(copies+(4+i)*PAGE_SIZE,
                                         before.target[i],PAGE_SIZE))goto out;
 if(copy_from_kernel_nofault(&after,(void *)owner_state_addr,sizeof(after))||
    memcmp(&before,&after,sizeof(before))||!n71_owner_closed(&after))goto out;
 for(i=0;i<4;i++)
  if(memcmp(copies+i*PAGE_SIZE,copies+(4+i)*PAGE_SIZE,PAGE_SIZE)||
     memchr_inv(copies+i*PAGE_SIZE+4096,0,PAGE_SIZE-4096))goto out;
 if(memcmp(copies,copies+2*PAGE_SIZE,4096)||
    memcmp(copies+PAGE_SIZE,copies+3*PAGE_SIZE,4096))goto out;
 rc=n71_apfs_checkpoint_observe(copies,copies+PAGE_SIZE,4096,
                                  partition_blocks,1ULL,&observed);
 if(rc)goto out;
 pr_info("n71-retained-apfs: CPU_COPY_PASS target_count=4 pairs_equal=1 guards_intact=1 owner_state_unchanged=1 samples=2 interval_ms=50 hardware_commands=0 owner_buffer_writes=0 DMA_release=NO\n");
 pr_info("n71-retained-apfs: CHECKPOINT_FLAGS anchor_valid=%u all_zero=%u all_ff=%u checksum_ok=%u kind=%u object_header_ok=%u inside_descriptor_area=%u descriptor_shape_valid=%u same_container_uuid=%u candidate_geometry_ok=%u candidate_ring_ok=%u latest_checkpoint_selected=0 complete_scan=0\n",
  observed.anchor_valid,observed.all_zero,observed.all_ff,observed.checksum_ok,
  observed.kind,observed.object_header_ok,observed.inside_anchor_descriptor_area,
  observed.descriptor_shape_valid,observed.same_container_uuid,
  observed.candidate_geometry_ok,observed.candidate_ring_ok);
 pr_info("n71-retained-apfs: MAPPING_FLAGS count=%u last=%u flags_ok=%u bounds_ok=%u ephemeral_types=%u inside_anchor_data=%u newer_than_anchor=%u equal_anchor=%u object_ids_and_references_exported=NO\n",
  observed.mapping_count,observed.mapping_last,observed.mapping_flags_ok,
  observed.mapping_bounds_ok,observed.mappings_ephemeral,
  observed.mappings_inside_anchor_data,observed.transaction_newer_than_anchor,
  observed.transaction_equal_anchor);

out:
 if(copies){memzero_explicit(copies,8*PAGE_SIZE);kvfree(copies);}
 kfree(meta);
 pr_info("n71-retained-apfs: RESULT rc=%d owner_reference_acquired=%u CPU_only=YES owner_reference_retained=YES no_owner_call_or_MMIO=YES no_mount=YES\n",rc,owner_ref_held);
 return rc;
}
static void __exit n71_retained_checkpoint_exit(void) { }
module_init(n71_retained_checkpoint_init);
module_exit(n71_retained_checkpoint_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 pinned closed-owner CPU-only APFS descriptor flags; no hardware commands or identifiers exported");
