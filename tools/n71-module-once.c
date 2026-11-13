// SPDX-License-Identifier: MIT
/* Load an owner-supplied module with exactly ONE kernel system call.
 * BusyBox insmod can retry failed finit_module via init_module, repeating
 * a one-shot experiment after its first module_init already ran/rolled back.
 * This intentionally has NO compatibility fallback and never ignores errors.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    struct stat st;
    int fd, rc, saved;

    if (argc < 2 || argc > 3) {
        fputs("Usage: n71-module-once module.ko [parameter-string]\n", stderr);
        return 2;
    }
    fd = open(argv[1], O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) {
        perror("open module");
        return 2;
    }
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) ||
        st.st_size < 1 || st.st_size > 16 * 1024 * 1024) {
        fputs("Refusing nonregular, empty or oversized module\n", stderr);
        close(fd);
        return 2;
    }
    /* Exactly one syscall, no init_module retry on ANY failure. */
    rc = syscall(SYS_finit_module, fd, argc == 3 ? argv[2] : "", 0);
    saved = rc < 0 ? errno : 0;
    close(fd);
    printf("FINIT_MODULE_ONCE rc=%d errno=%d\n", rc, saved);
    if (rc < 0)
        fprintf(stderr, "Module rejected: %s; no retry performed\n", strerror(saved));
    return rc < 0 ? 1 : 0;
}
