"""
Polymarket Arbitrage Trading Bot
Main orchestration module that coordinates all components.
"""

import asyncio
import signal
import sys
from typing import Optional
from loguru import logger

from config import Config, init_config
from logger import setup_logger
from rate_limiter import RateLimiter
from market_manager import MarketManager
from websocket_manager import WebSocketManager
from arbitrage_engine import ArbitrageEngine
from balance_checker import BalanceChecker
from clob_client_wrapper import ClobClientWrapper
from order_executor import OrderExecutor
from paper_trade_executor import PaperTradeExecutor


class PolymarketArbitrageBot:
    """
    Main bot class that orchestrates all components.
    
    Workflow:
    1. Initialize all components
    2. Fetch target markets
    3. Subscribe to WebSocket for real-time data
    4. Monitor for arbitrage opportunities
    5. Execute trades when opportunities arise
    """
    
    def __init__(self, config: Config):
        """
        Initialize bot with configuration.
        
        Args:
            config: Configuration object
        """
        self.config = config
        
        # Components
        self.rate_limiter: Optional[RateLimiter] = None
        self.market_manager: Optional[MarketManager] = None
        self.ws_manager: Optional[WebSocketManager] = None
        self.arbitrage_engine: Optional[ArbitrageEngine] = None
        self.balance_checker: Optional[BalanceChecker] = None
        self.clob_client: Optional[ClobClientWrapper] = None
        self.order_executor: Optional[OrderExecutor] = None
        self.paper_trade_executor: Optional[PaperTradeExecutor] = None
        
        # State
        self.running = False
        self.markets = []
        
        logger.info("PolymarketArbitrageBot initialized")
    
    async def initialize(self):
        """Initialize all bot components."""
        logger.info("Initializing bot components...")
        
        # Rate limiter
        self.rate_limiter = RateLimiter(
            max_calls=self.config.max_api_calls_per_minute,
            period=60.0
        )
        logger.success("✓ Rate limiter initialized")
        
        # Market manager
        self.market_manager = MarketManager(self.config, self.rate_limiter)
        logger.success("✓ Market manager initialized")
        
        # WebSocket manager
        self.ws_manager = WebSocketManager(self.config)
        logger.success("✓ WebSocket manager initialized")
        
        # Arbitrage engine
        self.arbitrage_engine = ArbitrageEngine(self.config, self.ws_manager)
        logger.success("✓ Arbitrage engine initialized")
        
        # Check if paper trading mode is enabled
        if self.config.paper_trading_mode:
            logger.warning("=" * 60)
            logger.warning("PAPER TRADING MODE ENABLED")
            logger.warning("No real trades will be executed!")
            logger.warning("All trades will be simulated and saved to CSV")
            logger.warning("=" * 60)
            
            # Paper trade executor (no real components needed)
            self.paper_trade_executor = PaperTradeExecutor(self.config)
            logger.success("✓ Paper trade executor initialized")
            
            # Still initialize balance checker for validation (but won't be used for trading)
            self.balance_checker = BalanceChecker(self.config)
            await self.balance_checker.connect()
            logger.success("✓ Balance checker connected (for validation only)")
        else:
            # Real trading mode - initialize all components
            # Balance checker
            self.balance_checker = BalanceChecker(self.config)
            await self.balance_checker.connect()
            logger.success("✓ Balance checker connected")
            
            # CLOB client
            self.clob_client = ClobClientWrapper(self.config)
            await self.clob_client.initialize_async()
            logger.success("✓ CLOB client initialized")
            
            # Order executor
            self.order_executor = OrderExecutor(
                self.config,
                self.clob_client,
                self.balance_checker
            )
            logger.success("✓ Order executor initialized")
        
        logger.success("All components initialized successfully!")
    
    async def fetch_markets(self):
        """Fetch target markets from Gamma API."""
        logger.info("Fetching target markets...")
        
        # Check market mode
        if self.config.market_mode == "btc_eth":
            logger.info(
                f"Mode: BTC/ETH {self.config.btc_eth_duration_minutes}-minute markets"
            )
            self.markets = await self.market_manager.fetch_btc_eth_markets(
                duration_minutes=self.config.btc_eth_duration_minutes,
                limit=50
            )
        else:
            logger.info(f"Mode: Tag-based ({', '.join(self.config.target_tags)})")
            self.markets = await self.market_manager.fetch_all_target_markets()
        
        if not self.markets:
            logger.error(
                "No markets found! Check your MARKET_MODE and related configuration."
            )
            return False
        
        logger.success(f"Fetched {len(self.markets)} markets to monitor")
        
        # Log top markets
        logger.info("Top markets by volume:")
        for i, market in enumerate(self.markets[:5], 1):
            logger.info(
                f"  {i}. {market.question[:60]}... "
                f"(${market.volume_24hr:.2f})"
            )
        
        return True
    
    async def subscribe_to_websocket(self):
        """Subscribe to WebSocket for real-time market data."""
        logger.info("Subscribing to WebSocket Market Channel...")
        
        await self.ws_manager.connect()
        await self.ws_manager.subscribe_to_markets(self.markets)
        
        # Set up callbacks
        self.ws_manager.on_book_update = self.on_orderbook_update
        
        logger.success("WebSocket subscription active!")
    
    async def on_orderbook_update(self, market_id: str, asset_id: str, orderbook):
        """
        Callback for orderbook updates.
        
        Args:
            market_id: Market condition ID
            asset_id: Token ID
            orderbook: OrderbookSnapshot
        """
        # Find the market
        market = self.market_manager.get_market(market_id)
        
        if not market:
            return
        
        # Check for arbitrage opportunity
        opportunity = self.arbitrage_engine.check_arbitrage_opportunity(market)
        
        if not opportunity:
            return
        
        # We found an opportunity!
        logger.info("🎯 Arbitrage opportunity detected, validating...")
        
        # Validate opportunity (check if still valid)
        if not self.arbitrage_engine.validate_opportunity(opportunity):
            logger.warning("Opportunity validation failed, skipping")
            return
        
        # Check balance before execution
        wallet_address = (
            self.config.poly_proxy_address
            if self.config.uses_proxy
            else self._get_wallet_address()
        )
        
        sufficient, balance = await self.balance_checker.check_sufficient_balance(
            wallet_address,
            opportunity.total_investment
        )
        
        if not sufficient:
            logger.warning(
                f"Skipping opportunity: Insufficient balance "
                f"(${balance:.2f} < ${opportunity.total_investment:.2f})"
            )
            return
        
        # Check if balance is above minimum threshold
        if balance < self.config.min_usdc_balance:
            logger.warning(
                f"Balance below minimum threshold: "
                f"${balance:.2f} < ${self.config.min_usdc_balance:.2f}. "
                f"Pausing trading."
            )
            return
        
        # Execute arbitrage (paper trading or real)
        if self.config.paper_trading_mode:
            logger.info("📝 [PAPER TRADE] Simulating arbitrage trade...")
            
            try:
                result = await self.paper_trade_executor.execute_arbitrage(opportunity)
                
                if result.success:
                    logger.success(
                        f"📝 [PAPER TRADE] Trade simulated successfully! "
                        f"Execution time: {result.execution_time_ms:.2f}ms"
                    )
                else:
                    logger.warning(
                        f"Paper trade simulation failed: YES={result.yes_status}, "
                        f"NO={result.no_status}"
                    )
            
            except Exception as e:
                logger.error(f"Error simulating paper trade: {e}")
        else:
            logger.info("💰 Executing arbitrage trade...")
            
            try:
                result = await self.order_executor.execute_arbitrage(opportunity)
                
                if result.success:
                    logger.success(
                        f"✅ Arbitrage executed successfully! "
                        f"Execution time: {result.execution_time_ms:.2f}ms"
                    )
                elif result.is_partial_fill():
                    logger.error(
                        "⚠️ PARTIAL FILL! Manual hedge may be required."
                    )
                else:
                    logger.warning(
                        f"Execution failed: YES={result.yes_status}, "
                        f"NO={result.no_status}"
                    )
            
            except Exception as e:
                logger.error(f"Error executing arbitrage: {e}")
    
    def _get_wallet_address(self) -> str:
        """Get wallet address."""
        if self.config.uses_proxy:
            return self.config.poly_proxy_address
        else:
            from eth_account import Account
            account = Account.from_key(self.config.poly_private_key)
            return account.address
    
    async def run(self):
        """Run the main bot loop."""
        self.running = True
        
        logger.info("=" * 70)
        logger.info("POLYMARKET ARBITRAGE BOT STARTING")
        logger.info("=" * 70)
        
        try:
            # Initialize components
            await self.initialize()
            
            # Fetch markets
            if not await self.fetch_markets():
                logger.error("Failed to fetch markets. Exiting.")
                return
            
            # Subscribe to WebSocket
            await self.subscribe_to_websocket()
            
            logger.success("=" * 70)
            logger.success("BOT IS NOW RUNNING - Monitoring for arbitrage opportunities")
            logger.success("=" * 70)
            
            # Start WebSocket listener
            await self.ws_manager.listen()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("=" * 70)
        logger.info("SHUTTING DOWN BOT")
        logger.info("=" * 70)
        
        self.running = False
        
        # Log final statistics
        if self.config.paper_trading_mode and self.paper_trade_executor:
            self.paper_trade_executor.log_statistics()
        elif self.order_executor:
            self.order_executor.log_statistics()
        
        # Close connections
        if self.ws_manager:
            await self.ws_manager.stop()
        
        if self.market_manager:
            await self.market_manager.close()
        
        if self.balance_checker:
            await self.balance_checker.close()
        
        logger.info("Bot shutdown complete. Goodbye!")


def setup_signal_handlers(bot: PolymarketArbitrageBot):
    """
    Setup signal handlers for graceful shutdown.
    
    Args:
        bot: Bot instance
    """
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        bot.running = False
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point."""
    # Load configuration
    try:
        config = init_config()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        print("You can use env_template.txt as a reference.")
        sys.exit(1)
    
    # Setup logger
    setup_logger(
        log_level=config.log_level,
        log_file=config.log_file
    )
    
    # Create and run bot
    bot = PolymarketArbitrageBot(config)
    setup_signal_handlers(bot)
    
    try:
        await bot.run()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nBot stopped by user.")
        sys.exit(0)

