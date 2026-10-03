-- One row per observed plate (a plate holds up to 1000 fibers = spectra).
-- Flux pixels sit on a log10(wavelength) grid: loglam = loglam0 + dloglam * i
CREATE TABLE plate (
  plate   INTEGER,
  mjd     INTEGER,             -- Modified Julian Date of the observation
  loglam0 DOUBLE,              -- log10(wavelength / Angstrom) of the first pixel
  dloglam DOUBLE,              -- log10 step between pixels
  PRIMARY KEY (plate, mjd)
);

-- One row per spectrum, with the SDSS pipeline's class and redshift.
CREATE TABLE spectrum (
  plate INTEGER,
  mjd   INTEGER,
  fiber INTEGER,
  class TEXT,                  -- STAR | GALAXY | QSO
  z     DOUBLE,                -- redshift
  flux  FLOAT[],               -- 1e-17 erg / s / cm^2 / Angstrom
  PRIMARY KEY (plate, mjd, fiber),
  FOREIGN KEY (plate, mjd) REFERENCES plate (plate, mjd)
);

-- Theory vs measurement for hydrogen Balmer lines (n_upper -> 2), vacuum.
CREATE TABLE line (
  name           TEXT PRIMARY KEY,
  n_upper        INTEGER,
  lambda_rydberg DOUBLE,       -- Angstrom, Rydberg formula
  lambda_nist    DOUBLE        -- Angstrom, measured in the lab (NIST)
);

-- Lines extracted from galaxy spectra: where the line actually is.
CREATE TABLE line_fit (
  plate      INTEGER,
  mjd        INTEGER,
  fiber      INTEGER,
  line       TEXT REFERENCES line (name),
  lambda_obs DOUBLE,           -- Angstrom, flux-weighted centroid
  z_line     DOUBLE,           -- lambda_obs / lambda_nist - 1
  PRIMARY KEY (plate, mjd, fiber, line),
  FOREIGN KEY (plate, mjd, fiber) REFERENCES spectrum (plate, mjd, fiber)
);
