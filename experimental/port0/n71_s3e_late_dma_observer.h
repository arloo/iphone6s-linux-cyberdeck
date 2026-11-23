/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_S3E_LATE_DMA_OBSERVER_H
#define N71_S3E_LATE_DMA_OBSERVER_H

/* A read-only, checksum-only falsification aid. This cannot prove DMA
 * quiescence; changes may also be due to CPU/cache effects. No register,
 * translation, page ownership, or DMA-retirement decision belongs here. */
struct n71_s3e_late_dma_observer {
    unsigned int samples;
    unsigned int cq_changed;
    unsigned int data_changed;
    unsigned int ever_changed;
    /* Distinguish repeated non-baseline samples from actual transitions. */
    unsigned int cq_transitions;
    unsigned int data_transitions;
    unsigned int first_cq_deviation_sample;   /* 1-based; 0 means none */
    unsigned int first_data_deviation_sample; /* 1-based; 0 means none */
    unsigned long long first_cq;
    unsigned long long first_data;
    unsigned long long previous_cq;
    unsigned long long previous_data;
};

static inline unsigned long long n71_s3e_late_dma_fingerprint(
    const unsigned char *src, unsigned int length)
{
    unsigned long long hash = 14695981039346656037ULL;
    unsigned int i;
    if (!src || !length)
        return 0;
    for (i = 0; i < length; ++i) {
        hash ^= src[i];
        hash *= 1099511628211ULL;
    }
    return hash;
}

static inline void n71_s3e_late_dma_observe(
    struct n71_s3e_late_dma_observer *s,
    unsigned long long cq_fingerprint,
    unsigned long long data_fingerprint)
{
    if (!s)
        return;
    if (!s->samples) {
        s->first_cq = cq_fingerprint;
        s->first_data = data_fingerprint;
    } else {
        if (cq_fingerprint != s->first_cq) {
            s->cq_changed++; /* non-baseline sample; not a transition */
            if (!s->first_cq_deviation_sample)
                s->first_cq_deviation_sample = s->samples+1;
        }
        if (data_fingerprint != s->first_data) {
            s->data_changed++;
            if (!s->first_data_deviation_sample)
                s->first_data_deviation_sample = s->samples+1;
        }
        if (cq_fingerprint != s->previous_cq)
            s->cq_transitions++;
        if (data_fingerprint != s->previous_data)
            s->data_transitions++;
        if (cq_fingerprint != s->first_cq ||
            data_fingerprint != s->first_data)
            s->ever_changed = 1;
    }
    s->previous_cq = cq_fingerprint;
    s->previous_data = data_fingerprint;
    s->samples++;
}

/* No observation, including all-stable samples, authorizes unmap/free. */
static inline int n71_s3e_late_dma_release_allowed(
    const struct n71_s3e_late_dma_observer *s)
{
    (void)s;
    return 0;
}
#endif
