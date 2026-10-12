import unittest

from test_trading_strategy import TradingStrategyTests
from test_strategy_integration import StrategyIntegrationTests
from test_strategy_agent import StrategyAgentTests
from test_mcp_strategy_client import MCPStrategyClientTests
from test_strategy_workflow import StrategyWorkflowTests


if __name__ == "__main__":
    suite = unittest.TestSuite()

    for test_class in (
        TradingStrategyTests,
        StrategyIntegrationTests,
        StrategyAgentTests,
        MCPStrategyClientTests,
        StrategyWorkflowTests,
    ):
        suite.addTests(
            unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
        )

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
