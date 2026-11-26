/* SPDX-License-Identifier: MIT */
#ifndef N71_APFS_CHECKPOINT_CORE_H
#define N71_APFS_CHECKPOINT_CORE_H
#include "n71-apfs-superblock-core.h"
/* Observe one already-read descriptor, not a checkpoint scan/selection.
 * Layout: Apple APFS Reference, checkpoint_mapping_t/checkpoint_map_phys_t.
 * No addresses, UUIDs, checksums or object/transaction IDs in the result. */
struct n71_apfs_checkpoint_result {
 unsigned anchor_valid,all_zero,all_ff,checksum_ok,kind,object_header_ok;
 unsigned inside_anchor_descriptor_area,descriptor_shape_valid;
 unsigned same_container_uuid,candidate_geometry_ok,candidate_ring_ok;
 unsigned mapping_count,mapping_last,mapping_flags_ok,mapping_bounds_ok;
 unsigned mappings_ephemeral,mappings_inside_anchor_data;
 unsigned transaction_newer_than_anchor,transaction_equal_anchor;
};
static inline int n71_apfs_ring_contains(unsigned index,unsigned length,
 unsigned slots,unsigned at)
{
 return slots&&index<slots&&length&&length<=slots&&at<slots&&
  ((unsigned long long)at+slots-index)%slots<length;
}
static inline int n71_apfs_checkpoint_observe(const unsigned char *anchor,
 const unsigned char *page,unsigned bytes,unsigned long long partition_blocks,
 unsigned long long relative_block,struct n71_apfs_checkpoint_result *out)
{
 struct n71_apfs_superblock_result a,c;
 struct n71_apfs_checkpoint_result v={0};
 unsigned i,type,flags,count;unsigned long long xid;
 if(!out)return -1;
 *out=v;
 if(!page||bytes!=4096U||n71_apfs_superblock_parse(anchor,bytes,partition_blocks,&a)||
    relative_block>=a.container_blocks)return -1;
 v.anchor_valid=1;v.all_zero=v.all_ff=1;
 for(i=0;i<bytes;i++){if(page[i])v.all_zero=0;if(page[i]!=255)v.all_ff=0;}
 v.inside_anchor_descriptor_area=relative_block>=a.desc_base&&
  relative_block-a.desc_base<a.desc_blocks;
 v.checksum_ok=n71_apfs_fletcher64(page,bytes)==n71_layout_le64(page);
 type=n71_layout_le32(page+24);
 if(n71_layout_magic(page+32,"NXSB",4))v.kind=1;
 else if((type&0xffffU)==12U)v.kind=2;
 if(!v.checksum_ok){*out=v;return 0;}
 xid=n71_layout_le64(page+16);
 if(xid){v.transaction_newer_than_anchor=xid>n71_layout_le64(anchor+16);v.transaction_equal_anchor=xid==n71_layout_le64(anchor+16);}
 if(v.kind==1) {
  v.object_header_ok=type==0x80000001U&&!n71_layout_le32(page+28)&&
    n71_layout_le64(page+8)==1ULL&&xid;
  v.same_container_uuid=1;
  for(i=72;i<88;i++)if(page[i]!=anchor[i])v.same_container_uuid=0;
  v.candidate_geometry_ok=!n71_apfs_superblock_parse(page,bytes,partition_blocks,&c);
  if(v.candidate_geometry_ok) {
   unsigned di=n71_layout_le32(page+136),dl=n71_layout_le32(page+140);
   unsigned ai=n71_layout_le32(page+144),al=n71_layout_le32(page+148);
   v.candidate_ring_ok=n71_layout_le32(page+128)<c.desc_blocks&&
     n71_layout_le32(page+132)<c.data_blocks&&ai<c.data_blocks&&al&&al<=c.data_blocks&&
     relative_block>=c.desc_base&&relative_block-c.desc_base<c.desc_blocks&&
     n71_apfs_ring_contains(di,dl,c.desc_blocks,(unsigned)(relative_block-c.desc_base));
  }
  v.descriptor_shape_valid=v.inside_anchor_descriptor_area&&v.object_header_ok&&
    v.same_container_uuid&&v.candidate_geometry_ok&&v.candidate_ring_ok;
 } else if(v.kind==2) {
  v.object_header_ok=type==0x4000000cU&&!n71_layout_le32(page+28)&&
    n71_layout_le64(page+8)==relative_block&&xid;
  flags=n71_layout_le32(page+32);count=n71_layout_le32(page+36);
  v.mapping_last=!!(flags&1U);v.mapping_flags_ok=!(flags&~1U);
  if(count<=(4096U-40U)/40U) {
   v.mapping_count=count;v.mapping_bounds_ok=v.mappings_ephemeral=v.mappings_inside_anchor_data=1;
   for(i=0;i<count;i++) {
    const unsigned char *m=page+40U+40U*i;
    unsigned long long size=n71_layout_le32(m+8),blocks=(size+4095ULL)/4096ULL;
    unsigned long long physical=n71_layout_le64(m+32);
    unsigned mt=n71_layout_le32(m);
    if(!size||!n71_layout_le64(m+24)||!n71_apfs_extent_valid(physical,blocks,a.container_blocks))v.mapping_bounds_ok=0;
    if((mt&0xc0000000U)!=0x80000000U||!(mt&0xffffU))v.mappings_ephemeral=0;
    if(physical<a.data_base||physical-a.data_base>=a.data_blocks||
       blocks>a.data_blocks-(physical-a.data_base))v.mappings_inside_anchor_data=0;
    /* cpm_pad is preserved padding; virtual/ephemeral IDs are not block addresses. */
   }
  }
  v.descriptor_shape_valid=v.inside_anchor_descriptor_area&&v.object_header_ok&&
    v.mapping_flags_ok&&count<=(4096U-40U)/40U&&v.mapping_bounds_ok&&v.mappings_ephemeral;
 }
 *out=v;return 0;
}
#endif
