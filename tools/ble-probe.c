// SPDX-License-Identifier: MIT
// CYBERDECK A9: passive, read-only Bluetooth Low Energy discovery probe.
// Uses HCI raw socket, does not print, copy, or save device addresses.
// The scan initiates radio reception only; this is NOT pairing.
#include <bluetooth/bluetooth.h>
#include <bluetooth/hci.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <time.h>
#include <unistd.h>

#define LE_META_EVENT 0x3e
#define LE_ADV_REPORT 0x02
#define HCI_EV_CMD_COMPLETE 0x0e
#define HCI_EV_CMD_STATUS 0x0f

static int64_t time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec*1000 + ts.tv_nsec/1000000;
}
static int read_packet(int fd, unsigned char* b, size_t sz, int ms) {
    fd_set rs; FD_ZERO(&rs); FD_SET(fd,&rs);
    struct timeval tv={ms/1000,(ms%1000)*1000};
    int n=select(fd+1,&rs,NULL,NULL,&tv);
    if(n<=0)return n;
    return (int)read(fd,b,sz);
}
static int hci_send(int fd,const unsigned char* b,size_t n) {
    ssize_t ret=write(fd,b,n);
    return ret==(ssize_t)n?0:-1;
}
static int wait_command(int fd,unsigned opcode, int timeout_ms) {
    unsigned char b[1024]; int64_t end=time_ms()+timeout_ms;
    while(time_ms()<end) {
        int rem=(int)(end-time_ms());
        if(rem<1)break;
        int n=read_packet(fd,b,sizeof(b),rem);
        if(n<0) {perror("HCI read");return -1;}
        if(n<7||b[0]!=HCI_EVENT_PKT) continue;
        if(b[1]==HCI_EV_CMD_COMPLETE && ((unsigned)b[4] | ((unsigned)b[5]<<8))==opcode) {
            printf("HCI cmd 0x%04x complete, status=%u\n",opcode,b[6]);
            return b[6]==0?0:-1;
        }
        if(b[1]==HCI_EV_CMD_STATUS && ((unsigned)b[5] | ((unsigned)b[6]<<8))==opcode) {
            printf("HCI cmd 0x%04x status=%u\n",opcode,b[3]);
            return b[3]==0?0:-1;
        }
    }
    fprintf(stderr,"HCI cmd 0x%04x timed out\n",opcode);
    return -1;
}
int main(int argc,char**argv) {
    int seconds=argc>=2?atoi(argv[1]):12;
    if(argc>2||seconds<1||seconds>30) {
        fprintf(stderr,"Usage: ble-probe [seconds: 1..30]\n");
        return 2;
    }
    int fd=socket(AF_BLUETOOTH,SOCK_RAW,BTPROTO_HCI);
    if(fd<0){perror("Bluetooth raw socket");return 1;}
    struct sockaddr_hci sa={.hci_family=AF_BLUETOOTH,.hci_dev=0,.hci_channel=HCI_CHANNEL_RAW};
    if(bind(fd,(struct sockaddr*)&sa,sizeof(sa))<0){perror("HCI bind");close(fd);return 1;}
    struct hci_filter filter={0};
    filter.type_mask=(uint32_t)1 << HCI_EVENT_PKT;
    filter.event_mask[0]=UINT32_MAX;
    filter.event_mask[1]=UINT32_MAX;
    if(setsockopt(fd,SOL_HCI,HCI_FILTER,&filter,sizeof(filter))<0) {
        perror("HCI filter");close(fd);return 1;
    }
    // LE Set Scan Parameters opcode 0x200B, passive, interval/window 0x0010,
    // public controller address type and accept all advertising events.
    const unsigned char params[]={0x01,0x0b,0x20,0x07,0x00,0x10,0x00,0x10,0x00,0x00,0x00};
    const unsigned char enable[]={0x01,0x0c,0x20,0x02,0x01,0x01};
    const unsigned char disable[]={0x01,0x0c,0x20,0x02,0x00,0x00};
    int result=1;
    printf("CYBERDECK A9 passive BLE scan (%d sec), privacy mode: no addresses\n",seconds);
    if(hci_send(fd,params,sizeof(params))<0 || wait_command(fd,0x200b,3000)<0) goto cleanup;
    if(hci_send(fd,enable,sizeof(enable))<0 || wait_command(fd,0x200c,3000)<0) goto cleanup;
    printf("Scan enabled (passive).\n");fflush(stdout);
    int64_t end=time_ms()+seconds*1000LL;
    unsigned packets=0,reports=0;
    unsigned char b[2048];
    while(time_ms()<end) {
        int rem=(int)(end-time_ms());if(rem<1)break;
        int n=read_packet(fd,b,sizeof(b),rem);
        if(n<0){perror("HCI read");goto stop;}
        if(n<5)continue;
        if(b[0]==HCI_EVENT_PKT && b[1]==LE_META_EVENT && b[3]==LE_ADV_REPORT) {
            packets++;
            reports+=b[4];
        }
    }
    printf("BLE events: %u; advertising reports: %u\n",packets,reports);
    puts(reports?"PASS: BLE advertisements received from RF environment.":"INCONCLUSIVE: no advertisements observed in this scan window.");
    result=0;
stop:
    if(hci_send(fd,disable,sizeof(disable))<0 || wait_command(fd,0x200c,3000)<0) {
        fprintf(stderr,"Warning: scan disable not confirmed\n");
        result=1;
    }
cleanup:
    close(fd);
    return result;
}
