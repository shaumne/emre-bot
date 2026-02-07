"""
Paper Trading Executor - Simulates trades without real money.
Records all trades to CSV/Excel for analysis.
"""

import csv
import os
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, asdict
import time
from loguru import logger

from config import Config
from arbitrage_engine import ArbitrageOpportunity
from order_executor import ExecutionResult


@dataclass
class PaperTrade:
    """Represents a paper trade record."""
    
    timestamp: str
    market_question: str
    condition_id: str
    yes_token_id: str
    no_token_id: str
    yes_price: float
    no_price: float
    yes_size: float
    no_size: float
    total_investment: float
    implied_sum: float
    expected_profit_pct: float
    expected_profit_usd: float
    execution_time_ms: float
    status: str  # "simulated", "filled", "failed"
    
    # Resolution tracking (will be updated when market resolves)
    resolved: bool = False
    resolution_date: Optional[str] = None
    winning_side: Optional[str] = None  # "YES" or "NO"
    actual_payout: Optional[float] = None
    actual_profit: Optional[float] = None
    actual_profit_pct: Optional[float] = None


class PaperTradeExecutor:
    """
    Simulates arbitrage trades without real money.
    Records all trades to CSV/Excel for analysis.
    """
    
    def __init__(self, config: Config):
        """
        Initialize paper trade executor.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.trades_file = config.paper_trading_file
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.trades_file) if os.path.dirname(self.trades_file) else ".", exist_ok=True)
        
        # Initialize CSV file with headers if it doesn't exist
        self._initialize_csv()
        
        # Track trades in memory
        self.trades: Dict[str, PaperTrade] = {}  # condition_id -> latest trade
        
        logger.info(f"PaperTradeExecutor initialized (mode: ON)")
        logger.info(f"Trades will be saved to: {self.trades_file}")
    
    def _initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist."""
        if os.path.exists(self.trades_file):
            return
        
        headers = [
            "timestamp",
            "market_question",
            "condition_id",
            "yes_token_id",
            "no_token_id",
            "yes_price",
            "no_price",
            "yes_size",
            "no_size",
            "total_investment",
            "implied_sum",
            "expected_profit_pct",
            "expected_profit_usd",
            "execution_time_ms",
            "status",
            "resolved",
            "resolution_date",
            "winning_side",
            "actual_payout",
            "actual_profit",
            "actual_profit_pct",
        ]
        
        with open(self.trades_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        
        logger.info(f"Created paper trading file: {self.trades_file}")
    
    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity
    ) -> ExecutionResult:
        """
        Simulate arbitrage trade execution (no real money).
        
        Args:
            opportunity: Arbitrage opportunity to simulate
        
        Returns:
            ExecutionResult with simulated execution details
        """
        start_time = time.time()
        market = opportunity.market
        
        logger.info(
            f"📝 [PAPER TRADE] Simulating arbitrage for: {market.question[:60]}..."
        )
        
        # Simulate successful execution (both orders filled)
        # In real trading, this might fail, but for paper trading we assume success
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Calculate expected profit
        expected_profit_usd = (
            opportunity.total_investment * opportunity.expected_profit_pct
        )
        
        # Create paper trade record
        paper_trade = PaperTrade(
            timestamp=datetime.now().isoformat(),
            market_question=market.question,
            condition_id=market.condition_id,
            yes_token_id=market.yes_token_id,
            no_token_id=market.no_token_id,
            yes_price=opportunity.yes_price,
            no_price=opportunity.no_price,
            yes_size=opportunity.yes_size,
            no_size=opportunity.no_size,
            total_investment=opportunity.total_investment,
            implied_sum=opportunity.implied_sum,
            expected_profit_pct=opportunity.expected_profit_pct,
            expected_profit_usd=expected_profit_usd,
            execution_time_ms=execution_time_ms,
            status="simulated",
        )
        
        # Save to CSV
        self._save_trade(paper_trade)
        
        # Store in memory
        self.trades[market.condition_id] = paper_trade
        
        # Create simulated execution result
        result = ExecutionResult(
            success=True,  # Always successful in paper trading
            yes_order_id=f"PAPER-{market.yes_token_id[:16]}",
            no_order_id=f"PAPER-{market.no_token_id[:16]}",
            yes_filled=True,
            no_filled=True,
            yes_status="filled",
            no_status="filled",
            yes_error=None,
            no_error=None,
            execution_time_ms=execution_time_ms,
        )
        
        logger.success(
            f"📝 [PAPER TRADE] Trade simulated successfully!\n"
            f"  Market: {market.question[:60]}...\n"
            f"  Investment: ${opportunity.total_investment:.2f}\n"
            f"  Expected Profit: ${expected_profit_usd:.2f} ({opportunity.expected_profit_pct * 100:.2f}%)\n"
            f"  YES: {opportunity.yes_size:.2f} @ ${opportunity.yes_price:.4f}\n"
            f"  NO: {opportunity.no_size:.2f} @ ${opportunity.no_price:.4f}\n"
            f"  Saved to: {self.trades_file}"
        )
        
        return result
    
    def _save_trade(self, trade: PaperTrade):
        """
        Save trade to CSV file.
        
        Args:
            trade: PaperTrade object to save
        """
        try:
            file_exists = os.path.exists(self.trades_file)
            
            with open(self.trades_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "timestamp",
                    "market_question",
                    "condition_id",
                    "yes_token_id",
                    "no_token_id",
                    "yes_price",
                    "no_price",
                    "yes_size",
                    "no_size",
                    "total_investment",
                    "implied_sum",
                    "expected_profit_pct",
                    "expected_profit_usd",
                    "execution_time_ms",
                    "status",
                    "resolved",
                    "resolution_date",
                    "winning_side",
                    "actual_payout",
                    "actual_profit",
                    "actual_profit_pct",
                ])
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(asdict(trade))
                f.flush()  # Force write to disk immediately
                os.fsync(f.fileno())  # Ensure OS writes to disk
        
        except Exception as e:
            logger.error(f"Failed to save paper trade to CSV: {e}")
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get paper trading statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_trades = len(self.trades)
        total_investment = sum(t.total_investment for t in self.trades.values())
        total_expected_profit = sum(t.expected_profit_usd for t in self.trades.values())
        
        resolved_trades = [t for t in self.trades.values() if t.resolved]
        total_actual_profit = sum(t.actual_profit or 0 for t in resolved_trades)
        
        return {
            "total_trades": total_trades,
            "total_investment": total_investment,
            "total_expected_profit": total_expected_profit,
            "resolved_trades": len(resolved_trades),
            "total_actual_profit": total_actual_profit,
            "expected_roi": (total_expected_profit / total_investment * 100) if total_investment > 0 else 0.0,
            "actual_roi": (total_actual_profit / total_investment * 100) if total_investment > 0 else 0.0,
        }
    
    def log_statistics(self):
        """Log paper trading statistics."""
        stats = self.get_statistics()
        
        logger.info("=" * 60)
        logger.info("PAPER TRADING STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Trades: {stats['total_trades']}")
        logger.info(f"Total Investment: ${stats['total_investment']:.2f}")
        logger.info(f"Expected Profit: ${stats['total_expected_profit']:.2f}")
        logger.info(f"Expected ROI: {stats['expected_roi']:.2f}%")
        logger.info(f"Resolved Trades: {stats['resolved_trades']}")
        if stats['resolved_trades'] > 0:
            logger.info(f"Actual Profit: ${stats['total_actual_profit']:.2f}")
            logger.info(f"Actual ROI: {stats['actual_roi']:.2f}%")
        logger.info(f"Trades File: {self.trades_file}")
        logger.info("=" * 60)

