// SPDX-License-Identifier: GPL-2.0-only
/* Read only the kernel's registered power-off capability. No handler call,
 * shutdown, storage I/O, device access or registration is performed here. */
#include <linux/module.h>
#include <linux/init.h>
#include <linux/reboot.h>
static bool armed;
module_param(armed, bool, 0400);
static int __init n71_poweroff_capability_init(void)
{
 if (!armed) { pr_info("n71-poweroff-capability: INERT\n"); return 0; }
 pr_info("n71-poweroff-capability: RESULT handler_registered=%u CPU_only=1 shutdown_invoked=0 hardware_access=0\n",
         (unsigned int)kernel_can_power_off());
 return 0;
}
static void __exit n71_poweroff_capability_exit(void) { }
module_init(n71_poweroff_capability_init);
module_exit(n71_poweroff_capability_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 CPU-only query of registered kernel power-off support");
