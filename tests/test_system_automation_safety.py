"""
Automation Safety Tests

Verifies that the GitHub Actions workflow is correctly configured
and references valid files and commands.

Test data and expected values are defined in tests/test_config.py.
Update that file to change test parameters without modifying this script.
"""

import pytest
import os
from pathlib import Path
import re

# Import externalized test configuration
from tests.test_config import CONFIG, EXPECTED, WORKFLOW


# Project root (tests/ is one level below root)
PROJECT_ROOT = Path(__file__).parent.parent


def get_workflow_content():
    """Load the GitHub Actions workflow file content."""
    workflow_path = PROJECT_ROOT / WORKFLOW["file_path"]
    if not workflow_path.exists():
        pytest.skip("GitHub Actions workflow not found")
    return workflow_path.read_text()


class TestWorkflowFileValidity:
    """Tests that the workflow file exists and is valid YAML structure."""
    
    def test_workflow_file_exists(self):
        """
        GIVEN: The repository
        WHEN: Workflow path is checked
        THEN: daily-digest.yml exists in .github/workflows/
        """
        workflow_path = PROJECT_ROOT / WORKFLOW["file_path"]
        
        assert workflow_path.exists(), \
            f"Workflow file should exist at {workflow_path}"
    
    def test_workflow_has_name(self):
        """
        GIVEN: The workflow file
        WHEN: Content is examined
        THEN: Has a 'name' field
        """
        content = get_workflow_content()
        
        assert "name:" in content, "Workflow should have a name"
    
    def test_workflow_has_on_trigger(self):
        """
        GIVEN: The workflow file
        WHEN: Content is examined
        THEN: Has an 'on:' trigger section
        """
        content = get_workflow_content()
        
        assert "on:" in content, "Workflow should have trigger configuration"


class TestScheduledExecution:
    """Tests for scheduled execution configuration."""
    
    def test_schedule_trigger_present(self):
        """
        GIVEN: The workflow file
        WHEN: Content is examined
        THEN: Contains schedule trigger
        """
        content = get_workflow_content()
        
        assert "schedule:" in content, "Workflow should have schedule trigger"
    
    def test_cron_expression_present(self):
        """
        GIVEN: The workflow file
        WHEN: Content is examined
        THEN: Contains a cron expression
        """
        content = get_workflow_content()
        
        assert "cron:" in content, "Workflow should have cron expression"
    
    def test_cron_expression_has_valid_format(self):
        """
        GIVEN: The workflow cron expression
        WHEN: Format is validated
        THEN: Matches valid cron pattern (5 fields)
        """
        content = get_workflow_content()
        
        # Extract cron expression
        cron_match = re.search(r"cron:\s*'([^']+)'", content)
        
        assert cron_match, "Should have cron expression in quotes"
        
        cron_expr = cron_match.group(1)
        fields = cron_expr.split()
        
        assert len(fields) == 5, \
            f"Cron expression should have 5 fields, got {len(fields)}: {cron_expr}"


class TestManualDispatch:
    """Tests for manual dispatch (workflow_dispatch) configuration."""
    
    def test_workflow_dispatch_present(self):
        """
        GIVEN: The workflow file
        WHEN: Content is examined
        THEN: Contains workflow_dispatch trigger
        """
        content = get_workflow_content()
        
        assert "workflow_dispatch:" in content, \
            "Workflow should support manual triggering via workflow_dispatch"
    
    def test_dispatch_has_inputs(self):
        """
        GIVEN: The workflow_dispatch configuration
        WHEN: Content is examined
        THEN: Has configurable inputs
        """
        content = get_workflow_content()
        
        # After workflow_dispatch there should be inputs
        assert "inputs:" in content, \
            "workflow_dispatch should have configurable inputs"
    
    def test_dry_run_input_available(self):
        """
        GIVEN: The workflow_dispatch inputs
        WHEN: Content is examined
        THEN: dry_run input is available
        """
        content = get_workflow_content()
        
        assert "dry_run:" in content, \
            "Should have dry_run input for safe testing"


