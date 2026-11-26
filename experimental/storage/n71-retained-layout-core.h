/* SPDX-License-Identifier: MIT */
#ifndef N71_RETAINED_LAYOUT_CORE_H
#define N71_RETAINED_LAYOUT_CORE_H
/* Private CPU copies only. Do not log payloads, CRC values, UUIDs or names.
 * GPT fields follow the installed kernel's block/partitions/efi.h and efi.c.
 * NXSB/APSB are signature hints only, from Apple's File System Reference. */
struct n71_layout_result {
 unsigned int mbr_signature,protective_mbr,gpt_signature,gpt_crc_ok;
 unsigned int gpt_geometry_ok,gpt_primary_header_ok;
 unsigned int apfs_container_signature[2],apfs_volume_signature[2];
 unsigned int all_zero[2],all_ff[2],different_sectors;
};
static inline unsigned int n71_layout_le32(const unsigned char *p)
{
 return (unsigned int)p[0]|((unsigned int)p[1]<<8)|
        ((unsigned int)p[2]<<16)|((unsigned int)p[3]<<24);
}
static inline unsigned long long n71_layout_le64(const unsigned char *p)
{
 return n71_layout_le32(p)|((unsigned long long)n71_layout_le32(p+4)<<32);
}
static inline int n71_layout_magic(const unsigned char *p,const char *s,unsigned n)
{
 unsigned i;for(i=0;i<n;i++)if(p[i]!=(unsigned char)s[i])return 0;return 1;
}
static inline unsigned int n71_layout_gpt_crc(const unsigned char *p,unsigned n)
{
 unsigned i,j,c=~0U;
 for(i=0;i<n;i++) {
  c^=i>=16U&&i<20U?0U:p[i];
  for(j=0;j<8;j++)c=(c>>1)^(0xedb88320U & (0U-(c&1U)));
 }
 return ~c;
}
static inline int n71_cpu_range_inside(unsigned long long address,
 unsigned long long bytes,unsigned long long base,unsigned long long size)
{
 return base && size && bytes && size-1ULL<=~0ULL-base &&
        address>=base && bytes<=size && address-base<=size-bytes;
}
static inline int n71_layout_classify(const unsigned char *a,const unsigned char *b,
 unsigned int bytes,unsigned long long nsze,struct n71_layout_result *out)
{
 struct n71_layout_result v={0};unsigned i,j,hsize,count,esize;
 unsigned long long first,last,table,table_blocks,table_bytes;
 const unsigned char *p[2]={a,b};
 if(!a||!b||!out||bytes!=4096U||nsze!=15625000ULL)return -1;
 for(j=0;j<2;j++) {
  v.all_zero[j]=v.all_ff[j]=1;
  for(i=0;i<bytes;i++){if(p[j][i])v.all_zero[j]=0;if(p[j][i]!=255)v.all_ff[j]=0;}
  v.apfs_container_signature[j]=n71_layout_magic(p[j]+32,"NXSB",4);
  v.apfs_volume_signature[j]=n71_layout_magic(p[j]+32,"APSB",4);
 }
 for(i=0;i<bytes;i++)if(a[i]!=b[i]){v.different_sectors=1;break;}
 v.mbr_signature=a[510]==0x55&&a[511]==0xaa;
 if(v.mbr_signature)for(i=0;i<4;i++)if(a[446+16*i+4]==0xee&&
      n71_layout_le32(a+446+16*i+8)==1U)v.protective_mbr=1;
 v.gpt_signature=n71_layout_magic(b,"EFI PART",8);
 if(v.gpt_signature) {
  hsize=n71_layout_le32(b+12);
  if(hsize>=92U&&hsize<=bytes)
   v.gpt_crc_ok=n71_layout_gpt_crc(b,hsize)==n71_layout_le32(b+16);
  first=n71_layout_le64(b+40);last=n71_layout_le64(b+48);
  table=n71_layout_le64(b+72);count=n71_layout_le32(b+80);esize=n71_layout_le32(b+84);
  table_bytes=(unsigned long long)count*esize;
  table_blocks=(table_bytes+4095ULL)/4096ULL;
  v.gpt_geometry_ok=n71_layout_le32(b+8)==0x10000U&&
   hsize>=92U&&hsize<=bytes&&!n71_layout_le32(b+20)&&
   n71_layout_le64(b+24)==1ULL&&n71_layout_le64(b+32)==nsze-1ULL&&
   first>=2ULL&&first<=last&&last<nsze-1ULL&&count&&count<=4096U&&
   esize==128U&&table>=2ULL&&table_blocks&&table_blocks<=nsze&&
   table<=nsze-table_blocks&&table<=first&&table_blocks<=first-table;
  v.gpt_primary_header_ok=v.gpt_crc_ok&&v.gpt_geometry_ok;
 }
 *out=v;return 0;
}
#endif
