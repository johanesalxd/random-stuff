"""Allow running bq_discovery as a module: python -m bq_discovery."""

from bq_discovery.cli import main

raise SystemExit(main())
