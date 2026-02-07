"""
Order executor for parallel arbitrage trade execution.
Handles FOK order submission and error handling.
"""

import asyncio
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from py_clob_client.clob_types import OrderType
from loguru import logger

from config import Config
from clob_client_wrapper import ClobClientWrapper, create_buy_order_args
from balance_checker import BalanceChecker
from arbitrage_engine import ArbitrageOpportunity
import logger as log_module


@dataclass
class ExecutionResult:
    """Result of trade execution."""
    
    success: bool
    yes_order_id: Optional[str]
    no_order_id: Optional[str]
    yes_filled: bool
    no_filled: bool
    yes_status: str
    no_status: str
    yes_error: Optional[str]
    no_error: Optional[str]
    execution_time_ms: float
    
    def is_partial_fill(self) -> bool:
        """Check if only one side filled (asymmetric position)."""
        return (self.yes_filled and not self.no_filled) or \
               (self.no_filled and not self.yes_filled)


class OrderExecutor:
    """
    Executes arbitrage trades by submitting parallel YES/NO orders.
    Uses FOK (Fill-Or-Kill) orders to avoid partial fills.
    """
    
    def __init__(
        self,
        config: Config,
        clob_client: ClobClientWrapper,
        balance_checker: BalanceChecker
    ):
        """
        Initialize order executor.
        
        Args:
            config: Configuration object
            clob_client: CLOB client wrapper
            balance_checker: Balance checker
        """
        self.config = config
        self.clob_client = clob_client
        self.balance_checker = balance_checker
        
        # Execution tracking
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.partial_fills = 0
        
        logger.info("OrderExecutor initialized")
    
    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity
    ) -> ExecutionResult:
        """
        Execute arbitrage trade by buying YES and NO tokens.
        
        Args:
            opportunity: Arbitrage opportunity to execute
        
        Returns:
            ExecutionResult with execution details
        """
        start_time = time.time()
        self.total_executions += 1
        
        market = opportunity.market
        
        logger.info(
            f"Executing arbitrage trade for: {market.question[:60]}..."
        )
        
        # Step 1: Check USDC balance
        wallet_address = (
            self.config.poly_proxy_address
            if self.config.uses_proxy
            else self._get_wallet_address_from_key()
        )
        
        sufficient, balance = await self.balance_checker.check_sufficient_balance(
            wallet_address,
            opportunity.total_investment
        )
        
        if not sufficient:
            logger.error(
                f"Insufficient USDC balance: ${balance:.2f} < "
                f"${opportunity.total_investment:.2f}"
            )
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return ExecutionResult(
                success=False,
                yes_order_id=None,
                no_order_id=None,
                yes_filled=False,
                no_filled=False,
                yes_status="insufficient_balance",
                no_status="insufficient_balance",
                yes_error="Insufficient USDC balance",
                no_error="Insufficient USDC balance",
                execution_time_ms=execution_time_ms,
            )
        
        logger.info(f"Balance check passed: ${balance:.2f} USDC available")
        
        # Step 2: Create orders
        try:
            yes_order_args = create_buy_order_args(
                token_id=market.yes_token_id,
                price=opportunity.yes_price,
                size=opportunity.yes_size,
            )
            
            no_order_args = create_buy_order_args(
                token_id=market.no_token_id,
                price=opportunity.no_price,
                size=opportunity.no_size,
            )
            
            logger.info("Order arguments created")
            
        except Exception as e:
            logger.error(f"Failed to create order arguments: {e}")
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return ExecutionResult(
                success=False,
                yes_order_id=None,
                no_order_id=None,
                yes_filled=False,
                no_filled=False,
                yes_status="order_creation_failed",
                no_status="order_creation_failed",
                yes_error=str(e),
                no_error=str(e),
                execution_time_ms=execution_time_ms,
            )
        
        # Step 3: Execute orders in parallel (FOK = Fill-Or-Kill)
        logger.info("Submitting parallel FOK orders...")
        
        yes_result = None
        no_result = None
        yes_error = None
        no_error = None
        
        try:
            # Submit both orders in parallel
            results = await asyncio.gather(
                self.clob_client.create_and_post_order(
                    yes_order_args,
                    OrderType.FOK
                ),
                self.clob_client.create_and_post_order(
                    no_order_args,
                    OrderType.FOK
                ),
                return_exceptions=True
            )
            
            yes_result = results[0]
            no_result = results[1]
            
            # Check if either returned an exception
            if isinstance(yes_result, Exception):
                yes_error = str(yes_result)
                yes_result = None
                logger.error(f"YES order failed: {yes_error}")
            
            if isinstance(no_result, Exception):
                no_error = str(no_result)
                no_result = None
                logger.error(f"NO order failed: {no_error}")
            
        except Exception as e:
            logger.error(f"Unexpected error during order submission: {e}")
            yes_error = str(e)
            no_error = str(e)
        
        # Step 4: Parse results
        execution_time_ms = (time.time() - start_time) * 1000
        
        yes_order_id = None
        no_order_id = None
        yes_filled = False
        no_filled = False
        yes_status = "failed"
        no_status = "failed"
        
        # Parse YES result
        if yes_result and isinstance(yes_result, dict):
            yes_order_id = yes_result.get("orderID", "")
            yes_success = yes_result.get("success", False)
            yes_status = "filled" if yes_success else yes_result.get("status", "failed")
            yes_filled = yes_success
            
            if not yes_success:
                yes_error = yes_result.get("errorMsg", "Unknown error")
        
        # Parse NO result
        if no_result and isinstance(no_result, dict):
            no_order_id = no_result.get("orderID", "")
            no_success = no_result.get("success", False)
            no_status = "filled" if no_success else no_result.get("status", "failed")
            no_filled = no_success
            
            if not no_success:
                no_error = no_result.get("errorMsg", "Unknown error")
        
        # Create execution result
        result = ExecutionResult(
            success=(yes_filled and no_filled),
            yes_order_id=yes_order_id,
            no_order_id=no_order_id,
            yes_filled=yes_filled,
            no_filled=no_filled,
            yes_status=yes_status,
            no_status=no_status,
            yes_error=yes_error,
            no_error=no_error,
            execution_time_ms=execution_time_ms,
        )
        
        # Update statistics
        if result.success:
            self.successful_executions += 1
            logger.success(
                f"✅ Arbitrage executed successfully in {execution_time_ms:.2f}ms"
            )
        elif result.is_partial_fill():
            self.partial_fills += 1
            logger.error(
                f"⚠️ PARTIAL FILL DETECTED! This creates asymmetric position risk!"
            )
            logger.error(f"  YES: {yes_status} | NO: {no_status}")
            logger.error(f"  Manual intervention may be required to hedge position")
        else:
            self.failed_executions += 1
            logger.warning(f"Execution failed in {execution_time_ms:.2f}ms")
        
        # Log detailed results
        log_module.log_trade_execution(
            condition_id=market.condition_id,
            question=market.question,
            yes_order_id=yes_order_id or "N/A",
            no_order_id=no_order_id or "N/A",
            yes_status=yes_status,
            no_status=no_status,
            yes_filled=yes_filled,
            no_filled=no_filled,
            execution_time_ms=execution_time_ms,
        )
        
        return result
    
    def _get_wallet_address_from_key(self) -> str:
        """
        Derive wallet address from private key (for EOA mode).
        
        Returns:
            Wallet address
        """
        from eth_account import Account
        
        account = Account.from_key(self.config.poly_private_key)
        return account.address
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get execution statistics.
        
        Returns:
            Dictionary with execution stats
        """
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "partial_fills": self.partial_fills,
            "success_rate": (
                self.successful_executions / self.total_executions * 100
                if self.total_executions > 0
                else 0.0
            ),
        }
    
    def log_statistics(self):
        """Log execution statistics."""
        stats = self.get_statistics()
        
        logger.info("=" * 60)
        logger.info("ORDER EXECUTOR STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Executions: {stats['total_executions']}")
        logger.info(f"Successful: {stats['successful_executions']}")
        logger.info(f"Failed: {stats['failed_executions']}")
        logger.info(f"Partial Fills: {stats['partial_fills']}")
        logger.info(f"Success Rate: {stats['success_rate']:.1f}%")
        logger.info("=" * 60)


async def test_order_executor():
    """Test order executor (without real trading)."""
    from config import Config
    from market_manager import Market
    
    print("Testing OrderExecutor...")
    
    # Create config
    try:
        config = Config()
    except Exception as e:
        print(f"⚠️  Config error: {e}")
        print("   Cannot test OrderExecutor without valid config")
        return
    
    # Create components
    clob_client = ClobClientWrapper(config)
    balance_checker = BalanceChecker(config)
    
    # Initialize client
    print("\n1. Initializing CLOB client...")
    try:
        await clob_client.initialize_async()
        print("   ✓ Client initialized")
    except Exception as e:
        print(f"   ✗ Initialization failed: {e}")
        return
    
    # Connect balance checker
    print("\n2. Connecting balance checker...")
    try:
        await balance_checker.connect()
        print("   ✓ Connected")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return
    
    # Create executor
    print("\n3. Creating order executor...")
    executor = OrderExecutor(config, clob_client, balance_checker)
    print("   ✓ OrderExecutor created")
    
    # Log statistics
    print("\n4. Statistics:")
    executor.log_statistics()
    
    print("\n✓ OrderExecutor test completed!")
    print("   Note: Actual trade execution requires real arbitrage opportunities")
    
    # Cleanup
    await balance_checker.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_order_executor())


