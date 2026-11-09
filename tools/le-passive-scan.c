// SPDX-License-Identifier: MIT
// Apple A9 / BCM4350C5: bounded, passive-only BLE receive test.
// Prints aggregate counts and RSSI only. No MACs, payloads or identifiers.
// Does NOT pair, connect, advertise, or transmit BLE radio frames.
#define _POSIX_C_SOURCE 200809L
#include <bluetooth/bluetooth.h>
#include <bluetooth/hci.h>
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define OPC_SET_SCAN_PARAMS 0x200b
#define OPC_SET_SCAN_ENABLE 0x200c
#define EVT_LE_META 0x3e
#define EVT_LE_ADVERTISING_REPORT 0x02
static volatile sig_atomic_t stopping;
static void request_stop(int sig) { (void)sig; stopping=1; }

static long now_ms(void) {
    struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
    return t.tv_sec*1000L+t.tv_nsec/1000000L;
}
static int cmd(int s,uint16_t opcode,const uint8_t *p,uint8_t n) {
    uint8_t b[4+32];
    if(n>32)return -1;
    b[0]=HCI_COMMAND_PKT;b[1]=opcode&255;b[2]=opcode>>8;b[3]=n;
    if(n)memcpy(b+4,p,n);
    ssize_t w=write(s,b,(size_t)4+n);
    if(w!=(ssize_t)4+n){perror("HCI write");return -1;}
    return 0;
}
static int recv_evt(int s,uint8_t *b,size_t cap,int wait_ms) {
    fd_set r;FD_ZERO(&r);FD_SET(s,&r);
    struct timeval t={wait_ms/1000,(wait_ms%1000)*1000};
    int ret=select(s+1,&r,NULL,NULL,&t);
    if(ret<=0)return ret;
    ssize_t n=read(s,b,cap);
    return n<0?-1:(int)n;
}
static int await_ack(int s,uint16_t opcode) {
    long end=now_ms()+3000;
    uint8_t b[1024];
    while(now_ms()<end&&!stopping) {
        int n=recv_evt(s,b,sizeof(b),350);
        if(n<7 || b[0]!=HCI_EVENT_PKT)continue;
        int got=-1,status=-1;
        if(b[1]==0x0e && n>=7){got=b[4]|b[5]<<8;status=b[6];}
        if(b[1]==0x0f && n>=7){got=b[5]|b[6]<<8;status=b[3];}
        if(got==opcode) {
            if(status)fprintf(stderr,"HCI opcode 0x%04x rejected status=0x%02x\n",opcode,status);
            return status==0?0:-1;
        }
    }
    fprintf(stderr,"Timed out waiting for HCI command 0x%04x acknowledgment\n",opcode);
    return -1;
}
int main(int argc,char **argv) {
    if(argc!=2) {fputs("Usage: le-passive-scan <seconds 1..15>\n",stderr);return 2;}
    char *end=NULL;long secs=strtol(argv[1],&end,10);
    if(!end||*end||secs<1||secs>15) {fputs("Use 1..15 seconds\n",stderr);return 2;}
    signal(SIGINT,request_stop);signal(SIGTERM,request_stop);
    int s=socket(AF_BLUETOOTH,SOCK_RAW,BTPROTO_HCI);
    if(s<0){perror("HCI raw socket");return 1;}
    struct sockaddr_hci sa={0};sa.hci_family=AF_BLUETOOTH;sa.hci_dev=0;
    sa.hci_channel=HCI_CHANNEL_RAW;
    if(bind(s,(struct sockaddr*)&sa,sizeof(sa))<0){perror("HCI bind");close(s);return 1;}
    struct hci_filter f={0};
    f.type_mask=1U<<HCI_EVENT_PKT;
    f.event_mask[0]=0xffffffffU; f.event_mask[1]=0xffffffffU;
    if(setsockopt(s,SOL_HCI,HCI_FILTER,&f,sizeof(f))<0){
        perror("HCI filter");close(s);return 1;
    }
    // Passive scan type 0x00. 10ms interval and 10ms window.
    // Public address type is selected but passive scanning emits no BLE RF TX.
    uint8_t params[]={0x00,0x10,0x00,0x10,0x00,0x00,0x00};
    uint8_t on[]={0x01,0x01},off[]={0x00,0x00};
    puts("CYBERDECK A9 — PASSIVE BLE RECEIVE-ONLY CHECK");
    puts("No pairing, no advertising, no addresses or payload capture.");
    if(cmd(s,OPC_SET_SCAN_PARAMS,params,sizeof(params))||await_ack(s,OPC_SET_SCAN_PARAMS)) {
        close(s);return 1;
    }
    if(cmd(s,OPC_SET_SCAN_ENABLE,on,sizeof(on))||await_ack(s,OPC_SET_SCAN_ENABLE)) {
        cmd(s,OPC_SET_SCAN_ENABLE,off,sizeof(off));close(s);return 1;
    }
    long endms=now_ms()+secs*1000L;
    unsigned reports=0,meta_events=0;int minr=127,maxr=-128;
    while(now_ms()<endms && !stopping) {
        uint8_t b[1024];int n=recv_evt(s,b,sizeof(b),250);
        if(n<5||b[0]!=HCI_EVENT_PKT||b[1]!=EVT_LE_META||b[3]!=EVT_LE_ADVERTISING_REPORT)continue;
        meta_events++;
        unsigned nreports=b[4];size_t pos=5;
        for(unsigned i=0;i<nreports;i++) {
            if(pos+10>(size_t)n)break;
            unsigned len=b[pos+8];
            if(pos+10+len>(size_t)n)break;
            int rssi=(int8_t)b[pos+9+len];
            if(rssi<minr)minr=rssi;
            if(rssi>maxr)maxr=rssi;
            reports++;pos+=10+len;
        }
    }
    // Disable scanning regardless of outcome; volatile HCI control only.
    int disabled=(cmd(s,OPC_SET_SCAN_ENABLE,off,sizeof(off))==0 &&
                  await_ack(s,OPC_SET_SCAN_ENABLE)==0);
    printf("LE_META_EVENTS=%u LE_REPORTS=%u\n",meta_events,reports);
    if(reports)printf("RSSI_RANGE_DBM=%d..%d\n",minr,maxr);
    printf("SCAN_DISABLED=%s\n",disabled?"YES":"NOT_CONFIRMED");
    close(s);
    if(!disabled)return 1;
    if(!reports)puts("No advertisements received; not proof of RF failure.");
    return 0;
}
