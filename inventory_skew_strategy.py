"""
Inventory Skew Market Making Strategy

This module implements a linear inventory skew strategy for market making on Polymarket.
The strategy adjusts bid/ask quotes based on current inventory position to maintain 
delta neutrality and manage risk.

Core Logic:
    - If we're Long (positive inventory) → Lower quotes to encourage selling
    - If we're Short (negative inventory) → Raise quotes to encourage buying
    - This keeps us hedged and reduces directional risk

Author: Senior Quantitative Developer
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class QuoteResult:
    """Result of quote calculation."""
    bid_price: float
    ask_price: float
    fair_value: float
    inventory_adjustment: float
    should_stop_buying: bool
    should_stop_selling: bool
    reason: Optional[str] = None


class InventorySkewStrategy:
    """
    Linear Inventory Skew Market Making Strategy.
    
    This strategy calculates bid/ask quotes that dynamically adjust based on 
    current inventory position. The goal is to maintain a delta-neutral position
    by making it more attractive to trade in the direction that reduces inventory risk.
    
    Mathematical Model:
        1. Mid_Price = (Best_Bid + Best_Ask) / 2
        2. Inventory_Risk_Adj = Current_Inventory * Skew_Factor
        3. Fair_Value = Mid_Price - Inventory_Risk_Adj
        4. My_Bid_Price = Fair_Value - (Spread / 2)
        5. My_Ask_Price = Fair_Value + (Spread / 2)
    
    Example:
        >>> strategy = InventorySkewStrategy(
        ...     target_spread=0.02,
        ...     skew_factor=0.0001,
        ...     max_inventory=1000
        ... )
        >>> quotes = strategy.calculate_quotes(
        ...     best_bid=0.48,
        ...     best_ask=0.50,
        ...     current_inventory=500
        ... )
        >>> print(f"Bid: {quotes['bid_price']}, Ask: {quotes['ask_price']}")
    """
    
    # Polymarket price constraints
    MIN_PRICE = 0.01  # Minimum valid price (1 cent)
    MAX_PRICE = 0.99  # Maximum valid price (99 cents)
    
    def __init__(
        self,
        target_spread: float,
        skew_factor: float,
        max_inventory: int,
        min_spread: float = 0.01,
        max_spread: float = 0.10
    ):
        """
        Initialize the Inventory Skew Strategy.
        
        Args:
            target_spread: Target spread between bid and ask (e.g., 0.02 = 2 cents profit)
            skew_factor: How much to adjust price per token held (e.g., 0.0001)
                        Higher = more aggressive inventory management
            max_inventory: Maximum inventory position (positive or negative)
                          Stop quoting when |inventory| exceeds this
            min_spread: Minimum allowed spread (default: 0.01 = 1 cent)
            max_spread: Maximum allowed spread (default: 0.10 = 10 cents)
        
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate inputs
        if target_spread <= 0:
            raise ValueError(f"target_spread must be positive, got {target_spread}")
        if skew_factor <= 0:
            raise ValueError(f"skew_factor must be positive, got {skew_factor}")
        if max_inventory <= 0:
            raise ValueError(f"max_inventory must be positive, got {max_inventory}")
        if min_spread <= 0 or min_spread >= 1:
            raise ValueError(f"min_spread must be in (0, 1), got {min_spread}")
        if max_spread <= min_spread or max_spread >= 1:
            raise ValueError(f"max_spread must be in (min_spread, 1), got {max_spread}")
        if target_spread < min_spread:
            raise ValueError(f"target_spread ({target_spread}) cannot be less than min_spread ({min_spread})")
        if target_spread > max_spread:
            raise ValueError(f"target_spread ({target_spread}) cannot exceed max_spread ({max_spread})")
        
        self.target_spread = target_spread
        self.skew_factor = skew_factor
        self.max_inventory = max_inventory
        self.min_spread = min_spread
        self.max_spread = max_spread
        
        logger.info("=" * 60)
        logger.info("INVENTORY SKEW STRATEGY INITIALIZED")
        logger.info("=" * 60)
        logger.info(f"Target Spread: {self.target_spread * 100:.2f}% ({self.target_spread:.4f})")
        logger.info(f"Skew Factor: {self.skew_factor:.6f}")
        logger.info(f"Max Inventory: ±{self.max_inventory} tokens")
        logger.info(f"Spread Range: {self.min_spread * 100:.1f}% - {self.max_spread * 100:.1f}%")
        logger.info("=" * 60)
    
    def calculate_quotes(
        self,
        best_bid: float,
        best_ask: float,
        current_inventory: int
    ) -> Dict:
        """
        Calculate bid and ask quotes based on market state and inventory position.
        
        This is the core strategy logic that implements the inventory skew model.
        
        Args:
            best_bid: Current market best bid price (e.g., 0.48)
            best_ask: Current market best ask price (e.g., 0.50)
            current_inventory: Net inventory position
                              Positive = Long YES tokens
                              Negative = Short YES tokens (Long NO)
        
        Returns:
            dict: {
                "bid_price": float,              # Our bid quote (rounded to 2 decimals)
                "ask_price": float,              # Our ask quote (rounded to 2 decimals)
                "fair_value": float,             # Calculated fair value
                "inventory_adjustment": float,   # Price adjustment due to inventory
                "should_stop_buying": bool,      # True if inventory too high
                "should_stop_selling": bool,     # True if inventory too low (short)
                "mid_price": float,              # Market mid price
                "spread": float,                 # Actual spread used
                "reason": str or None            # Reason if quotes are invalid
            }
        
        Example:
            >>> result = strategy.calculate_quotes(0.48, 0.50, 500)
            >>> if not result["should_stop_buying"]:
            ...     place_bid_order(result["bid_price"])
            >>> if not result["should_stop_selling"]:
            ...     place_ask_order(result["ask_price"])
        """
        # Input validation
        validation_result = self._validate_inputs(best_bid, best_ask, current_inventory)
        if validation_result:
            return validation_result
        
        # Step 1: Calculate Mid Price
        mid_price = (best_bid + best_ask) / 2.0
        
        # Step 2: Calculate Inventory Risk Adjustment
        # Positive inventory (Long) → Negative adjustment → Lower fair value → Encourage selling
        # Negative inventory (Short) → Positive adjustment → Higher fair value → Encourage buying
        inventory_adjustment = current_inventory * self.skew_factor
        
        # Step 3: Calculate Fair Value
        fair_value = mid_price - inventory_adjustment
        
        # Step 4: Calculate Bid and Ask Prices
        half_spread = self.target_spread / 2.0
        raw_bid = fair_value - half_spread
        raw_ask = fair_value + half_spread
        
        # Step 5: Apply Price Constraints (0 < price < 1)
        bid_price = self._clamp_price(raw_bid)
        ask_price = self._clamp_price(raw_ask)
        
        # Ensure bid < ask (can be violated by clamping)
        if bid_price >= ask_price:
            # Adjust to maintain minimum spread
            mid = (bid_price + ask_price) / 2.0
            bid_price = max(self.MIN_PRICE, mid - self.min_spread / 2.0)
            ask_price = min(self.MAX_PRICE, mid + self.min_spread / 2.0)
            
            # If still invalid, quotes are not feasible
            if bid_price >= ask_price:
                return self._create_invalid_quote_response(
                    mid_price, inventory_adjustment, current_inventory,
                    "Bid >= Ask after constraint adjustments"
                )
        
        # Step 6: Round to 2 decimal places (penny precision)
        bid_price = round(bid_price, 2)
        ask_price = round(ask_price, 2)
        fair_value = round(fair_value, 4)
        actual_spread = round(ask_price - bid_price, 4)
        
        # Step 7: Check Inventory Limits
        should_stop_buying = abs(current_inventory) >= self.max_inventory and current_inventory > 0
        should_stop_selling = abs(current_inventory) >= self.max_inventory and current_inventory < 0
        
        # Log quote calculation
        self._log_quote_calculation(
            best_bid, best_ask, mid_price, current_inventory,
            inventory_adjustment, fair_value, bid_price, ask_price,
            should_stop_buying, should_stop_selling
        )
        
        return {
            "bid_price": bid_price,
            "ask_price": ask_price,
            "fair_value": fair_value,
            "inventory_adjustment": inventory_adjustment,
            "should_stop_buying": should_stop_buying,
            "should_stop_selling": should_stop_selling,
            "mid_price": mid_price,
            "spread": actual_spread,
            "reason": None
        }
    
    def _validate_inputs(
        self,
        best_bid: float,
        best_ask: float,
        current_inventory: int
    ) -> Optional[Dict]:
        """
        Validate input parameters.
        
        Returns:
            Dict with error response if validation fails, None otherwise
        """
        # Check for None/NaN values
        if best_bid is None or best_ask is None:
            return self._create_invalid_quote_response(
                0.0, 0.0, current_inventory or 0,
                "Invalid market data: best_bid or best_ask is None"
            )
        
        # Check price range
        if best_bid <= 0 or best_bid >= 1:
            return self._create_invalid_quote_response(
                0.0, 0.0, current_inventory,
                f"Invalid best_bid: {best_bid} (must be in range 0 < p < 1)"
            )
        
        if best_ask <= 0 or best_ask >= 1:
            return self._create_invalid_quote_response(
                0.0, 0.0, current_inventory,
                f"Invalid best_ask: {best_ask} (must be in range 0 < p < 1)"
            )
        
        # Check bid < ask
        if best_bid >= best_ask:
            return self._create_invalid_quote_response(
                0.0, 0.0, current_inventory,
                f"Invalid market: best_bid ({best_bid}) >= best_ask ({best_ask})"
            )
        
        # Check if spread is too wide
        market_spread = best_ask - best_bid
        if market_spread > 0.5:  # More than 50 cents
            logger.warning(
                f"Unusually wide market spread: {market_spread * 100:.1f}% "
                f"(Bid: {best_bid}, Ask: {best_ask})"
            )
        
        return None
    
    def _clamp_price(self, price: float) -> float:
        """
        Clamp price to valid Polymarket range (0.01 to 0.99).
        
        Args:
            price: Raw calculated price
        
        Returns:
            Clamped price within valid range
        """
        return max(self.MIN_PRICE, min(self.MAX_PRICE, price))
    
    def _create_invalid_quote_response(
        self,
        mid_price: float,
        inventory_adjustment: float,
        current_inventory: int,
        reason: str
    ) -> Dict:
        """
        Create response for invalid quote scenarios.
        
        Args:
            mid_price: Market mid price
            inventory_adjustment: Calculated inventory adjustment
            current_inventory: Current inventory position
            reason: Reason why quotes are invalid
        
        Returns:
            Dict with invalid quote data
        """
        logger.warning(f"⚠️ Invalid Quote: {reason}")
        
        return {
            "bid_price": 0.0,
            "ask_price": 0.0,
            "fair_value": 0.0,
            "inventory_adjustment": inventory_adjustment,
            "should_stop_buying": True,
            "should_stop_selling": True,
            "mid_price": mid_price,
            "spread": 0.0,
            "reason": reason
        }
    
    def _log_quote_calculation(
        self,
        best_bid: float,
        best_ask: float,
        mid_price: float,
        current_inventory: int,
        inventory_adjustment: float,
        fair_value: float,
        bid_price: float,
        ask_price: float,
        should_stop_buying: bool,
        should_stop_selling: bool
    ):
        """Log detailed quote calculation for debugging and monitoring."""
        logger.debug("=" * 60)
        logger.debug("QUOTE CALCULATION")
        logger.debug("=" * 60)
        logger.debug(f"Market Data:")
        logger.debug(f"  Best Bid: ${best_bid:.4f}")
        logger.debug(f"  Best Ask: ${best_ask:.4f}")
        logger.debug(f"  Mid Price: ${mid_price:.4f}")
        logger.debug(f"  Market Spread: ${best_ask - best_bid:.4f} ({(best_ask - best_bid) * 100:.2f}%)")
        logger.debug(f"")
        logger.debug(f"Inventory:")
        logger.debug(f"  Current: {current_inventory:+d} tokens")
        logger.debug(f"  Max Allowed: ±{self.max_inventory}")
        logger.debug(f"  Utilization: {abs(current_inventory) / self.max_inventory * 100:.1f}%")
        logger.debug(f"  Risk Adjustment: ${inventory_adjustment:+.6f}")
        logger.debug(f"")
        logger.debug(f"Calculated Quotes:")
        logger.debug(f"  Fair Value: ${fair_value:.4f}")
        logger.debug(f"  Our Bid: ${bid_price:.4f}")
        logger.debug(f"  Our Ask: ${ask_price:.4f}")
        logger.debug(f"  Our Spread: ${ask_price - bid_price:.4f} ({(ask_price - bid_price) * 100:.2f}%)")
        logger.debug(f"")
        logger.debug(f"Risk Controls:")
        logger.debug(f"  Stop Buying: {should_stop_buying}")
        logger.debug(f"  Stop Selling: {should_stop_selling}")
        logger.debug("=" * 60)
    
    def get_strategy_stats(self, current_inventory: int) -> Dict:
        """
        Get current strategy statistics and risk metrics.
        
        Args:
            current_inventory: Current inventory position
        
        Returns:
            Dict with strategy statistics
        """
        inventory_utilization = abs(current_inventory) / self.max_inventory
        max_price_skew = self.max_inventory * self.skew_factor
        
        return {
            "target_spread": self.target_spread,
            "skew_factor": self.skew_factor,
            "max_inventory": self.max_inventory,
            "current_inventory": current_inventory,
            "inventory_utilization_pct": inventory_utilization * 100,
            "max_price_skew": max_price_skew,
            "is_at_max_long": current_inventory >= self.max_inventory,
            "is_at_max_short": current_inventory <= -self.max_inventory,
        }
    
    def update_parameters(
        self,
        target_spread: Optional[float] = None,
        skew_factor: Optional[float] = None,
        max_inventory: Optional[int] = None
    ):
        """
        Update strategy parameters dynamically.
        
        Useful for adjusting risk management during trading based on market conditions.
        
        Args:
            target_spread: New target spread (optional)
            skew_factor: New skew factor (optional)
            max_inventory: New max inventory limit (optional)
        """
        if target_spread is not None:
            if target_spread <= 0 or target_spread >= 1:
                raise ValueError(f"Invalid target_spread: {target_spread}")
            old_spread = self.target_spread
            self.target_spread = target_spread
            logger.info(f"Updated target_spread: {old_spread:.4f} → {target_spread:.4f}")
        
        if skew_factor is not None:
            if skew_factor <= 0:
                raise ValueError(f"Invalid skew_factor: {skew_factor}")
            old_skew = self.skew_factor
            self.skew_factor = skew_factor
            logger.info(f"Updated skew_factor: {old_skew:.6f} → {skew_factor:.6f}")
        
        if max_inventory is not None:
            if max_inventory <= 0:
                raise ValueError(f"Invalid max_inventory: {max_inventory}")
            old_max = self.max_inventory
            self.max_inventory = max_inventory
            logger.info(f"Updated max_inventory: ±{old_max} → ±{max_inventory}")


