/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_RO_PROBE_RUNTIME_H
#define N71_S3E_RO_PROBE_RUNTIME_H
/* An opt-in char probe, NOT a userspace block disk. The kernel client owns
 * all bios. Userspace can trigger four trusted reads and receives only the
 * validated CPU-only targets. Every target and this static state outlive
 * late/failed copy_to_user; neither can reference a freed bio or DMA page. */
static struct {
    struct completion request,reply,consumed;
    struct mutex read_lock;
    atomic_t opened;
    unsigned int next,requested,copied;
    int major,reply_rc;
    bool active,failed,removed;
} n71_ro_probe;
static int n71_ro_probe_open(struct inode *inode,struct file *file)
{
    (void)inode;
    if (!ans_ro_probe_once || !capable(CAP_SYS_RAWIO) ||
        (file->f_mode & FMODE_WRITE) || !READ_ONCE(n71_ro_probe.active) ||
        atomic_cmpxchg(&n71_ro_probe.opened,0,1)) return -EACCES;
    return 0;
}
static ssize_t n71_ro_probe_read(struct file *file,char __user *out,
                                size_t bytes,loff_t *offset)
{
    unsigned int step;
    int rc;
    (void)file;
    if (!capable(CAP_SYS_RAWIO)) return -EACCES;
    if (!mutex_trylock(&n71_ro_probe.read_lock)) return -EBUSY;
    step=n71_ro_probe.next;
    if (!n71_ro_probe_request_valid(READ_ONCE(n71_ro_probe.active),
            READ_ONCE(n71_ro_probe.failed),step,n71_series_base(),
            (unsigned long long)*offset,bytes)) {rc=-EINVAL;goto out;}
    reinit_completion(&n71_ro_probe.reply);
    WRITE_ONCE(n71_ro_probe.requested,step+1U);
    complete(&n71_ro_probe.request);
    if (!wait_for_completion_timeout(&n71_ro_probe.reply,
                                      msecs_to_jiffies(8000))) {
        rc=-ETIMEDOUT;goto fail;
    }
    rc=READ_ONCE(n71_ro_probe.reply_rc);
    if (rc || READ_ONCE(n71_ro_probe.failed)) {if (!rc) rc=-EIO;goto fail;}
    /* The only source is the retained, validated CPU target; no direct DMA
     * mapping, snapshots from another step, sector logging or hashing. */
    if (copy_to_user(out,n71_ro_block_memory.target[step],4096)) {
        rc=-EFAULT;goto fail;
    }
    n71_ro_probe.next=step+1U;
    WRITE_ONCE(n71_ro_probe.copied,step+1U);
    *offset+=4096;
    if (step==3U) complete(&n71_ro_probe.consumed);
    rc=4096;goto out;
fail:
    WRITE_ONCE(n71_ro_probe.failed,true);
    complete(&n71_ro_probe.request);
    complete(&n71_ro_probe.consumed);
out:
    mutex_unlock(&n71_ro_probe.read_lock);
    return rc;
}
static const struct file_operations n71_ro_probe_fops={
    .owner=THIS_MODULE,.open=n71_ro_probe_open,.read=n71_ro_probe_read,
    .llseek=default_llseek,
};
static void n71_ro_probe_prepare(void)
{
    if (!ans_ro_probe_once) return;
    init_completion(&n71_ro_probe.request);
    init_completion(&n71_ro_probe.reply);
    init_completion(&n71_ro_probe.consumed);
    mutex_init(&n71_ro_probe.read_lock);
    atomic_set(&n71_ro_probe.opened,0);
}
static int n71_ro_probe_start(void)
{
    int major;
    if (!ans_ro_probe_once) return 0;
    WRITE_ONCE(n71_ro_probe.active,true);
    major=register_chrdev(0,"n71nand_probe",&n71_ro_probe_fops);
    if (major<0) {WRITE_ONCE(n71_ro_probe.active,false);return major;}
    n71_ro_probe.major=major;
    pr_info("n71-s3e-p0: RO_PROBE_REGISTERED major=%d root_only=YES open_budget=1 pread_budget=4 payload_export=LOCAL_PRIVATE_USER_MEMORY_ONLY\n",major);
    return 0;
}
static int n71_ro_probe_wait(unsigned int step)
{
    if (!ans_ro_probe_once) return 0;
    if (!wait_for_completion_timeout(&n71_ro_probe.request,
                                      msecs_to_jiffies(8000))) return -ETIMEDOUT;
    if (kthread_should_stop() || READ_ONCE(n71_ro_probe.failed) ||
        READ_ONCE(n71_ro_block_memory.flow.closed) ||
        READ_ONCE(n71_ro_probe.requested)!=step+1U) return -ECANCELED;
    return 0;
}
static void n71_ro_probe_reply(int rc)
{
    if (!ans_ro_probe_once) return;
    WRITE_ONCE(n71_ro_probe.reply_rc,rc);
    complete(&n71_ro_probe.reply);
}
static int n71_ro_probe_finish(int rc)
{
    if (!ans_ro_probe_once) return rc;
    if (!rc && (!wait_for_completion_timeout(&n71_ro_probe.consumed,
                                             msecs_to_jiffies(8000)) ||
                READ_ONCE(n71_ro_probe.failed) ||
                READ_ONCE(n71_ro_probe.copied)!=4U)) rc=-EIO;
    if (rc) {
        WRITE_ONCE(n71_ro_probe.failed,true);
        n71_ro_probe_reply(rc);
    }
    return rc;
}
static void n71_ro_probe_close(int failed)
{
    if (!ans_ro_probe_once) return;
    WRITE_ONCE(n71_ro_probe.active,false);
    if (failed) {
        WRITE_ONCE(n71_ro_probe.failed,true);
        n71_ro_probe_reply(-EIO);
    }
    complete(&n71_ro_probe.request);
    if (n71_ro_probe.major>0) {
        unregister_chrdev(n71_ro_probe.major,"n71nand_probe");
        n71_ro_probe.major=0;n71_ro_probe.removed=true;
    }
}
#endif
