"""Rendering layer. Statistics live in Result; presentation lives here."""

from __future__ import annotations

# method -> (title, top panel, bottom panel)
# panel = (table column, signal column, y label, (center key, lcl key, ucl key))
_SPECS = {
    "imr": (
        "I-MR chart",
        ("value", "i_signal", "individual value", ("i_center", "i_lcl", "i_ucl")),
        ("moving_range", "mr_signal", "moving range", ("mr_center", "mr_lcl", "mr_ucl")),
    ),
    "xbar_r": (
        "Xbar-R chart",
        ("mean", "mean_signal", "subgroup mean", ("xbar_center", "xbar_lcl", "xbar_ucl")),
        ("range", "range_signal", "subgroup range", ("r_center", "r_lcl", "r_ucl")),
    ),
    "xbar_s": (
        "Xbar-S chart",
        ("mean", "mean_signal", "subgroup mean", ("xbar_center", "xbar_lcl", "xbar_ucl")),
        ("stdev", "stdev_signal", "subgroup stdev", ("s_center", "s_lcl", "s_ucl")),
    ),
}


def render(result, ax=None):
    try:
        title, top, bottom = _SPECS[result.method]
    except KeyError:
        raise NotImplementedError(
            f"No renderer for method {result.method!r} yet. "
            "Use result.table to plot with your own tooling."
        ) from None

    import matplotlib.pyplot as plt

    if ax is None:
        _, axes = plt.subplots(
            2, 1, sharex=True, figsize=(9, 5.5), height_ratios=[2, 1]
        )
    else:
        axes = ax

    table = result.table
    _panel(axes[0], table, result.stats, top)
    _panel(axes[1], table, result.stats, bottom)
    axes[0].set_title(f"{title} - {result.meta.get('source', '')}")
    axes[1].set_xlabel("observation")
    return axes


def _panel(a, table, stats, spec):
    col, sigcol, label, (center, lcl, ucl) = spec
    values = table[col].to_numpy()
    xs = range(len(values))

    a.plot(xs, values, marker="o", ms=4, lw=1, color="#1f77b4")
    a.axhline(stats[center], color="#444444", lw=1)
    for key in (lcl, ucl):
        if key in stats:
            a.axhline(stats[key], color="#d62728", lw=1, ls="--")

    flagged = table[sigcol].to_numpy()
    a.plot(
        [i for i in xs if flagged[i]],
        values[flagged],
        "o",
        ms=7,
        mfc="none",
        mec="#d62728",
        mew=1.6,
        ls="",
    )
    a.set_ylabel(label)
