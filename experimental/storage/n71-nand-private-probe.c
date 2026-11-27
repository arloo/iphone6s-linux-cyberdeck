/* SPDX-License-Identifier: MIT */
/* One local, bounded char probe. Only parsed range/type/count summaries
 * may leave private memory in explicit layout mode; no raw sectors, CRC
 * values, hashes, unique GUIDs or names. No mount or NAND Write. */
#define _GNU_SOURCE
#define _FILE_OFFSET_BITS 64
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <sys/prctl.h>
#include <sys/sysmacros.h>
#include <time.h>
#include <unistd.h>
#include "n71-gpt-full-core.h"
#include "n71-apfs-superblock-core.h"
#include "n71-apfs-checkpoint-pair-core.h"
static unsigned probe_major(void)
{
    unsigned major=0,n;
    char name[64],line[160];
    FILE *f=fopen("/proc/devices","r");
    if (!f) return 0;
    while (fgets(line,sizeof(line),f))
        if (sscanf(line,"%u %63s",&n,name)==2 && !strcmp(name,"n71nand_probe")) {
            major=n;break;
        }
    fclose(f);return major;
}
static int select_pair(int argc,char **argv,unsigned *base,int *layout)
{
 char *end;unsigned long long n;const char *s;
 *layout=0;
 if(argc==2) {
  if(!strcmp(argv[1],"--initial")){*base=0;return 0;}
  if(!strcmp(argv[1],"--tail")){*base=15624998U;return 0;}
  if(!strcmp(argv[1],"--layout")){*base=1;*layout=1;return 0;}
  if(!strcmp(argv[1],"--gpt-full")){*base=1;*layout=2;return 0;}
 } else if(argc==3&&!strcmp(argv[1],"--pair")) {
  if(!argv[2][0])return -1;
  for(s=argv[2];*s;s++)if(*s<'0'||*s>'9')return -1;
  errno=0;n=strtoull(argv[2],&end,10);
  if(errno||*end||n>15624998ULL)return -1;
  *base=(unsigned)n;return 0;
 }
 return -1;
}
/* A separate strict selector keeps all accepted legacy argument modes intact.
 * Host must bind both native coordinates to the privately validated GPT. */
static int select_apfs(int argc,char **argv,unsigned *base,
 unsigned long long *partition_blocks)
{
 unsigned long long first,last;char *end;const char *s;unsigned i;
 if(argc!=4||strcmp(argv[1],"--apfs"))return -1;
 for(i=2;i<4;i++) {
  if(!argv[i][0])return -1;
  for(s=argv[i];*s;s++)if(*s<'0'||*s>'9')return -1;
 }
 errno=0;first=strtoull(argv[2],&end,10);if(errno||*end)return -1;
 errno=0;last=strtoull(argv[3],&end,10);if(errno||*end)return -1;
 if(first<6ULL||first>15624998ULL||last<=first||last>=15625000ULL)return -1;
 *base=(unsigned)first;*partition_blocks=last-first+1ULL;return 0;
}
/* First/last remain GPT-native bounds; relative names the first descriptor.
 * Host binds it to the accepted private container selection before insertion. */
