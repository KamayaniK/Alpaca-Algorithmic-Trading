import unittest

TEST_MODULES = [
    "test_mcp_client",
    "test_mcp_strategy_client",
    "test_news_gate",
    "test_portfolio_risk",
    "test_strategy_agent",
    "test_strategy_integration",
    "test_strategy_workflow",
    "test_trading_strategy",
]


def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for module_name in TEST_MODULES:
        suite.addTests(loader.loadTestsFromName(module_name))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
