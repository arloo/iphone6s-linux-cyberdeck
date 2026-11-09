/* CYBERDECK A9 -- static ARM64 diagnostics / authorized network testing.
 * No kernel exploits, credential collection or persistent writes.
 * Usage: cyberprobe scan|banner|http|capture.
 * GNU/Linux only; compiled for Apple A9 aarch64.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/if_packet.h>
#include <linux/if_ether.h>
#include <net/if.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

static void usage(void) {
  puts("CYBERPROBE 0.1 // ARM64 local network diagnostics");
  puts("Use only on devices and networks you own or may test.");
  puts("  cyberprobe scan <IPv4> [comma-separated-ports | start-end]");
  puts("  cyberprobe banner <IPv4> <port>");
  puts("  cyberprobe http <IPv4> <port> [path]    (cleartext HTTP only)");
  puts("  cyberprobe capture <iface> <packets> <seconds> <file.pcap>");
  puts("e.g. cyberprobe scan 172.16.42.2 22,23,80,443");
}

static int parse_port(const char *s) {
  char *end=NULL; long n = strtol(s,&end,10);
  if(!s[0] || !end || *end || n<1 || n>65535) return -1;
  return (int)n;
}
static int connect_ipv4(const char *ip,int port,int ms) {
  struct sockaddr_in to={0}; to.sin_family=AF_INET;
  to.sin_port=htons((uint16_t)port);
  if(inet_pton(AF_INET,ip,&to.sin_addr)!=1) return -2;
  int fd=socket(AF_INET,SOCK_STREAM,0);
  if(fd<0) return -1;
  int fl=fcntl(fd,F_GETFL,0); fcntl(fd,F_SETFL,fl|O_NONBLOCK);
  int rc=connect(fd,(struct sockaddr*)&to,sizeof(to));
  if(rc<0 && errno!=EINPROGRESS) { close(fd); return -1; }
  if(rc<0) {
    fd_set wf; FD_ZERO(&wf); FD_SET(fd,&wf);
    struct timeval tv={ms/1000,(ms%1000)*1000};
    rc=select(fd+1,NULL,&wf,NULL,&tv);
    if(rc<=0) {close(fd);return -1;}
    int err=0;socklen_t len=sizeof(err);
    if(getsockopt(fd,SOL_SOCKET,SO_ERROR,&err,&len)<0 || err!=0) {close(fd);return -1;}
  }
  fcntl(fd,F_SETFL,fl);
  struct timeval tv={2,0};
  setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
  setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
  return fd;
}
static void print_read(int fd,int limit) {
  char b[512];int total=0;
  while(total<limit) {
    int take=limit-total; if(take>(int)sizeof(b))take=sizeof(b);
    ssize_t n=recv(fd,b,(size_t)take,0);
    if(n<=0)break;
    for(ssize_t i=0;i<n;i++) {
      unsigned char c=(unsigned char)b[i];
      if(c=='\n'||c=='\r'||c=='\t'||(c>=32&&c<127))putchar((char)c);
      else putchar('.');
    }
    total+=(int)n;
    if(memchr(b,'\n',(size_t)n))break;
  }
  putchar('\n');
}
static int scan(const char *ip,const char *list) {
  if(!list) list="21,22,23,25,53,80,110,139,443,445,8080,8443";
  char *copy=strdup(list);
  if(!copy)return 1;
  int num=0,open=0;
  printf("CYBERPROBE TCP scan target=%s ports=%s\n",ip,list);
  char *save=NULL;
  for(char *seg=strtok_r(copy,",",&save);seg;seg=strtok_r(NULL,",",&save)) {
    char *sep=strchr(seg,'-');
    int from,to;
    if(sep) { *sep=0; from=parse_port(seg); to=parse_port(sep+1); }
    else { from=to=parse_port(seg); }
    if(from<1||to<from||to>65535) {fprintf(stderr,"Invalid port: %s\n",seg);free(copy);return 2;}
    if(num+(to-from+1)>512) {fputs("Port list exceeds 512 entries\n",stderr);free(copy);return 2;}
    for(int p=from;p<=to;p++) {
      int fd=connect_ipv4(ip,p,350);
      if(fd==-2) {fputs("Use a numeric IPv4 address (DNS via nslookup)\n",stderr);free(copy);return 2;}
      num++;
      if(fd>=0) {printf("OPEN %-5d/tcp\n",p);open++;close(fd);}
    }
  }
  printf("Done: %d ports tested; %d open (TCP connect method)\n",num,open);
  free(copy);return 0;
}
static int banner_http(int argc,char**argv,int http) {
  if(argc<(http?4:4)) {usage();return 2;}
  int port=parse_port(argv[3]); if(port<1)return 2;
  int fd=connect_ipv4(argv[2],port,1500);
  if(fd<0){fprintf(stderr,"Unable to connect %s:%d\n",argv[2],port);return 1;}
  printf("TCP_CONNECTED %s:%d\n",argv[2],port);
  if(http) {
    const char *path=argc>4?argv[4]:"/";
    if(path[0]!='/' || strlen(path)>200) {fputs("path must start / and <=200 bytes\n",stderr);close(fd);return 2;}
    char req[512];
    int n=snprintf(req,sizeof(req),"HEAD %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: Cyberdeck-A9/0.1\r\nConnection: close\r\n\r\n",path,argv[2]);
    if(n>0 && n<(int)sizeof(req))send(fd,req,(size_t)n,MSG_NOSIGNAL);
  }
  print_read(fd,http?2048:512);
  close(fd);return 0;
}
/* pcap classic format, capture only on interface chosen by operator. */
struct pcap_file {uint32_t magic;uint16_t major,minor;int32_t tz;uint32_t sigfigs,snaplen,network;};
struct pcap_packet {uint32_t sec,usec,incl,orig;};
static int capture(const char *iface,const char *count_s,const char *secs_s,const char *out) {
  int max=atoi(count_s),seconds=atoi(secs_s);
  if(max<1||max>1000||seconds<1||seconds>60||strncmp(out,"/tmp/",5)!=0) {
    fputs("Limits: 1-1000 packets, 1-60 seconds, output under /tmp only\n",stderr);
    return 2;
  }
  unsigned idx=if_nametoindex(iface);
  if(!idx){perror("if_nametoindex");return 1;}
  int fd=socket(AF_PACKET,SOCK_RAW,htons(ETH_P_ALL));
  if(fd<0){perror("packet socket");return 1;}
  struct sockaddr_ll s={0};s.sll_family=AF_PACKET;s.sll_protocol=htons(ETH_P_ALL);s.sll_ifindex=(int)idx;
  if(bind(fd,(struct sockaddr*)&s,sizeof(s))<0){perror("bind");close(fd);return 1;}
  FILE*f=fopen(out,"wb");if(!f){perror("fopen");close(fd);return 1;}
  struct pcap_file h={0xa1b2c3d4,2,4,0,0,65535,1};fwrite(&h,sizeof(h),1,f);
  printf("Capture interface=%s max_packets=%d time_limit=%ds -> %s\n",iface,max,seconds,out);
  fflush(stdout);
  time_t deadline=time(NULL)+seconds;int captured=0;
  while(captured<max && time(NULL)<deadline) {
    fd_set rs;FD_ZERO(&rs);FD_SET(fd,&rs);
    struct timeval tv={0,250000};
    if(select(fd+1,&rs,NULL,NULL,&tv)<=0)continue;
    unsigned char b[4096];ssize_t len=recv(fd,b,sizeof(b),0);
    if(len<=0)continue;
    struct timeval now;gettimeofday(&now,NULL);
    struct pcap_packet rec={(uint32_t)now.tv_sec,(uint32_t)now.tv_usec,(uint32_t)len,(uint32_t)len};
    fwrite(&rec,sizeof(rec),1,f);
    fwrite(b,1,(size_t)len,f);
    captured++;
  }
  fclose(f);close(fd);
  printf("Captured %d frames, RAM-only file %s\n",captured,out);
  return 0;
}
int main(int argc,char**argv) {
  if(argc<2){usage();return 0;}
  if(!strcmp(argv[1],"scan") && argc>=3) return scan(argv[2],argc>3?argv[3]:NULL);
  if(!strcmp(argv[1],"banner"))return banner_http(argc,argv,0);
  if(!strcmp(argv[1],"http"))return banner_http(argc,argv,1);
  if(!strcmp(argv[1],"capture") && argc==6)return capture(argv[2],argv[3],argv[4],argv[5]);
  usage();return 2;
}