static int select_checkpoint(int argc,char **argv,unsigned *base,
 unsigned long long *partition_blocks,unsigned long long *relative)
{
 char *a[5],*end;const char *s;unsigned first;unsigned long long n;
 if(argc!=5||strcmp(argv[1],"--checkpoint"))return -1;
 a[0]=argv[0];a[1]="--apfs";a[2]=argv[2];a[3]=argv[3];a[4]=NULL;
 if(select_apfs(4,a,&first,partition_blocks)||!argv[4][0])return -1;
 for(s=argv[4];*s;s++)if(*s<'0'||*s>'9')return -1;
 errno=0;n=strtoull(argv[4],&end,10);
 if(errno||*end||!n||n>=*partition_blocks-1ULL)return -1;
 *base=first+(unsigned)n;*relative=n;return 0;
}
int main(int argc,char **argv)
{
    const char *path="/dev/n71nand-probe";
    unsigned base,major=0,i,count;
    unsigned long long partition_blocks=0,relative=0;
    unsigned char data[5][4096];
    struct stat st;
    const struct rlimit no_core={0,0};
    struct timespec delay={0,100000000};
    int fd=-1,rc=1,created=0,layout_mode=0;
    if (!select_checkpoint(argc,argv,&base,&partition_blocks,&relative)) layout_mode=4;
    else if (!select_apfs(argc,argv,&base,&partition_blocks)) layout_mode=3;
    else if (select_pair(argc,argv,&base,&layout_mode)) {
        fputs("Usage: n71-nand-private-probe --initial|--tail|--layout|--gpt-full|--pair BASE|--apfs FIRST LAST|--checkpoint FIRST LAST RELATIVE_MAP\n",stderr);return 2;
    }
    count=layout_mode==2?5U:4U;
    if (geteuid()!=0) {fputs("ROOT_REQUIRED\n",stderr);return 2;}
    if (setrlimit(RLIMIT_CORE,&no_core) || prctl(PR_SET_DUMPABLE,0,0,0,0)) {
        fputs("PRIVATE_MEMORY_GUARD_FAILED\n",stderr);return 2;
    }
    if (!lstat(path,&st) || errno!=ENOENT) {
        fputs("EXISTING_OR_UNSAFE_NODE_REFUSED\n",stderr);return 2;
    }
    /* Wait at most 30 seconds for an explicitly armed owner insertion. */
    for (i=0;i<300;i++) {
        major=probe_major();if (major) break;
        nanosleep(&delay,NULL);
    }
    if (!major) {fputs("NO_ARMED_PROBE_WITHIN_WINDOW\n",stderr);return 1;}
    if (mknod(path,S_IFCHR|0600,makedev(major,0))) {
        fputs("PRIVATE_NODE_CREATE_FAILED\n",stderr);return 1;
    }
    created=1;
    /* Write opens must fail without consuming the only read-open budget. */
    fd=open(path,O_RDWR|O_NOFOLLOW|O_CLOEXEC);
    if (fd>=0) {fputs("WRITE_OPEN_UNEXPECTEDLY_ACCEPTED\n",stderr);goto done;}
    if (errno!=EACCES && errno!=EPERM) {fputs("WRITE_GATE_UNEXPECTED_ERROR\n",stderr);goto done;}
    fd=open(path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if (fd<0) {fprintf(stderr,"PRIVATE_CHAR_OPEN_FAILED errno=%d\n",errno);goto done;}
    if (fstat(fd,&st) || !S_ISCHR(st.st_mode) ||
        major(st.st_rdev)!=major || minor(st.st_rdev)!=0 || st.st_uid!=0 ||
        (st.st_mode&0777)!=0600) {fputs("PRIVATE_CHAR_IDENTITY_FAILED\n",stderr);goto done;}
    if (pread(fd,data[0],1,(off_t)base*4096)!=-1 || errno!=EINVAL) {
        fputs("SIZE_REJECTION_FAILED\n",stderr);goto done;
    }
    if (pread(fd,data[0],4096,(off_t)(base+1U)*4096)!=-1 || errno!=EINVAL) {
        fputs("SEQUENCE_REJECTION_FAILED\n",stderr);goto done;
    }
    for (i=0;i<count;i++) {
        ssize_t n=pread(fd,data[i],4096,(off_t)(base+(layout_mode==2?i:(i&1U)))*4096);
        /* No retry after any failed/short Read: ownership is uncertain. */
        if (n!=4096) {fputs("PREAD_FAILED_NO_RETRY\n",stderr);goto done;}
    }
    if (layout_mode!=2) {
        if (memcmp(data[0],data[2],4096) || memcmp(data[1],data[3],4096)) {
            fputs("PRIVATE_PAIR_COMPARISON_FAILED\n",stderr);goto done;
        }
        puts("PRIVATE_PREAD_PASS completed=4 pair_equality=1 writes=0 payload_and_hashes_exported=0");
    }
    if(layout_mode==2) {
        struct n71_gpt_full_result g;
        const unsigned char *pages[4]={data[1],data[2],data[3],data[4]};
        int grc=n71_gpt_full_parse(data[0],pages,&g);
        if(grc){explicit_bzero(&g,sizeof(g));fprintf(stderr,"GPT_FULL_FAILED rc=%d\n",grc);goto done;}
        printf("GPT_FULL_PASS completed=5 declared_entries=%u checked_entries=%u used_entries=%u apfs_type_hints=%u array_complete=%u array_crc_checked=%u array_crc_ok=%u writes=0 pair_equality_tested=0\n",
            g.declared,g.checked,g.used,g.apfs_type_count,g.array_complete,g.array_crc_checked,g.array_crc_ok);
        for(i=0;i<g.used;i++)printf("PRIVATE_GPT_RANGE slot=%u type=%s first_lba=%llu last_lba=%llu\n",
            g.ranges[i].slot,g.ranges[i].apfs_type?"APFS_HINT":"OTHER",g.ranges[i].first,g.ranges[i].last);
        explicit_bzero(&g,sizeof(g));
    }
    if (layout_mode==1) {
        struct n71_gpt_prefix_result g;
        int grc=n71_gpt_prefix_parse(data[0],data[1],4096,&g);
        if (grc) {fprintf(stderr,"GPT_PREFIX_FAILED rc=%d\n",grc);goto done;}
        printf("GPT_PREFIX_PASS declared_entries=%u checked_entries=%u used_entries=%u apfs_type_hints=%u array_complete=%u array_crc_checked=%u array_crc_ok=%u\n",
            g.declared,g.checked,g.used,g.apfs_type_count,g.array_complete,g.array_crc_checked,g.array_crc_ok);
        /* Parsed coordinates are owner-private diagnostic metadata. Never
         * publish per-device ranges, names, GUIDs or CRC values to Git. */
        for(i=0;i<g.used;i++)printf("PRIVATE_GPT_RANGE slot=%u type=%s first_lba=%llu last_lba=%llu\n",
            g.ranges[i].slot,g.ranges[i].apfs_type?"APFS_HINT":"OTHER",
            g.ranges[i].first,g.ranges[i].last);
        explicit_bzero(&g,sizeof(g));
    }
    if(layout_mode==3) {
        struct n71_apfs_superblock_result a;
        int arc=n71_apfs_superblock_parse(data[0],4096,partition_blocks,&a);
        if(arc){explicit_bzero(&a,sizeof(a));fprintf(stderr,"APFS_SUPERBLOCK_FAILED rc=%d\n",arc);goto done;}
        printf("APFS_SUPERBLOCK_PASS nxsb=%u checksum_ok=%u object_header_ok=%u native_block_size=%u container_range_ok=%u checkpoint_ranges_ok=%u omap_present=%u omap_reference_ok=%u max_volume_slots=%u used_volume_slots=%u latest_checkpoint_selected=0 filesystem_mounted=0\n",
            a.magic_ok,a.checksum_ok,a.object_header_ok,a.block_size,a.geometry_ok,
            a.checkpoint_ranges_ok,a.omap_present,a.omap_reference_ok,a.max_volume_slots,a.used_volume_slots);
        /* Geometry and physical references are owner-private. They are not
         * unique UUIDs, raw checksum values or virtual/ephemeral object IDs. */
        printf("PRIVATE_APFS_REFS container_blocks=%llu checkpoint_desc_base=%llu checkpoint_desc_blocks=%u checkpoint_data_base=%llu checkpoint_data_blocks=%u omap_block=%llu\n",
            a.container_blocks,a.desc_base,a.desc_blocks,a.data_base,a.data_blocks,a.omap_block);
        explicit_bzero(&a,sizeof(a));
    }
    if(layout_mode==4) {
        struct n71_apfs_checkpoint_pair_result c;
        struct n71_apfs_checkpoint_pair_refs p;
        int crc=n71_apfs_checkpoint_pair_parse(data[0],data[1],4096,
                                              partition_blocks,relative,&c,&p);
        if(crc){explicit_bzero(&c,sizeof(c));explicit_bzero(&p,sizeof(p));fprintf(stderr,"APFS_CHECKPOINT_PAIR_FAILED rc=%d\n",crc);goto done;}
        printf("APFS_CHECKPOINT_PAIR_PASS nxsb_valid=%u checksum_pair_ok=%u object_headers_ok=%u same_transaction=%u descriptor_ring_ok=%u descriptor_pair_complete=%u data_ring_ok=%u mapping_count=%u mapping_extents_in_data_window=%u mapping_keys_unique=%u mapping_extents_nonoverlap=%u spaceman_mapping_present=%u reaper_mapping_present=%u omap_reference_present=%u volume_slot_count=%u max_volume_slots=%u block_zero_UUID_compared=0 complete_scan=0 latest_checkpoint_selected=0 checkpoint_data_objects_read=0 filesystem_mounted=0\n",
            c.nxsb_valid,c.checksum_pair_ok,c.object_headers_ok,c.same_transaction,
            c.descriptor_ring_ok,c.descriptor_pair_complete,c.data_ring_ok,c.mapping_count,
            c.mapping_extents_in_data_window,c.mapping_keys_unique,c.mapping_extents_nonoverlap,
            c.spaceman_mapping_present,c.reaper_mapping_present,c.omap_reference_present,
            c.volume_slot_count,c.max_volume_slots);
        printf("PRIVATE_CHECKPOINT_REFS container_blocks=%llu checkpoint_desc_base=%llu checkpoint_desc_blocks=%u checkpoint_data_base=%llu checkpoint_data_blocks=%u omap_block=%llu spaceman_block=%llu spaceman_blocks=%u reaper_block=%llu reaper_blocks=%u\n",
            p.container_blocks,p.desc_base,p.desc_blocks,p.data_base,p.data_blocks,p.omap_block,
            p.spaceman_block,p.spaceman_blocks,p.reaper_block,p.reaper_blocks);
        explicit_bzero(&c,sizeof(c));explicit_bzero(&p,sizeof(p));
    }
    rc=0;
done:
    /* Volatile RAM node only; buffer bytes never written to any file. */
    explicit_bzero(data,sizeof(data));
    if (fd>=0) close(fd);
    if (created) unlink(path);
    return rc;
}
