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
#include "n71-gpt-prefix-core.h"
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
 } else if(argc==3&&!strcmp(argv[1],"--pair")) {
  if(!argv[2][0])return -1;
  for(s=argv[2];*s;s++)if(*s<'0'||*s>'9')return -1;
  errno=0;n=strtoull(argv[2],&end,10);
  if(errno||*end||n>15624998ULL)return -1;
  *base=(unsigned)n;return 0;
 }
 return -1;
}
int main(int argc,char **argv)
{
    const char *path="/dev/n71nand-probe";
    unsigned base,major=0,i;
    unsigned char data[4][4096];
    struct stat st;
    const struct rlimit no_core={0,0};
    struct timespec delay={0,100000000};
    int fd=-1,rc=1,created=0,layout_mode=0;
    if (select_pair(argc,argv,&base,&layout_mode)) {
        fputs("Usage: n71-nand-private-probe --initial|--tail|--layout|--pair BASE\n",stderr);return 2;
    }
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
    for (i=0;i<4;i++) {
        ssize_t n=pread(fd,data[i],4096,(off_t)(base+(i&1U))*4096);
        /* No retry after any failed/short Read: ownership is uncertain. */
        if (n!=4096) {fputs("PREAD_FAILED_NO_RETRY\n",stderr);goto done;}
    }
    if (memcmp(data[0],data[2],4096) || memcmp(data[1],data[3],4096)) {
        fputs("PRIVATE_PAIR_COMPARISON_FAILED\n",stderr);goto done;
    }
    puts("PRIVATE_PREAD_PASS completed=4 pair_equality=1 writes=0 payload_and_hashes_exported=0");
    if (layout_mode) {
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
    rc=0;
done:
    /* Volatile RAM node only; buffer bytes never written to any file. */
    explicit_bzero(data,sizeof(data));
    if (fd>=0) close(fd);
    if (created) unlink(path);
    return rc;
}