class TestRequiredSecrets:
    """Tests that required secrets are documented and referenced."""
    
    def test_airtable_api_key_documented(self):
        """
        GIVEN: The workflow file
        WHEN: Comments are examined
        THEN: AIRTABLE_API_KEY is documented as required
        """
        content = get_workflow_content()
        
        assert "AIRTABLE_API_KEY" in content, \
            "Should document/reference AIRTABLE_API_KEY secret"
    
    def test_airtable_base_id_documented(self):
        """
        GIVEN: The workflow file
        WHEN: Comments are examined
        THEN: AIRTABLE_BASE_ID is documented as required
        """
        content = get_workflow_content()
        
        assert "AIRTABLE_BASE_ID" in content, \
            "Should document/reference AIRTABLE_BASE_ID secret"
    
    def test_secrets_referenced_correctly(self):
        """
        GIVEN: The workflow file
        WHEN: Secret references are examined
        THEN: Uses correct ${{ secrets.NAME }} syntax
        """
        content = get_workflow_content()
        
        # Should reference secrets with correct syntax
        assert "${{ secrets.AIRTABLE_API_KEY }}" in content, \
            "Should reference AIRTABLE_API_KEY with correct syntax"
        assert "${{ secrets.AIRTABLE_BASE_ID }}" in content, \
            "Should reference AIRTABLE_BASE_ID with correct syntax"


class TestWorkflowCommands:
    """Tests that workflow runs valid commands."""
    
    def test_references_main_py(self):
        """
        GIVEN: The workflow file
        WHEN: Run steps are examined
        THEN: References main.py as entry point
        """
        content = get_workflow_content()
        
        assert "main.py" in content, \
            "Workflow should run main.py"
    
    def test_references_requirements_txt(self):
        """
        GIVEN: The workflow file
        WHEN: Run steps are examined
        THEN: References requirements.txt for dependencies
        """
        content = get_workflow_content()
        
        assert "requirements.txt" in content, \
            "Workflow should install from requirements.txt"
    
    def test_main_py_exists(self):
        """
        GIVEN: The workflow references main.py
        WHEN: File system is checked
        THEN: main.py exists
        """
        main_path = PROJECT_ROOT / "main.py"
        
        assert main_path.exists(), \
            "main.py must exist for workflow to succeed"
    
    def test_requirements_txt_exists(self):
        """
        GIVEN: The workflow references requirements.txt
        WHEN: File system is checked
        THEN: requirements.txt exists
        """
        req_path = PROJECT_ROOT / "requirements.txt"
        
        assert req_path.exists(), \
            "requirements.txt must exist for workflow to succeed"


class TestWorkflowJobs:
    """Tests for workflow job configuration."""
    
    def test_has_jobs_section(self):
        """
        GIVEN: The workflow file
        WHEN: Content is examined
        THEN: Has jobs section
        """
        content = get_workflow_content()
        
        assert "jobs:" in content, "Workflow should have jobs section"
    
    def test_uses_ubuntu_runner(self):
        """
        GIVEN: The workflow file
        WHEN: Runner is examined
        THEN: Uses ubuntu-latest (or similar)
        """
        content = get_workflow_content()
        
        assert "ubuntu" in content.lower(), \
            "Workflow should use ubuntu runner"
    
    def test_sets_up_python(self):
        """
        GIVEN: The workflow file
        WHEN: Steps are examined
        THEN: Sets up Python
        """
        content = get_workflow_content()
        
        assert "setup-python" in content or "python" in content.lower(), \
            "Workflow should set up Python"
    
    def test_installs_dependencies(self):
        """
        GIVEN: The workflow file
        WHEN: Steps are examined
        THEN: Installs pip dependencies
        """
        content = get_workflow_content()
        
        assert "pip install" in content, \
            "Workflow should install dependencies via pip"


class TestWorkflowDocumentation:
    """Tests that workflow is properly documented."""
    
    def test_has_comments_explaining_secrets(self):
        """
        GIVEN: The workflow file
        WHEN: Content is examined
        THEN: Has comments explaining how to configure secrets
        """
        content = get_workflow_content()
        
        # Should have instructional comments
        assert "Required" in content or "required" in content, \
            "Should indicate which secrets are required"
    
    def test_has_instructions_for_manual_trigger(self):
        """
        GIVEN: The workflow file
        WHEN: Content is examined
        THEN: Documents manual triggering capability
        """
        content = get_workflow_content()
        
        # Should mention manual/dispatch somewhere
        has_manual_docs = (
            "manual" in content.lower() or
            "dispatch" in content.lower() or
            "Actions tab" in content
        )
        
        assert has_manual_docs, \
            "Should document manual trigger capability"

