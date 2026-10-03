// EMA 5937 project report template. Compiled by the Makefile from the repo root:
//   typst compile --root . report/main.typ report/main.pdf
// Every number and figure comes from results/results.json and figures/.

#let R = json("/results/results.json")
#let ds = R.dataset
#let f(x, d: 3) = str(calc.round(x, digits: d))
#let pct(x) = str(calc.round(x * 100, digits: 1)) + "%"
#let src = [SDSS eBOSS optical spectra @sdss_dr17]
#let feat = [coadded flux in #ds.n_features log-wavelength pixels]
#let lbl = [spectroscopic class]
#let tgt = [redshift]

#set document(title: "Five classical methods and one physical law on SDSS spectra", author: "Your Name")
#set page(margin: 2.5cm, numbering: "1")
#set text(font: "New Computer Modern", size: 11pt)
#set heading(numbering: "1.1")

#align(center)[
  #text(17pt, weight: "bold")[SVD, PCA, LDA, SVM, an MLP and the Rydberg formula on SDSS spectra]
  #v(0.4em)
  Your Name — EMA 5937 Special Topics: ML for Materials Science \
  #text(9pt, fill: gray)[Generated #R.generated_utc · #ds.n_rows spectra · #str(R.config.plates) plates]
]

= Data

The dataset is #src: #ds.n_rows rows described by #feat. Each row carries a
#lbl label for classification and a #tgt target for regression. Class counts:
#ds.classes.pairs().map(((k, v)) => [#raw(k) (#v)]).join(", "). Every plate was fetched exactly once by a single paced client and is
redistributed over irohds, so the origin server is never re-queried by peers.
The DuckDB schema (`schema.sql`) keeps plates, spectra, Balmer-line theory and
line measurements in four related tables.

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

= Experiment, extraction and theory

Hydrogen's Balmer lines tie the spectra to a physical law. The Rydberg formula
with hydrogen's reduced mass, $1 / lambda = R_H (1 / 2^2 - 1 / n^2)$, predicts
each rest wavelength; NIST lists the lab value @nist_asd. In #R.lines.map(l => l.n).sum()
galaxy spectra a line rises 5#sym.sigma above its continuum, and its centroid
gives a redshift from one line alone, compared with the pipeline's full-spectrum fit.

#let kms(x) = if x == none [—] else [#f(x, d: 1)]
#figure(
  table(columns: 6, align: (left, right, right, right, right, right), stroke: none,
    table.hline(),
    table.header([*Line*], [*Rydberg (Å)*], [*NIST (Å)*], [*Theory offset (km/s)*],
      [*Galaxies*], [*Line − pipeline (km/s)*]),
    table.hline(stroke: 0.5pt),
    ..R.lines.map(l => ([#l.name], [#f(l.rydberg, d: 2)], [#f(l.nist, d: 2)],
      [#f(l.dv_theory, d: 1)], [#l.n], [#kms(l.dv_median) ± #kms(l.dv_mad)])).flatten(),
    table.hline()),
  caption: [Balmer rest wavelengths from theory and the lab, and the velocity offset
  between one-line and pipeline redshifts (median ± median absolute deviation).]) <tab-lines>

#figure(image("/figures/lines.png", width: 95%),
  caption: [Redshift from one Balmer line against the pipeline redshift, and the
  distribution of their velocity difference.]) <fig-lines>

= Discussion

_Interpret @tab-metrics: which classes confuse the SVC, where the regressors fail,
how much of the signal the leading singular vectors already carry, and what the
next model (a CNN over the raw spectrum, a graph network over the crystal) would add._

= Reproducibility

`just` builds this PDF from nothing; `just hpc` runs the identical pipeline on all
plates with `config.hpc.yaml`. Peers in the same irohds namespace (`MSEML_NS`)
receive every plate without contacting the origin.

#bibliography("refs.bib", style: "ieee")
