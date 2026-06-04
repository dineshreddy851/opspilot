import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class WebInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (WEB / "static" / "index.html").read_text(encoding="utf-8")
        cls.styles = (WEB / "static" / "styles.css").read_text(encoding="utf-8")
        cls.app = (WEB / "src" / "main.ts").read_text(encoding="utf-8")
        cls.config = (WEB / "static" / "config.js.example").read_text(encoding="utf-8")
        cls.package = (WEB / "package.json").read_text(encoding="utf-8")
        cls.all_browser_source = "\n".join(
            (cls.index, cls.styles, cls.app, cls.config)
        )

    def test_required_reviewer_interface_is_present(self):
        for element_id in (
            "sign-in",
            "request",
            "outcome-tool",
            "outcome-risk",
            "outcome-result",
            "approval-status",
            "timeline",
        ):
            self.assertIn(f'id="{element_id}"', self.index)
        self.assertIn("TypeScript", (WEB / "README.md").read_text(encoding="utf-8"))

    def test_cognito_sign_in_uses_authorization_code_with_pkce(self):
        self.assertIn('response_type: "code"', self.app)
        self.assertIn('code_challenge_method: "S256"', self.app)
        self.assertIn("crypto.subtle.digest", self.app)
        self.assertIn("/oauth2/authorize", self.app)
        self.assertIn("/oauth2/token", self.app)
        self.assertIn("sessionStorage", self.app)
        self.assertNotIn("localStorage", self.app)

    def test_interface_calls_only_scoped_opspilot_api_routes(self):
        for route in (
            '"/requests"',
            '"/controlled-requests"',
            '"/timeline"',
            "`/approvals/${encodeURIComponent(activeApprovalRequestId)}`",
        ):
            self.assertIn(route, self.app)
        self.assertIn("Run read-only request", self.index)
        self.assertIn("Request controlled approval", self.index)

    def test_browser_source_contains_no_aws_credentials_or_callback_secrets(self):
        forbidden = (
            r"AWS_ACCESS_KEY_ID",
            r"AWS_SECRET_ACCESS_KEY",
            r"SECRET_ACCESS_KEY",
            r"task_token",
            r"taskToken",
        )
        for pattern in forbidden:
            self.assertNotRegex(self.all_browser_source, pattern)
        self.assertNotRegex(
            self.config,
            r"(?i)(password|clientSecret|secretKey)\s*:",
        )

    def test_untrusted_api_content_is_rendered_as_text(self):
        self.assertIn("textContent", self.app)
        self.assertIn("replaceChildren", self.app)
        self.assertNotIn("innerHTML", self.app)

    def test_web_build_is_dependency_light_and_typescript_based(self):
        self.assertIn('"typescript"', self.package)
        self.assertIn('"typecheck": "tsc --noEmit"', self.package)
        self.assertFalse(re.search(r'"(react|angular|vue|aws-sdk)"\s*:', self.package))


if __name__ == "__main__":
    unittest.main()
