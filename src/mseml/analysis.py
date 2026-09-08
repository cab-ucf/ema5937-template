"""dataset.parquet -> SVD, PCA, LDA, SVM, MLP -> one figure each + results.json for the report.

SVD/PCA reduce the wide matrix to k components once; LDA, SVM and the MLP are fit on
those k components (dimensionality reduction as preprocessing). [pedregosa2011sklearn]

Usage:
    uv run python -m mseml.analysis config.yaml data/dataset.parquet figures results/results.json
"""

import json
import sys
import yaml
from datetime import UTC, datetime
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, SVR
from sklearn.utils.extmath import randomized_svd
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")
plt.rcParams.update({"figure.dpi": 200, "savefig.bbox": "tight", "font.size": 10})


def scatter_classes(ax, Z, y, title, xlabel, ylabel):
    for c in np.unique(y):
        # Boolean vector of matching class 'c'
        m = y == c
        ax.scatter(Z[m, 0], Z[m, 1],
	           s=4, alpha=0.6, linewidths=0,
		   rasterized=True, label=f"{c} ({m.sum()})")
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    ax.legend(markerscale=3, fontsize=8)


def parity(ax, t, pred, title):
    # np.r_ concatenates in first axis
    lo, hi = np.percentile(np.r_[t, pred], [0.5, 99.5])
    ax.plot([lo, hi], [lo, hi], "--", color="gray", lw=1)
    ax.scatter(t, pred, s=4, alpha=0.4, linewidths=0, rasterized=True)
    ax.set(xlim=(lo, hi), ylim=(lo, hi), xlabel="true target", ylabel="prediction", title=title)


def main(config: str, data: str, figdir: str, out: str) -> None:
    cfg = yaml.safe_load(open(config))
    k = cfg["n_components"]
    seed = cfg["seed"]
    figs = Path(figdir)
    figs.mkdir(parents=True, exist_ok=True)

    # ---- load & standardize ---------------------------------------------------------------
    df = pd.read_parquet(data)
    X = df.filter(regex=r"^f\d+$").to_numpy(np.float32)
    if cfg["source"] == "sdss":  # spectra: divide each by its median flux first
        med = np.median(X, axis=1, keepdims=True)
        keep = med[:, 0] > 0
        df, X = df[keep].reset_index(drop=True), X[keep] / med[keep]
    y = df["label"].to_numpy()
    t = df["target"].to_numpy()
    Xs = StandardScaler().fit_transform(X)
    print(f"[analysis] {Xs.shape[0]} rows x {Xs.shape[1]} features, classes {sorted(set(y))}")

    # ---- SVD: scree + low-rank reconstruction error [halko2011randomized] ------------------
    _, S, _ = randomized_svd(Xs, n_components=k, random_state=seed)
    total = np.linalg.norm(Xs) ** 2
    recon = np.sqrt(np.maximum(total - np.cumsum(S**2), 0) / total)
    fig, ax = plt.subplots(1, 2, figsize=(8, 3))
    ax[0].semilogy(np.arange(1, k + 1), S, ".-")
    ax[0].set(xlabel="component", ylabel="singular value", title="Scree")
    ax[1].plot(np.arange(1, k + 1), recon, ".-")
    ax[1].set(xlabel="rank r", ylabel="relative reconstruction error", title="Low-rank approximation")
    fig.savefig(figs / "svd.png")

    # ---- PCA: k components, 2-D scatter -----------------------------------------------------
    pca = PCA(n_components=k, svd_solver="randomized", random_state=seed).fit(Xs)
    Z, ratio = pca.transform(Xs), pca.explained_variance_ratio_
    fig, ax = plt.subplots(figsize=(5, 4))
    scatter_classes(ax, Z, y, "PCA", f"PC1 ({ratio[0]:.0%})", f"PC2 ({ratio[1]:.0%})")
    fig.savefig(figs / "pca.png")

    Ztr, Zte, ytr, yte, ttr, tte = train_test_split(Z, y, t, test_size=0.2, random_state=seed, stratify=y)

    # ---- LDA: supervised projection + classifier [fisher1936lda] ---------------------------
    lda = LinearDiscriminantAnalysis(n_components=min(2, len(set(y)) - 1)).fit(Ztr, ytr)
    proj, lda_acc = lda.transform(Zte), accuracy_score(yte, lda.predict(Zte))
    if proj.shape[1] == 1:
        proj = np.c_[proj, np.random.default_rng(0).normal(scale=0.05, size=len(proj))]
    fig, ax = plt.subplots(figsize=(5, 4))
    scatter_classes(ax, proj, yte, "LDA projection (test set)", "LD1", "LD2")
    fig.savefig(figs / "lda.png")

    # ---- SVM: SVC for the label, SVR for the target [cortes1995svm] ------------------------
    idx = np.random.default_rng(seed).permutation(len(Ztr))[: cfg["max_fit_rows"]]
    svc = SVC(C=10).fit(Ztr[idx], ytr[idx])
    svr = SVR(C=10).fit(Ztr[idx], ttr[idx])
    svc_acc, svr_pred = accuracy_score(yte, svc.predict(Zte)), svr.predict(Zte)
    fig, ax = plt.subplots(1, 2, figsize=(8.5, 3.6))
    ConfusionMatrixDisplay.from_predictions(yte, svc.predict(Zte), ax=ax[0], colorbar=False, xticks_rotation=45)
    ax[0].set_title(f"SVC, accuracy {svc_acc:.3f}")
    parity(ax[1], tte, svr_pred, f"SVR, MAE {mean_absolute_error(tte, svr_pred):.3g}")
    fig.savefig(figs / "svm.png")

    # ---- MLP: same two tasks with a small neural network [prince2023udl] -------------------
    kw = dict(hidden_layer_sizes=(128, 64), early_stopping=True, max_iter=300, random_state=seed)
    clf = MLPClassifier(**kw).fit(Ztr, ytr)
    reg = MLPRegressor(**kw).fit(Ztr, ttr)
    mlp_acc, mlp_pred = accuracy_score(yte, clf.predict(Zte)), reg.predict(Zte)
    fig, ax = plt.subplots(1, 2, figsize=(8.5, 3.6))
    ax[0].plot(clf.loss_curve_)
    ax[0].set(xlabel="epoch", ylabel="training loss", title=f"MLP classifier, accuracy {mlp_acc:.3f}")
    parity(ax[1], tte, mlp_pred, f"MLP regressor, MAE {mean_absolute_error(tte, mlp_pred):.3g}")
    fig.savefig(figs / "mlp.png")

    # ---- numbers for the report -----------------------------------------------------------
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "config": cfg,
        "dataset": {"source": cfg["source"], "n_rows": len(df), "n_features": int(X.shape[1]),
                    "n_train": len(Ztr), "n_test": len(Zte), "classes": {c: int(n) for c, n in zip(*np.unique(y, return_counts=True))}},
        "svd": {"recon_error_at_k": float(recon[-1])},
        "pca": {"explained_2": float(ratio[:2].sum()), "explained_k": float(ratio.sum())},
        "lda": {"acc": lda_acc},
        "svm": {"acc": svc_acc, "mae": mean_absolute_error(tte, svr_pred), "r2": r2_score(tte, svr_pred)},
        "mlp": {"acc": mlp_acc, "mae": mean_absolute_error(tte, mlp_pred), "r2": r2_score(tte, mlp_pred)},
    }, indent=2))
    print(f"[analysis] -> {figdir}/ and {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
