"""
WebSocket manager for Polymarket CLOB Market Channel.
Handles real-time orderbook updates and event parsing.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Callable, Any
import websockets
from websockets.client import WebSocketClientProtocol
from loguru import logger

from config import Config
from market_manager import Market


class OrderbookSnapshot:
    """Represents an orderbook snapshot for a token."""
    
    def __init__(self, asset_id: str, event_data: Dict[str, Any]):
        """
        Initialize orderbook snapshot from event data.
        
        Args:
            asset_id: Token ID
            event_data: Event data from WebSocket
        """
        self.asset_id = asset_id
        self.timestamp = event_data.get("timestamp", "")
        self.hash = event_data.get("hash", "")
        
        # Parse bids and asks
        self.bids = self._parse_orders(event_data.get("bids", []))
        self.asks = self._parse_orders(event_data.get("asks", []))
    
    def _parse_orders(self, orders: List[Dict]) -> List[Dict[str, float]]:
        """Parse order list to standardized format."""
        return [
            {
                "price": float(order["price"]),
                "size": float(order["size"]),
            }
            for order in orders
        ]
    
    def get_best_bid(self) -> Optional[Dict[str, float]]:
        """Get best bid (highest buy price)."""
        return self.bids[0] if self.bids else None
    
    def get_best_ask(self) -> Optional[Dict[str, float]]:
        """Get best ask (lowest sell price)."""
        return self.asks[0] if self.asks else None
    
    def __repr__(self) -> str:
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        return (
            f"Orderbook(asset={self.asset_id[:16]}..., "
            f"bid={best_bid['price'] if best_bid else 'N/A'}, "
            f"ask={best_ask['price'] if best_ask else 'N/A'})"
        )


class WebSocketManager:
    """
    Manages WebSocket connection to Polymarket Market Channel.
    Handles subscriptions and real-time orderbook updates.
    """
    
    def __init__(self, config: Config):
        """
        Initialize WebSocket manager.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.ws: Optional[WebSocketClientProtocol] = None
        self.orderbooks: Dict[str, OrderbookSnapshot] = {}  # asset_id -> orderbook
        self.subscribed_markets: List[str] = []
        self.subscribed_assets: List[str] = []
        
        # Callbacks
        self.on_book_update: Optional[Callable] = None
        self.on_price_change: Optional[Callable] = None
        
        # Connection management
        self._running = False
        self._reconnect_delay = 5.0
        self._max_reconnect_delay = 60.0
        
        logger.info("WebSocketManager initialized")
    
    async def connect(self):
        """
        Connect to WebSocket endpoint.
        
        Raises:
            Exception: If connection fails
        """
        try:
            logger.info(f"Connecting to WebSocket: {self.config.wss_url}")
            
            self.ws = await websockets.connect(
                self.config.wss_url,
                ping_interval=20,
                ping_timeout=10,
            )
            
            logger.success("WebSocket connected")
            
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            raise
    
    async def subscribe_to_markets(self, markets: List[Market]):
        """
        Subscribe to Market Channel for multiple markets.
        
        Args:
            markets: List of Market objects to subscribe to
        """
        if not self.ws:
            await self.connect()
        
        # Collect all asset IDs and market IDs
        asset_ids = []
        market_ids = []
        
        for market in markets:
            if market.yes_token_id:
                asset_ids.append(market.yes_token_id)
            if market.no_token_id:
                asset_ids.append(market.no_token_id)
            if market.condition_id:
                market_ids.append(market.condition_id)
        
        # Limit subscriptions
        if len(asset_ids) > self.config.max_ws_subscriptions * 2:
            logger.warning(
                f"Too many assets to subscribe ({len(asset_ids)}). "
                f"Limiting to {self.config.max_ws_subscriptions * 2}"
            )
            asset_ids = asset_ids[:self.config.max_ws_subscriptions * 2]
            market_ids = market_ids[:self.config.max_ws_subscriptions]
        
        # Build subscription message (Market Channel is public, no auth needed)
        # Note: type must be lowercase "market" according to docs
        subscribe_msg = {
            "type": "market",
            "assets_ids": asset_ids,
        }
        
        logger.info(
            f"Subscribing to {len(market_ids)} markets "
            f"({len(asset_ids)} assets)"
        )
        
        try:
            await self.ws.send(json.dumps(subscribe_msg))
            
            self.subscribed_assets = asset_ids
            self.subscribed_markets = market_ids
            
            logger.success(
                f"Subscribed to {len(market_ids)} markets successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to subscribe to markets: {e}")
            raise
    
    async def listen(self):
        """
        Listen for WebSocket messages and handle events.
        
        This runs in a loop until stopped.
        """
        self._running = True
        reconnect_delay = self._reconnect_delay
        last_ping_time = time.time()
        ping_interval = 10.0  # Send PING every 10 seconds
        
        while self._running:
            try:
                # Check if WebSocket is connected
                if not self.ws:
                    logger.warning("WebSocket not connected, connecting...")
                    await self.connect()
                    
                    # Resubscribe to markets if we had subscriptions
                    if self.subscribed_assets:
                        subscribe_msg = {
                            "type": "market",
                            "assets_ids": self.subscribed_assets,
                        }
                        await self.ws.send(json.dumps(subscribe_msg))
                        logger.info("Resubscribed to markets after reconnection")
                        last_ping_time = time.time()
                
                # Send PING to keep connection alive (every 10 seconds)
                current_time = time.time()
                if current_time - last_ping_time >= ping_interval:
                    if self.ws:
                        try:
                            await self.ws.send("PING")
                            last_ping_time = current_time
                        except Exception:
                            pass
                            # Connection might be closed, will be handled below
                
                # Receive message with timeout to allow PING sending
                try:
                    message = await asyncio.wait_for(
                        self.ws.recv(),
                        timeout=1.0  # 1 second timeout to check for PING
                    )
                    
                    # Reset reconnect delay on successful receive
                    reconnect_delay = self._reconnect_delay
                    
                    # Parse and handle message
                    await self._handle_message(message)
                    
                except asyncio.TimeoutError:
                    # Timeout is OK, we'll check for PING and continue
                    continue
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                
                if self._running:
                    logger.info(f"Reconnecting in {reconnect_delay}s...")
                    await asyncio.sleep(reconnect_delay)
                    
                    # Exponential backoff
                    reconnect_delay = min(
                        reconnect_delay * 2,
                        self._max_reconnect_delay
                    )
                
            except Exception as e:
                logger.error(f"Error in WebSocket listen loop: {e}")
                
                if self._running:
                    await asyncio.sleep(reconnect_delay)
    
    async def _handle_message(self, message: str):
        """
        Handle incoming WebSocket message.
        
        Args:
            message: Raw message string
        """
        try:
            data = json.loads(message)
            event_type = data.get("event_type")
            
            if event_type == "book":
                await self._handle_book_event(data)
            elif event_type == "price_change":
                await self._handle_price_change_event(data)
            elif event_type == "last_trade_price":
                await self._handle_last_trade_event(data)
            elif event_type == "tick_size_change":
                await self._handle_tick_size_change(data)
            else:
                pass
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def _handle_book_event(self, data: Dict[str, Any]):
        """
        Handle 'book' event (full orderbook snapshot).
        
        Args:
            data: Event data
        """
        asset_id = data.get("asset_id", "")
        market = data.get("market", "")
        
        # Create orderbook snapshot
        orderbook = OrderbookSnapshot(asset_id, data)
        
        # Cache orderbook
        self.orderbooks[asset_id] = orderbook
        
        # Trigger callback
        if self.on_book_update:
            try:
                await self.on_book_update(market, asset_id, orderbook)
            except Exception as e:
                logger.error(f"Error in book update callback: {e}")
    
    async def _handle_price_change_event(self, data: Dict[str, Any]):
        """
        Handle 'price_change' event (incremental orderbook update).
        
        Args:
            data: Event data
        """
        market = data.get("market", "")
        price_changes = data.get("price_changes", [])
        
        for change in price_changes:
            asset_id = change.get("asset_id", "")
            best_bid = change.get("best_bid")
            best_ask = change.get("best_ask")
            size_str = str(change.get("size", "100"))
            
            # Build minimal orderbook snapshot from price_change for arbitrage detection
            if best_bid is not None and best_ask is not None:
                try:
                    event_data = {
                        "bids": [{"price": str(best_bid), "size": size_str}] if best_bid and float(best_bid) > 0 else [],
                        "asks": [{"price": str(best_ask), "size": size_str}] if best_ask and float(best_ask) > 0 else [],
                        "timestamp": data.get("timestamp", ""),
                        "hash": change.get("hash", ""),
                    }
                    orderbook = OrderbookSnapshot(asset_id, event_data)
                    self.orderbooks[asset_id] = orderbook
                    
                    # Trigger same callback as book event - bot will check arbitrage
                    if self.on_book_update:
                        try:
                            await self.on_book_update(market, asset_id, orderbook)
                        except Exception as e:
                            logger.error(f"Error in price change -> book callback: {e}")
                except (ValueError, TypeError) as e:
                    logger.debug(f"Invalid price_change data for {asset_id[:16]}: {e}")
    
    async def _handle_last_trade_event(self, data: Dict[str, Any]):
        """Handle 'last_trade_price' event (market trades - not our executions)."""
        pass
    
    async def _handle_tick_size_change(self, data: Dict[str, Any]):
        """Handle 'tick_size_change' event (suppress - not trade related)."""
        pass
    
    def get_orderbook(self, asset_id: str) -> Optional[OrderbookSnapshot]:
        """
        Get cached orderbook for an asset.
        
        Args:
            asset_id: Token ID
        
        Returns:
            OrderbookSnapshot or None if not cached
        """
        return self.orderbooks.get(asset_id)
    
    def get_best_prices(
        self,
        yes_token_id: str,
        no_token_id: str
    ) -> Optional[Dict[str, float]]:
        """
        Get best ask prices for YES and NO tokens.
        
        Args:
            yes_token_id: YES token ID
            no_token_id: NO token ID
        
        Returns:
            Dictionary with yes_ask and no_ask prices or None
        """
        yes_book = self.orderbooks.get(yes_token_id)
        no_book = self.orderbooks.get(no_token_id)
        
        if not yes_book or not no_book:
            return None
        
        yes_ask = yes_book.get_best_ask()
        no_ask = no_book.get_best_ask()
        
        if not yes_ask or not no_ask:
            return None
        
        return {
            "yes_ask": yes_ask["price"],
            "no_ask": no_ask["price"],
        }
    
    async def stop(self):
        """Stop listening and close WebSocket connection."""
        self._running = False
        
        if self.ws:
            try:
                # Check if connection is still open by checking close_code
                if hasattr(self.ws, 'close_code') and self.ws.close_code is None:
                    await self.ws.close()
                    logger.info("WebSocket closed")
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")


