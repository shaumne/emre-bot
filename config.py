"""
Configuration loader and validator for Polymarket Arbitrage Bot.
Parses .env file and validates all required settings.
"""

import os
from typing import List, Optional
from dotenv import load_dotenv
from loguru import logger


class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass


class Config:
    """
    Configuration management for the Polymarket arbitrage bot.
    Loads environment variables and validates required settings.
    """
    
    def __init__(self, env_file: str = ".env"):
        """
        Initialize configuration from environment file.
        
        Args:
            env_file: Path to .env file (default: ".env")
        
        Raises:
            ConfigError: If required configuration is missing or invalid
        """
        # Load environment variables
        if not load_dotenv(env_file):
            logger.warning(f"No {env_file} file found. Using environment variables.")
        
        # Wallet Configuration
        self.poly_private_key = self._get_required("POLY_PRIVATE_KEY")
        self.poly_proxy_address = os.getenv("POLY_PROXY_ADDRESS", "")
        self.poly_signature_type = int(os.getenv("POLY_SIGNATURE_TYPE", "1"))
        
        # Validate signature type
        if self.poly_signature_type not in [0, 1, 2]:
            raise ConfigError(
                f"Invalid POLY_SIGNATURE_TYPE: {self.poly_signature_type}. "
                "Must be 0 (EOA), 1 (Email/Magic), or 2 (Browser Wallet)."
            )
        
        # Trading Parameters
        self.trigger_threshold = float(os.getenv("TRIGGER_THRESHOLD", "0.98"))
        self.fixed_investment_amount = float(os.getenv("FIXED_INVESTMENT_AMOUNT", "50.0"))
        self.min_profit_threshold = float(os.getenv("MIN_PROFIT_THRESHOLD", "0.02"))
        self.min_usdc_balance = float(os.getenv("MIN_USDC_BALANCE", "100.0"))
        self.opportunity_cooldown = float(os.getenv("OPPORTUNITY_COOLDOWN", "5.0"))
        
        # Validate trading parameters
        if not 0.5 <= self.trigger_threshold <= 1.0:
            raise ConfigError(
                f"Invalid TRIGGER_THRESHOLD: {self.trigger_threshold}. "
                "Must be between 0.5 and 1.0."
            )
        
        if self.fixed_investment_amount <= 0:
            raise ConfigError(
                f"Invalid FIXED_INVESTMENT_AMOUNT: {self.fixed_investment_amount}. "
                "Must be greater than 0."
            )
        
        # Market Selection
        self.market_mode = os.getenv("MARKET_MODE", "btc_eth").lower()
        self.btc_eth_duration_minutes = int(os.getenv("BTC_ETH_DURATION_MINUTES", "15"))
        self.target_tags = self._parse_tags(os.getenv("TARGET_TAGS", "crypto,politics"))
        self.min_market_volume = float(os.getenv("MIN_MARKET_VOLUME", "1000.0"))
        self.min_liquidity = float(os.getenv("MIN_LIQUIDITY", "500.0"))
        
        # Network Endpoints
        self.polygon_rpc_url = os.getenv(
            "POLYGON_RPC_URL",
            "https://polygon-rpc.com/"
        )
        self.clob_api_url = os.getenv(
            "CLOB_API_URL",
            "https://clob.polymarket.com"
        )
        self.gamma_api_url = os.getenv(
            "GAMMA_API_URL",
            "https://gamma-api.polymarket.com"
        )
        # WebSocket URL - Market Channel requires /ws/market path
        self.wss_url = os.getenv(
            "WSS_URL",
            "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        )
        
        # Rate Limiting
        self.max_api_calls_per_minute = int(os.getenv("MAX_API_CALLS_PER_MINUTE", "80"))
        self.max_ws_subscriptions = int(os.getenv("MAX_WS_SUBSCRIPTIONS", "50"))
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.log_file = os.getenv("LOG_FILE", "logs/arbitrage.log")
        
        # Paper Trading Mode
        self.paper_trading_mode = os.getenv("PAPER_TRADING_MODE", "false").lower() == "true"
        self.paper_trading_file = os.getenv("PAPER_TRADING_FILE", "paper_trades.csv")
        
        # Market Maker Settings
        self.mm_paper_trading = os.getenv("MM_PAPER_TRADING", "true").lower() == "true"
        self.mm_paper_trading_file = os.getenv("MM_PAPER_TRADING_FILE", "mm_paper_trades.csv")
        self.mm_target_spread = float(os.getenv("MM_TARGET_SPREAD", "0.02"))
        self.mm_skew_factor = float(os.getenv("MM_SKEW_FACTOR", "0.0001"))
        self.mm_max_inventory = int(os.getenv("MM_MAX_INVENTORY", "1000"))
        self.mm_quote_update_interval = float(os.getenv("MM_QUOTE_UPDATE_INTERVAL", "5.0"))
        
        # Polygon chain ID (fixed for Polygon mainnet)
        self.chain_id = 137
        
        # Polygon USDC contract address (6 decimals)
        self.usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        
        # CTF Exchange contract address (for monitoring)
        self.ctf_exchange_address = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
        
        logger.info("Configuration loaded successfully")
        self._log_config_summary()
    
    def _get_required(self, key: str) -> str:
        """
        Get required environment variable.
        
        Args:
            key: Environment variable name
        
        Returns:
            Environment variable value
        
        Raises:
            ConfigError: If environment variable is not set
        """
        value = os.getenv(key)
        if not value:
            raise ConfigError(
                f"Required environment variable {key} is not set. "
                f"Please check your .env file."
            )
        return value
    
    def _parse_tags(self, tags_str: str) -> List[str]:
        """
        Parse comma-separated tags string.
        
        Args:
            tags_str: Comma-separated tags (e.g., "crypto,politics")
        
        Returns:
            List of tag strings
        """
        return [tag.strip().lower() for tag in tags_str.split(",") if tag.strip()]
    
    def _log_config_summary(self):
        """Log configuration summary (without sensitive data)."""
        logger.info("=" * 60)
        logger.info("POLYMARKET ARBITRAGE BOT CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"Signature Type: {self._get_signature_type_name()}")
        logger.info(f"Proxy Address: {self.poly_proxy_address[:10]}..." if self.poly_proxy_address else "Proxy Address: Not set (EOA mode)")
        logger.info(f"Trigger Threshold: {self.trigger_threshold} (YES + NO < {self.trigger_threshold})")
        logger.info(f"Investment Amount: ${self.fixed_investment_amount:.2f} per trade")
        logger.info(f"Min Profit Threshold: {self.min_profit_threshold * 100:.1f}%")
        logger.info(f"Opportunity Cooldown: {self.opportunity_cooldown}s")
        logger.info(f"Min USDC Balance: ${self.min_usdc_balance:.2f}")
        
        if self.market_mode == "btc_eth":
            logger.info(f"Market Mode: BTC/ETH {self.btc_eth_duration_minutes}-minute markets ONLY")
        else:
            logger.info(f"Market Mode: Tag-based ({', '.join(self.target_tags)})")
        
        logger.info(f"Min Market Volume: ${self.min_market_volume:.2f}")
        logger.info(f"Min Liquidity: ${self.min_liquidity:.2f}")
        logger.info(f"Max WS Subscriptions: {self.max_ws_subscriptions} markets")
        logger.info(f"Rate Limit: {self.max_api_calls_per_minute} calls/minute")
        logger.info(f"Log Level: {self.log_level}")
        logger.info(f"Paper Trading Mode: {'ENABLED' if self.paper_trading_mode else 'DISABLED'}")
        if self.paper_trading_mode:
            logger.info(f"Paper Trading File: {self.paper_trading_file}")
        logger.info("=" * 60)
    
    def _get_signature_type_name(self) -> str:
        """Get human-readable signature type name."""
        signature_types = {
            0: "EOA (Direct Wallet)",
            1: "Polymarket Proxy (Email/Magic)",
            2: "Polymarket Proxy (Browser Wallet)"
        }
        return signature_types.get(self.poly_signature_type, "Unknown")
    
    @property
    def uses_proxy(self) -> bool:
        """Check if configuration uses proxy wallet."""
        return self.poly_signature_type in [1, 2]


# Global config instance (initialized when imported)
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance (singleton pattern).
    
    Returns:
        Config instance
    
    Raises:
        ConfigError: If configuration is not initialized
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(env_file: str = ".env") -> Config:
    """
    Initialize global configuration.
    
    Args:
        env_file: Path to .env file
    
    Returns:
        Config instance
    """
    global _config
    _config = Config(env_file)
    return _config


if __name__ == "__main__":
    # Test configuration loading
    try:
        config = Config()
        print("✓ Configuration loaded successfully!")
        print(f"  Chain ID: {config.chain_id}")
        print(f"  Signature Type: {config._get_signature_type_name()}")
        print(f"  Target Tags: {config.target_tags}")
        print(f"  Trigger Threshold: {config.trigger_threshold}")
    except ConfigError as e:
        print(f"✗ Configuration error: {e}")

