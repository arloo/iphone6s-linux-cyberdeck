// SPDX-License-Identifier: MIT
// Encrypted classic Bluetooth L2CAP echo test. Peer address stays in a private file.
#include <bluetooth/bluetooth.h>
#include <bluetooth/l2cap.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <stdlib.h>
#include <ctype.h>
int main(int argc,char **argv)
{
 char text[40];unsigned int part[6];struct sockaddr_l2 peer={.l2_family=AF_BLUETOOTH};
 struct bt_security security={.level=BT_SECURITY_MEDIUM};socklen_t len=sizeof(security);
 struct timeval timeout={.tv_sec=10};int fd;FILE *file;
 if(argc!=2){fputs("Usage: n71-bt-l2cap-echo PRIVATE_PEER_FILE\n",stderr);return 2;}
 file=fopen(argv[1],"r");if(!file){perror("peer file");return 1;}
 if(!fgets(text,sizeof(text),file)){fclose(file);return 2;}fclose(file);
 text[strcspn(text,"\r\n")]=0;
 if(strlen(text)!=17||sscanf(text,"%2x:%2x:%2x:%2x:%2x:%2x",&part[0],&part[1],&part[2],&part[3],&part[4],&part[5])!=6){fputs("Invalid private peer address\n",stderr);return 2;}
 for(int i=0;i<17;i++)if(i%3==2 ? text[i]!=':' : !isxdigit((unsigned char)text[i])){fputs("Invalid private peer address\n",stderr);return 2;}
 for(int i=0;i<6;i++)peer.l2_bdaddr.b[i]=(unsigned char)part[5-i];
 peer.l2_psm=htobs(0x1001);
 fd=socket(AF_BLUETOOTH,SOCK_SEQPACKET,BTPROTO_L2CAP);if(fd<0){perror("L2CAP socket");return 1;}
 if(setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout))||setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout))||setsockopt(fd,SOL_BLUETOOTH,BT_SECURITY,&security,sizeof(security))){perror("L2CAP options");close(fd);return 1;}
 if(connect(fd,(struct sockaddr *)&peer,sizeof(peer))){perror("Encrypted Bluetooth connect");close(fd);return 1;}
 if(getsockopt(fd,SOL_BLUETOOTH,BT_SECURITY,&security,&len)||security.level<BT_SECURITY_MEDIUM){fputs("Bluetooth encryption requirement not met\n",stderr);close(fd);return 1;}
 for(unsigned int i=0;i<256;i++){
  unsigned char sent[256],received[512];ssize_t n;
  for(unsigned int j=0;j<sizeof(sent);j++)sent[j]=(unsigned char)((i*29+j)^0xa9);
  sent[0]=(unsigned char)i;sent[1]=(unsigned char)(i>>8);
  if(send(fd,sent,sizeof(sent),0)!=(ssize_t)sizeof(sent)){perror("Bluetooth send");close(fd);return 1;}
  n=recv(fd,received,sizeof(received),0);
  if(n!=(ssize_t)sizeof(sent)||memcmp(sent,received,sizeof(sent))){fputs("Bluetooth echo mismatch or timeout\n",stderr);close(fd);return 1;}
 }
 printf("N71_BLUETOOTH_ENCRYPTED_ECHO_PASS bytes=65536 packets=256 security_level=%u\n",security.level);
 close(fd);return 0;
}
