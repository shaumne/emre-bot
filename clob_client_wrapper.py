"""
Wrapper for py-clob-client to provide async interface.
Handles ClobClient initialization and API credential management.
"""

import asyncio
from typing import Optional, Dict, Any
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, ApiCreds
from py_clob_client.order_builder.constants import BUY, SELL
from loguru import logger

from config import Config


class ClobClientWrapper:
    """
    Async wrapper for Polymarket ClobClient.
    
    The official py-clob-client is synchronous, so we wrap it
    to work with our async architecture.
    """
    
    def __init__(self, config: Config):
        """
        Initialize CLOB client wrapper.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.client: Optional[ClobClient] = None
        self._initialized = False
        
        logger.info("ClobClientWrapper initialized")
    
    def initialize(self):
        """
        Initialize ClobClient with credentials.
        
        This is synchronous as py-clob-client doesn't support async initialization.
        
        Raises:
            Exception: If initialization fails
        """
        try:
            # Create ClobClient based on signature type
            if self.config.uses_proxy:
                # Using Polymarket proxy wallet (signature_type 1 or 2)
                if not self.config.poly_proxy_address:
                    raise ValueError(
                        "POLY_PROXY_ADDRESS is required when using "
                        "signature_type 1 or 2"
                    )
                
                self.client = ClobClient(
                    host=self.config.clob_api_url,
                    key=self.config.poly_private_key,
                    chain_id=self.config.chain_id,
                    signature_type=self.config.poly_signature_type,
                    funder=self.config.poly_proxy_address,
                )
                
                logger.info(
                    f"ClobClient initialized with proxy wallet: "
                    f"{self.config.poly_proxy_address[:10]}..."
                )
            else:
                # Using EOA (signature_type 0)
                self.client = ClobClient(
                    host=self.config.clob_api_url,
                    key=self.config.poly_private_key,
                    chain_id=self.config.chain_id,
                )
                
                logger.info("ClobClient initialized with EOA wallet")
            
            # Create or derive API credentials (L2 authentication)
            api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(api_creds)
            
            logger.success("API credentials created and set")
            logger.info(f"API Key: {api_creds.api_key[:16]}...")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize ClobClient: {e}")
            raise
    
    async def initialize_async(self):
        """Async wrapper for initialize()."""
        await asyncio.get_event_loop().run_in_executor(None, self.initialize)
    
    def create_order(self, order_args: OrderArgs) -> Dict[str, Any]:
        """
        Create and sign an order (synchronous).
        
        Args:
            order_args: Order arguments
        
        Returns:
            Signed order dictionary
        
        Raises:
            Exception: If client not initialized or order creation fails
        """
        if not self._initialized or not self.client:
            raise RuntimeError("ClobClient not initialized. Call initialize() first.")
        
        try:
            signed_order = self.client.create_order(order_args)
            return signed_order
            
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            raise
    
    async def create_order_async(self, order_args: OrderArgs) -> Dict[str, Any]:
        """
        Create and sign an order (async).
        
        Args:
            order_args: Order arguments
        
        Returns:
            Signed order dictionary
        """
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self.create_order,
            order_args
        )
    
    def post_order(
        self,
        signed_order: Dict[str, Any],
        order_type: OrderType = OrderType.GTC
    ) -> Dict[str, Any]:
        """
        Post a signed order to the CLOB (synchronous).
        
        Args:
            signed_order: Signed order dictionary
            order_type: Order type (GTC, FOK, GTD)
        
        Returns:
            Order response dictionary
        
        Raises:
            Exception: If order submission fails
        """
        if not self._initialized or not self.client:
            raise RuntimeError("ClobClient not initialized. Call initialize() first.")
        
        try:
            response = self.client.post_order(signed_order, order_type)
            return response
            
        except Exception as e:
            logger.error(f"Failed to post order: {e}")
            raise
    
    async def post_order_async(
        self,
        signed_order: Dict[str, Any],
        order_type: OrderType = OrderType.GTC
    ) -> Dict[str, Any]:
        """
        Post a signed order to the CLOB (async).
        
        Args:
            signed_order: Signed order dictionary
            order_type: Order type (GTC, FOK, GTD)
        
        Returns:
            Order response dictionary
        """
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self.post_order,
            signed_order,
            order_type
        )
    
    async def create_and_post_order(
        self,
        order_args: OrderArgs,
        order_type: OrderType = OrderType.GTC
    ) -> Dict[str, Any]:
        """
        Create, sign, and post an order in one call (async).
        
        Args:
            order_args: Order arguments
            order_type: Order type (GTC, FOK, GTD)
        
        Returns:
            Order response dictionary
        """
        # Create and sign order
        signed_order = await self.create_order_async(order_args)
        
        # Post order
        response = await self.post_order_async(signed_order, order_type)
        
        return response
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order (synchronous).
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            Cancellation response
        """
        if not self._initialized or not self.client:
            raise RuntimeError("ClobClient not initialized. Call initialize() first.")
        
        try:
            response = self.client.cancel(order_id)
            return response
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise
    
    async def cancel_order_async(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order (async).
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            Cancellation response
        """
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self.cancel_order,
            order_id
        )
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status (synchronous).
        
        Args:
            order_id: Order ID
        
        Returns:
            Order details
        """
        if not self._initialized or not self.client:
            raise RuntimeError("ClobClient not initialized. Call initialize() first.")
        
        try:
            order = self.client.get_order(order_id)
            return order
            
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            raise
    
    async def get_order_async(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status (async).
        
        Args:
            order_id: Order ID
        
        Returns:
            Order details
        """
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self.get_order,
            order_id
        )
    
    def get_orderbook(self, token_id: str) -> Dict[str, Any]:
        """
        Get orderbook for a token (synchronous).
        
        Args:
            token_id: Token ID
        
        Returns:
            Orderbook data
        """
        if not self._initialized or not self.client:
            raise RuntimeError("ClobClient not initialized. Call initialize() first.")
        
        try:
            orderbook = self.client.get_order_book(token_id)
            return orderbook
            
        except Exception as e:
            logger.error(f"Failed to get orderbook for {token_id}: {e}")
            raise
    
    async def get_orderbook_async(self, token_id: str) -> Dict[str, Any]:
        """
        Get orderbook for a token (async).
        
        Args:
            token_id: Token ID
        
        Returns:
            Orderbook data
        """
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self.get_orderbook,
            token_id
        )
    
    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized


def create_buy_order_args(
    token_id: str,
    price: float,
    size: float,
    negrisk: bool = False
) -> OrderArgs:
    """
    Create OrderArgs for a BUY order.
    
    Args:
        token_id: Token ID to buy
        price: Price per token (0.0 - 1.0)
        size: Number of tokens to buy
        negrisk: Whether this is a negrisk market
    
    Returns:
        OrderArgs object
    """
    return OrderArgs(
        price=price,
        size=size,
        side=BUY,
        token_id=token_id,
        negrisk=negrisk,
    )


def create_sell_order_args(
    token_id: str,
    price: float,
    size: float,
    negrisk: bool = False
) -> OrderArgs:
    """
    Create OrderArgs for a SELL order.
    
    Args:
        token_id: Token ID to sell
        price: Price per token (0.0 - 1.0)
        size: Number of tokens to sell
        negrisk: Whether this is a negrisk market
    
    Returns:
        OrderArgs object
    """
    return OrderArgs(
        price=price,
        size=size,
        side=SELL,
        token_id=token_id,
        negrisk=negrisk,
    )


async def test_clob_client():
    """Test CLOB client wrapper."""
    from config import Config
    
    print("Testing ClobClientWrapper...")
    
    # Create config
    try:
        config = Config()
    except Exception as e:
        print(f"⚠️  Config error (expected if .env not set): {e}")
        print("   Skipping CLOB client test (requires valid credentials)")
        return
    
    # Create wrapper
    wrapper = ClobClientWrapper(config)
    
    # Test initialization
    print("\n1. Testing initialization...")
    try:
        await wrapper.initialize_async()
        print("   ✓ Client initialized successfully")
    except Exception as e:
        print(f"   ✗ Initialization failed: {e}")
        return
    
    # Test order creation (without posting)
    print("\n2. Testing order creation...")
    try:
        order_args = create_buy_order_args(
            token_id="12345",
            price=0.50,
            size=10.0,
        )
        print(f"   ✓ OrderArgs created: {order_args.price} @ {order_args.size}")
    except Exception as e:
        print(f"   ✗ Order creation failed: {e}")
    
    print("\n✓ ClobClientWrapper test completed!")


if __name__ == "__main__":
    asyncio.run(test_clob_client())


