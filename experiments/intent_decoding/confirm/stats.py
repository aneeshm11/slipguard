"""Small stats helpers: Wilson score interval, paired/cluster bootstrap."""
import math, random


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return [float('nan'), float('nan')]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0.0, c - h), min(1.0, c + h)]


def cluster_bootstrap(clusters, stat, B=2000, seed=0):
    """clusters: list of per-cluster items (each a list of records); stat: f(list of records) -> float.
    Returns (point, lo, hi) percentile 95% CI resampling clusters with replacement."""
    rng = random.Random(seed)
    flat = [r for c in clusters for r in c]
    pt = stat(flat)
    vals = []
    for _ in range(B):
        samp = []
        for _ in range(len(clusters)):
            samp.extend(clusters[rng.randrange(len(clusters))])
        try:
            v = stat(samp)
        except ZeroDivisionError:
            continue
        if v == v:
            vals.append(v)
    vals.sort()
    if not vals:
        return pt, float('nan'), float('nan')
    lo = vals[int(0.025 * (len(vals) - 1))]
    hi = vals[int(0.975 * (len(vals) - 1))]
    return pt, lo, hi
