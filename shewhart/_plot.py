"""Rendering layer. Statistics live in Result; presentation lives here."""

from __future__ import annotations


def render(result, ax=None):
    if result.method == "imr":
        return _render_imr(result, ax)
    raise NotImplementedError(
        f"No renderer for method {result.method!r} yet. "
        "Use result.table to plot with your own tooling."
    )


def _render_imr(result, ax=None):
    import matplotlib.pyplot as plt

    if ax is None:
        _, axes = plt.subplots(2, 1, sharex=True, figsize=(9, 5.5), height_ratios=[2, 1])
    else:
        axes = ax

    t = result.table
    s = result.stats
    xs = range(len(t))

    a0, a1 = axes
    a0.plot(xs, t["value"], marker="o", ms=4, lw=1, color="#1f77b4")
    a0.axhline(s["i_center"], color="#444444", lw=1)
    a0.axhline(s["i_ucl"], color="#d62728", lw=1, ls="--")
    a0.axhline(s["i_lcl"], color="#d62728", lw=1, ls="--")
    flag = t["i_signal"].to_numpy()
    a0.plot(
        [i for i in xs if flag[i]],
        t["value"].to_numpy()[flag],
        "o",
        ms=7,
        mfc="none",
        mec="#d62728",
        mew=1.6,
        ls="",
    )
    a0.set_ylabel("individual value")
    a0.set_title(f"I-MR chart - {result.meta.get('source', '')}")

    a1.plot(xs, t["moving_range"], marker="o", ms=4, lw=1, color="#1f77b4")
    a1.axhline(s["mr_center"], color="#444444", lw=1)
    a1.axhline(s["mr_ucl"], color="#d62728", lw=1, ls="--")
    mflag = t["mr_signal"].to_numpy()
    a1.plot(
        [i for i in xs if mflag[i]],
        t["moving_range"].to_numpy()[mflag],
        "o",
        ms=7,
        mfc="none",
        mec="#d62728",
        mew=1.6,
        ls="",
    )
    a1.set_ylabel("moving range")
    a1.set_xlabel("observation")

    return axes
