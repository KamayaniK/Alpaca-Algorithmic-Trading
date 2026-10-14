import unittest
from decimal import Decimal

from mock_order_system import (
    EXECUTION_ENABLED, LIVE_TRADING_ENABLED, PAPER_ORDER_SUBMISSION_ENABLED,
    OrderStatus, SimulatedBroker, size_order, validate_request,
)


class OrderSizingTests(unittest.TestCase):
    def test_caps_single_position_at_13000(self):
        req = size_order("Mahi", "AMZN", "100", "20000")
        self.assertEqual(req.notional, Decimal("13000.000000"))

    def test_fractional_quantity_supported_in_proposal(self):
        req = size_order("Mahi", "AMZN", "400", "1000")
        self.assertLess(req.quantity, Decimal("3.000000"))
        self.assertGreater(req.quantity, Decimal("2"))

    def test_rejects_zero_or_invalid_price(self):
        for price in (0, -1, "abc", float("inf")):
            with self.subTest(price=price), self.assertRaises(ValueError):
                size_order("Mahi", "AMZN", price)

    def test_wrong_member_ticker_rejected(self):
        req = size_order("Mahi", "AMZN", "100")
        wrong = type(req)("Ashima", req.ticker, req.side, req.quantity, req.limit_price)
        with self.assertRaisesRegex(ValueError, "isolation"):
            validate_request(wrong)

    def test_cash_reserve_enforced(self):
        req = size_order("Mahi", "AMZN", "100", "13000")
        with self.assertRaisesRegex(ValueError, "Cash reserve"):
            validate_request(req, current_cash="17000")

    def test_tech_cap_enforced(self):
        req = size_order("Mahi", "AMZN", "100", "13000")
        with self.assertRaisesRegex(ValueError, "Technology"):
            validate_request(req, current_tech_exposure="30000")

    def test_ai_hardware_cap_enforced(self):
        req = size_order("Mahi", "SNDK", "100", "13000")
        with self.assertRaisesRegex(ValueError, "AI hardware"):
            validate_request(req, current_ai_hardware_exposure="12000")

    def test_non_buy_rejected(self):
        req = size_order("Mahi", "AMZN", "100")
        wrong = type(req)(req.member, req.ticker, "sell", req.quantity, req.limit_price)
        with self.assertRaisesRegex(ValueError, "BUY"):
            validate_request(wrong)


class MockLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.broker = SimulatedBroker()
        self.request = size_order("Mahi", "AMZN", "100", "1000")

    def test_mock_submission_and_full_fill(self):
        order = self.broker.submit(self.request)
        self.assertEqual(order.status, OrderStatus.ACCEPTED)
        filled = self.broker.partial_fill(order.order_id, self.request.quantity)
        self.assertEqual(filled.status, OrderStatus.FILLED)

    def test_partial_fill_then_cancel(self):
        order = self.broker.submit(self.request)
        self.broker.partial_fill(order.order_id, Decimal("2"))
        self.assertEqual(order.status, OrderStatus.PARTIALLY_FILLED)
        canceled = self.broker.cancel(order.order_id)
        self.assertEqual(canceled.status, OrderStatus.CANCELED)
        self.assertEqual(canceled.filled_quantity, Decimal("2"))

    def test_mock_rejection(self):
        self.broker.reject_next_reason = "simulated buying-power rejection"
        order = self.broker.submit(self.request)
        self.assertEqual(order.status, OrderStatus.REJECTED)
        self.assertIn("buying-power", order.rejection_reason)

    def test_cannot_overfill(self):
        order = self.broker.submit(self.request)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.broker.partial_fill(order.order_id, self.request.quantity + Decimal("1"))

    def test_cannot_cancel_filled_order(self):
        order = self.broker.submit(self.request)
        self.broker.partial_fill(order.order_id, self.request.quantity)
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.broker.cancel(order.order_id)

    def test_unknown_order_id_fails(self):
        with self.assertRaises(KeyError):
            self.broker.get_order("REAL-ORDER-ID")

    def test_safety_flags_remain_off(self):
        self.assertFalse(EXECUTION_ENABLED)
        self.assertFalse(PAPER_ORDER_SUBMISSION_ENABLED)
        self.assertFalse(LIVE_TRADING_ENABLED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
