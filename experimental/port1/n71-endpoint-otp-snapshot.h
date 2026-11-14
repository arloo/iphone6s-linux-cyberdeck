/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_ENDPOINT_OTP_SNAPSHOT_H
#define N71_ENDPOINT_OTP_SNAPSHOT_H
#define N71_OTP_MAX_BYTES 832
struct n71_otp_ops {int (*ready)(void *);unsigned int (*read)(void *,unsigned int);};
struct n71_otp_result {unsigned int capabilities,erom,bytes,reads;};
/* Read the4350 ChipCommon OTP shadow only, using upstream40nm size encoding.
 * OTP is private board/device data: never log or publish its raw contents.
 */
static int n71_endpoint_otp_snapshot(const struct n71_otp_ops *o,void *ctx,unsigned char *data,struct n71_otp_result *r)
{
 unsigned int enc,i,w,n;
 r->bytes=r->reads=r->capabilities=r->erom=0;
 for(i=0;i<N71_OTP_MAX_BYTES;i++)data[i]=0;
 if(!o->ready(ctx))return -1;
 r->capabilities=o->read(ctx,4);r->reads++;
 if(!o->ready(ctx))return -1;
 r->erom=o->read(ctx,0xfc);r->reads++;
 enc=(r->capabilities&0x00380000U)>>19;
 if(!enc)return -2;
 n=(enc+1)*128-192;
 if(n>N71_OTP_MAX_BYTES||(n&3))return -2;
 for(i=0;i<n;i+=4) {
  if(!o->ready(ctx))return -1;
  w=o->read(ctx,0x8c0+i);r->reads++;
  data[i]=w;data[i+1]=w>>8;data[i+2]=w>>16;data[i+3]=w>>24;
 }
 if(!o->ready(ctx))return -1;
 r->bytes=n;return 0;
}
#endif
