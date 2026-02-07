"""
USDC balance checker for Polygon network using web3.py.
Provides async balance and allowance queries for trading validation.
"""

import asyncio
from typing import Optional
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
from web3.exceptions import Web3Exception
from loguru import logger

from config import Config


# ERC20 ABI (minimal - only balanceOf and allowance functions)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


class BalanceChecker:
    """
    Async USDC balance checker for Polygon network.
    """
    
    def __init__(self, config: Config):
        """
        Initialize balance checker.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.w3: Optional[AsyncWeb3] = None
        self.usdc_contract = None
        self.usdc_decimals = 6  # USDC has 6 decimals on Polygon
        
        logger.info(f"BalanceChecker initialized for {config.usdc_address}")
    
    async def connect(self):
        """
        Connect to Polygon RPC and initialize USDC contract.
        
        Raises:
            Web3Exception: If connection fails
        """
        try:
            # Initialize AsyncWeb3 with HTTP provider
            provider = AsyncHTTPProvider(self.config.polygon_rpc_url)
            self.w3 = AsyncWeb3(provider)
            
            # Check connection
            is_connected = await self.w3.is_connected()
            if not is_connected:
                raise Web3Exception(
                    f"Failed to connect to Polygon RPC: {self.config.polygon_rpc_url}"
                )
            
            # Get chain ID to verify we're on Polygon
            chain_id = await self.w3.eth.chain_id
            if chain_id != 137:
                logger.warning(
                    f"Connected to chain ID {chain_id} (expected 137 for Polygon)"
                )
            
            # Initialize USDC contract
            self.usdc_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(self.config.usdc_address),
                abi=ERC20_ABI,
            )
            
            # Verify decimals
            try:
                decimals = await self.usdc_contract.functions.decimals().call()
                self.usdc_decimals = decimals
                logger.info(f"USDC contract verified: {decimals} decimals")
            except Exception as e:
                logger.warning(f"Could not verify USDC decimals: {e}")
            
            logger.success(
                f"Connected to Polygon RPC (Chain ID: {chain_id})"
            )
            
        except Exception as e:
            logger.error(f"Failed to connect to Polygon: {e}")
            raise
    
    async def get_usdc_balance(self, wallet_address: str) -> float:
        """
        Get USDC balance for a wallet address.
        
        Args:
            wallet_address: Wallet address to check
        
        Returns:
            USDC balance in human-readable format (e.g., 100.50)
        
        Raises:
            Web3Exception: If query fails
        """
        if not self.w3 or not self.usdc_contract:
            await self.connect()
        
        try:
            # Get balance in wei (raw units)
            checksum_address = self.w3.to_checksum_address(wallet_address)
            balance_raw = await self.usdc_contract.functions.balanceOf(
                checksum_address
            ).call()
            
            # Convert to human-readable (divide by 10^decimals)
            balance = balance_raw / (10 ** self.usdc_decimals)
            
            logger.debug(f"USDC balance for {wallet_address[:10]}...: ${balance:.2f}")
            
            return balance
            
        except Exception as e:
            logger.error(f"Failed to get USDC balance for {wallet_address}: {e}")
            raise
    
    async def get_allowance(
        self,
        owner_address: str,
        spender_address: str
    ) -> float:
        """
        Get USDC allowance for a spender.
        
        Args:
            owner_address: Token owner address
            spender_address: Spender address (e.g., CTF Exchange contract)
        
        Returns:
            Allowance in human-readable format
        
        Raises:
            Web3Exception: If query fails
        """
        if not self.w3 or not self.usdc_contract:
            await self.connect()
        
        try:
            checksum_owner = self.w3.to_checksum_address(owner_address)
            checksum_spender = self.w3.to_checksum_address(spender_address)
            
            allowance_raw = await self.usdc_contract.functions.allowance(
                checksum_owner,
                checksum_spender
            ).call()
            
            # Convert to human-readable
            allowance = allowance_raw / (10 ** self.usdc_decimals)
            
            logger.debug(
                f"USDC allowance for {owner_address[:10]}... → "
                f"{spender_address[:10]}...: ${allowance:.2f}"
            )
            
            return allowance
            
        except Exception as e:
            logger.error(
                f"Failed to get USDC allowance for "
                f"{owner_address} → {spender_address}: {e}"
            )
            raise
    
    async def check_sufficient_balance(
        self,
        wallet_address: str,
        required_amount: float
    ) -> tuple[bool, float]:
        """
        Check if wallet has sufficient USDC balance.
        
        Args:
            wallet_address: Wallet address to check
            required_amount: Required USDC amount
        
        Returns:
            Tuple of (has_sufficient, current_balance)
        """
        try:
            balance = await self.get_usdc_balance(wallet_address)
            has_sufficient = balance >= required_amount
            
            if not has_sufficient:
                logger.warning(
                    f"Insufficient USDC balance: ${balance:.2f} < ${required_amount:.2f}"
                )
            
            return has_sufficient, balance
            
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            return False, 0.0
    
    async def check_allowance_sufficient(
        self,
        owner_address: str,
        spender_address: str,
        required_amount: float
    ) -> tuple[bool, float]:
        """
        Check if spender has sufficient allowance.
        
        Args:
            owner_address: Token owner address
            spender_address: Spender address
            required_amount: Required allowance amount
        
        Returns:
            Tuple of (has_sufficient, current_allowance)
        """
        try:
            allowance = await self.get_allowance(owner_address, spender_address)
            has_sufficient = allowance >= required_amount
            
            if not has_sufficient:
                logger.warning(
                    f"Insufficient USDC allowance: ${allowance:.2f} < ${required_amount:.2f}. "
                    f"Owner needs to approve {spender_address}"
                )
            
            return has_sufficient, allowance
            
        except Exception as e:
            logger.error(f"Failed to check allowance: {e}")
            return False, 0.0
    
    async def get_gas_price(self) -> dict:
        """
        Get current gas prices on Polygon.
        
        Returns:
            Dictionary with gas price info in gwei
        """
        if not self.w3:
            await self.connect()
        
        try:
            # Get base gas price
            gas_price_wei = await self.w3.eth.gas_price
            gas_price_gwei = gas_price_wei / 10**9
            
            # Calculate recommended gas prices
            # Polygon is fast, so we add 10% buffer for next block inclusion
            fast_gas_price_gwei = gas_price_gwei * 1.1
            
            result = {
                "standard_gwei": round(gas_price_gwei, 2),
                "fast_gwei": round(fast_gas_price_gwei, 2),
                "standard_wei": gas_price_wei,
                "fast_wei": int(gas_price_wei * 1.1),
            }
            
            logger.debug(
                f"Gas price: {result['standard_gwei']} gwei "
                f"(fast: {result['fast_gwei']} gwei)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get gas price: {e}")
            # Return default values if query fails
            return {
                "standard_gwei": 50.0,
                "fast_gwei": 55.0,
                "standard_wei": 50_000_000_000,
                "fast_wei": 55_000_000_000,
            }
    
    async def close(self):
        """Close web3 connection."""
        if self.w3:
            # AsyncWeb3 doesn't have explicit close, but we can clean up
            self.w3 = None
            self.usdc_contract = None
            logger.info("BalanceChecker connection closed")


async def test_balance_checker():
    """Test balance checker functionality."""
    from config import Config
    
    print("Testing BalanceChecker...")
    
    # Create mock config
    config = Config()
    
    # Create balance checker
    checker = BalanceChecker(config)
    
    # Test connection
    print("\n1. Testing connection...")
    await checker.connect()
    
    # Test balance check (use a known Polygon address)
    print("\n2. Testing balance check...")
    test_address = "0x0000000000000000000000000000000000000000"
    try:
        balance = await checker.get_usdc_balance(test_address)
        print(f"   Balance: ${balance:.2f} USDC")
    except Exception as e:
        print(f"   Balance check failed (expected): {e}")
    
    # Test gas price
    print("\n3. Testing gas price...")
    gas_prices = await checker.get_gas_price()
    print(f"   Standard: {gas_prices['standard_gwei']} gwei")
    print(f"   Fast: {gas_prices['fast_gwei']} gwei")
    
    # Close connection
    print("\n4. Closing connection...")
    await checker.close()
    
    print("\n✓ BalanceChecker test completed!")


if __name__ == "__main__":
    asyncio.run(test_balance_checker())

