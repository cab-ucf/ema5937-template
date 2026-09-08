// EMA 5937 project report template. Compiled by the Makefile from the repo root:
//   typst compile --root . report/main.typ report/main.pdf
// Every number and figure comes from results/results.json and figures/.

#let R = json("/results/results.json")
#let ds = R.dataset
#let f(x, d: 3) = str(calc.round(x, digits: d))
#let pct(x) = str(calc.round(x * 100, digits: 1)) + "%"
#let sdss = ds.source == "sdss"
#let src = if sdss [SDSS eBOSS optical spectra @sdss_dr17] else [the AFLOW materials database @aflow2022 via AFLUX @rose2017aflux]
#let feat = if sdss [coadded flux in #ds.n_features log-wavelength pixels] else [#ds.n_features element-fraction and unit-cell descriptors]
#let lbl = if sdss [spectroscopic class] else [electronic type (`Egap_type`)]
#let tgt = if sdss [redshift] else [formation enthalpy per atom (eV)]

#set document(title: "Five classical methods on wide tabular data", author: "Your Name")
#set page(margin: 2.5cm, numbering: "1")
#set text(font: "New Computer Modern", size: 11pt)
#set heading(numbering: "1.1")

#align(center)[
  #text(17pt, weight: "bold")[SVD, PCA, LDA, SVM and an MLP on #raw(ds.source) data]
  #v(0.4em)
  Your Name — EMA 5937 Special Topics: ML for Materials Science \
  #text(9pt, fill: gray)[Generated #R.generated_utc · #ds.n_rows rows · #str(R.config.shards) shards]
]

= Data

The dataset is #src: #ds.n_rows rows described by #feat. Each row carries a
#lbl label for classification and a #tgt target for regression. Class counts:
#ds.classes.pairs().map(((k, v)) => [#raw(k) (#v)]).join(", "). Every shard
(a plate or an API page) was fetched exactly once by a single paced client and
is redistributed over irohds, so the origin server is never re-queried by peers.

_Replace this paragraph with your own motivation. The rest of the document
regenerates from `results/results.json` whenever the config or code changes._

= Methods

All models are fit with scikit-learn @pedregosa2011sklearn on standardized
features. A randomized truncated SVD @halko2011randomized of rank
#str(R.config.n_components) gives the scree and reconstruction-error
curves; PCA on the same matrix yields the #str(R.config.n_components)
components on which LDA @fisher1936lda, RBF support-vector machines
@cortes1995svm (SVC / SVR) and two-hidden-layer perceptrons @prince2023udl
(classifier / regressor) are trained, using a stratified
80% / 20% split
(#ds.n_train / #ds.n_test rows).

= Results

#figure(image("/figures/svd.png", width: 92%),
  caption: [Singular-value spectrum and relative Frobenius reconstruction error versus rank.
  Rank #str(R.config.n_components) leaves #pct(R.svd.recon_error_at_k) of the norm unexplained.]) <fig-svd>

#figure(grid(columns: 2, gutter: 8pt, image("/figures/pca.png"), image("/figures/lda.png")),
  caption: [Left: first two principal components (#pct(R.pca.explained_2) of variance).
  Right: LDA projection of the test set; LDA classification accuracy #f(R.lda.acc).]) <fig-proj>

#figure(
  table(columns: 4, align: (left, right, right, right), stroke: none,
    table.hline(),
    table.header([*Model*], [*Accuracy*], [*MAE*], [*R#super[2]*]),
    table.hline(stroke: 0.5pt),
    [LDA], [#f(R.lda.acc)], [—], [—],
    [SVM (SVC / SVR)], [#f(R.svm.acc)], [#f(R.svm.mae)], [#f(R.svm.r2)],
    [MLP (classifier / regressor)], [#f(R.mlp.acc)], [#f(R.mlp.mae)], [#f(R.mlp.r2)],
    table.hline()),
  caption: [Held-out metrics on #ds.n_test rows: classification of #lbl, regression of #tgt.]) <tab-metrics>

#figure(image("/figures/svm.png", width: 95%),
  caption: [SVC confusion matrix and SVR parity plot.]) <fig-svm>
#figure(image("/figures/mlp.png", width: 95%),
  caption: [MLP classifier training loss and MLP regressor parity plot.]) <fig-mlp>

= Discussion

_Interpret @tab-metrics: which classes confuse the SVC, where the regressors fail,
how much of the signal the leading singular vectors already carry, and what the
next model (a CNN over the raw spectrum, a graph network over the crystal) would add._

= Reproducibility

`just` builds this PDF from nothing; `just hpc` runs the identical pipeline on all
shards with `config.hpc.yaml`. Peers in the irohds namespace
#raw(R.config.namespace) receive every shard without contacting the origin.

#bibliography("refs.bib", style: "ieee")
