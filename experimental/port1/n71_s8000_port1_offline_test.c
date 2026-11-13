/* Offline native test harness for the exact source linked into ARM64 Kbuild.
 * Uses only in-memory synthetic 32-bit values. Never accesses hardware. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "pcie-apple-s8000-port1-offline.c"

static void test_plan(void)
{
    const struct {unsigned int offset, mask, value; bool write;} expected[6] = {
        {0x1a4,1,0,true},
        {0x194,1,1,true},
        {0x1ac,1,0,false},
        {0x180,1<<8,0,true},
        {0x180,1<<20,1<<20,true},
        {0x1a4,1,1,true},
    };
    struct n71_s8000_port1_rmw op={0};
    unsigned int i;
    for (i=0; i<6; ++i) {
        assert(!n71_s8000_port1_plan_step(i,true,&op));
        assert(op.offset==expected[i].offset);
        assert(op.mask==expected[i].mask);
        assert(op.value==expected[i].value);
        assert(op.write==expected[i].write);
    }
    assert(n71_s8000_port1_plan_step(N71_P1_ROOT_2000_OPTIONAL,
                                    false,&op)==-EOPNOTSUPP);
    assert(n71_s8000_port1_plan_step((enum n71_s8000_port1_step)6,
                                    true,&op)==-EINVAL);
    assert(n71_s8000_port1_plan_step(N71_P1_ROOT_1968_ASSERT,
                                    true,NULL)==-EINVAL);
}

static void test_shadow(void)
{
    struct n71_s8000_port1_rmw op={0};
    unsigned int v,after,seed=0x9d5e8d7bU;
    unsigned int i;
    for (i=0; i<200000; ++i) {
        v=(seed=seed*1664525U + 1013904223U);
        assert(!n71_s8000_port1_plan_step(i%6,true,&op));
        if (!op.write) {
            assert(n71_s8000_port1_shadow_apply(v,&op,&after)==-EINVAL);
            continue;
        }
        assert(!n71_s8000_port1_shadow_apply(v,&op,&after));
        assert((after&~op.mask)==(v&~op.mask));
        assert((after&op.mask)==op.value);
    }
    assert(!n71_s8000_port1_plan_step(N71_P1_ROOT_1968_ASSERT,true,&op));
    op.offset=0x2c; /* Global/shared status is READ ONLY. */
    assert(n71_s8000_port1_shadow_apply(1,&op,&after)==-EOPNOTSUPP);
    op.offset=0x124; /* Different root bank, unqualified port identity. */
    assert(n71_s8000_port1_shadow_apply(1,&op,&after)==-EOPNOTSUPP);
    op.offset=0x1a4;
    op.mask=0xffffffffU; /* Every full-register write is forbidden. */
    op.value=0;
    assert(n71_s8000_port1_shadow_apply(1,&op,&after)==-EOPNOTSUPP);
    op.offset=0x180;
    op.mask=(1U<<8)|(1U<<20); /* Combining masks is forbidden. */
    op.value=(1U<<20);
    assert(n71_s8000_port1_shadow_apply(1,&op,&after)==-EOPNOTSUPP);
    op.offset=0x194;
    op.mask=1;
    op.value=0; /* Original start sequence sets bit0, never clears. */
    assert(n71_s8000_port1_shadow_apply(1,&op,&after)==-EOPNOTSUPP);
    op.offset=0x1a4;
    op.mask=1;
    op.value=2; /* Cannot write bits outside mask. */
    assert(n71_s8000_port1_shadow_apply(1,&op,&after)==-EINVAL);
    assert(n71_s8000_port1_shadow_apply(1,NULL,&after)==-EINVAL);
    assert(n71_s8000_port1_shadow_apply(1,&op,NULL)==-EINVAL);
}

static void test_timeout(void)
{
    unsigned int samples[1000]={0};
    unsigned int consumed=0;
    assert(N71_ROOT_POLL_INTERVAL_US==10);
    assert(N71_REFCLK_PERST_SOURCE_DELAY_US==100);
    assert(N71_P1_MAX_POLL_SAMPLES==1000);
    assert(n71_s8000_poll_observations(samples,1000,4,&consumed)==-ETIMEDOUT);
    assert(consumed==1000);
    samples[999]=1U<<4;
    assert(!n71_s8000_poll_observations(samples,1000,4,&consumed));
    assert(consumed==1000);
    samples[0]=1U<<4;
    assert(!n71_s8000_poll_observations(samples,1000,4,&consumed));
    assert(consumed==1);
    samples[0]=1;
    assert(!n71_s8000_poll_observations(samples,1000,0,&consumed));
    assert(consumed==1);
    assert(n71_s8000_poll_observations(samples,0,4,&consumed)==-EINVAL);
    assert(n71_s8000_poll_observations(samples,1001,4,&consumed)==-EINVAL);
    assert(n71_s8000_poll_observations(samples,1000,5,&consumed)==-EINVAL);
    assert(n71_s8000_poll_observations(NULL,1,4,&consumed)==-EINVAL);
    assert(n71_s8000_poll_observations(samples,1,4,NULL)==-EINVAL);
}
int main(void)
{
    test_plan();
    test_shadow();
    test_timeout();
    assert(n71_s8000_port1_host_enable()==-EOPNOTSUPP);
    puts("N71_S8000_PORT1_OFFLINE_SHADOW_RMW_200000_VECTORS_PASS");
    puts("N71_S8000_PORT1_FINITE_POLL_FAIL_CLOSED_PASS");
    puts("N71_S8000_PORT1_PHYSICAL_MMIO_ACTIVATION_REFUSED_PASS");
    return 0;
}