async def test_websocket_manager():
    """Test WebSocket manager functionality."""
    from config import Config
    from market_manager import MarketManager
    from rate_limiter import RateLimiter
    
    print("Testing WebSocketManager...")
    
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
    
    # Fetch some markets
    print("\n1. Fetching markets...")
    markets = await market_manager.fetch_markets_by_tag("crypto", limit=3)
    print(f"   Found {len(markets)} markets")
    
    if not markets:
        print("   No markets found, skipping WebSocket test")
        return
    
    # Connect and subscribe
    print("\n2. Connecting to WebSocket...")
    try:
        await ws_manager.connect()
        await ws_manager.subscribe_to_markets(markets)
        print("   ✓ Connected and subscribed")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return
    
    # Listen for 10 seconds
    print("\n3. Listening for events (10 seconds)...")
    
    async def listen_task():
        await ws_manager.listen()
    
    async def timeout_task():
        await asyncio.sleep(10)
        await ws_manager.stop()
    
    try:
        await asyncio.gather(listen_task(), timeout_task())
    except Exception as e:
        print(f"   Error during listen: {e}")
    
    # Check cached orderbooks
    print("\n4. Checking cached orderbooks...")
    orderbook_count = len(ws_manager.orderbooks)
    print(f"   Cached orderbooks: {orderbook_count}")
    
    if orderbook_count > 0:
        asset_id = list(ws_manager.orderbooks.keys())[0]
        orderbook = ws_manager.orderbooks[asset_id]
        print(f"   Example: {orderbook}")
    
    print("\n✓ WebSocketManager test completed!")
    
    # Cleanup
    await market_manager.close()


if __name__ == "__main__":
    asyncio.run(test_websocket_manager())


