// SPDX-License-Identifier: MIT
// iPhone 6s HCI controller state inspection via BlueZ socket ioctls.
// Read-only by default. Does not print device-unique Bluetooth addresses.
// "up" explicitly requests HCI bring-up (volatile, may trigger firmware load).
#include <bluetooth/bluetooth.h>
#include <bluetooth/hci.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <stdlib.h>

static void display(int fd, int dev) {
    struct hci_dev_info di={0};
    di.dev_id=(unsigned short)dev;
    if(ioctl(fd, HCIGETDEVINFO, &di)<0) {
        fprintf(stderr,"HCIGETDEVINFO hci%d failed: %s\n",dev,strerror(errno));
        return;
    }
    printf("hci%d name=%.8s flags=0x%08x type=%u acl_mtu=%u sco_mtu=%u\n",
           dev,di.name,di.flags,di.type,di.acl_mtu,di.sco_mtu);
    printf("Features:");
    for(int i=0;i<8;i++) printf(" %02x",di.features[i]);
    printf("\nStats: cmd_tx=%u evt_rx=%u err_rx=%u err_tx=%u\n",
           di.stat.cmd_tx,di.stat.evt_rx,di.stat.err_rx,di.stat.err_tx);
    puts("Controller address deliberately redacted.");
}
int main(int argc,char**argv) {
    int dev=0;
    if(argc>2) {fputs("Usage: hci-probe [info|up|down]\n",stderr);return 2;}
    const char* cmd=argc>1?argv[1]:"info";
    if(strcmp(cmd,"info") && strcmp(cmd,"up") && strcmp(cmd,"down")) {
        fputs("Usage: hci-probe [info|up|down]\n",stderr);return 2;
    }
    int fd=socket(AF_BLUETOOTH,SOCK_RAW,BTPROTO_HCI);
    if(fd<0) {perror("socket(AF_BLUETOOTH)");return 1;}
    if(!strcmp(cmd,"up") || !strcmp(cmd,"down")) {
        printf("Requesting volatile HCI %s on hci%d\n",cmd,dev);
        if(ioctl(fd,!strcmp(cmd,"up")?HCIDEVUP:HCIDEVDOWN,dev)<0)
           fprintf(stderr,"HCI %s: %s\n",cmd,strerror(errno));
    }
    display(fd,dev);
    close(fd);
    return 0;
}
