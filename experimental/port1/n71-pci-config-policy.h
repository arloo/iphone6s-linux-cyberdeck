/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_PCI_CONFIG_POLICY_H
#define N71_PCI_CONFIG_POLICY_H
/* Fixed WLAN root00:01.0 and endpoint01:00.0; never other root slots. */
static int n71_cfg_target(unsigned int bus,unsigned int devfn,unsigned int off,unsigned int size)
{
 if(size!=1&&size!=2&&size!=4)return -1;
 if(off>4096-size||(off&(size-1)))return -1;
 if(bus==0&&devfn==8)return 0;
 if(bus==1&&devfn==0)return 1;
 return -1;
}
static int n71_cfg_write_allowed(unsigned int target,unsigned int off,unsigned int size,unsigned int value,unsigned int command)
{
 if(target>1)return 0;
 if(off==4&&size==2)return value==0||value==2;
 if(size!=4||(off&3)||(command&7))return 0;
 if(target==0)return off==0x10||off==0x14;
 return off>=0x10&&off<=0x24;
}
#endif
