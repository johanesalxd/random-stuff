"""Froyo Lakehouse CA data agent definition (single unified agent).

Builds the BigQuery datasource references and system instruction for one
Conversational Analytics API data agent that spans, in a single query surface:

  - native BigQuery knowledge tables (dataset ``froyo_demo_ue4`` in ``us-east4``),
    seeded from the recipe/supplier PDFs, and
  - AWS-federated Apache Iceberg tables (customer loyalty + sales history) that
    physically live in AWS S3/Glue and are read cross-cloud through the BigLake
    federated catalog.

The federated tables are referenced with the four-part ``P.C.N.T`` syntax that
the CA API supports for Lakehouse / external-catalog tables: the ``project_id``
is the GCP project, the ``dataset_id`` is ``<catalog>.<namespace>``
(catalog.namespace, C.N), and the ``table_id`` is the table name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# agent/config/agent_definition.py -> agent/ -> bq_cross_cloud_lakehouse/
_AGENT_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _AGENT_ROOT.parent
_DEMO_CONFIG = _DEMO_ROOT / "config.local.env"
_AGENT_ENV = _AGENT_ROOT / ".env"


def env_flag(name: str, default: str = "false") -> bool:
    """Reads an environment variable as a boolean flag.

    The accepted spellings match the shell scripts' ``NO_AWS`` handling so that
    the Python and Bash halves of the demo cannot disagree.

    Args:
        name: Environment variable name.
        default: Value assumed when the variable is unset.

    Returns:
        True when the value is one of ``1``, ``true``, ``yes`` or ``on``
        (case-insensitive).
    """
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LakehouseConfig:
    """Resolved infrastructure identifiers for the cross-cloud lakehouse.

    Args:
        project_id: GCP project that owns the BigQuery datasets and the
            federated catalog.
        native_dataset: Native BigQuery dataset holding the seeded knowledge
            tables (co-located in the lakehouse region).
        federated_catalog: BigLake federated catalog name.
        glue_database: Glue database / Iceberg namespace inside the catalog.
        loyalty_table: Federated customer-loyalty Iceberg table name.
        sales_table: Federated sales-history Iceberg table name.
        no_aws: When True, the demo runs entirely on GCP: the loyalty and sales
            tables are seeded natively into ``native_dataset`` instead of being
            federated from AWS Glue, and the agent is told so.
    """

    project_id: str
    native_dataset: str
    federated_catalog: str
    glue_database: str
    loyalty_table: str
    sales_table: str
    no_aws: bool = False

    @property
    def federated_dataset_id(self) -> str:
        """Return the ``catalog.namespace`` (C.N) dataset id for P.C.N.T refs."""
        return f"{self.federated_catalog}.{self.glue_database}"

    @property
    def analytics_dataset_id(self) -> str:
        """Return the dataset id that actually holds loyalty and sales.

        This is the native dataset in ``no_aws`` mode and the federated
        ``catalog.namespace`` otherwise.
        """
        return self.native_dataset if self.no_aws else self.federated_dataset_id


@dataclass(frozen=True)
class TableRef:
    """A single BigQuery table reference plus its agent-facing description.

    Args:
        dataset_id: Dataset id. For native tables this is the dataset name; for
            federated Lakehouse tables it is ``<catalog>.<namespace>``.
        table_id: Table (or view) name.
        description: Short description surfaced to the agent as table context.
    """

    dataset_id: str
    table_id: str
    description: str


@dataclass(frozen=True)
class AgentDefinition:
    """Complete definition for the Froyo Lakehouse CA data agent.

    Args:
        agent_id: CA API data agent id.
        description: Human-readable agent description (also shown in GE).
        tables: BigQuery table references available to the agent.
        system_instruction: Business scope, schema hints, join keys, and rules.
    """

    agent_id: str
    description: str
    tables: tuple[TableRef, ...]
    system_instruction: str


def load_lakehouse_config() -> LakehouseConfig:
    """Load infra values from ``../config.local.env`` then the agent ``.env``.

    The demo's ``config.local.env`` is the single source of truth for the
    project, region, catalog, and table names. The agent ``.env`` may override
    them and adds the Gemini Enterprise / OAuth settings used elsewhere.

    Returns:
        Resolved lakehouse configuration.

    Raises:
        ValueError: If ``GCP_PROJECT`` cannot be resolved.
    """
    if _DEMO_CONFIG.exists():
        load_dotenv(_DEMO_CONFIG, override=False)
    if _AGENT_ENV.exists():
        load_dotenv(_AGENT_ENV, override=True)

    project_id = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError(
            "GCP_PROJECT must be set (source ../config.local.env or set it in .env)."
        )

    return LakehouseConfig(
        project_id=project_id,
        native_dataset=os.getenv("FROYO_NATIVE_DATASET", "froyo_demo_ue4"),
        federated_catalog=os.getenv("FEDERATED_CATALOG", "demo_glue_cat"),
        glue_database=os.getenv("GLUE_DATABASE", "froyo_lakehouse"),
        loyalty_table=os.getenv("FROYO_LOYALTY_TABLE", "global_loyalty"),
        sales_table=os.getenv("FROYO_SALES_TABLE", "sales_history"),
        no_aws=env_flag("NO_AWS"),
    )


def _system_instruction(config: LakehouseConfig) -> str:
    """Build the system instruction with fully-qualified table names.

    Args:
        config: Resolved lakehouse configuration.

    Returns:
        The agent system instruction string.
    """
    native = f"{config.project_id}.{config.native_dataset}"
    fed = f"{config.project_id}.{config.analytics_dataset_id}"

    if config.no_aws:
        location_desc = "all tables live natively in Google Cloud BigQuery."
        table_source_desc = "Native BigQuery tables"
        rule_desc = (
            "all tables are native to BigQuery. Join them using ordinary BigQuery SQL."
        )
    else:
        location_desc = (
            "native product/allergen knowledge lives in Google Cloud BigQuery, "
            "while customer loyalty and sales history physically live in AWS "
            "S3/Glue as Apache Iceberg tables, federated into BigQuery."
        )
        table_source_desc = (
            "AWS-federated Iceberg tables (physically in AWS S3/Glue, read cross-cloud)"
        )
        rule_desc = (
            "the loyalty and sales tables are AWS-resident but directly "
            "queryable from BigQuery. Join them with the native knowledge "
            "tables using ordinary BigQuery SQL."
        )

    loyalty = f"{fed}.{config.loyalty_table}"
    sales = f"{fed}.{config.sales_table}"

    return (
        "You are the Froyo Lakehouse Analyst, a data agent for the frozen-yogurt "
        f"brand 'Froyo'. Its hero product is 'Midnight Swirl'. You answer business "
        f"questions by writing BigQuery SQL: {location_desc}\n\n"
        "Native knowledge tables (Google Cloud BigQuery):\n"
        f"- {native}.products: product catalog. Columns: product_id, product_name, "
        "category, launch_date, status.\n"
        f"- {native}.recipes: per-product ingredient lists. Columns: product_id, "
        "product_name, ingredient_id, ingredient_name, quantity_g.\n"
        f"- {native}.ingredient_allergens: allergen declarations extracted from "
        "supplier datasheets (only allergen-bearing rows). Columns: ingredient_id, "
        "ingredient_name, allergen, supplier, source_doc.\n"
        f"- {native}.product_allergens: convenience VIEW joining recipes to "
        "ingredient_allergens. Columns: product_id, product_name, allergen, "
        "ingredient_name, supplier, source_doc. Prefer this view for "
        "'what allergens are in product X' questions.\n\n"
        f"{table_source_desc}:\n"
        f"- {loyalty}: customer loyalty. Columns: customer_id, region "
        "(APAC/EMEA/AMER), loyalty_tier (Platinum/Gold/Silver/Bronze), "
        "favorite_flavor, avg_monthly_spend, soy_sensitive_flag (boolean), "
        "last_order_date.\n"
        f"- {sales}: historical daily sales. Columns: sale_date, product_name, "
        "region, units_sold, revenue.\n\n"
        "Join relationships (join by product name string):\n"
        f"- {native}.product_allergens.product_name = {loyalty}.favorite_flavor\n"
        f"- {native}.product_allergens.product_name = {sales}.product_name\n"
        f"- {native}.recipes.ingredient_id"
        f" = {native}.ingredient_allergens.ingredient_id\n\n"
        "Critical business rules:\n"
        "1. Allergen safety: Midnight Swirl contains the ingredient 'Midnight Base "
        "204', which declares a Soy allergen (source_doc "
        "'midnight_base_204_manual.pdf'). Therefore Midnight Swirl contains Soy. "
        "Any Midnight Swirl customer-targeting or campaign list MUST exclude "
        "customers whose soy_sensitive_flag is TRUE.\n"
        f"2. {rule_desc}\n"
        "3. Forecasting scope: you perform ad-hoc analytics (aggregations, trends, "
        "comparisons) on the sales history. You do not train time-series models; "
        "the deterministic ARIMA_PLUS revenue forecast is a separate scripted step "
        "of the demo (gcp/50_forecast_bqml.sh).\n\n"
        "When answering, state exact figures, explain the business rationale, and "
        + (
            "do not describe the data as cross-cloud; every table is native to "
            "BigQuery."
            if config.no_aws
            else "make the cross-cloud nature explicit when a query spans both clouds."
        )
    )


def build_agent_definition(
    config: LakehouseConfig,
    agent_id: str,
) -> AgentDefinition:
    """Build the single Froyo Lakehouse Analyst agent definition.

    Args:
        config: Resolved lakehouse configuration.
        agent_id: CA API data agent id to assign.

    Returns:
        The fully-populated agent definition.
    """
    native = config.native_dataset
    fed = config.analytics_dataset_id

    if config.no_aws:
        table_type_desc = "Mock customer loyalty"
        sales_table_desc = "Mock daily sales history"
        agent_desc = (
            "Froyo analyst spanning native BigQuery allergen/recipe knowledge "
            "and mock customer loyalty/sales tables."
        )
    else:
        table_type_desc = "AWS-federated Iceberg customer loyalty"
        sales_table_desc = "AWS-federated Iceberg daily sales history"
        agent_desc = (
            "Cross-cloud Froyo lakehouse analyst spanning native BigQuery "
            "allergen/recipe knowledge and AWS-federated customer loyalty and "
            "sales Iceberg tables."
        )

    tables = (
        TableRef(
            native,
            "products",
            "Froyo product catalog: product_id, product_name, category, "
            "launch_date, status.",
        ),
        TableRef(
            native,
            "recipes",
            "Per-product ingredient lists: product_id, product_name, "
            "ingredient_id, ingredient_name, quantity_g.",
        ),
        TableRef(
            native,
            "ingredient_allergens",
            "Allergen declarations from supplier datasheets: ingredient_id, "
            "ingredient_name, allergen, supplier, source_doc.",
        ),
        TableRef(
            native,
            "product_allergens",
            "View joining recipes to ingredient_allergens: product_id, "
            "product_name, allergen, ingredient_name, supplier, source_doc.",
        ),
        TableRef(
            fed,
            config.loyalty_table,
            f"{table_type_desc}: customer_id, region, "
            "loyalty_tier, favorite_flavor, avg_monthly_spend, "
            "soy_sensitive_flag, last_order_date.",
        ),
        TableRef(
            fed,
            config.sales_table,
            f"{sales_table_desc}: sale_date, "
            "product_name, region, units_sold, revenue.",
        ),
    )

    return AgentDefinition(
        agent_id=agent_id,
        description=agent_desc,
        tables=tables,
        system_instruction=_system_instruction(config),
    )


def is_federated_dataset_id(dataset_id: str) -> bool:
    """Return whether a dataset id is a federated ``catalog.namespace`` ref.

    Native BigQuery datasets are a single identifier; federated Lakehouse
    tables use the four-part P.C.N.T form where the dataset id is
    ``<catalog>.<namespace>`` (and therefore contains a dot).

    Args:
        dataset_id: The dataset id from a :class:`TableRef`.

    Returns:
        ``True`` for a federated (catalog.namespace) dataset id.
    """
    return "." in dataset_id


def native_table_ids(
    config: LakehouseConfig,
    agent_id: str = "froyo_lakehouse_agent",
) -> tuple[str, ...]:
    """Return the native (single-dataset) BigQuery table ids for the agent.

    Native tables live in ``config.native_dataset`` and can be targeted by
    Dataplex data profile and data documentation scans.

    Args:
        config: Resolved lakehouse configuration.
        agent_id: Agent id used to build the definition (does not affect the
            table set).

    Returns:
        Ordered, deduplicated native table ids.
    """
    definition = build_agent_definition(config, agent_id)
    seen: dict[str, None] = {}
    for table in definition.tables:
        if not is_federated_dataset_id(table.dataset_id):
            seen.setdefault(table.table_id, None)
    return tuple(seen)


def federated_table_refs(
    config: LakehouseConfig,
    agent_id: str = "froyo_lakehouse_agent",
) -> tuple[tuple[str, str], ...]:
    """Return ``(dataset_id, table_id)`` pairs for federated Iceberg tables.

    Federated tables use the P.C.N.T ``<catalog>.<namespace>`` dataset id. Their
    schemas are owned by the external catalog, so BigQuery DDL (and therefore
    schema-level column descriptions) cannot be written to them.

    Args:
        config: Resolved lakehouse configuration.
        agent_id: Agent id used to build the definition (does not affect the
            table set).

    Returns:
        Ordered, deduplicated ``(dataset_id, table_id)`` pairs.
    """
    definition = build_agent_definition(config, agent_id)
    seen: dict[tuple[str, str], None] = {}
    for table in definition.tables:
        if is_federated_dataset_id(table.dataset_id):
            seen.setdefault((table.dataset_id, table.table_id), None)
    return tuple(seen)
