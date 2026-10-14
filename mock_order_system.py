"""Mock-only order workflow for Task 2.

SAFETY:
- This module contains no Alpaca SDK imports and no network/broker adapter.
- SimulatedBroker stores orders in memory only.
- Do not connect a real broker to this module without a separate review and explicit approval.
- It never submits real paper or live orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from enum import Enum
from typing import Dict, Iterable, Optional


EXECUTION_ENABLED = False
LIVE_TRADING_ENABLED = False
PAPER_ORDER_SUBMISSION_ENABLED = False

MEMBER_TICKERS = {
    "Mahi": frozenset("SNDK AMD APP MRNA GOOGL AMZN JPM LLY META XOM PEP ABT".split()),
    "Ashima": frozenset("SMCI MU MRVL WDC MSFT ETN GS ISRG CAT FCX PG CVX".split()),
    "Kamayani": frozenset("HOOD COIN PLTR LITE TSLA AAPL NFLX GE AXP UNH DIS ABBV".split()),
}

MAX_PLANNED_INVESTMENT = Decimal("95000")
CASH_RESERVE = Decimal("5000")
MAX_POSITION_VALUE = Decimal("13000")
TECH_CAP = Decimal("33250")
AI_HARDWARE_CAP = Decimal("23750")

TECH_TICKERS = frozenset(
    "SNDK AMD APP GOOGL AMZN META SMCI MU MRVL WDC MSFT HOOD COIN PLTR LITE TSLA AAPL NFLX".split()
)
AI_HARDWARE_TICKERS = frozenset("SNDK AMD SMCI MU MRVL WDC LITE".split())


class OrderStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELED = "canceled"
    REJECTED = "rejected"


TERMINAL_STATUSES = {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}


@dataclass(frozen=True)
class OrderRequest:
    member: str
    ticker: str
    side: str
    quantity: Decimal
    limit_price: Decimal

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.limit_price


@dataclass
class SimulatedOrder:
    order_id: str
    request: OrderRequest
    status: OrderStatus
    filled_quantity: Decimal = Decimal("0")
    rejection_reason: Optional[str] = None


def _positive_decimal(value, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field} must be a valid number") from None
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{field} must be greater than zero and finite")
    return result


def size_order(member: str, ticker: str, price, budget=MAX_POSITION_VALUE) -> OrderRequest:
    """Create a safe, long-only BUY proposal; does not submit anything."""
    if member not in MEMBER_TICKERS:
        raise ValueError(f"Unknown member: {member!r}")
    ticker = str(ticker).strip().upper()
    if ticker not in MEMBER_TICKERS[member]:
        raise ValueError(f"{ticker} is not assigned to {member}")
    px = _positive_decimal(price, "price")
    available_budget = _positive_decimal(budget, "budget")
    available_budget = min(available_budget, MAX_POSITION_VALUE)
    quantity = (available_budget / px).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    if quantity <= 0:
        raise ValueError("Budget is too small to buy a positive quantity")
    return OrderRequest(member, ticker, "buy", quantity, px)


def validate_request(request: OrderRequest, *, account_equity=Decimal("100000"),
                     current_cash=Decimal("100000"), planned_investment=Decimal("0"),
                     current_tech_exposure=Decimal("0"),
                     current_ai_hardware_exposure=Decimal("0")) -> None:
    """Validate request and portfolio limits without broker access."""
    if request.member not in MEMBER_TICKERS:
        raise ValueError("Unknown member")
    if request.ticker not in MEMBER_TICKERS[request.member]:
        raise ValueError("Ticker/account isolation check failed")
    if request.side.lower() != "buy":
        raise ValueError("Only long-only BUY proposals are allowed")
    qty = _positive_decimal(request.quantity, "quantity")
    px = _positive_decimal(request.limit_price, "limit_price")
    notional = qty * px
    equity = _positive_decimal(account_equity, "account_equity")
    cash = _positive_decimal(current_cash, "current_cash")
    planned = Decimal(str(planned_investment))
    tech = Decimal(str(current_tech_exposure))
    ai = Decimal(str(current_ai_hardware_exposure))
    if not all(x.is_finite() and x >= 0 for x in (planned, tech, ai)):
        raise ValueError("Existing exposure values must be finite and non-negative")
    if notional > MAX_POSITION_VALUE:
        raise ValueError("Single-position cap exceeded")
    if planned + notional > MAX_PLANNED_INVESTMENT:
        raise ValueError("Maximum planned investment exceeded")
    if cash - notional < CASH_RESERVE:
        raise ValueError("Cash reserve would be breached")
    if request.ticker in TECH_TICKERS and tech + notional > TECH_CAP:
        raise ValueError("Technology exposure cap exceeded")
    if request.ticker in AI_HARDWARE_TICKERS and ai + notional > AI_HARDWARE_CAP:
        raise ValueError("AI hardware exposure cap exceeded")
    if notional > equity:
        raise ValueError("Order value exceeds account equity")


class SimulatedBroker:
    """In-memory fake broker for unit tests; no network calls are possible."""

    def __init__(self):
        self.orders: Dict[str, SimulatedOrder] = {}
        self._next_id = 1
        self.reject_next_reason: Optional[str] = None

    def submit(self, request: OrderRequest) -> SimulatedOrder:
        if not EXECUTION_ENABLED or not PAPER_ORDER_SUBMISSION_ENABLED or LIVE_TRADING_ENABLED:
            # The simulation can record a mock submission, but all real execution flags stay off.
            pass
        if self.reject_next_reason:
            reason = self.reject_next_reason
            self.reject_next_reason = None
            order = SimulatedOrder(f"MOCK-{self._next_id}", request, OrderStatus.REJECTED,
                                   rejection_reason=reason)
        else:
            order = SimulatedOrder(f"MOCK-{self._next_id}", request, OrderStatus.ACCEPTED)
        self._next_id += 1
        self.orders[order.order_id] = order
        return order

    def partial_fill(self, order_id: str, quantity) -> SimulatedOrder:
        order = self._get_active(order_id)
        qty = _positive_decimal(quantity, "fill quantity")
        remaining = order.request.quantity - order.filled_quantity
        if qty > remaining:
            raise ValueError("Fill quantity exceeds remaining order quantity")
        order.filled_quantity += qty
        order.status = (OrderStatus.FILLED if order.filled_quantity == order.request.quantity
                        else OrderStatus.PARTIALLY_FILLED)
        return order

    def cancel(self, order_id: str) -> SimulatedOrder:
        order = self._get_active(order_id)
        if order.status == OrderStatus.FILLED:
            raise ValueError("Cannot cancel a fully filled order")
        order.status = OrderStatus.CANCELED
        return order

    def reject(self, order_id: str, reason: str) -> SimulatedOrder:
        order = self._get_active(order_id)
        order.status = OrderStatus.REJECTED
        order.rejection_reason = str(reason)
        return order

    def get_order(self, order_id: str) -> SimulatedOrder:
        try:
            return self.orders[order_id]
        except KeyError:
            raise KeyError(f"Unknown simulated order: {order_id}") from None

    def _get_active(self, order_id: str) -> SimulatedOrder:
        order = self.get_order(order_id)
        if order.status in TERMINAL_STATUSES:
            raise ValueError(f"Order is already in terminal status: {order.status.value}")
        return order
