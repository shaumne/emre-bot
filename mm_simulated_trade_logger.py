"""
Simulated Trade Logger for Market Maker

Simüle edilmiş alış/satışları kaydeder ve kar/zarar hesaplar.
"""

import csv
import os
from datetime import datetime
from typing import Dict, Optional, Literal
from dataclasses import dataclass
from loguru import logger


@dataclass
class Trade:
    """Simulated trade data."""
    timestamp: str
    action: Literal["BUY", "SELL"]
    market_question: str
    condition_id: str
    price: float
    size: int
    cost: float  # Total cost/revenue
    inventory_after: int
    pnl: float  # P&L for this trade
    cumulative_pnl: float  # Total P&L so far


class SimulatedTradeLogger:
    """
    Simüle edilmiş trade'leri kaydeder ve PnL hesaplar.
    
    Mantık:
    - Bot quote verdiğinde (Bid/Ask) bunları takip eder
    - Market fiyatı quote'a ulaştığında "fill oldu" simüle eder
    - Her trade'i kaydeder ve kar/zarar hesaplar
    """
    
    def __init__(self, csv_file: str = "mm_simulated_trades.csv"):
        """
        Initialize simulated trade logger.
        
        Args:
            csv_file: CSV file path for trade log
        """
        self.csv_file = csv_file
        self.inventories: Dict[str, int] = {}  # condition_id -> inventory
        self.avg_buy_prices: Dict[str, float] = {}  # condition_id -> avg buy price
        self.cumulative_pnl = 0.0
        self.total_trades = 0
        
        self._initialize_csv()
        logger.info(f"SimulatedTradeLogger initialized: {csv_file}")
    
    def _initialize_csv(self):
        """Initialize CSV file with headers."""
        if os.path.exists(self.csv_file):
            logger.info(f"Trade log file exists: {self.csv_file}")
            # Load existing data to restore state
            self._load_existing_trades()
            return
        
        headers = [
            "timestamp",
            "action",
            "market_question",
            "condition_id",
            "price",
            "size",
            "cost",
            "inventory_after",
            "pnl",
            "cumulative_pnl",
        ]
        
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        
        logger.info(f"Created trade log file: {self.csv_file}")
    
    def _load_existing_trades(self):
        """Load existing trades to restore state."""
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
                if not rows:
                    return
                
                # Restore state from last row
                last_row = rows[-1]
                self.cumulative_pnl = float(last_row['cumulative_pnl'])
                self.total_trades = len(rows)
                
                # Rebuild inventory state
                for row in rows:
                    condition_id = row['condition_id']
                    inventory_after = int(row['inventory_after'])
                    self.inventories[condition_id] = inventory_after
                    
                    # Track average buy price
                    if row['action'] == 'BUY' and inventory_after > 0:
                        # Recalculate average buy price
                        price = float(row['price'])
                        size = int(row['size'])
                        
                        old_inventory = inventory_after - size
                        old_avg = self.avg_buy_prices.get(condition_id, price)
                        
                        if old_inventory > 0:
                            total_cost = (old_avg * old_inventory) + (price * size)
                            self.avg_buy_prices[condition_id] = total_cost / inventory_after
                        else:
                            self.avg_buy_prices[condition_id] = price
                
                logger.info(
                    f"Loaded {self.total_trades} existing trades. "
                    f"Cumulative PnL: ${self.cumulative_pnl:.2f}"
                )
        
        except Exception as e:
            logger.error(f"Failed to load existing trades: {e}")
    
    def simulate_fill(
        self,
        action: Literal["BUY", "SELL"],
        market_question: str,
        condition_id: str,
        price: float,
        size: int = 10
    ) -> Trade:
        """
        Simulate a trade fill.
        
        Args:
            action: BUY or SELL
            market_question: Market question text
            condition_id: Market condition ID
            price: Fill price
            size: Number of tokens (default: 10)
        
        Returns:
            Trade object with PnL calculation
        """
        # Get current inventory
        current_inventory = self.inventories.get(condition_id, 0)
        
        # Calculate cost
        cost = price * size
        
        # Calculate PnL
        pnl = 0.0
        
        if action == "BUY":
            # Update average buy price
            if current_inventory > 0:
                old_avg = self.avg_buy_prices.get(condition_id, price)
                total_cost = (old_avg * current_inventory) + cost
                new_inventory = current_inventory + size
                self.avg_buy_prices[condition_id] = total_cost / new_inventory
            else:
                self.avg_buy_prices[condition_id] = price
            
            # Update inventory
            new_inventory = current_inventory + size
        
        else:  # SELL
            # Calculate PnL
            avg_buy_price = self.avg_buy_prices.get(condition_id, price)
            pnl = (price - avg_buy_price) * size
            
            # Update inventory
            new_inventory = current_inventory - size
            
            # Clear average price if inventory is 0
            if new_inventory <= 0:
                self.avg_buy_prices.pop(condition_id, None)
        
        # Update cumulative PnL
        self.cumulative_pnl += pnl
        self.inventories[condition_id] = new_inventory
        self.total_trades += 1
        
        # Create trade object
        trade = Trade(
            timestamp=datetime.now().isoformat(),
            action=action,
            market_question=market_question,
            condition_id=condition_id,
            price=price,
            size=size,
            cost=cost if action == "BUY" else -cost,
            inventory_after=new_inventory,
            pnl=pnl,
            cumulative_pnl=self.cumulative_pnl
        )
        
        # Save to CSV
        self._save_trade(trade)
        
        # Log
        logger.success(
            f"[TRADE] {action} {size} @ ${price:.4f} | "
            f"PnL: ${pnl:+.2f} | "
            f"Inventory: {new_inventory:+d} | "
            f"Cumulative: ${self.cumulative_pnl:+.2f}"
        )
        
        return trade
    
    def _save_trade(self, trade: Trade):
        """Save trade to CSV."""
        try:
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade.timestamp,
                    trade.action,
                    trade.market_question,
                    trade.condition_id,
                    f"{trade.price:.4f}",
                    trade.size,
                    f"{trade.cost:.2f}",
                    trade.inventory_after,
                    f"{trade.pnl:.2f}",
                    f"{trade.cumulative_pnl:.2f}",
                ])
                f.flush()
                os.fsync(f.fileno())
        
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
    
    def get_inventory(self, condition_id: str) -> int:
        """Get current inventory for a market."""
        return self.inventories.get(condition_id, 0)
    
    def get_statistics(self) -> Dict:
        """Get trading statistics."""
        # Count wins/losses
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                trades = list(reader)
                
                if not trades:
                    return {
                        "total_trades": 0,
                        "total_pnl": 0.0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                    }
                
                winning_trades = sum(1 for t in trades if float(t['pnl']) > 0)
                losing_trades = sum(1 for t in trades if float(t['pnl']) < 0)
                
                return {
                    "total_trades": self.total_trades,
                    "total_pnl": self.cumulative_pnl,
                    "winning_trades": winning_trades,
                    "losing_trades": losing_trades,
                    "win_rate": (winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
                    "current_positions": len([inv for inv in self.inventories.values() if inv != 0]),
                }
        
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                "total_trades": self.total_trades,
                "total_pnl": self.cumulative_pnl,
            }
    
    def log_statistics(self):
        """Log trading statistics."""
        stats = self.get_statistics()
        
        logger.info("=" * 60)
        logger.info("SIMULATED TRADING STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Trades: {stats.get('total_trades', 0)}")
        logger.info(f"Total PnL: ${stats.get('total_pnl', 0):.2f}")
        
        if 'winning_trades' in stats:
            logger.info(f"Winning Trades: {stats['winning_trades']}")
            logger.info(f"Losing Trades: {stats['losing_trades']}")
            logger.info(f"Win Rate: {stats['win_rate']:.1f}%")
        
        if 'current_positions' in stats:
            logger.info(f"Current Open Positions: {stats['current_positions']}")
        
        logger.info(f"CSV File: {self.csv_file}")
        logger.info("=" * 60)


# Example usage
if __name__ == "__main__":
    logger.info("Testing SimulatedTradeLogger...")
    
    trade_logger = SimulatedTradeLogger("test_trades.csv")
    
    # Simulate some trades
    market = "Bitcoin Up or Down - Test"
    condition_id = "test123"
    
    # Buy
    trade_logger.simulate_fill("BUY", market, condition_id, 0.45, 100)
    
    # Sell for profit
    trade_logger.simulate_fill("SELL", market, condition_id, 0.55, 100)
    
    # Buy again
    trade_logger.simulate_fill("BUY", market, condition_id, 0.32, 50)
    
    # Sell for profit
    trade_logger.simulate_fill("SELL", market, condition_id, 0.35, 50)
    
    # Statistics
    trade_logger.log_statistics()
    
    # Clean up
    if os.path.exists("test_trades.csv"):
        os.remove("test_trades.csv")
    
    logger.success("Test completed!")

