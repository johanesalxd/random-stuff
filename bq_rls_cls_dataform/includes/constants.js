/**
 * Configurable constants for different environments.
 */

const envConfig = {
  dev: {
    project: "johanesa-playground-326616",
    dataset: "demo_dataset",
    location: "us"
  },
  prod: {
    project: "YOUR_PROD_PROJECT",
    dataset: "YOUR_PROD_DATASET",
    location: "YOUR_PROD_LOCATION"
  }
};

const currentEnv = dataform.projectConfig.vars.env || "dev";
const config = envConfig[currentEnv];

module.exports = {
  project: config.project,
  dataset: config.dataset,
  location: config.location,
  region: `region-${config.location}`,  // For DATA_POLICY: "region-us"
  env: currentEnv
};
