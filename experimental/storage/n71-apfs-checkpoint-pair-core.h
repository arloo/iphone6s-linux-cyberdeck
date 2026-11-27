/* SPDX-License-Identifier: MIT */
#ifndef N71_APFS_CHECKPOINT_PAIR_CORE_H
#define N71_APFS_CHECKPOINT_PAIR_CORE_H
#include "n71-apfs-checkpoint-core.h"
/* One adjacent map/NXSB descriptor pair, not a complete descriptor-area scan.
 * Original code using Apple APFS Reference wire facts. Data objects remain unread.
 * No UUID or object/transaction identifier is returned. */
struct n71_apfs_checkpoint_pair_result {
 unsigned nxsb_valid,checksum_pair_ok,object_headers_ok,same_transaction;
 unsigned descriptor_ring_ok,descriptor_pair_complete,data_ring_ok,mapping_count;
 unsigned mapping_extents_in_data_window,mapping_keys_unique,mapping_extents_nonoverlap;
 unsigned spaceman_mapping_present,reaper_mapping_present,omap_reference_present;
 unsigned volume_slot_count,max_volume_slots;
};
/* Parsed physical references are strictly owner-private next-read metadata. */
struct n71_apfs_checkpoint_pair_refs {
 unsigned long long container_blocks,desc_base,data_base,omap_block;
 unsigned long long spaceman_block,reaper_block;
 unsigned desc_blocks,data_blocks,spaceman_blocks,reaper_blocks;
};
static inline int n71_apfs_ring_extent(unsigned index,unsigned length,
 unsigned slots,unsigned at,unsigned count)
{
 unsigned long long delta;
 if(!slots||index>=slots||!length||length>slots||at>=slots||!count||count>slots-at)return 0;
 if(length==slots)return 1;
 delta=((unsigned long long)at+slots-index)%slots;
 return delta<length&&count<=length-delta;
}
static inline int n71_apfs_checkpoint_pair_parse(const unsigned char *map,
 const unsigned char *nxsb,unsigned bytes,unsigned long long partition_blocks,
 unsigned long long map_relative,struct n71_apfs_checkpoint_pair_result *out,
 struct n71_apfs_checkpoint_pair_refs *refs)
{
 struct n71_apfs_checkpoint_pair_result v={0};
 struct n71_apfs_checkpoint_pair_refs physical={0};
 struct n71_apfs_superblock_result a;
 struct n71_apfs_checkpoint_result m;
 unsigned di,dl,ai,al,i,j;
 unsigned long long spaceman,reaper;
 if(out)*out=v;
 if(refs)*refs=physical;
 if(!out||!refs||!map||!nxsb||bytes!=4096U||!map_relative||
    partition_blocks<2ULL||partition_blocks>15625000ULL||
    map_relative>=partition_blocks-1ULL)return -1;
 if(n71_apfs_superblock_parse(nxsb,bytes,partition_blocks,&a))return -2;
 di=n71_layout_le32(nxsb+136);dl=n71_layout_le32(nxsb+140);
 ai=n71_layout_le32(nxsb+144);al=n71_layout_le32(nxsb+148);
 if(n71_layout_le32(nxsb+128)>=a.desc_blocks||
    n71_layout_le32(nxsb+132)>=a.data_blocks||
    !n71_apfs_ring_contains(di,dl,a.desc_blocks,di)||
    !n71_apfs_ring_contains(ai,al,a.data_blocks,ai)||
    map_relative<a.desc_base||map_relative-a.desc_base>=a.desc_blocks||
    map_relative+1ULL-a.desc_base>=a.desc_blocks)return -3;
 if(n71_apfs_checkpoint_observe(nxsb,map,bytes,partition_blocks,map_relative,&m)||
    m.kind!=2||!m.descriptor_shape_valid||!m.mapping_count||
    !m.mappings_inside_anchor_data)return -4;
 if(!m.transaction_equal_anchor)return -5;
 /* Restrict this named candidate to one complete, physically adjacent map
  * followed by its NXSB. Larger/wrapped descriptor groups need another plan. */
 if(!m.mapping_last||dl!=2U||di!=(unsigned)(map_relative-a.desc_base)||
    !n71_apfs_ring_contains(di,dl,a.desc_blocks,(unsigned)(map_relative+1ULL-a.desc_base)))return -6;
 physical.container_blocks=a.container_blocks;physical.desc_base=a.desc_base;
 physical.data_base=a.data_base;physical.omap_block=a.omap_block;
 physical.desc_blocks=a.desc_blocks;physical.data_blocks=a.data_blocks;
 spaceman=n71_layout_le64(nxsb+152);reaper=n71_layout_le64(nxsb+168);
 for(i=0;i<m.mapping_count;i++) {
  const unsigned char *entry=map+40U+40U*i;
  unsigned long long at=n71_layout_le64(entry+32);
  unsigned long long size=n71_layout_le32(entry+8),blocks=(size+4095ULL)/4096ULL;
  unsigned long long fs=n71_layout_le64(entry+16),oid=n71_layout_le64(entry+24);
  unsigned type=n71_layout_le32(entry)&0xffffU;
  if(!n71_apfs_ring_extent(ai,al,a.data_blocks,(unsigned)(at-a.data_base),(unsigned)blocks))return -7;
  for(j=0;j<i;j++) {
   const unsigned char *prior=map+40U+40U*j;
   unsigned long long p=n71_layout_le64(prior+32);
   unsigned long long n=(n71_layout_le32(prior+8)+4095ULL)/4096ULL;
   if((fs==n71_layout_le64(prior+16)&&oid==n71_layout_le64(prior+24))||
      (at<p+n&&p<at+blocks))return -8;
  }
  if(!fs&&oid==spaceman) {
   if(type!=5U||n71_layout_le32(entry+4)||size<32ULL)return -9;
   v.spaceman_mapping_present=1;physical.spaceman_block=at;physical.spaceman_blocks=(unsigned)blocks;
  }
  if(!fs&&oid==reaper) {
   if(type!=17U||n71_layout_le32(entry+4)||size<32ULL)return -9;
   v.reaper_mapping_present=1;physical.reaper_block=at;physical.reaper_blocks=(unsigned)blocks;
  }
 }
 if(!spaceman||!v.spaceman_mapping_present||(reaper&&!v.reaper_mapping_present))return -9;
 v.nxsb_valid=v.checksum_pair_ok=v.object_headers_ok=v.same_transaction=1;
 v.descriptor_ring_ok=v.descriptor_pair_complete=v.data_ring_ok=1;
 v.mapping_extents_in_data_window=v.mapping_keys_unique=v.mapping_extents_nonoverlap=1;
 v.mapping_count=m.mapping_count;v.omap_reference_present=a.omap_present;
 v.volume_slot_count=a.used_volume_slots;v.max_volume_slots=a.max_volume_slots;
 *out=v;*refs=physical;return 0;
}
#endif
