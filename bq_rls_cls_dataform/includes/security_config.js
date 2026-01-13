/**
 * Security configuration for RLS and CLS policies.
 * Aligned with quick_demo.sql for 2-group scenario.
 */

const IDENTITY_DOMAIN = "johanesa.altostrat.com";

// Two groups for demo: admin and sales
const groups = {
  admin: "group:bq-rls-cls-dataform-admin@johanesa.altostrat.com",
  sales: "group:bq-rls-cls-dataform-sales@johanesa.altostrat.com"
};

// For CLS GRANT statements, use principalSet format
const principalSets = {
  admin: "principalSet://goog/group/bq-rls-cls-dataform-admin@johanesa.altostrat.com",
  sales: "principalSet://goog/group/bq-rls-cls-dataform-sales@johanesa.altostrat.com"
};

module.exports = {
  IDENTITY_DOMAIN,
  groups,
  principalSets
};
