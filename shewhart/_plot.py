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


# single-panel charts: (title, value column, y label, center key)
_SINGLE = {
    "p_chart": ("p chart", "proportion", "proportion defective", "p_center"),
    "np_chart": ("np chart", "defectives", "defective units", "np_center"),
    "c_chart": ("c chart", "defects", "defects", "c_center"),
    "u_chart": ("u chart", "per_unit", "defects per unit", "u_center"),
    "laney_p": ("Laney p' chart", "proportion", "proportion defective", "p_center"),
    "laney_u": ("Laney u' chart", "per_unit", "defects per unit", "u_center"),
    "run_chart": ("run chart", "value", "value", "median"),
    "ewma": ("EWMA chart", "ewma", "EWMA", "center"),
}


def render(result, ax=None):
    if result.method == "capability":
        return _render_capability(result, ax)
    if result.method == "pareto":
        return _render_pareto(result, ax)
    if result.method == "cusum":
        return _render_cusum(result, ax)
    if result.method in _SINGLE:
        return _render_single(result, ax)
    if result.method == "xbar_s" and result.meta.get("variable_sizes"):
        return _render_variable_xbar_s(result, ax)
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


def _render_cusum(result, ax=None):
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))

    t = result.table
    xs = range(len(t))
    h = result.stats["cusum_limit"]

    ax.plot(xs, t["cusum_pos"], marker="o", ms=4, lw=1, color="#1f77b4", label="C+")
    ax.plot(xs, t["cusum_neg"], marker="o", ms=4, lw=1, color="#7f7f7f", label="C-")
    ax.axhline(0, color="#444444", lw=1)
    ax.axhline(h, color="#d62728", lw=1, ls="--")
    ax.axhline(-h, color="#d62728", lw=1, ls="--")

    flagged = t["signal"].to_numpy()
    for col in ("cusum_pos", "cusum_neg"):
        vals = t[col].to_numpy()
        ax.plot(
            [i for i in xs if flagged[i]],
            vals[flagged],
            "o", ms=7, mfc="none", mec="#d62728", mew=1.6, ls="",
        )
    ax.set_ylabel("cumulative sum")
    ax.set_xlabel("observation")
    ax.set_title(f"CUSUM chart - {result.meta.get('source', '')}")
    ax.legend(frameon=False)
    return ax


def _render_pareto(result, ax=None):
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4.5))

    t = result.table
    xs = range(len(t))
    ax.bar(xs, t["count"].to_numpy(), color="#9ecae1", edgecolor="white")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([str(i) for i in t.index], rotation=30, ha="right")
    ax.set_ylabel("count")

    ax2 = ax.twinx()
    ax2.plot(xs, 100 * t["cumulative_share"].to_numpy(),
             marker="o", ms=4, color="#d62728", lw=1.2)
    ax2.axhline(80, color="#888888", lw=0.8, ls=":")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("cumulative %")

    ax.set_title("Pareto chart")
    return ax


def _render_capability(result, ax=None):
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy import stats as sps

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4.5))

    x = result.table["value"].to_numpy()
    s = result.stats
    ax.hist(x, bins="auto", density=True, color="#9ecae1", edgecolor="white")

    grid = np.linspace(x.min() - 3 * s["sigma_overall"], x.max() + 3 * s["sigma_overall"], 300)
    ax.plot(grid, sps.norm.pdf(grid, s["mean"], s["sigma_within"]),
            color="#1f77b4", lw=1.5, label="within")
    ax.plot(grid, sps.norm.pdf(grid, s["mean"], s["sigma_overall"]),
            color="#1f77b4", lw=1.5, ls="--", label="overall")

    ax.axvline(s["mean"], color="#444444", lw=1)
    for key, label in (("lsl", "LSL"), ("usl", "USL"), ("target", "T")):
        v = result.params.get(key)
        if v is not None:
            ax.axvline(v, color="#d62728", lw=1.5)
            ax.text(v, ax.get_ylim()[1] * 0.95, label, color="#d62728",
                    ha="center", va="top")

    cpk = s.get("cpk")
    title = "Process capability" + (f"  (Cpk = {cpk:.2f})" if cpk is not None else "")
    ax.set_title(title)
    ax.legend(frameon=False)
    ax.set_xlabel(result.params.get("value") or "value")
    return ax


def _render_single(result, ax=None):
    import matplotlib.pyplot as plt

    title, col, label, center_key = _SINGLE[result.method]
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))

    table = result.table
    values = table[col].to_numpy()
    xs = range(len(values))

    ax.plot(xs, values, marker="o", ms=4, lw=1, color="#1f77b4")
    ax.axhline(result.stats[center_key], color="#444444", lw=1)
    if "ucl" in table.columns:
        ax.step(xs, table["ucl"].to_numpy(), where="mid", color="#d62728", lw=1, ls="--")
        ax.step(xs, table["lcl"].to_numpy(), where="mid", color="#d62728", lw=1, ls="--")

    flagged = table["signal"].to_numpy()
    ax.plot(
        [i for i in xs if flagged[i]],
        values[flagged],
        "o",
        ms=7,
        mfc="none",
        mec="#d62728",
        mew=1.6,
        ls="",
    )
    ax.set_ylabel(label)
    ax.set_xlabel("period")
    ax.set_title(f"{title} - {result.meta.get('source', '')}")
    return ax


def _render_variable_xbar_s(result, ax=None):
    """Stair-step Xbar-S: limits vary per subgroup, so they come from the
    table columns rather than scalar stats."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, axes = plt.subplots(
            2, 1, sharex=True, figsize=(9, 5.5), height_ratios=[2, 1]
        )
    else:
        axes = ax

    t = result.table
    xs = range(len(t))
    panels = [
        (axes[0], "mean", "mean_signal", "subgroup mean",
         "mean_lcl", "mean_ucl", result.stats["xbar_center"]),
        (axes[1], "stdev", "stdev_signal", "subgroup stdev",
         "stdev_lcl", "stdev_ucl", None),
    ]
    for a, col, sigcol, label, lcl, ucl, center in panels:
        values = t[col].to_numpy()
        a.plot(xs, values, marker="o", ms=4, lw=1, color="#1f77b4")
        if center is not None:
            a.axhline(center, color="#444444", lw=1)
        a.step(xs, t[ucl].to_numpy(), where="mid", color="#d62728", lw=1, ls="--")
        a.step(xs, t[lcl].to_numpy(), where="mid", color="#d62728", lw=1, ls="--")
        flagged = t[sigcol].to_numpy()
        a.plot([i for i in xs if flagged[i]], values[flagged],
               "o", ms=7, mfc="none", mec="#d62728", mew=1.6, ls="")
        a.set_ylabel(label)
    axes[0].set_title(f"Xbar-S chart - {result.meta.get('source', '')}")
    axes[1].set_xlabel("observation")
    return axes


def _panel(a, table, stats, spec):
    col, sigcol, label, (center, lcl, ucl) = spec
    values = table[col].to_numpy()
    xs = range(len(values))

    a.plot(xs, values, marker="o", ms=4, lw=1, color="#1f77b4")
    if center in stats:
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
