/* SPDX-License-Identifier: MIT */
/* One local, bounded char-probe client. No payload or sector hashes leave
 * process memory. This does not mount, write or scan the phone's NAND. */
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
int main(int argc,char **argv)
{
    const char *path="/dev/n71nand-probe";
    unsigned base,major=0,i;
    unsigned char data[4][4096];
    struct stat st;
    const struct rlimit no_core={0,0};
    struct timespec delay={0,100000000};
    int fd=-1,rc=1,created=0;
    if (argc!=2 || (strcmp(argv[1],"--initial") && strcmp(argv[1],"--tail"))) {
        fputs("Usage: n71-nand-private-probe --initial|--tail\n",stderr);return 2;
    }
    if (geteuid()!=0) {fputs("ROOT_REQUIRED\n",stderr);return 2;}
    if (setrlimit(RLIMIT_CORE,&no_core) || prctl(PR_SET_DUMPABLE,0,0,0,0)) {
        fputs("PRIVATE_MEMORY_GUARD_FAILED\n",stderr);return 2;
    }
    base=!strcmp(argv[1],"--tail")?15624998U:0U;
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
    rc=0;
done:
    /* Volatile RAM node only; buffer bytes never written to any file. */
    explicit_bzero(data,sizeof(data));
    if (fd>=0) close(fd);
    if (created) unlink(path);
    return rc;
}
