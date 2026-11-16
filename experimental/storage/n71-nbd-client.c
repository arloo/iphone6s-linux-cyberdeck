// SPDX-License-Identifier: MIT
// Minimal lab-only NBD client for isolated N71 USB gadget, dedicated /dev/nbd0.
// Never connects to internal Apple storage. Do not put personal data on this export.
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/nbd.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <arpa/inet.h>

static int readall(int fd, void *buf, size_t len) {
    size_t got = 0;
    while (got < len) {
        ssize_t n = read(fd, (char *)buf + got, len - got);
        if (n <= 0) return -1;
        got += (size_t)n;
    }
    return 0;
}
static uint64_t be64(const unsigned char *b) {
    uint64_t v = 0;
    for (int i = 0; i < 8; ++i) v = (v << 8) | b[i];
    return v;
}
static uint32_t be32(const unsigned char *b) {
    uint32_t v = 0;
    for (int i = 0; i < 4; ++i) v = (v << 8) | b[i];
    return v;
}
int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "--ro") && strcmp(argv[1], "--rw"))) {
        fputs("Usage: n71-nbd-client --ro|--rw (fixed isolated USB endpoint and /dev/nbd0)\n", stderr);
        return 2;
    }
    int writable = !strcmp(argv[1], "--rw"), fd = -1, sock = -1, started = 0, rc = 1;
    struct sockaddr_in host = { .sin_family = AF_INET, .sin_port = htons(18890) };
    struct sockaddr_in device = { .sin_family = AF_INET, .sin_port = 0 };
    if (inet_pton(AF_INET, "172.16.42.2", &host.sin_addr) != 1 ||
        inet_pton(AF_INET, "172.16.42.1", &device.sin_addr) != 1) return 2;
    sock = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (sock < 0 || bind(sock, (struct sockaddr *)&device, sizeof(device)) < 0 ||
        connect(sock, (struct sockaddr *)&host, sizeof(host)) < 0) {
        perror("NBD USB socket");
        goto done;
    }
    unsigned char hs[152] = {0};
    if (readall(sock, hs, sizeof(hs)) < 0 ||
        memcmp(hs, "NBDMAGIC", 8) != 0 ||
        be64(hs + 8) != 0x00420281861253ULL) {
        fputs("Untrusted or incomplete NBD handshake\n", stderr);
        goto done;
    }
    uint64_t size = be64(hs + 16);
    uint32_t flags = be32(hs + 24);
    if (size < 32ULL*1024*1024 || size > 1024ULL*1024*1024 || size % 4096 ||
        !(flags & NBD_FLAG_HAS_FLAGS) || (writable && (flags & NBD_FLAG_READ_ONLY)) ||
        (flags & ~(NBD_FLAG_HAS_FLAGS | NBD_FLAG_READ_ONLY | NBD_FLAG_SEND_FLUSH | NBD_FLAG_SEND_FUA))) {
        fputs("Rejected NBD export size/flags/mode\n", stderr);
        goto done;
    }
    fd = open("/dev/nbd0", O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        perror("Open fixed /dev/nbd0");
        goto done;
    }
    if (ioctl(fd, NBD_SET_BLKSIZE, 4096UL) < 0 ||
        ioctl(fd, NBD_SET_SIZE_BLOCKS, (unsigned long)(size / 4096)) < 0 ||
        ioctl(fd, NBD_SET_FLAGS, (unsigned long)flags) < 0 ||
        ioctl(fd, NBD_SET_TIMEOUT, 45UL) < 0 ||
        ioctl(fd, NBD_SET_SOCK, sock) < 0) {
        perror("NBD configure");
        goto done;
    }
    started = 1;
    printf("N71_NBD_KERNEL_ATTACHED bytes=%llu mode=%s\n",
           (unsigned long long)size, writable ? "rw" : "ro");
    fflush(stdout);
    if (ioctl(fd, NBD_DO_IT) < 0) perror("NBD_DO_IT");
    else rc = 0;
done:
    if (fd >= 0) {
        if (started) ioctl(fd, NBD_CLEAR_QUE);
        if (started) ioctl(fd, NBD_CLEAR_SOCK);
        close(fd);
    }
    if (sock >= 0) close(sock);
    return rc;
}
