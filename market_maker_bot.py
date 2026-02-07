"""
Polymarket Market Maker Bot

Bu bot, inventory skew stratejisi kullanarak Polymarket'te market making yapar.
Arbitrage bot'tan tamamen bağımsız çalışır.

Özellikler:
- Inventory-aware quote calculation
- Paper trading mode
- Real-time orderbook tracking
- Risk management
"""

import asyncio
import signal
import sys
import time
from typing import Optional, Dict, Any
from loguru import logger
from datetime import datetime

from config import Config, init_config
from logger import setup_logger
from rate_limiter import RateLimiter
from market_manager import MarketManager, Market
from websocket_manager import WebSocketManager
from inventory_skew_strategy import InventorySkewStrategy
from balance_checker import BalanceChecker
from clob_client_wrapper import ClobClientWrapper
from mm_trade_logger import MarketMakerLogger
from mm_simulated_trade_logger import SimulatedTradeLogger


class MarketMakerBot:
    """
    Market Maker Bot using Inventory Skew Strategy.
    
    Workflow:
    1. Fetch target markets
    2. Subscribe to WebSocket for orderbook updates
    3. Calculate quotes based on inventory
    4. Place/update orders
    5. Track fills and adjust inventory
    """
    
    def __init__(self, config: Config):
        """Initialize bot with configuration."""
        self.config = config
        
        # Components
        self.rate_limiter: Optional[RateLimiter] = None
        self.market_manager: Optional[MarketManager] = None
        self.ws_manager: Optional[WebSocketManager] = None
        self.strategy: Optional[InventorySkewStrategy] = None
        self.balance_checker: Optional[BalanceChecker] = None
        self.clob_client: Optional[ClobClientWrapper] = None
        self.logger: Optional[MarketMakerLogger] = None
        self.trade_logger: Optional[SimulatedTradeLogger] = None
        
        # State
        self.running = False
        self.markets: Dict[str, Market] = {}  # condition_id -> Market
        self.inventories: Dict[str, int] = {}  # condition_id -> inventory
        self.active_orders: Dict[str, Dict] = {}  # order_id -> order_info
        self.last_quote_update: Dict[str, float] = {}  # condition_id -> timestamp
        
        # Config
        self.paper_trading = getattr(config, 'mm_paper_trading', True)
        self.quote_update_interval = getattr(config, 'mm_quote_update_interval', 5.0)
        
        logger.info("MarketMakerBot initialized")
    
    async def initialize(self):
        """Initialize all bot components."""
        logger.info("Initializing Market Maker Bot...")
        
        # Rate limiter
        self.rate_limiter = RateLimiter(
            max_calls=self.config.max_api_calls_per_minute,
            period=60.0
        )
        logger.success("[OK] Rate limiter initialized")
        
        # Market manager
        self.market_manager = MarketManager(self.config, self.rate_limiter)
        logger.success("[OK] Market manager initialized")
        
        # WebSocket manager
        self.ws_manager = WebSocketManager(self.config)
        
        # Set orderbook callback
        self.ws_manager.on_book_update = self.on_orderbook_update
        logger.success("[OK] WebSocket manager initialized")
        
        # Strategy
        mm_spread = getattr(self.config, 'mm_target_spread', 0.02)
        mm_skew = getattr(self.config, 'mm_skew_factor', 0.0001)
        mm_max_inv = getattr(self.config, 'mm_max_inventory', 1000)
        
        self.strategy = InventorySkewStrategy(
            target_spread=mm_spread,
            skew_factor=mm_skew,
            max_inventory=mm_max_inv
        )
        logger.success("[OK] Market maker strategy initialized")
        
        # CSV Logger (quotes)
        mm_csv_file = getattr(self.config, 'mm_paper_trading_file', 'mm_paper_trades.csv')
        self.logger = MarketMakerLogger(mm_csv_file)
        logger.success(f"[OK] Quote logger initialized: {mm_csv_file}")
        
        # Trade Logger (simulated fills)
        self.trade_logger = SimulatedTradeLogger("mm_simulated_trades.csv")
        logger.success("[OK] Trade logger initialized: mm_simulated_trades.csv")
        
        # Paper trading check
        if self.paper_trading:
            logger.warning("=" * 60)
            logger.warning("PAPER TRADING MODE - Market Maker")
            logger.warning("Orders will be simulated, not actually placed!")
            logger.warning("=" * 60)
        else:
            # Real trading components
            self.balance_checker = BalanceChecker(self.config)
            await self.balance_checker.connect()
            logger.success("[OK] Balance checker connected")
            
            self.clob_client = ClobClientWrapper(self.config)
            logger.success("[OK] CLOB client initialized")
        
        logger.success("Market Maker Bot initialized successfully!")
    
    async def fetch_markets(self):
        """Fetch target markets for market making."""
        logger.info("Fetching markets for market making...")
        
        if self.config.market_mode == "btc_eth":
            markets = await self.market_manager.fetch_btc_eth_markets(
                duration_minutes=self.config.btc_eth_duration_minutes,
                limit=50
            )
        else:
            markets = await self.market_manager.fetch_markets(
                tags=self.config.target_tags,
                limit=50
            )
        
        if not markets:
            logger.error("No markets found for market making!")
            return False
        
        # Store markets and initialize inventories
        for market in markets:
            self.markets[market.condition_id] = market
            self.inventories[market.condition_id] = 0  # Start with 0 inventory
            self.last_quote_update[market.condition_id] = 0.0
        
        logger.success(f"[OK] Loaded {len(markets)} markets for market making")
        return True
    
    async def start(self):
        """Start the market maker bot."""
        self.running = True
        
        # Fetch markets
        if not await self.fetch_markets():
            logger.error("Failed to fetch markets. Exiting.")
            return
        
        # Subscribe to WebSocket
        markets_list = list(self.markets.values())
        await self.ws_manager.subscribe_to_markets(markets_list)
        
        # Start WebSocket listener
        asyncio.create_task(self.ws_manager.listen())
        
        logger.success("=" * 60)
        logger.success("MARKET MAKER BOT STARTED")
        logger.success(f"Monitoring {len(self.markets)} markets")
        logger.success(f"Paper Trading: {self.paper_trading}")
        logger.success("=" * 60)
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Bot task cancelled")
    
    async def on_orderbook_update(self, market_id: str, asset_id: str, orderbook):
        """
        Handle orderbook updates.
        
        Args:
            market_id: Market ID (condition_id)
            asset_id: Asset ID (token ID)
            orderbook: OrderbookSnapshot object
        """
        # Find market by condition_id
        market = self.markets.get(market_id)
        if not market:
            logger.debug(f"Market {market_id} not found in tracked markets")
            return
        
        # Check if we should update quotes
        now = time.time()
        last_update = self.last_quote_update.get(market_id, 0)
        
        if now - last_update < self.quote_update_interval:
            return  # Too soon to update
        
        # Extract best bid/ask from OrderbookSnapshot
        best_bid_order = orderbook.get_best_bid()
        best_ask_order = orderbook.get_best_ask()
        
        if not best_bid_order or not best_ask_order:
            logger.debug(f"Empty orderbook for {market.question[:50]}...")
            return
        
        best_bid = best_bid_order["price"]
        best_ask = best_ask_order["price"]
        
        if best_bid <= 0 or best_ask <= 0 or best_bid >= best_ask:
            logger.debug(f"Invalid orderbook for {market.question[:50]}...")
            return
        
        # Get current inventory from trade logger (real simulated inventory)
        current_inventory = self.trade_logger.get_inventory(market_id) if self.trade_logger else 0
        
        # Also update local inventory tracking
        self.inventories[market_id] = current_inventory
        
        # Calculate quotes
        quotes = self.strategy.calculate_quotes(
            best_bid=best_bid,
            best_ask=best_ask,
            current_inventory=current_inventory
        )
        
        if quotes["reason"]:
            logger.warning(
                f"Cannot quote {market.question[:40]}...: {quotes['reason']}"
            )
            return
        
        # Log quote decision
        logger.info(
            f"\n{'='*60}\n"
            f"Market: {market.question[:60]}...\n"
            f"  Current: Bid=${best_bid:.4f}, Ask=${best_ask:.4f}\n"
            f"  Inventory: {current_inventory:+d} (Util: {abs(current_inventory)/self.strategy.max_inventory*100:.1f}%)\n"
            f"  Our Quotes: Bid=${quotes['bid_price']:.4f}, Ask=${quotes['ask_price']:.4f}\n"
            f"  Fair Value: ${quotes['fair_value']:.4f} (Adj: ${quotes['inventory_adjustment']:+.6f})\n"
            f"  Spread: ${quotes['spread']:.4f} ({quotes['spread']*100:.2f}%)"
        )
        
        # Risk warnings
        if quotes["should_stop_buying"]:
            logger.warning("  [!] STOP BUYING - Inventory too HIGH")
        if quotes["should_stop_selling"]:
            logger.warning("  [!] STOP SELLING - Inventory too LOW")
        
        # Log quote to CSV
        if self.logger:
            self.logger.log_quote(
                market_question=market.question,
                condition_id=market_id,
                inventory=current_inventory,
                max_inventory=self.strategy.max_inventory,
                market_best_bid=best_bid,
                market_best_ask=best_ask,
                quotes=quotes
            )
        
        # SIMULATE FILLS: Check if market hit our quotes
        if self.trade_logger:
            await self.simulate_fills(
                market=market,
                market_id=market_id,
                best_bid=best_bid,
                best_ask=best_ask,
                our_bid=quotes['bid_price'],
                our_ask=quotes['ask_price'],
                should_stop_buying=quotes['should_stop_buying'],
                should_stop_selling=quotes['should_stop_selling']
            )
        
        # Update quotes (paper trading only logs)
        await self.update_quotes(market, quotes)
        
        # Update last quote time
        self.last_quote_update[market_id] = now
    
    async def update_quotes(self, market: Market, quotes: Dict[str, Any]):
        """
        Update/place orders for a market.
        
        Args:
            market: Market object
            quotes: Quote calculation result
        """
        if self.paper_trading:
            # Paper trading: just log
            logger.info(
                f"  [PAPER] Would place orders:\n"
                f"    BID: {quotes['bid_price']:.4f} (skip: {quotes['should_stop_buying']})\n"
                f"    ASK: {quotes['ask_price']:.4f} (skip: {quotes['should_stop_selling']})"
            )
            return
        
        # Real trading: place orders
        # TODO: Implement real order placement
        # 1. Cancel existing orders for this market
        # 2. Place new bid order (if not should_stop_buying)
        # 3. Place new ask order (if not should_stop_selling)
        
        logger.warning("Real trading not yet implemented!")
    
    async def simulate_fills(
        self,
        market: Market,
        market_id: str,
        best_bid: float,
        best_ask: float,
        our_bid: float,
        our_ask: float,
        should_stop_buying: bool,
        should_stop_selling: bool
    ):
        """
        Simulate order fills based on market prices.
        
        REALISTIC MARKET MAKER LOGIC:
        - If our bid >= best_bid (we're at or better than market) → Likely to get filled
        - If our ask <= best_ask (we're at or better than market) → Likely to get filled
        - Market makers get filled when they provide tight spreads
        
        Args:
            market: Market object
            market_id: Market condition ID
            best_bid: Market's best bid
            best_ask: Market's best ask
            our_bid: Our bid quote
            our_ask: Our ask quote
            should_stop_buying: Risk flag - don't buy
            should_stop_selling: Risk flag - don't sell
        """
        fill_size = 10  # Fixed size per fill
        
        # BUY simulation: Our bid is competitive (at or better than market bid)
        # AND our bid is inside the spread (between best_bid and best_ask)
        # This means we're providing liquidity and would likely get filled
        if not should_stop_buying:
            # Check if our bid is competitive
            if our_bid >= best_bid and our_bid < best_ask:
                # We're providing a better bid than the market
                # Assume we get filled at our price
                fill_price = our_bid
                
                self.trade_logger.simulate_fill(
                    action="BUY",
                    market_question=market.question,
                    condition_id=market_id,
                    price=fill_price,
                    size=fill_size
                )
                
                logger.info(
                    f"[FILL] BUY {fill_size} @ ${fill_price:.4f} | "
                    f"Market: Bid=${best_bid:.4f} Ask=${best_ask:.4f} | "
                    f"{market.question[:40]}..."
                )
        
        # SELL simulation: Our ask is competitive (at or better than market ask)
        # AND our ask is inside the spread
        if not should_stop_selling:
            # Check if our ask is competitive
            if our_ask <= best_ask and our_ask > best_bid:
                # We're providing a better ask than the market
                # Assume we get filled at our price
                fill_price = our_ask
                
                self.trade_logger.simulate_fill(
                    action="SELL",
                    market_question=market.question,
                    condition_id=market_id,
                    price=fill_price,
                    size=fill_size
                )
                
                logger.info(
                    f"[FILL] SELL {fill_size} @ ${fill_price:.4f} | "
                    f"Market: Bid=${best_bid:.4f} Ask=${best_ask:.4f} | "
                    f"{market.question[:40]}..."
                )
    
    async def shutdown(self):
        """Shutdown the bot gracefully."""
        logger.info("Shutting down Market Maker Bot...")
        self.running = False
        
        # Stop WebSocket
        if self.ws_manager:
            await self.ws_manager.stop()
            logger.success("[OK] WebSocket disconnected")
        
        # Cancel all orders (if real trading)
        if not self.paper_trading and self.clob_client:
            # TODO: Cancel all active orders
            pass
        
        # Log final statistics
        logger.info("=" * 60)
        logger.info("FINAL STATISTICS - Market Maker")
        logger.info("=" * 60)
        logger.info(f"Markets Tracked: {len(self.markets)}")
        logger.info(f"Paper Trading: {self.paper_trading}")
        
        total_inventory = sum(abs(inv) for inv in self.inventories.values())
        logger.info(f"Total Inventory (absolute): {total_inventory}")
        
        for condition_id, inventory in self.inventories.items():
            if inventory != 0:
                market = self.markets.get(condition_id)
                question = market.question[:60] if market else condition_id
                logger.info(f"  {question}...: {inventory:+d}")
        
        # Quote logger stats
        if self.logger:
            stats = self.logger.get_stats()
            logger.info(f"Quote Log Stats:")
            logger.info(f"  Total Quotes Logged: {stats.get('total_quotes', 0)}")
            logger.info(f"  Unique Markets: {stats.get('unique_markets', 0)}")
            logger.info(f"  CSV File: {stats.get('csv_file', 'N/A')}")
        
        # Trade logger stats
        if self.trade_logger:
            logger.info("")
            self.trade_logger.log_statistics()
        
        logger.info("=" * 60)
        logger.success("Market Maker Bot stopped")


async def main():
    """Main entry point."""
    # Setup logging
    setup_logger("DEBUG")
    
    logger.info("=" * 60)
    logger.info("POLYMARKET MARKET MAKER BOT")
    logger.info("=" * 60)
    
    # Load config
    try:
        config = init_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Create bot
    bot = MarketMakerBot(config)
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.warning(f"Received signal {sig}, shutting down...")
        asyncio.create_task(bot.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize
        await bot.initialize()
        
        # Start
        await bot.start()
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

