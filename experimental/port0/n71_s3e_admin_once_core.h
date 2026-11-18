/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_ADMIN_ONCE_CORE_H
#define N71_S3E_ADMIN_ONCE_CORE_H
struct n71_admin_once_ops {
    int (*qualified)(void *);
    int (*master)(void *,int);
    void (*cc)(void *,unsigned int);
    unsigned int (*csts)(void *);
    void (*delay_ms)(void *,unsigned int);
    int (*identify)(void *);
};
struct n71_admin_once_result {
    unsigned int master_seen,started,ready,stopped,master_off;
    unsigned int enable_polls,shutdown_polls,disable_polls,last_csts;
    unsigned int shutdown_attempted,shutdown_csts,disable_csts;
    int inner_rc,shutdown_rc,disable_rc;
};
static int n71_admin_wait(const struct n71_admin_once_ops *o,void *ctx,
        unsigned int mask,unsigned int want,unsigned int bound,int fatal,
        unsigned int *polls,unsigned int *last)
{
    unsigned int i;
    *polls=0;
    for (i=0;i<bound;i++) {
        *last=o->csts(ctx);(*polls)++;
        if (*last==~0U || (fatal && (*last&2))) return -2;
        if ((*last&mask)==want) return 0;
        o->delay_ms(ctx,1);
    }
    return -1;
}
/* No BME until owned HMB/queues/FlatDMA are qualified.
 * Never release their memory unless CC/CSTS and commands are back to
 * their qualified disabled baseline. -3 requires caller quarantine.
 */
static int n71_admin_once_core(const struct n71_admin_once_ops *o,void *ctx,
                              struct n71_admin_once_result *r)
{
    int rc,shutdown_ok=1,disable_ok;
    r->master_seen=r->started=r->ready=r->stopped=r->master_off=0;
    r->enable_polls=r->shutdown_polls=r->disable_polls=r->last_csts=0;
    r->shutdown_attempted=r->shutdown_csts=r->disable_csts=0;
    r->inner_rc=-1;r->shutdown_rc=r->disable_rc=0;
    if (!o->qualified(ctx)) return -1;
    rc=o->master(ctx,1);
    if (rc) {
        r->master_off=!o->master(ctx,0);
        return r->master_off && o->qualified(ctx) ? -1 : -3;
    }
    r->master_seen=1;
    o->cc(ctx,0x00460001U);r->started=1;
    o->delay_ms(ctx,100);
    rc=n71_admin_wait(o,ctx,1,1,5000,1,&r->enable_polls,&r->last_csts);
    if (!rc) {
        r->ready=1;
        rc=o->identify(ctx);
    }
    r->inner_rc=rc;
    r->last_csts=o->csts(ctx);
    if ((r->last_csts&3)==1) {
        r->shutdown_attempted=1;
        o->cc(ctx,0x00464001U);
        r->shutdown_rc=n71_admin_wait(o,ctx,12,8,2000,1,
            &r->shutdown_polls,&r->last_csts);
        r->shutdown_csts=r->last_csts;
        shutdown_ok=!r->shutdown_rc;
    }
    o->cc(ctx,0);
    r->disable_rc=n71_admin_wait(o,ctx,1,0,2000,0,
        &r->disable_polls,&r->last_csts);
    r->disable_csts=r->last_csts;
    disable_ok=!r->disable_rc;
    r->master_off=!o->master(ctx,0);
    r->stopped=shutdown_ok && disable_ok && r->master_off && o->qualified(ctx);
    return r->stopped ? rc : -3;
}
#endif
