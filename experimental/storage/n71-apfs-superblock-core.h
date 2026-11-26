/* SPDX-License-Identifier: MIT */
#ifndef N71_APFS_SUPERBLOCK_CORE_H
#define N71_APFS_SUPERBLOCK_CORE_H
#include "n71-retained-layout-core.h"
/* Original bounded block-zero observer. Apple APFS Reference: obj_phys_t,
 * nx_superblock_t, storage methods and block-zero checkpoint fields.
 * APFS checksum arithmetic: libyal/libfsapfs format documentation 4.2.
 * No raw checksum, UUID, transaction/virtual/ephemeral ID or name output. */
struct n71_apfs_superblock_result {
 unsigned magic_ok,checksum_ok,object_header_ok,geometry_ok;
 unsigned checkpoint_ranges_ok,omap_present,omap_reference_ok;
 unsigned block_size,max_volume_slots,used_volume_slots;
 unsigned desc_blocks,data_blocks;
 unsigned long long container_blocks,desc_base,data_base,omap_block;
};
static inline unsigned long long n71_apfs_fletcher64(const unsigned char *p,
 unsigned bytes)
{
 const unsigned long long mod=0xffffffffULL;
 unsigned long long first=0,second=0,low,high;unsigned i;
 if(!p||bytes!=4096U)return 0;
 for(i=8;i<bytes;i+=4) {
  first=(first+n71_layout_le32(p+i))%mod;
  second=(second+first)%mod;
 }
 low=mod-(first+second)%mod;
 high=mod-(first+low)%mod;
 return low|(high<<32);
}
static inline int n71_apfs_extent_valid(unsigned long long base,
 unsigned long long count,unsigned long long total)
{
 return base>0&&base<total&&count>0&&count<=total-base;
}
static inline int n71_apfs_superblock_parse(const unsigned char *p,unsigned bytes,
 unsigned long long partition_blocks,struct n71_apfs_superblock_result *out)
{
 struct n71_apfs_superblock_result v={0};unsigned i,j,max;
 unsigned long long blocks,desc,data,omap,oid;
 unsigned dcount,acount;
 if(!out)return -1;
 *out=(struct n71_apfs_superblock_result){0};
 if(!p||bytes!=4096U||partition_blocks<2ULL||partition_blocks>15625000ULL)return -1;
 if(!n71_layout_magic(p+32,"NXSB",4))return -2;
 if(n71_layout_le32(p+36)!=4096U)return -3; /* larger objects need a different plan */
 if(n71_apfs_fletcher64(p,bytes)!=n71_layout_le64(p))return -4;
 if(n71_layout_le64(p+8)!=1ULL||!n71_layout_le64(p+16)||
    n71_layout_le32(p+24)!=0x80000001U||n71_layout_le32(p+28))return -5;
 blocks=n71_layout_le64(p+40);max=n71_layout_le32(p+180);
 if(blocks<256ULL||blocks>partition_blocks||!max||max>100U)return -6;
 /* This parser qualifies the known single-device v2 representation only. */
 if(n71_layout_le64(p+64)!=2ULL)return -7;
 dcount=n71_layout_le32(p+104);acount=n71_layout_le32(p+108);
 if((dcount|acount)&0x80000000U)return -8; /* checkpoint extent trees unimplemented */
 desc=n71_layout_le64(p+112);data=n71_layout_le64(p+120);
 if(!n71_apfs_extent_valid(desc,dcount,blocks)||
    !n71_apfs_extent_valid(data,acount,blocks)||
    (desc<data+acount&&data<desc+dcount))return -9;
 /* Block-zero next/index/length cursors have no checkpoint meaning. Never
  * reject this anchor using those fields or claim it is the latest checkpoint. */
 omap=n71_layout_le64(p+160);
 if(omap&&omap>=blocks)return -10; /* physical OID is a block address */
 for(i=0;i<100;i++) {
  oid=n71_layout_le64(p+184U+8U*i);
  if(!oid)continue;
  if(i>=max)return -6;
  for(j=0;j<i;j++)if(n71_layout_le64(p+184U+8U*j)==oid)return -6;
  v.used_volume_slots++;
 }
 /* Spaceman/reaper and volume OIDs are not physical addresses. They are
  * neither range-checked as blocks nor exported; later lookup is unqualified. */
 v.magic_ok=v.checksum_ok=v.object_header_ok=v.geometry_ok=1;
 v.checkpoint_ranges_ok=1;v.omap_present=omap!=0;v.omap_reference_ok=omap!=0;
 v.block_size=4096;v.max_volume_slots=max;
 v.desc_blocks=dcount;v.data_blocks=acount;
 v.container_blocks=blocks;v.desc_base=desc;v.data_base=data;v.omap_block=omap;
 *out=v;return 0;
}
#endif
