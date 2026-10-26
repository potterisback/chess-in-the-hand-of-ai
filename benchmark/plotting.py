"""Common chart style for the benchmark figures."""

COLORS = ["#2a78b8", "#e07b39", "#3a9a5b", "#8a5cc2", "#c94f6d", "#7d7d7d"]


def style(plt) -> None:
    plt.rcParams.update({
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.titleweight": "bold",
        "figure.facecolor": "white",
    })
