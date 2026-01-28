import argparse
import os
import sys
import yaml
import re
from google.cloud import bigquery
import vertexai
from vertexai.generative_models import GenerativeModel


def get_table_schema(client, table_id):
    """Fetches table schema as a simplified string."""
    try:
        table = client.get_table(table_id)
        schema = []
        for field in table.schema:
            schema.append(f"{field.name} ({field.field_type})")
        return ", ".join(schema)
    except Exception as e:
        return f"Error fetching schema: {str(e)}"


def generate_validation_script(prod_table, pr_table):
    """
    Asks Gemini to write a validation script based on the agent definition.
    """

    # 1. Load Agent Context
    try:
        with open(".agents/agents/validation_subagent.md", "r") as f:
            agent_prompt = f.read()
        with open("migration_validator/VALIDATION_COOKBOOK.md", "r") as f:
            cookbook = f.read()
    except FileNotFoundError:
        print("❌ Error: Agent definitions not found.")
        sys.exit(1)

    # 2. Get Schemas
    bq_client = bigquery.Client()
    prod_schema = get_table_schema(bq_client, prod_table)
    pr_schema = get_table_schema(bq_client, pr_table)

    # 3. Construct Prompt
    full_prompt = f"""
    {agent_prompt}

    ---
    CONTEXT:
    {cookbook}

    ---
    TASK:
    You are running in a CI/CD environment.
    Write a standalone Python script to validate the Data Parity between the following two tables.
    
    PROD TABLE (Baseline): {prod_table}
    Schema: {prod_schema}

    PR TABLE (Candidate): {pr_table}
    Schema: {pr_schema}

    REQUIREMENTS:
    1. Use the `google-cloud-bigquery` library.
    2. Compare Row Counts (Threshold: 1%).
    3. Compare Schema (Columns must match).
    4. Validate Primary Key Uniqueness (if identifiable).
    5. Check specific metrics (SUM/AVG) for numeric columns if they exist.
    6. Output must be a standalone, executable Python script.
    7. The script must print "✅ Validation Passed" or "❌ Validation Failed" at the end.
    8. Do NOT use markdown formatting (```python) in your response, just return the raw code.
    
    """

    # 4. Call Vertex AI
    print("🧠 Asking Gemini 3 Pro to generate validation logic...")
    # Initialize Vertex AI
    # Defaults to "us-central1" if not set, but usually safe to assume from env
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or prod_table.split(".")[0]
    vertexai.init(project=project_id, location="us-central1")

    model = GenerativeModel("gemini-3-pro-preview")
    response = model.generate_content(full_prompt)

    # 5. Extract Code
    code = response.text
    # Clean up markdown if the model disregarded the instruction
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[1].split("```")[0]

    return code.strip()


def main():
    parser = argparse.ArgumentParser(description="AI Validation Runner for CI/CD")
    parser.add_argument("--prod", required=True, help="Production Table ID")
    parser.add_argument("--pr", required=True, help="PR Table ID")
    args = parser.parse_args()

    # Generate the script
    script_content = generate_validation_script(args.prod, args.pr)

    # Save to a temporary file
    script_path = "scripts/temp_validation_job.py"
    with open(script_path, "w") as f:
        f.write(script_content)

    print(f"💾 Validation script generated at: {script_path}")
    print("▶️ Executing validation script...\n")

    # Execute the generated script
    try:
        # Pass current env to the subprocess so it inherits creds
        # Use uv run to ensure dependencies are found
        result = os.system(f"uv run python {script_path}")
        if result != 0:
            sys.exit(1)
    except Exception as e:
        print(f"❌ Execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
