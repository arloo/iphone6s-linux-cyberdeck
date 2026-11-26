// SPDX-License-Identifier: GPL-2.0-only
/* CPU-only observation of an already accepted, closed and pinned owner.
 * Never calls owner routines, writes owner targets, maps I/O or submits commands.
 * One additional ordinary module reference is acquired and retained.
 * Host must attest the exact 7a28e2... owner ELF/source and runtime symbols.
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
#include "n71-retained-layout-core.h"
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
static int __init n71_retained_layout_init(void)
{
 struct module *meta=NULL,*owner=(struct module *)owner_module_addr;
 struct n71_retained_owner before,after;
 struct n71_layout_result layout;
 unsigned char *copies=NULL;
 unsigned int i,j;
 int rc=-EPERM;
 bool owner_ref_held=false;
 BUILD_BUG_ON(sizeof(struct n71_retained_owner)!=176);
 BUILD_BUG_ON(offsetof(struct n71_retained_owner,target)!=48);
 BUILD_BUG_ON(PAGE_SIZE!=16384);
 if(!armed){pr_info("n71-retained-layout: INERT\n");return 0;}
 if(!owner_hash_attested||!n71_module_ram(owner_module_addr,sizeof(*owner)))goto out;
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
 rc=n71_layout_classify(copies,copies+PAGE_SIZE,4096,15625000ULL,&layout);
 if(rc)goto out;
 pr_info("n71-retained-layout: CPU_COPY_PASS target_count=4 pairs_equal=1 guards_intact=1 owner_state_unchanged=1 samples=2 interval_ms=50 hardware_commands=0 owner_buffer_writes=0 DMA_release=NO\n");
 pr_info("n71-retained-layout: LAYOUT_FLAGS mbr_signature=%u protective_mbr=%u gpt_signature=%u gpt_crc_ok=%u gpt_geometry_ok=%u gpt_primary_header_ok=%u partition_entries_read=NO\n",
  layout.mbr_signature,layout.protective_mbr,layout.gpt_signature,
  layout.gpt_crc_ok,layout.gpt_geometry_ok,layout.gpt_primary_header_ok);
 pr_info("n71-retained-layout: GPT512_FLAGS signature=%u crc_ok=%u geometry_ok=%u primary_header_ok=%u candidate_logical_view_bytes=512 native_NVMe_LBA_bytes=4096 partition_entries_read=NO\n",
  layout.gpt512_signature,layout.gpt512_crc_ok,layout.gpt512_geometry_ok,layout.gpt512_primary_header_ok);
 pr_info("n71-retained-layout: FORMAT_HINTS lba0_NXSB=%u lba1_NXSB=%u lba0_APSB=%u lba1_APSB=%u signature_only=YES APFS_validated=NO\n",
  layout.apfs_container_signature[0],layout.apfs_container_signature[1],
  layout.apfs_volume_signature[0],layout.apfs_volume_signature[1]);
 pr_info("n71-retained-layout: CONTENT_FLAGS lba0_all_zero=%u lba1_all_zero=%u lba0_all_ff=%u lba1_all_ff=%u different_lbas_differ=%u payload_and_hashes_exported=NO\n",
  layout.all_zero[0],layout.all_zero[1],layout.all_ff[0],layout.all_ff[1],layout.different_sectors);
out:
 if(copies){memzero_explicit(copies,8*PAGE_SIZE);kvfree(copies);}
 kfree(meta);
 pr_info("n71-retained-layout: RESULT rc=%d owner_reference_acquired=%u CPU_only=YES owner_reference_retained=YES no_owner_call_or_MMIO=YES no_mount=YES\n",rc,owner_ref_held);
 return rc;
}
static void __exit n71_retained_layout_exit(void) { }
module_init(n71_retained_layout_init);
module_exit(n71_retained_layout_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 pinned closed-owner CPU-only retained target layout flags; no hardware commands or payload export");
