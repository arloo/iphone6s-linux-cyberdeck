/* SPDX-License-Identifier: MIT */
#ifndef N71_GPT_FULL_CORE_H
#define N71_GPT_FULL_CORE_H
#include "n71-gpt-prefix-core.h"
#define N71_GPT_FULL_ENTRIES 128U
struct n71_gpt_full_result {
 unsigned declared,checked,used,apfs_type_count,array_complete,array_crc_checked,array_crc_ok;
 struct n71_gpt_prefix_range ranges[N71_GPT_FULL_ENTRIES];
};
/* Five fixed sectors only: native LBA1 header and LBA2..5 entry array.
 * No cross-epoch header, data-dependent reads, identifiers or CRC output. */
static inline int n71_gpt_full_crc_valid(const unsigned char *header,
 const unsigned char *const pages[4])
{
 unsigned crc,geometry,c=~0U,i,j,k;
 if(!header||!pages||!n71_layout_magic(header,"EFI PART",8)||
    !n71_layout_gpt_header(header,4096,15625000ULL,&crc,&geometry)||
    n71_layout_le64(header+72)!=2ULL||
    n71_layout_le32(header+80)!=128U||n71_layout_le32(header+84)!=128U)return 0;
 for(i=0;i<4;i++)if(!pages[i])return 0;
 for(i=0;i<4;i++)for(j=0;j<4096;j++) {
  c^=pages[i][j];for(k=0;k<8;k++)c=(c>>1)^(0xedb88320U&(0U-(c&1U)));
 }
 return (~c)==n71_layout_le32(header+88);
}
static inline int n71_gpt_full_parse(const unsigned char *header,
 const unsigned char *const pages[4],struct n71_gpt_full_result *out)
{
 static const unsigned char apfs[16]={0xef,0x57,0x34,0x7c,0,0,0xaa,0x11,0xaa,0x11,0,0x30,0x65,0x43,0xec,0xac};
 unsigned i,j;unsigned long long usable_first,usable_last,first,last;
 if(!out)return -1;
 /* Failure always clears partial coordinates. Original sector buffers are read-only. */
 *out=(struct n71_gpt_full_result){0};
 if(!n71_gpt_full_crc_valid(header,pages))return -1;
 usable_first=n71_layout_le64(header+40);usable_last=n71_layout_le64(header+48);
 for(i=0;i<128;i++) {
  const unsigned char *entry=pages[i/32U]+128U*(i%32U);unsigned used=0,type=1;
  for(j=0;j<16;j++){if(entry[j])used=1;if(entry[j]!=apfs[j])type=0;}
  if(!used)continue;
  first=n71_layout_le64(entry+32);last=n71_layout_le64(entry+40);
  if(first>last||first<usable_first||last>usable_last)goto invalid_range;
  for(j=0;j<out->used;j++)if(first<=out->ranges[j].last&&out->ranges[j].first<=last)goto overlap;
  out->ranges[out->used++]=(struct n71_gpt_prefix_range){i+1U,type,first,last};
  if(type)out->apfs_type_count++;
 }
 out->declared=out->checked=128;out->array_complete=out->array_crc_checked=out->array_crc_ok=1;
 return 0;
invalid_range:*out=(struct n71_gpt_full_result){0};return -3;
overlap:*out=(struct n71_gpt_full_result){0};return -4;
}
#endif
