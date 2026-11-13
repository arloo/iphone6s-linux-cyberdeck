"""Compile the real trial C with fake kernel I/O; never load a host module."""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHIM = r"""
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#define __init
#define __exit
#define BIT(n) (1u << (n))
#define module_param(...)
#define MODULE_LICENSE(...)
#define MODULE_DESCRIPTION(...)
#define module_init(...)
#define module_exit(...)
#define pr_info(...) do {} while (0)
#define pr_err(...) do {} while (0)
struct device_node {int unused;};
struct device {struct device_node *of_node;};
struct regmap {int unused;};
struct power_supply {int unused;};
struct work_struct {int unused;};
struct delayed_work {int unused;};
struct mutex {int unused;};
#define DEFINE_MUTEX(n) struct mutex n
#define INIT_DELAYED_WORK(w, fn) do {} while (0)
#define msecs_to_jiffies(ms) (ms)
#define time_after_eq(a,b) ((long)((a)-(b)) >= 0)
unsigned long jiffies;
int i2c_bus_type;
union power_supply_propval {int intval;};
enum {POWER_SUPPLY_PROP_CAPACITY, POWER_SUPPLY_PROP_TEMP, POWER_SUPPLY_PROP_VOLTAGE_NOW};
static unsigned int regs[256] = {[7]=0xb9, [9]=0, [16]=4};
static int cap=30, temperature=300, voltage=3700000, vbus=5000000;
static int device_refs, battery_refs, bus_gets, writes, input_writes, scheduled;
static bool board=true, adc_timeout, partial_input_fail, fail_restore, no_battery;
static struct device_node node;
static struct device dev = {&node};
static struct regmap map;
static struct power_supply psy;
int of_machine_is_compatible(const char *s) {return board;}
int of_device_is_compatible(struct device_node *n, const char *s) {return board;}
struct device *bus_find_device_by_name(int *bus, void *start, const char *s) {bus_gets++;device_refs++;return &dev;}
struct regmap *dev_get_regmap(struct device *d, void *x) {return &map;}
void put_device(struct device *d) {device_refs--;}
struct power_supply *power_supply_get_by_name(const char *s) {if(no_battery)return NULL;battery_refs++;return &psy;}
void power_supply_put(struct power_supply *p) {battery_refs--;}
int power_supply_get_property(struct power_supply *p, int prop, union power_supply_propval *v) {
    v->intval = prop==POWER_SUPPLY_PROP_CAPACITY ? cap : prop==POWER_SUPPLY_PROP_TEMP ? temperature : voltage;
    return 0;
}
int regmap_read(struct regmap *m, unsigned int r, unsigned int *v) {
    *v = r==0x12 ? vbus/25000 : regs[r];return 0;
}
int regmap_write(struct regmap *m, unsigned int r, unsigned int v) {
    assert(r==0x09 || r==0x11); /* A write to charge profile/control is a test failure. */
    writes++;
    if(r==0x09) {
        input_writes++;
        if(v==0 && fail_restore)return -EIO;
        regs[r]=v;
        if(v!=0 && partial_input_fail)return -EIO;
    } else regs[r]=adc_timeout?v:0;
    return 0;
}
#define regmap_read_poll_timeout(m,r,v,condition,delay,timeout) \
    (regmap_read(m,r,&(v)) ?: ((condition) ? 0 : -ETIMEDOUT))
int schedule_delayed_work(struct delayed_work *w, unsigned int ticks) {scheduled++;return 0;}
void cancel_delayed_work_sync(struct delayed_work *w) {}
void mutex_lock(struct mutex *m) {}
void mutex_unlock(struct mutex *m) {}
"""
HARNESS = r"""
int main(int argc, char **argv) {
    const char *case_name=argv[1]; int rc;
    if(!strcmp(case_name,"unarmed")) {
        assert(trial_init()==0 && bus_gets==0 && writes==0);trial_exit();return 0;
    }
    armed=true;
    if(!strcmp(case_name,"low-battery"))cap=9;
    if(!strcmp(case_name,"hot"))temperature=400;
    if(!strcmp(case_name,"cold"))temperature=99;
    if(!strcmp(case_name,"low-voltage"))voltage=3299999;
    if(!strcmp(case_name,"wrong-board"))board=false;
    if(!strcmp(case_name,"invalid-current"))input_ua=600000;
    if(!strcmp(case_name,"existing-input"))regs[9]=41;
    if(!strcmp(case_name,"disabled-input"))regs[16]=12;
    if(!strcmp(case_name,"adc-timeout"))adc_timeout=true;
    if(!strcmp(case_name,"low-vbus"))vbus=4300000;
    if(!strcmp(case_name,"no-battery"))no_battery=true;
    if(!strcmp(case_name,"partial-write"))partial_input_fail=true;
    if(!strcmp(case_name,"restore-failure")){partial_input_fail=true;fail_restore=true;}
    rc=trial_init();
    if(!strcmp(case_name,"low-battery") || !strcmp(case_name,"hot") || !strcmp(case_name,"cold") || !strcmp(case_name,"low-voltage")) {
        assert(rc==-ERANGE && writes==0 && device_refs==0 && battery_refs==0);return 0;
    }
    if(!strcmp(case_name,"wrong-board")){assert(rc==-ENODEV && bus_gets==0 && writes==0);return 0;}
    if(!strcmp(case_name,"invalid-current")){assert(rc==-EINVAL && bus_gets==0 && writes==0);return 0;}
    if(!strcmp(case_name,"existing-input") || !strcmp(case_name,"disabled-input")) {
        assert(rc==-EPERM && writes==0 && device_refs==0 && battery_refs==0);return 0;
    }
    if(!strcmp(case_name,"no-battery")){assert(rc==-ENODEV && writes==0 && device_refs==0 && battery_refs==0);return 0;}
    if(!strcmp(case_name,"adc-timeout") || !strcmp(case_name,"low-vbus")) {
        assert(rc<0 && input_writes==0 && device_refs==0 && battery_refs==0);return 0;
    }
    if(!strcmp(case_name,"partial-write")){assert(rc==-EIO && regs[9]==0 && device_refs==0 && battery_refs==0);return 0;}
    if(!strcmp(case_name,"restore-failure")) {
        assert(rc==0 && changed && device_refs==1 && battery_refs==1);
        fail_restore=false;partial_input_fail=false;trial_exit();
        assert(regs[9]==0 && device_refs==0 && battery_refs==0);return 0;
    }
    assert(rc==0 && regs[9]==21 && scheduled==1 && changed);
    if(!strcmp(case_name,"deadline"))jiffies=30000;
    else if(!strcmp(case_name,"droop")){jiffies=2000;vbus=4500000;}
    else if(!strcmp(case_name,"detach")){jiffies=2000;regs[7]&=~BIT(5);}
    else if(!strcmp(case_name,"hot-monitor")){jiffies=2000;temperature=400;}
    else if(!strcmp(case_name,"healthy-monitor"))jiffies=2000;
    else if(strcmp(case_name,"unload"))abort();
    if(strcmp(case_name,"unload"))monitor_work(NULL);
    if(!strcmp(case_name,"healthy-monitor"))assert(changed && regs[9]==21 && scheduled==2);
    else if(strcmp(case_name,"unload"))assert(!changed && regs[9]==0);
    trial_exit();assert(!changed && regs[9]==0 && device_refs==0 && battery_refs==0);
    return 0;
}
"""

class TrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('cc')
        if not cc:
            raise unittest.SkipTest('host C compiler required')
        cls.temp = tempfile.TemporaryDirectory(prefix='n71-sn2400-test-')
        cls.exe = pathlib.Path(cls.temp.name) / 'trial'
        source = (ROOT/'experimental/power/n71-sn2400-input-trial.c').read_text()
        source = re.sub(r'^#include <linux/[^>]+>\n', '', source, flags=re.M)
        cfile = pathlib.Path(cls.temp.name) / 'trial.c'
        cfile.write_text(SHIM + source + HARNESS)
        subprocess.run([cc,'-std=gnu11','-O2','-o',str(cls.exe),str(cfile)],check=True,capture_output=True,text=True)
    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
    def test_compiled_module_policy_and_cleanup(self):
        for case in ['unarmed','low-battery','hot','cold','low-voltage','wrong-board',
                     'invalid-current','existing-input','disabled-input','adc-timeout',
                     'low-vbus','no-battery','partial-write','restore-failure','deadline',
                     'droop','detach','hot-monitor','healthy-monitor','unload']:
            with self.subTest(case=case):
                subprocess.run([str(self.exe),case],check=True,capture_output=True,text=True)

if __name__ == '__main__':
    unittest.main()
