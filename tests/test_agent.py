import unittest

from opspilot.agent import DevOpsAgent
from opspilot.models import Risk


class DevOpsAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = DevOpsAgent()

    def test_routes_docker_status(self) -> None:
        operation = self.agent.plan("show docker container status")
        self.assertIsNotNone(operation)
        self.assertEqual(operation.name, "docker-containers")

    def test_routes_namespaced_kubernetes_pods(self) -> None:
        operation = self.agent.plan("show k8s pods in namespace production")
        self.assertIsNotNone(operation)
        self.assertEqual(
            operation.command,
            ("kubectl", "get", "pods", "-n", "production"),
        )

    def test_restart_is_mutating(self) -> None:
        operation = self.agent.plan("restart deployment api in namespace production")
        self.assertIsNotNone(operation)
        self.assertEqual(operation.risk, Risk.MUTATING)
        self.assertEqual(
            operation.command,
            (
                "kubectl",
                "rollout",
                "restart",
                "deployment/api",
                "-n",
                "production",
            ),
        )

    def test_unknown_request_is_not_executed(self) -> None:
        self.assertIsNone(self.agent.plan("delete everything"))


if __name__ == "__main__":
    unittest.main()

