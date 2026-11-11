#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>
#include "font_data.h"

#define MAX_TOUCH 32
#define TEST_TARGETS 4
#define COL_BG 0x090F19u
#define COL_GRID 0x123039u
#define COL_CYAN 0x25E4D5u
#define COL_PINK 0xFB5289u
#define COL_WHITE 0xDAEAF1u
#define COL_SOFT 0x88ABBBu
#define COL_AMBER 0xFACA65u

static int fbfd=-1, evfd=-1, W,H, stride, nbytes;
static uint8_t *pixels,*backup;
static struct fb_var_screeninfo vinfo;
static struct fb_fix_screeninfo finfo;
static volatile sig_atomic_t running=1;
static int hit[TEST_TARGETS], events_count, frame_count;
static int active_slot=0, max_active;
static struct point { int id,x,y,pending,has_x,has_y; } touches[MAX_TOUCH];
static int tx[TEST_TARGETS],ty[TEST_TARGETS];
static unsigned long draw_num;
static int last_btn_id=-1;

static void on_signal(int sig) { (void)sig; running=0; }
static uint32_t channel(unsigned value,struct fb_bitfield bf) {
    if(!bf.length) return 0;
    unsigned maxbit=(1u<<bf.length)-1u;
    return (((value*maxbit+127)/255)&maxbit)<<bf.offset;
}
static uint32_t rgb(uint32_t val) {
    unsigned r=(val>>16)&255, g=(val>>8)&255, b=val&255;
    return channel(r,vinfo.red)|channel(g,vinfo.green)|channel(b,vinfo.blue);
}
static void rect(int x,int y,int w,int h,uint32_t color) {
    if(x<0){w+=x;x=0;} if(y<0){h+=y;y=0;}
    if(x>=W||y>=H||w<=0||h<=0) return;
    if(x+w>W)w=W-x;
    if(y+h>H)h=H-y;
    uint32_t c=rgb(color);
    for(int yy=y;yy<y+h;yy++){
        uint32_t *p=(uint32_t *)(pixels+(size_t)yy*stride)+(size_t)x;
        for(int xx=0;xx<w;xx++)p[xx]=c;
    }
}
static void line(int x0,int y0,int x1,int y1,uint32_t color) {
    int dx=abs(x1-x0),sx=x0<x1?1:-1;
    int dy=-abs(y1-y0),sy=y0<y1?1:-1,err=dx+dy;
    uint32_t c=rgb(color);
    for(;;){
        if(x0>=0&&x0<W&&y0>=0&&y0<H)
            *(uint32_t *)(pixels+(size_t)y0*stride+(size_t)x0*4)=c;
        if(x0==x1&&y0==y1)break;
        int e2=err*2;
        if(e2>=dy){err+=dy;x0+=sx;}
        if(e2<=dx){err+=dx;y0+=sy;}
    }
}
static void outline(int x,int y,int w,int h,uint32_t c) {
    line(x,y,x+w,y,c);line(x,y,x,y+h,c);
    line(x+w,y,x+w,y+h,c);line(x,y+h,x+w,y+h,c);
}
static void ring(int cx,int cy,int r,uint32_t color) {
    int x=r,y=0,err=1-x; uint32_t c=rgb(color);
    while(x>=y){
        int pts[8][2]={{cx+x,cy+y},{cx+y,cy+x},{cx-y,cy+x},
            {cx-x,cy+y},{cx-x,cy-y},{cx-y,cy-x},{cx+y,cy-x},{cx+x,cy-y}};
        for(int k=0;k<8;k++) {
            int a=pts[k][0],b=pts[k][1];
            if(a>=0&&a<W&&b>=0&&b<H)
                *(uint32_t *)(pixels+(size_t)b*stride+(size_t)a*4)=c;
        }
        ++y;
        if(err<0)err+=2*y+1; else {--x;err+=2*(y-x+1);}
    }
}
static void label(int x,int y,const char *text,int scale,uint32_t color) {
    if(scale<1||scale>3)return;
    for(const char *p=text;*p;p++){
        unsigned char ch=(unsigned char)*p;
        if(ch>='a'&&ch<='z')ch-='a'-'A';
        if(ch<32||ch>126)ch='?';
        for(int cy=0;cy<24;cy++){
            uint16_t bits=font14x24[ch-32][cy];
            for(int cx=0;cx<14;cx++)
                if(bits&(1u<<(13-cx)))
                    rect(x+cx*scale,y+cy*scale,scale,scale,color);
        }
        x+=14*scale;
        if(x>W-14*scale)break;
    }
}
static long sec_uptime(void) {
    struct timespec t;
    if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;
    return t.tv_sec;
}
static void render(void) {
    rect(0,0,W,H,COL_BG);
    for(int x=0;x<W;x+=50)line(x,300,x,H-220,COL_GRID);
    for(int y=320;y<H-220;y+=50)line(0,y,W,y,COL_GRID);
    rect(0,0,W,8,COL_PINK);rect(0,8,W,3,COL_CYAN);
    label(28,33,"CYBERDECK / A9",2,COL_CYAN);
    label(33,106,"N71 // NATIVE LINUX // V0.1",1,COL_SOFT);
    line(30,145,W-30,145,COL_CYAN);
    rect(28,166,334,118,0x10212C);
    rect(388,166,334,118,0x10212C);
    outline(28,166,334,118,COL_GRID);
    outline(388,166,334,118,COL_GRID);
    label(42,185,"SYSTEM / ARM64",1,COL_CYAN);
    label(42,225,"LINUX ONLINE",1,COL_WHITE);
    label(402,185,"TOUCH / Z2",1,COL_CYAN);
    label(402,225,"2-FINGER READY",1,COL_WHITE);
    line(28,300,W-28,300,COL_PINK);
    label(33,321,"EDGE TEST / 4 POINTS",1,COL_WHITE);

    tx[0]=52; tx[1]=W-52;
    tx[2]=52; tx[3]=W-52;
    ty[0]=398;ty[1]=398;
    ty[2]=H-320;ty[3]=H-320;
    for(int i=0;i<TEST_TARGETS;i++){
        uint32_t c=hit[i]?COL_CYAN:COL_AMBER;
        ring(tx[i],ty[i],41,c);
        ring(tx[i],ty[i],19,c);
        line(tx[i]-50,ty[i],tx[i]+50,ty[i],c);
        line(tx[i],ty[i]-50,tx[i],ty[i]+50,c);
        if(hit[i])rect(tx[i]-8,ty[i]-8,16,16,COL_CYAN);
    }
    label(215,410,"PRESS THE",1,COL_SOFT);
    label(215,443,"FOUR TARGETS",1,COL_WHITE);
    ring(W/2,(H+260)/2,142,COL_GRID);
    ring(W/2,(H+260)/2,92,COL_GRID);
    line(W/2-180,(H+260)/2,W/2+180,(H+260)/2,COL_GRID);
    line(W/2,(H+260)/2-180,W/2,(H+260)/2+180,COL_GRID);

    int active=0;
    for(int i=0;i<MAX_TOUCH;i++){
        if(touches[i].id>=0&&touches[i].has_x&&touches[i].has_y){
            active++;
            int x=touches[i].x,y=touches[i].y;
            ring(x,y,22,COL_PINK);
            ring(x,y,10,COL_CYAN);
            line(x-30,y,x+30,y,COL_PINK);
            line(x,y-30,x,y+30,COL_PINK);
        }
    }
    if(active>max_active)max_active=active;
    char buf[120];
    rect(25,H-224,W-50,205,0x10212C);
    outline(25,H-224,W-50,205,COL_CYAN);
    snprintf(buf,sizeof(buf),"ACTIVE:%d  MAX:%d",active,max_active);
    label(42,H-210,buf,1,COL_WHITE);
    snprintf(buf,sizeof(buf),"EVENTS:%d FRAMES:%d",events_count,frame_count);
    label(42,H-172,buf,1,COL_SOFT);
    snprintf(buf,sizeof(buf),"EDGES:%d / 4   UP:%lds",
        !!hit[0]+!!hit[1]+!!hit[2]+!!hit[3],sec_uptime());
    label(42,H-134,buf,1,COL_AMBER);
    rect(40,H-80,315,54,0x183B44);
    rect(390,H-80,315,54,0x422138);
    outline(40,H-80,315,54,COL_CYAN);
    outline(390,H-80,315,54,COL_PINK);
    label(105,H-64,"RESET",1,COL_CYAN);
    label(491,H-64,"EXIT",1,COL_PINK);
    rect(0,H-7,W,7,COL_PINK);
    draw_num++;
}
static int flush_fb(void){
    size_t done=0;
    while(done<(size_t)nbytes) {
        ssize_t n=pwrite(fbfd,pixels+done,(size_t)nbytes-done,(off_t)done);
        if(n<0&&errno==EINTR)continue;
        if(n<=0)return -1;
        done+=(size_t)n;
    }
    return 0;
}
static void hit_test(int x,int y,int id){
    if(id==last_btn_id)return;
    if(y>=H-84&&y<=H-22){
        if(x>=40&&x<=355){memset(hit,0,sizeof(hit));events_count=0;frame_count=0;}
        if(x>=390&&x<=705){running=0;}
        last_btn_id=id;
        return;
    }
    for(int t=0;t<TEST_TARGETS;t++){
        int dx=x-tx[t],dy=y-ty[t];
        if(dx*dx+dy*dy <= 62*62){
            hit[t]=1;
            break;
        }
    }
}
static void handle(struct input_event *e){
    events_count++;
    if(e->type==EV_ABS) {
        switch(e->code) {
        case ABS_MT_SLOT:
            if(e->value>=0&&e->value<MAX_TOUCH)active_slot=e->value;
            else active_slot=-1;
            break;
        case ABS_MT_TRACKING_ID:
            if(active_slot<0)return;
            if(e->value<0) {
                touches[active_slot].id=-1;
                touches[active_slot].pending=0;
                touches[active_slot].has_x=0;touches[active_slot].has_y=0;
            } else {
                touches[active_slot].id=e->value;
                touches[active_slot].pending=1;
                touches[active_slot].has_x=0;touches[active_slot].has_y=0;
            }
            break;
        case ABS_MT_POSITION_X:
            if(active_slot>=0) {
                touches[active_slot].x=e->value;
                touches[active_slot].has_x=1;
            }
            break;
        case ABS_MT_POSITION_Y:
            if(active_slot>=0) {
                touches[active_slot].y=e->value;
                touches[active_slot].has_y=1;
            }
            break;
        }
    } else if(e->type==EV_SYN&&e->code==SYN_REPORT){
        frame_count++;
        for(int k=0;k<MAX_TOUCH;k++){
            struct point *t=&touches[k];
            if(t->id>=0&&t->pending&&t->has_x&&t->has_y){
                hit_test(t->x,t->y,t->id);
                t->pending=0;
            }
        }
    }
}
int main(void){
    signal(SIGTERM,on_signal);signal(SIGINT,on_signal);
    for(int k=0;k<MAX_TOUCH;k++)touches[k].id=-1;
    fbfd=open("/dev/fb0",O_RDWR|O_CLOEXEC);
    if(fbfd<0){perror("open fb0");return 2;}
    if(ioctl(fbfd,FBIOGET_FSCREENINFO,&finfo)<0||
       ioctl(fbfd,FBIOGET_VSCREENINFO,&vinfo)<0){
        perror("fb info");return 3;
    }
    W=vinfo.xres;H=vinfo.yres;stride=finfo.line_length;
    if(W!=750||H!=1334||vinfo.bits_per_pixel!=32||
       vinfo.xoffset||vinfo.yoffset||stride<(W*4)||
       stride>(W*4+4096)||H>4096){
        fprintf(stderr,"Unsupported framebuffer %dx%d %dbpp stride %d offset %d:%d\n",
           W,H,vinfo.bits_per_pixel,stride,vinfo.xoffset,vinfo.yoffset);
        return 4;
    }
    nbytes=stride*H;
    pixels=calloc(1,(size_t)nbytes);
    backup=malloc((size_t)nbytes);
    if(!pixels||!backup){perror("alloc");return 5;}
    ssize_t n=pread(fbfd,backup,(size_t)nbytes,0);
    if(n!=nbytes){free(backup);backup=NULL;}
    evfd=open("/dev/input/event0",O_RDONLY|O_NONBLOCK|O_CLOEXEC);
    if(evfd<0){perror("open event0");return 6;}
    fprintf(stdout,
       "CYBERDECK_GUI_START: framebuffer %dx%d stride=%d bytes=%d, evdev ready\n",
       W,H,stride,nbytes);
    fflush(stdout);
    render();
    if(flush_fb()<0){perror("first fb write");return 7;}
    long last_render_ms=0;
    while(running){
        struct pollfd pf={.fd=evfd,.events=POLLIN};
        int n=poll(&pf,1,80);
        int changed=0;
        if(n>0&&(pf.revents&POLLIN)){
            struct input_event ev[64];
            for(int batches=0;batches<8;batches++){
                ssize_t got=read(evfd,ev,sizeof(ev));
                if(got<=0)break;
                for(size_t k=0;k<(size_t)got/sizeof(ev[0]);k++) {
                    handle(&ev[k]);changed=1;
                }
            }
        }
        struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
        long now_ms=t.tv_sec*1000L+t.tv_nsec/1000000L;
        if((changed&&now_ms-last_render_ms>=55)||
           now_ms-last_render_ms>=1000) {
            render();
            if(flush_fb()<0){perror("fb write");break;}
            last_render_ms=now_ms;
        }
    }
    if(backup) {
        size_t off=0;
        while(off<(size_t)nbytes){
            ssize_t n=pwrite(fbfd,backup+off,(size_t)nbytes-off,(off_t)off);
            if(n<=0)break;
            off+=(size_t)n;
        }
    }
    close(evfd);close(fbfd);free(backup);free(pixels);
    fprintf(stdout,
       "CYBERDECK_GUI_END: events=%d frames=%d targets=%d%d%d%d max_contacts=%d draws=%lu\n",
       events_count,frame_count,hit[0],hit[1],hit[2],hit[3],max_active,draw_num);
    return 0;
}