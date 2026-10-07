"""How many CPUs this process may really use, and holding every library to it.

In a container the host's core count is what most libraries see: Render's
Pro plan gives the listening service 2 CPUs on a machine with many more, and
PyTorch, numba, BLAS and ONNX Runtime each start a thread per host core, which
then fight over the two. A live step took 2.0-3.2 s on Render against 0.3 s on
a laptop (spec 053, "Live latency"). `cpu_budget` reads the container's own
limit (its cgroup CPU quota and the process's CPU affinity) and `limit_threads`
holds the libraries to it. Call `limit_threads` before importing them.
"""

import math
import os


def cpu_budget():
    """-> (cpus to use, {what was read}). The smallest of the host's count, the
    CPUs this process may run on, and the cgroup's quota."""
    seen = {"host": os.cpu_count() or 1}
    n = seen["host"]
    if hasattr(os, "sched_getaffinity"):
        seen["affinity"] = len(os.sched_getaffinity(0))
        n = min(n, seen["affinity"])
    quota = None
    try:                                   # cgroup v2: "max 100000" or "200000 100000"
        with open("/sys/fs/cgroup/cpu.max") as f:
            q, period = f.read().split()
            if q != "max":
                quota = int(q) / int(period)
    except (OSError, ValueError):
        try:                               # cgroup v1
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
                q = int(f.read())
            with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
                period = int(f.read())
            if q > 0:
                quota = q / period
        except (OSError, ValueError):
            pass
    if quota:
        seen["cgroup_quota"] = round(quota, 2)
        n = min(n, max(1, math.ceil(quota)))
    return max(1, n), seen


def limit_threads(n=None):
    """Hold OpenMP, BLAS, numba, PyTorch and ONNX Runtime to `n` threads (the
    CPU budget by default). -> (n, {what was read})."""
    budget, seen = cpu_budget()
    n = n or budget
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS"):
        os.environ[var] = str(n)
    try:
        import torch

        torch.set_num_threads(n)
        torch.set_num_interop_threads(1)
    except Exception:  # torch absent, or interop threads already fixed
        pass
    try:
        import onnxruntime as ort

        if not getattr(ort.InferenceSession, "_thread_limited", False):
            base = ort.InferenceSession

            class Limited(base):
                _thread_limited = True

                def __init__(self, path_or_bytes, sess_options=None, *a, **k):
                    opts = sess_options or ort.SessionOptions()
                    opts.intra_op_num_threads = n
                    opts.inter_op_num_threads = 1
                    super().__init__(path_or_bytes, opts, *a, **k)

            ort.InferenceSession = Limited
    except Exception:  # onnxruntime absent
        pass
    return n, seen
