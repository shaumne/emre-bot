"""
Market Maker Trade Logger

CSV'ye canlı olarak market maker quote'larını kaydeder.
"""

import csv
import os
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger


class MarketMakerLogger:
    """Market maker quote'larını CSV'ye kaydeder."""
    
    def __init__(self, csv_file: str):
        """
        Initialize logger.
        
        Args:
            csv_file: CSV file path
        """
        self.csv_file = csv_file
        self._initialize_csv()
        logger.info(f"MarketMakerLogger initialized: {csv_file}")
    
    def _initialize_csv(self):
        """Initialize CSV file with headers."""
        if os.path.exists(self.csv_file):
            logger.info(f"CSV file exists: {self.csv_file}")
            return
        
        headers = [
            "timestamp",
            "market_question",
            "condition_id",
            "inventory",
            "inventory_utilization_pct",
            "market_best_bid",
            "market_best_ask",
            "market_spread",
            "our_bid",
            "our_ask",
            "our_spread",
            "fair_value",
            "inventory_adjustment",
            "should_stop_buying",
            "should_stop_selling",
        ]
        
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        
        logger.info(f"Created CSV file: {self.csv_file}")
    
    def log_quote(
        self,
        market_question: str,
        condition_id: str,
        inventory: int,
        max_inventory: int,
        market_best_bid: float,
        market_best_ask: float,
        quotes: Dict[str, Any]
    ):
        """
        Log a quote to CSV.
        
        Args:
            market_question: Market question text
            condition_id: Market condition ID
            inventory: Current inventory
            max_inventory: Maximum inventory limit
            market_best_bid: Market's best bid price
            market_best_ask: Market's best ask price
            quotes: Quote calculation result
        """
        try:
            timestamp = datetime.now().isoformat()
            market_spread = market_best_ask - market_best_bid
            inventory_util = abs(inventory) / max_inventory * 100 if max_inventory > 0 else 0
            
            row = [
                timestamp,
                market_question,
                condition_id,
                inventory,
                f"{inventory_util:.1f}",
                f"{market_best_bid:.4f}",
                f"{market_best_ask:.4f}",
                f"{market_spread:.4f}",
                f"{quotes['bid_price']:.4f}",
                f"{quotes['ask_price']:.4f}",
                f"{quotes['spread']:.4f}",
                f"{quotes['fair_value']:.4f}",
                f"{quotes['inventory_adjustment']:+.6f}",
                quotes['should_stop_buying'],
                quotes['should_stop_selling'],
            ]
            
            # Append to CSV
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
                f.flush()  # Flush to OS buffer
                os.fsync(f.fileno())  # Ensure OS buffer is written to disk
            
            logger.debug(f"Logged quote: {condition_id[:16]}... Inv:{inventory:+d}")
        
        except Exception as e:
            logger.error(f"Failed to log quote to CSV: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from CSV file."""
        if not os.path.exists(self.csv_file):
            return {
                "total_quotes": 0,
                "unique_markets": 0,
            }
        
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
                if not rows:
                    return {
                        "total_quotes": 0,
                        "unique_markets": 0,
                    }
                
                unique_markets = set(row['condition_id'] for row in rows)
                
                return {
                    "total_quotes": len(rows),
                    "unique_markets": len(unique_markets),
                    "csv_file": self.csv_file,
                }
        
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "total_quotes": 0,
                "unique_markets": 0,
                "error": str(e),
            }

