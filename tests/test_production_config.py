import os
import subprocess
import sys


def test_production_requires_secrets_manager_reference():
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "production",
            "SAP_WRITE_ENABLED": "true",
            "JWT_SECRET_KEY": "test-only-long-secret",
        }
    )
    env.pop("SECRETS_MANAGER_SECRET_ID", None)
    result = subprocess.run(
        [sys.executable, "-c", "import backend.src.config"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )
    assert result.returncode != 0
    assert "SECRETS_MANAGER_SECRET_ID" in (result.stderr + result.stdout)


def test_staging_rejects_production_resource_reference():
    env = os.environ.copy()
    env.update(
        {
            "ENVIRONMENT": "staging",
            "DYNAMODB_TABLE": "AutoReplenish_ProductionTable",
        }
    )
    env.pop("SECRETS_MANAGER_SECRET_ID", None)
    result = subprocess.run(
        [sys.executable, "-c", "import backend.src.config"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )
    assert result.returncode != 0
    assert "Environment boundary violation" in (result.stderr + result.stdout)


def test_environment_uses_isolated_default_table_name():
    env = os.environ.copy()
    env.pop("DYNAMODB_TABLE", None)
    env["ENVIRONMENT"] = "staging"
    env["SECRETS_MANAGER_SECRET_ID"] = "test-only-secret-reference"
    script = (
        "import boto3; "
        "boto3.client=lambda *a, **k: type('C', (), "
        "{'get_secret_value': lambda self, **kw: {'SecretString': '{}'}})(); "
        "import backend.src.config as c; print(c.DYNAMODB_TABLE)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "AutoReplenish_StagingTable"
