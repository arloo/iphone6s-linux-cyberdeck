/* SPDX-License-Identifier: MIT */
#ifndef N71_GPT_PREFIX_CORE_H
#define N71_GPT_PREFIX_CORE_H
#include "n71-retained-layout-core.h"
/* One first entry-array page only. Never claim a complete array if it spans
 * further pages. GUIDs/names/CRC values never leave the private parser. */
struct n71_gpt_prefix_range {unsigned slot,apfs_type;unsigned long long first,last;};
struct n71_gpt_prefix_result {
 unsigned declared,checked,used,apfs_type_count,array_complete,array_crc_checked,array_crc_ok;
 struct n71_gpt_prefix_range ranges[32];
};
static inline unsigned int n71_gpt_array_crc(const unsigned char *p,unsigned n)
{
 unsigned c=~0U,i,j;
 for(i=0;i<n;i++){c^=p[i];for(j=0;j<8;j++)c=(c>>1)^(0xedb88320U&(0U-(c&1U)));}
 return ~c;
}
static inline int n71_gpt_prefix_parse(const unsigned char *header,
 const unsigned char *page,unsigned bytes,struct n71_gpt_prefix_result *out)
{
 static const unsigned char apfs_type[16]={0xef,0x57,0x34,0x7c,0,0,0xaa,0x11,0xaa,0x11,0,0x30,0x65,0x43,0xec,0xac};
 struct n71_gpt_prefix_result v={0};unsigned crc,geometry,i,j;
 unsigned long long first,last,usable_first,usable_last,total;
 if(!header||!page||!out||bytes!=4096U||!n71_layout_magic(header,"EFI PART",8)||
    !n71_layout_gpt_header(header,4096,15625000ULL,&crc,&geometry)||
    n71_layout_le64(header+72)!=2ULL)return -1;
 v.declared=n71_layout_le32(header+80);v.checked=v.declared<32U?v.declared:32U;
 total=(unsigned long long)v.declared*128ULL;
 v.array_complete=total<=bytes;
 if(v.array_complete) {
  v.array_crc_checked=1;v.array_crc_ok=n71_gpt_array_crc(page,(unsigned)total)==n71_layout_le32(header+88);
  if(!v.array_crc_ok)return -2;
 }
 usable_first=n71_layout_le64(header+40);usable_last=n71_layout_le64(header+48);
 for(i=0;i<v.checked;i++) {
  const unsigned char *entry=page+128U*i;unsigned used=0,apfs=1;
  for(j=0;j<16;j++){if(entry[j])used=1;if(entry[j]!=apfs_type[j])apfs=0;}
  if(!used)continue;
  first=n71_layout_le64(entry+32);last=n71_layout_le64(entry+40);
  if(first>last||first<usable_first||last>usable_last)return -3;
  for(j=0;j<v.used;j++)if(first<=v.ranges[j].last&&v.ranges[j].first<=last)return -4;
  v.ranges[v.used]=(struct n71_gpt_prefix_range){i+1U,apfs,first,last};
  v.used++;if(apfs)v.apfs_type_count++;
 }
 *out=v;return 0;
}
#endif
