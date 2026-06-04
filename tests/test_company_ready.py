import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
WORKFLOWS = ROOT / ".github" / "workflows"


class CompanyReadyTests(unittest.TestCase):
    def test_required_company_documents_exist_and_state_limitations(self):
        required = (
            "architecture.md",
            "threat-model.md",
            "runbook.md",
            "demo-script.md",
            "cost-controls.md",
        )
        for name in required:
            path = DOCS / name
            self.assertTrue(path.is_file(), name)
            self.assertGreater(len(path.read_text(encoding="utf-8")), 600, name)

        combined = "\n".join(
            (DOCS / name).read_text(encoding="utf-8").lower() for name in required
        )
        self.assertIn("limitation", combined)
        self.assertIn("prompt injection", combined)
        self.assertIn("excessive permissions", combined)
        self.assertIn("investigate", combined)

    def test_demo_script_covers_five_minute_evidence_path(self):
        demo = (DOCS / "demo-script.md").read_text(encoding="utf-8").lower()
        for evidence in (
            "read-only",
            "destructive",
            "approval",
            "terraform",
            "tests",
            "github actions",
            "cloudwatch",
            "dynamodb",
            "cloudtrail",
        ):
            self.assertIn(evidence, demo)

    def test_pull_request_workflow_runs_tests_web_and_terraform_checks(self):
        workflow = (WORKFLOWS / "test.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn("python -m unittest discover", workflow)
        self.assertIn("npm run build", workflow)
        self.assertIn("terraform fmt -check -recursive", workflow)
        self.assertIn("terraform validate", workflow)

    def test_deployment_workflow_uses_oidc_and_no_access_key_secrets(self):
        workflow = (WORKFLOWS / "deploy-dev.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("environment: development", workflow)
        self.assertIn("aws-actions/configure-aws-credentials@v4", workflow)
        self.assertIn("role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}", workflow)
        self.assertIn("terraform plan -input=false -out=tfplan", workflow)
        self.assertIn("terraform apply -input=false -auto-approve tfplan", workflow)
        self.assertNotRegex(
            workflow,
            re.compile(r"AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY)", re.IGNORECASE),
        )


if __name__ == "__main__":
    unittest.main()