# Example usage and testing
if __name__ == "__main__":
    # Initialize strategy
    strategy = InventorySkewStrategy(
        target_spread=0.02,     # 2 cent spread
        skew_factor=0.0001,     # 1 basis point per token
        max_inventory=1000      # Max 1000 tokens long or short
    )
    
    # Test scenarios
    test_cases = [
        # (best_bid, best_ask, inventory, description)
        (0.48, 0.50, 0, "Neutral inventory"),
        (0.48, 0.50, 500, "Long 500 tokens"),
        (0.48, 0.50, -500, "Short 500 tokens"),
        (0.48, 0.50, 1000, "Max long position"),
        (0.48, 0.50, -1000, "Max short position"),
        (0.48, 0.50, 1500, "Over max long"),
        (0.10, 0.12, 0, "Low price market"),
        (0.88, 0.90, 0, "High price market"),
        (0.01, 0.99, 0, "Extremely wide spread"),
    ]
    
    print("\n" + "=" * 80)
    print("INVENTORY SKEW STRATEGY - TEST SCENARIOS")
    print("=" * 80)
    
    for best_bid, best_ask, inventory, description in test_cases:
        print(f"\n[Test] {description}")
        print(f"   Market: Bid={best_bid:.2f}, Ask={best_ask:.2f}, Inventory={inventory:+d}")
        
        result = strategy.calculate_quotes(best_bid, best_ask, inventory)
        
        if result["reason"]:
            print(f"   [X] Invalid: {result['reason']}")
        else:
            print(f"   [OK] Valid Quotes:")
            print(f"      Fair Value: ${result['fair_value']:.4f}")
            print(f"      Our Bid: ${result['bid_price']:.2f}")
            print(f"      Our Ask: ${result['ask_price']:.2f}")
            print(f"      Spread: ${result['spread']:.4f} ({result['spread'] * 100:.2f}%)")
            print(f"      Inventory Adj: ${result['inventory_adjustment']:+.6f}")
            
            if result["should_stop_buying"]:
                print(f"      [!] STOP BUYING (inventory too high)")
            if result["should_stop_selling"]:
                print(f"      [!] STOP SELLING (inventory too low)")
    
    print("\n" + "=" * 80)
    print("[OK] All tests completed!")
    print("=" * 80)

