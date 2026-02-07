"""
Arbitrage engine for detecting and calculating arbitrage opportunities.
Implements the core "Statistical Arbitrage" logic for binary options.
"""

import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from config import Config
from market_manager import Market
from websocket_manager import WebSocketManager


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity."""
    
    market: Market
    yes_price: float
    no_price: float
    implied_sum: float
    expected_profit_pct: float
    yes_size: float
    no_size: float
    total_investment: float
    timestamp: float
    
    def __repr__(self) -> str:
        return (
            f"ArbitrageOpportunity("
            f"market='{self.market.question[:40]}...', "
            f"implied_sum={self.implied_sum:.4f}, "
            f"profit={self.expected_profit_pct * 100:.2f}%)"
        )


class ArbitrageEngine:
    """
    Detects and calculates arbitrage opportunities in binary options markets.
    
    Core Strategy:
    - Binary option: YES + NO must equal 1.00 at resolution
    - If we can buy both for < 0.98 (trigger threshold), we profit
    - Example: YES @ 0.47 + NO @ 0.49 = 0.96 → 4% profit (risk-free)
    """
    
    def __init__(self, config: Config, ws_manager: WebSocketManager):
        """
        Initialize arbitrage engine.
        
        Args:
            config: Configuration object
            ws_manager: WebSocket manager for orderbook data
        """
        self.config = config
        self.ws_manager = ws_manager
        
        # Opportunity tracking
        self.last_opportunity_time: Dict[str, float] = {}
        self.opportunity_cooldown = config.opportunity_cooldown  # Seconds between opportunities for same market
        
        logger.info("ArbitrageEngine initialized")
        logger.info(f"Trigger threshold: {config.trigger_threshold}")
        logger.info(f"Min profit threshold: {config.min_profit_threshold * 100:.1f}%")
    
    def check_arbitrage_opportunity(
        self,
        market: Market
    ) -> Optional[ArbitrageOpportunity]:
        """
        Check if a market has an arbitrage opportunity.
        
        Args:
            market: Market to check
        
        Returns:
            ArbitrageOpportunity if found, None otherwise
        """
        # Get best ask prices for YES and NO tokens
        prices = self.ws_manager.get_best_prices(
            market.yes_token_id,
            market.no_token_id
        )
        
        if not prices:
            return None
        
        yes_ask = prices["yes_ask"]
        no_ask = prices["no_ask"]
        
        # Calculate implied probability sum
        implied_sum = yes_ask + no_ask
        
        # Check if sum is below trigger threshold
        if implied_sum >= self.config.trigger_threshold:
            # No arbitrage opportunity
            return None
        
        # Calculate expected profit
        # When market resolves, we get 1.00 for the winning side
        # Since we buy both, we're guaranteed to get 1.00 total
        expected_payout = 1.00
        expected_profit_pct = (expected_payout - implied_sum) / implied_sum
        
        # Check if profit meets minimum threshold
        if expected_profit_pct < self.config.min_profit_threshold:
            return None
        
        # Check cooldown (avoid spam for same market)
        now = time.time()
        last_opp = self.last_opportunity_time.get(market.condition_id, 0)
        if now - last_opp < self.opportunity_cooldown:
            return None
        
        # Calculate position sizes (delta-neutral)
        # We want to invest proportionally to maintain equal expected value
        total_investment = self.config.fixed_investment_amount
        
        # Calculate optimal allocation
        yes_investment = total_investment * (yes_ask / implied_sum)
        no_investment = total_investment * (no_ask / implied_sum)
        
        # Size in tokens (investment / price)
        yes_size = yes_investment / yes_ask
        no_size = no_investment / no_ask
        
        # Record opportunity time
        self.last_opportunity_time[market.condition_id] = now
        
        # Create opportunity object
        opportunity = ArbitrageOpportunity(
            market=market,
            yes_price=yes_ask,
            no_price=no_ask,
            implied_sum=implied_sum,
            expected_profit_pct=expected_profit_pct,
            yes_size=yes_size,
            no_size=no_size,
            total_investment=total_investment,
            timestamp=now,
        )
        
        logger.success(
            f"🎯 ARBITRAGE OPPORTUNITY DETECTED!\n"
            f"  Market: {market.question}\n"
            f"  YES Price: ${yes_ask:.4f} | NO Price: ${no_ask:.4f}\n"
            f"  Implied Sum: {implied_sum:.4f} (Threshold: {self.config.trigger_threshold})\n"
            f"  Expected Profit: {expected_profit_pct * 100:.2f}%\n"
            f"  Investment: ${total_investment:.2f} "
            f"(YES: ${yes_investment:.2f}, NO: ${no_investment:.2f})\n"
            f"  Position Size: {yes_size:.2f} YES + {no_size:.2f} NO tokens"
        )
        
        return opportunity
    
    def scan_all_markets(self, markets: list[Market]) -> list[ArbitrageOpportunity]:
        """
        Scan all markets for arbitrage opportunities.
        
        Args:
            markets: List of markets to scan
        
        Returns:
            List of detected arbitrage opportunities
        """
        opportunities = []
        
        for market in markets:
            opportunity = self.check_arbitrage_opportunity(market)
            if opportunity:
                opportunities.append(opportunity)
        
        if opportunities:
            logger.info(f"Found {len(opportunities)} arbitrage opportunities")
        
        return opportunities
    
    def validate_opportunity(
        self,
        opportunity: ArbitrageOpportunity,
        max_age_seconds: float = 2.0
    ) -> bool:
        """
        Validate that an opportunity is still valid.
        
        Args:
            opportunity: Opportunity to validate
            max_age_seconds: Maximum age in seconds
        
        Returns:
            True if still valid, False otherwise
        """
        # Check age
        age = time.time() - opportunity.timestamp
        if age > max_age_seconds:
            logger.warning(
                f"Opportunity expired: {age:.2f}s > {max_age_seconds}s"
            )
            return False
        
        # Re-check prices (they might have changed)
        prices = self.ws_manager.get_best_prices(
            opportunity.market.yes_token_id,
            opportunity.market.no_token_id
        )
        
        if not prices:
            logger.warning("Orderbook data no longer available")
            return False
        
        # Check if prices are still favorable
        current_sum = prices["yes_ask"] + prices["no_ask"]
        if current_sum >= self.config.trigger_threshold:
            logger.warning(
                f"Prices moved unfavorably: "
                f"{opportunity.implied_sum:.4f} → {current_sum:.4f}"
            )
            return False
        
        return True
    
    def calculate_expected_pnl(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, float]:
        """
        Calculate expected P&L for an opportunity.
        
        Args:
            opportunity: Arbitrage opportunity
        
        Returns:
            Dictionary with P&L breakdown
        """
        # Cost
        yes_cost = opportunity.yes_size * opportunity.yes_price
        no_cost = opportunity.no_size * opportunity.no_price
        total_cost = yes_cost + no_cost
        
        # Revenue (when market resolves)
        # One of the tokens will be worth $1, the other $0
        # Since we own both, we get the sum of their sizes at resolution
        # But in practice, we'll get $1 per token for the winning side
        # The math: we own (yes_size + no_size) tokens total, but only
        # one side wins, so we get max(yes_size, no_size) * $1
        # Actually, both sides sum to close to total_investment / avg_price
        # Expected revenue is the size * $1 for winning side
        expected_revenue = opportunity.total_investment / opportunity.implied_sum
        
        # Profit
        expected_profit = expected_revenue - total_cost
        profit_pct = (expected_profit / total_cost) * 100 if total_cost > 0 else 0
        
        return {
            "yes_cost": yes_cost,
            "no_cost": no_cost,
            "total_cost": total_cost,
            "expected_revenue": expected_revenue,
            "expected_profit": expected_profit,
            "profit_pct": profit_pct,
        }


async def test_arbitrage_engine():
    """Test arbitrage engine functionality."""
    from config import Config
    from market_manager import MarketManager
    from rate_limiter import RateLimiter
    import asyncio
    
    print("Testing ArbitrageEngine...")
    
    # Create config
    try:
        config = Config()
    except Exception as e:
        print(f"⚠️  Config error: {e}")
        import os
        os.environ["POLY_PRIVATE_KEY"] = "test"
        config = Config()
    
    # Create managers
    rate_limiter = RateLimiter(max_calls=10, period=60.0)
    market_manager = MarketManager(config, rate_limiter)
    ws_manager = WebSocketManager(config)
    
    # Fetch markets
    print("\n1. Fetching markets...")
    markets = await market_manager.fetch_markets_by_tag("crypto", limit=5)
    print(f"   Found {len(markets)} markets")
    
    if not markets:
        print("   No markets found, skipping test")
        return
    
    # Connect WebSocket
    print("\n2. Connecting to WebSocket...")
    try:
        await ws_manager.connect()
        await ws_manager.subscribe_to_markets(markets)
        print("   ✓ Connected")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return
    
    # Wait for orderbook data
    print("\n3. Waiting for orderbook data (5 seconds)...")
    
    async def listen_task():
        await ws_manager.listen()
    
    async def wait_task():
        await asyncio.sleep(5)
        await ws_manager.stop()
    
    await asyncio.gather(listen_task(), wait_task())
    
    # Create arbitrage engine
    print("\n4. Creating arbitrage engine...")
    engine = ArbitrageEngine(config, ws_manager)
    
    # Scan for opportunities
    print("\n5. Scanning for arbitrage opportunities...")
    opportunities = engine.scan_all_markets(markets)
    
    if opportunities:
        print(f"   ✓ Found {len(opportunities)} opportunities!")
        for opp in opportunities:
            print(f"   - {opp}")
            pnl = engine.calculate_expected_pnl(opp)
            print(f"     Expected profit: ${pnl['expected_profit']:.2f} ({pnl['profit_pct']:.2f}%)")
    else:
        print("   No arbitrage opportunities found (this is normal)")
    
    print("\n✓ ArbitrageEngine test completed!")
    
    # Cleanup
    await market_manager.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_arbitrage_engine())


