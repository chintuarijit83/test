"""
Configuration for the Rule Agent components.

Everything AWS-specific is a placeholder here - fill in real values via
environment variables (or a .env file) once each Knowledge Base and
Redshift access is actually provisioned. Mock mode is set PER SERVICE
(not one global switch) because rollout is incremental - e.g. Rules KB
might be real while Metrics/Schema KB and Redshift are still mocked.
"""

import os

from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# --- Knowledge Bases (Bedrock) - PLACEHOLDER: fill in once provisioned ---
RULES_KB_ID = os.environ.get("RULES_KB_ID")  # e.g. "ABCD1234EF"
METRICS_SCHEMA_KB_ID = os.environ.get("METRICS_SCHEMA_KB_ID")
HISTORICAL_INSIGHTS_KB_ID = os.environ.get("HISTORICAL_INSIGHTS_KB_ID")

# --- Redshift (Data API) - PLACEHOLDER: fill in once provisioned ---
REDSHIFT_WORKGROUP = os.environ.get("REDSHIFT_WORKGROUP")  # serverless
REDSHIFT_CLUSTER_ID = os.environ.get("REDSHIFT_CLUSTER_ID")  # provisioned, alt to workgroup
REDSHIFT_DATABASE = os.environ.get("REDSHIFT_DATABASE", "dev")
REDSHIFT_SECRET_ARN = os.environ.get("REDSHIFT_SECRET_ARN")


def _flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).lower() != "false"


# --- Mode, per service ---
# Each defaults to mocked (true). Flip only the ones you've actually
# provisioned - e.g. set RULES_KB_MOCK=false once RULES_KB_ID is real,
# while METRICS_SCHEMA_KB_MOCK and REDSHIFT_MOCK stay true.
# MOCK_MODE (legacy/global) still works as a fallback default for all three.
MOCK_MODE = _flag("MOCK_MODE")
RULES_KB_MOCK = _flag("RULES_KB_MOCK", "true" if MOCK_MODE else "false")
METRICS_SCHEMA_KB_MOCK = _flag("METRICS_SCHEMA_KB_MOCK", "true" if MOCK_MODE else "false")
REDSHIFT_MOCK = _flag("REDSHIFT_MOCK", "true" if MOCK_MODE else "false")
