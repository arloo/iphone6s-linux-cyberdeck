// SPDX-License-Identifier: MIT
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
#include "../fb-cyberdeck/font_data.h"
#include <pty.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <glob.h>
#include <linux/kd.h>

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
static int events_count, frame_count;
static int active_slot=0;
static struct point { int id,x,y,pending,has_x,has_y; } touches[MAX_TOUCH];
static unsigned long draw_num;

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

#define ROWS 24
#define COLS 48
static char terminal[ROWS][COLS+1];
static int cursor_x,cursor_y,escape_state,page,shifted,symbol_mode,input_dropped,dirty=1,master=-1;
static pid_t child=-1;
static int ttyfd=-1,saved_kd_mode=KD_TEXT;
static char backlight[256];
static struct telemetry {int battery,temp,current,brightness,maxbrightness,mem_kib,cpu_percent,wlan,bt;char charge[32],governor[32];} stats;
static unsigned long long prev_total,prev_idle;
static long long milliseconds(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (long long)t.tv_sec*1000+t.tv_nsec/1000000;}
static int read_text(const char *path,char *value,size_t size){
 FILE *f=fopen(path,"r");if(!f){value[0]=0;return -1;}
 if(!fgets(value,(int)size,f)){fclose(f);value[0]=0;return -1;}
 fclose(f);value[strcspn(value,"\r\n")]=0;return 0;
}
static int read_integer(const char *path,int fallback){char b[64];return read_text(path,b,sizeof(b))?fallback:atoi(b);}
static void sample(void){
 struct telemetry t;memset(&t,0,sizeof(t));
 t.battery=read_integer("/sys/class/power_supply/bq27540-0/capacity",-1);
 t.temp=read_integer("/sys/class/power_supply/bq27540-0/temp",-1);
 t.current=read_integer("/sys/class/power_supply/bq27540-0/current_now",0)/1000;
 read_text("/sys/class/power_supply/bq27540-0/status",t.charge,sizeof(t.charge));
 read_text("/sys/devices/system/cpu/cpufreq/policy0/scaling_governor",t.governor,sizeof(t.governor));
 t.brightness=read_integer(backlight,-1);char path[300];snprintf(path,sizeof(path),"%s",backlight);
 char *end=strrchr(path,'/');if(end){strcpy(end+1,"max_brightness");t.maxbrightness=read_integer(path,0);}
 t.wlan=read_integer("/sys/class/net/wlan0/carrier",0)==1;
 t.bt=access("/sys/class/bluetooth/hci0",F_OK)==0;
 FILE *f=fopen("/proc/meminfo","r");if(f){char linebuf[256];while(fgets(linebuf,sizeof(linebuf),f))if(sscanf(linebuf,"MemAvailable: %d",&t.mem_kib)==1)break;fclose(f);}
 f=fopen("/proc/stat","r");if(f){unsigned long long a[8]={0};if(fscanf(f,"cpu %llu %llu %llu %llu %llu %llu %llu %llu",a,a+1,a+2,a+3,a+4,a+5,a+6,a+7)==8){
 unsigned long long total=0;for(int i=0;i<8;i++)total+=a[i];unsigned long long idle=a[3]+a[4];
 if(total>prev_total&&prev_total){t.cpu_percent=(int)(100*(total-prev_total-(idle-prev_idle))/(total-prev_total));}
 prev_total=total;prev_idle=idle;}fclose(f);}
 if(memcmp(&stats,&t,sizeof(t))){stats=t;dirty=1;}
}
static void new_line(void){cursor_x=0;if(++cursor_y>=ROWS){memmove(terminal[0],terminal[1],(ROWS-1)*(COLS+1));memset(terminal[ROWS-1],' ',COLS);terminal[ROWS-1][COLS]=0;cursor_y=ROWS-1;}}
static void terminal_bytes(const char *data,size_t n){
 for(size_t i=0;i<n;i++){unsigned char c=(unsigned char)data[i];
 if(escape_state==3){if(c==7)escape_state=0;else if(c==27)escape_state=4;continue;}
 if(escape_state==4){escape_state=c=='\\'?0:3;continue;}
 if(escape_state==1){escape_state=c=='['?2:(c==']'?3:0);continue;}
 if(escape_state==2){if(c>=0x40&&c<=0x7e)escape_state=0;continue;}
 if(c==27){escape_state=1;continue;}if(c=='\r'){cursor_x=0;continue;}
 if(c=='\n'){new_line();continue;}if(c==8||c==127){if(cursor_x)cursor_x--;continue;}
 if(c=='\t'){do{terminal[cursor_y][cursor_x++]=' ';if(cursor_x==COLS){new_line();break;}}while(cursor_x%8);continue;}
 if(c>=32&&c<=126){terminal[cursor_y][cursor_x++]=(char)c;if(cursor_x==COLS)new_line();}
 }dirty=1;
}
static int start_shell(void){
 struct winsize win={.ws_row=ROWS,.ws_col=COLS};child=forkpty(&master,NULL,NULL,&win);
 if(child==0){setenv("TERM","dumb",1);setenv("PS1","deck# ",1);execl("/bin/sh","sh","-i",(char *)NULL);_exit(127);}
 if(child<0)return -1;
 fcntl(master,F_SETFL,fcntl(master,F_GETFL)|O_NONBLOCK);fcntl(master,F_SETFD,FD_CLOEXEC);return 0;
}
static void key_send(const char *s){if(master>=0){ssize_t n=write(master,s,strlen(s));if(n<0&&errno!=EAGAIN)running=0;}}
static void button(int x,int y,int w,const char *text,int selected){rect(x,y,w,60,selected?0x183B44:0x10212C);outline(x,y,w,60,selected?COL_CYAN:COL_GRID);label(x+12,y+18,text,1,selected?COL_CYAN:COL_WHITE);}
static void card(int x,int y,const char *title,const char *value,const char *detail){rect(x,y,334,170,0x10212C);outline(x,y,334,170,COL_GRID);label(x+18,y+17,title,1,COL_SOFT);label(x+18,y+61,value,2,COL_CYAN);label(x+18,y+114,detail,1,COL_WHITE);}
static const char *letters[]={"1234567890","qwertyuiop","asdfghjkl","zxcvbnm/."};
static const char *symbols[]={"!@#$%^&*()","[]{}<>_=+-",";:\'\"`~|?","\\/.,:="};
static void render_shell(void){
 rect(0,0,W,H,COL_BG);rect(0,0,W,7,COL_PINK);rect(0,7,W,3,COL_CYAN);
 label(28,28,"CYBERDECK / A9",2,COL_CYAN);label(30,88,"N71  //  NATIVE LINUX  //  0.2",1,COL_SOFT);
 const char *tabs[]={"HOME","TERMINAL","SYSTEM","TOOLS"};for(int i=0;i<4;i++)button(28+i*178,130,160,tabs[i],page==i);
 char a[100],b[100];
 if(page==0){
  label(30,218,"LOCAL OPERATIONS",1,COL_WHITE);ring(694,230,16,COL_CYAN);
  snprintf(a,sizeof(a),"%d%% %.1fC",stats.battery,stats.temp/10.0);snprintf(b,sizeof(b),"%s %+d mA",stats.charge,stats.current);card(28,270,"BATTERY",a,b);
  card(388,270,"WIFI / NATIVE",stats.wlan?"LINK UP":"LINK DOWN","BCM4350C5 / PCIe");
  card(28,466,"BLUETOOTH",stats.bt?"PRESENT":"ABSENT","HID TEST PENDING");
  snprintf(a,sizeof(a),"CPU %d%%",stats.cpu_percent);snprintf(b,sizeof(b),"RAM AVAIL %d MiB",stats.mem_kib/1024);card(388,466,"SYSTEM / ARM64",a,b);
  label(30,686,"TOUCH FIRST. LOCAL SHELL.",1,COL_CYAN);
  label(30,736,"USB RECOVERY REMAINS AVAILABLE",1,COL_SOFT);
  label(30,786,"KALI TOOLSET: NOT INSTALLED",1,COL_AMBER);
  label(30,836,"CHARGING USES A FINITE LEASE",1,COL_SOFT);
  button(30,950,690,"OPEN LOCAL TERMINAL",1);
  button(30,1030,690,"SYSTEM / DISPLAY CONTROLS",0);
 }else if(page==1){
  label(30,210,"LOCAL SHELL / ASCII / TERM=dumb",1,COL_SOFT);
  for(int y=0;y<ROWS;y++)label(30,258+y*24,terminal[y],1,COL_WHITE);
  if(cursor_x<COLS)rect(30+cursor_x*14,258+cursor_y*24+22,13,2,COL_CYAN);
  const char **rows=symbol_mode?symbols:letters;
  for(int row=0;row<4;row++){int count=(int)strlen(rows[row]);int off=(W-count*70)/2;for(int col=0;col<count;col++){
   char k[2]={rows[row][col],0};if(shifted&&k[0]>='a'&&k[0]<='z')k[0]-=32;button(off+col*70,875+row*65,64,k,0);}}
  const char *keys[]={"SHIFT","SPACE",symbol_mode?"ABC":"SYM","BACK","ENTER"};for(int i=0;i<5;i++)button(25+i*142,1140,134,keys[i],i==0&&shifted);
  button(25,1220,220,"CTRL-C",0);button(265,1220,220,"TAB",0);button(505,1220,220,"CLEAR VIEW",0);
 }else if(page==2){
  label(30,240,"POWER / PERFORMANCE",1,COL_CYAN);
  snprintf(a,sizeof(a),"CPU GOVERNOR: %s",stats.governor);label(30,302,a,1,COL_WHITE);
  snprintf(a,sizeof(a),"DISPLAY: %d / %d",stats.brightness,stats.maxbrightness);label(30,360,a,1,COL_WHITE);
  button(30,430,210,"DIM 35%",0);button(270,430,210,"BALANCED",1);button(510,430,210,"BRIGHT 74%",0);
  label(30,540,"WIFI POWER SAVE: MANAGED BY DRIVER",1,COL_SOFT);
  label(30,600,"NO CPU OVERCLOCK / NO RADIO RESET",1,COL_SOFT);
  label(30,660,"CHARGER LEASE: SUPERVISED ONLY",1,COL_AMBER);
  label(30,720,"BLUETOOTH PRESENCE IS NOT HID PROOF",1,COL_SOFT);
  label(30,800,"EXIT RESTORES THE PREVIOUS FRAMEBUFFER",1,COL_WHITE);
  button(30,950,690,"EXIT TO PREVIOUS DISPLAY",0);
 }else{
  label(30,240,"TOOLS / INTEGRATION STATUS",1,COL_CYAN);
  label(30,315,"AVAILABLE: BUSYBOX LOCAL SHELL",1,COL_WHITE);
  label(30,375,"AVAILABLE: WIFI / BLUEZ RUNTIME",1,COL_WHITE);
  label(30,465,"KALI ARM64 PACKAGES: PLANNED",1,COL_AMBER);
  label(30,525,"NMAP / TCPDUMP: NOT INSTALLED",1,COL_SOFT);
  label(30,585,"MONITOR / INJECTION: NOT QUALIFIED",1,COL_SOFT);
  label(30,675,"NO PLACEHOLDER TOOL RUN BUTTONS",1,COL_SOFT);
  button(30,950,690,"OPEN WORKING LOCAL SHELL",1);
 }
 draw_num++;dirty=0;
}
static void set_display(int percent){if(!backlight[0]||stats.maxbrightness<=0)return;FILE *f=fopen(backlight,"w");if(f){fprintf(f,"%d\n",stats.maxbrightness*percent/100);fclose(f);}sample();}
static void tap(int x,int y){
 if(y>=130&&y<=190){for(int i=0;i<4;i++)if(x>=28+i*178&&x<=188+i*178){page=i;dirty=1;}return;}
 if(page==0){if(y>=950&&y<=1010)page=1;else if(y>=1030&&y<=1090)page=2;dirty=1;}
 else if(page==2){if(y>=430&&y<=490){if(x>=30&&x<=240)set_display(35);else if(x>=270&&x<=480)set_display(50);else if(x>=510&&x<=720)set_display(74);}if(y>=950&&y<=1010)running=0;}
 else if(page==3){if(y>=950&&y<=1010){page=1;dirty=1;}}
 else if(page==1){
  const char **rows=symbol_mode?symbols:letters;
  for(int row=0;row<4;row++)if(y>=875+row*65&&y<=935+row*65){int count=(int)strlen(rows[row]),off=(W-count*70)/2;int col=(x-off)/70;
   if(x>=off&&col<count&&(x-off)%70<64){char s[2]={rows[row][col],0};if(shifted&&s[0]>='a'&&s[0]<='z')s[0]-=32;key_send(s);}return;}
  if(y>=1140&&y<=1200){int k=(x-25)/142;if(x<25||k>=5||(x-25)%142>=134)return;
   if(k==0){shifted=!shifted;dirty=1;}else if(k==1)key_send(" ");else if(k==2){symbol_mode=!symbol_mode;dirty=1;}else if(k==3)key_send("\177");else key_send("\r");}
  if(y>=1220&&y<=1280){if(x>=25&&x<=245)key_send("\003");else if(x>=265&&x<=485)key_send("\t");else if(x>=505&&x<=725){for(int i=0;i<ROWS;i++){memset(terminal[i],' ',COLS);terminal[i][COLS]=0;}cursor_x=cursor_y=0;dirty=1;}}
 }
}
static void input_event(const struct input_event *e){
 events_count++;
 if(input_dropped){if(e->type==EV_SYN&&e->code==SYN_REPORT)input_dropped=0;return;}
 if(e->type==EV_SYN&&e->code==SYN_DROPPED){for(int i=0;i<MAX_TOUCH;i++){touches[i].id=-1;touches[i].pending=0;}input_dropped=1;active_slot=0;return;}
 if(e->type==EV_ABS){
  if(e->code==ABS_MT_SLOT){active_slot=(e->value>=0&&e->value<MAX_TOUCH)?e->value:-1;return;}if(active_slot<0)return;
  struct point *t=&touches[active_slot];
  if(e->code==ABS_MT_TRACKING_ID){t->id=e->value;t->pending=e->value>=0;t->has_x=t->has_y=0;}
  else if(e->code==ABS_MT_POSITION_X){t->x=e->value;t->has_x=1;}
  else if(e->code==ABS_MT_POSITION_Y){t->y=e->value;t->has_y=1;}
 }else if(e->type==EV_SYN&&e->code==SYN_REPORT){frame_count++;for(int i=0;i<MAX_TOUCH;i++){struct point *t=&touches[i];if(t->id>=0&&t->pending&&t->has_x&&t->has_y){tap(t->x,t->y);t->pending=0;}}}
}
static int flush(void){size_t off=0;while(off<(size_t)nbytes){ssize_t n=pwrite(fbfd,pixels+off,(size_t)nbytes-off,(off_t)off);if(n<0&&errno==EINTR)continue;if(n<=0)return -1;off+=(size_t)n;}return 0;}
static int discover_touch(void){
 for(int i=0;i<32;i++){char path[64],name[128]={0};snprintf(path,sizeof(path),"/dev/input/event%d",i);int fd=open(path,O_RDONLY|O_NONBLOCK|O_CLOEXEC);if(fd<0)continue;
 if(ioctl(fd,EVIOCGNAME(sizeof(name)),name)>=0&&strstr(name,"iPhone 6s Touchscreen")){struct input_absinfo x,y;if(ioctl(fd,EVIOCGABS(ABS_MT_POSITION_X),&x)==0&&ioctl(fd,EVIOCGABS(ABS_MT_POSITION_Y),&y)==0&&x.minimum==0&&y.minimum==0&&x.maximum==749&&y.maximum==1333)return fd;}
 close(fd);}return -1;
}
int main(int argc,char **argv){
 signal(SIGTERM,on_signal);signal(SIGINT,on_signal);signal(SIGPIPE,SIG_IGN);umask(077);
 W=750;H=1334;stride=W*4;nbytes=stride*H;
 for(int i=0;i<ROWS;i++){memset(terminal[i],' ',COLS);terminal[i][COLS]=0;}for(int i=0;i<MAX_TOUCH;i++)touches[i].id=-1;
 if(argc==3&&strcmp(argv[1],"--preview")==0){
  vinfo.red=(struct fb_bitfield){.offset=16,.length=8};vinfo.green=(struct fb_bitfield){.offset=8,.length=8};vinfo.blue=(struct fb_bitfield){.length=8};pixels=calloc(1,(size_t)nbytes);if(!pixels)return 1;
  stats=(struct telemetry){.battery=39,.temp=341,.current=30,.brightness=1023,.maxbrightness=2047,.mem_kib=1700000,.cpu_percent=1,.wlan=1,.bt=1};strcpy(stats.charge,"Charging");strcpy(stats.governor,"schedutil");
  const char *view=getenv("N71_PREVIEW_PAGE");if(view)page=atoi(view);terminal_bytes("deck# echo ready\r\nready\r\ndeck# ",strlen("deck# echo ready\r\nready\r\ndeck# "));render_shell();
  FILE *f=fopen(argv[2],"wb");if(!f)return 1;fprintf(f,"P6\n%d %d\n255\n",W,H);for(int i=0;i<W*H;i++){unsigned char *p=pixels+i*4;fputc(p[2],f);fputc(p[1],f);fputc(p[0],f);}fclose(f);free(pixels);return 0;
 }
 if(argc==2&&strcmp(argv[1],"--selftest")==0){
  if(start_shell())return 10;
  char initial[2048]={0};size_t have=0;long long ready_until=milliseconds()+2000;
  while(milliseconds()<ready_until&&have<sizeof(initial)-1){struct pollfd p={.fd=master,.events=POLLIN};poll(&p,1,100);ssize_t n=read(master,initial+have,sizeof(initial)-have-1);if(n>0){have+=(size_t)n;initial[have]=0;if(strstr(initial,"deck# "))break;}}
  page=0;tap(100,970);if(page!=1)return 11;
  const char *command="echo uiok";
  for(const char *ch=command;*ch;ch++){
   if(*ch==' '){tap(180,1160);continue;}
   int found=0;for(int row=0;row<4;row++){const char *at=strchr(letters[row],*ch);if(at){int col=(int)(at-letters[row]);int off=(750-(int)strlen(letters[row])*70)/2;tap(off+col*70+20,895+row*65);found=1;break;}}
   if(!found)return 12;
  }
  tap(620,1160);char output[4096]={0};size_t used=0;long long deadline=milliseconds()+5000;
  while(milliseconds()<deadline&&used<sizeof(output)-1){struct pollfd p={.fd=master,.events=POLLIN};poll(&p,1,100);ssize_t n=read(master,output+used,sizeof(output)-used-1);if(n>0){used+=(size_t)n;output[used]=0;if(strstr(output,"\r\nuiok\r\n")||strstr(output,"\nuiok\n"))break;}}
  int ok=strstr(output,"\r\nuiok\r\n")!=NULL||strstr(output,"\nuiok\n")!=NULL;
  if(!ok)fprintf(stderr,"Synthetic PTY selftest output: %s\n",output);
  key_send("exit\r");close(master);kill(-child,SIGHUP);waitpid(child,NULL,0);
  terminal_bytes("abc\rZ\n123\b4",12);if(terminal[0][0]!='Z'||terminal[1][2]!='4')return 14;
  puts(ok?"N71_UI_SELFTEST_PASS touch_key_dispatch=1 native_pty_shell=1 terminal_parser=1":"N71_UI_SELFTEST_FAIL");return ok?0:13;
 }
 int probe=argc==2&&strcmp(argv[1],"--probe")==0;
 if(argc!=1&&!probe){fputs("Usage: cyberdeck-shell [--preview PRIVATE_PPM]\n",stderr);return 2;}
 fbfd=open("/dev/fb0",O_RDWR|O_CLOEXEC);if(fbfd<0)return 2;
 if(ioctl(fbfd,FBIOGET_FSCREENINFO,&finfo)<0||ioctl(fbfd,FBIOGET_VSCREENINFO,&vinfo)<0)return 3;
 W=vinfo.xres;H=vinfo.yres;stride=finfo.line_length;
 if(W!=750||H!=1334||vinfo.bits_per_pixel!=32||vinfo.xoffset||vinfo.yoffset||stride<W*4||stride>W*4+4096)return 4;
 nbytes=stride*H;pixels=calloc(1,(size_t)nbytes);backup=malloc((size_t)nbytes);if(!pixels||!backup)return 5;
 if(pread(fbfd,backup,(size_t)nbytes,0)!=nbytes){fputs("Framebuffer backup required\n",stderr);return 6;}
 evfd=discover_touch();if(evfd<0){fputs("Qualified touchscreen unavailable\n",stderr);return 7;}
 glob_t paths;if(glob("/sys/class/backlight/*/brightness",0,NULL,&paths)==0){if(paths.gl_pathc==1)snprintf(backlight,sizeof(backlight),"%s",paths.gl_pathv[0]);globfree(&paths);}
 if(probe){puts("N71_UI_HARDWARE_PROBE_PASS framebuffer=750x1334 native_touch=1 backup_read=1");close(evfd);close(fbfd);free(backup);free(pixels);return 0;}
 if(start_shell()<0){return 8;}
 ttyfd=open("/dev/tty0",O_RDWR|O_CLOEXEC);
 if(ttyfd>=0&&ioctl(ttyfd,KDGETMODE,&saved_kd_mode)==0){
  if(ioctl(ttyfd,KDSETMODE,KD_GRAPHICS)<0){close(ttyfd);ttyfd=-1;}
 }else if(ttyfd>=0){close(ttyfd);ttyfd=-1;}
 sample();long long next_sample=milliseconds()+2000,last_draw=0;
 puts("N71_CYBERDECK_SHELL_STARTED framebuffer=750x1334 native_touch=1 local_pty=1");fflush(stdout);
 while(running){struct pollfd fds[2]={{.fd=evfd,.events=POLLIN},{.fd=master,.events=POLLIN}};int n=poll(fds,2,250);if(n<0&&errno!=EINTR)break;
  if(fds[0].revents&POLLIN){struct input_event e[64];ssize_t count=read(evfd,e,sizeof(e));if(count>0)for(size_t i=0;i<(size_t)count/sizeof(e[0]);i++)input_event(&e[i]);}
  if(fds[1].revents&POLLIN){char buf[2048];ssize_t count=read(master,buf,sizeof(buf));if(count>0)terminal_bytes(buf,(size_t)count);}
  if(fds[1].revents&(POLLHUP|POLLERR)){terminal_bytes("\r\n[shell ended]",15);close(master);master=-1;if(child>0)waitpid(child,NULL,WNOHANG);child=-1;}
  long long now=milliseconds();if(now>=next_sample){sample();next_sample=now+2000;}
  if(dirty&&now-last_draw>=100){render_shell();if(flush())break;last_draw=now;}
 }
 if(child>0){kill(-child,SIGHUP);for(int i=0;i<10;i++){if(waitpid(child,NULL,WNOHANG)==child){child=-1;break;}usleep(50000);}if(child>0){kill(-child,SIGTERM);waitpid(child,NULL,WNOHANG);}}
 if(backup){memcpy(pixels,backup,(size_t)nbytes);flush();}if(ttyfd>=0){ioctl(ttyfd,KDSETMODE,saved_kd_mode);close(ttyfd);}
 if(master>=0){close(master);}
 close(evfd);close(fbfd);free(backup);free(pixels);
 printf("N71_CYBERDECK_SHELL_STOPPED events=%d frames=%d draws=%lu\n",events_count,frame_count,draw_num);return 0;
}
