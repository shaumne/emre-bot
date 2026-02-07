"""
Structured logging setup using Loguru for Polymarket Arbitrage Bot.
Provides console and file logging with rotation and formatting.
"""

import sys
import os
from pathlib import Path
from loguru import logger


def setup_logger(log_level: str = "INFO", log_file: str = "logs/arbitrage.log"):
    """
    Setup Loguru logger with console and file outputs.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
    """
    # Remove default handler
    logger.remove()
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Console handler with color formatting
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=log_level,
        colorize=True,
    )
    
    # File handler with rotation and retention
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level=log_level,
        rotation="1 day",      # Rotate daily
        retention="30 days",   # Keep logs for 30 days
        compression="zip",     # Compress old logs
        enqueue=True,          # Thread-safe logging
    )
    
    logger.info(f"Logger initialized with level: {log_level}")
    logger.info(f"Log file: {log_file}")


def log_arbitrage_opportunity(
    condition_id: str,
    question: str,
    yes_token_id: str,
    no_token_id: str,
    yes_price: float,
    no_price: float,
    implied_sum: float,
    expected_profit: float,
    yes_size: float,
    no_size: float,
):
    """
    Log arbitrage opportunity in structured format.
    
    Args:
        condition_id: Market condition ID
        question: Market question
        yes_token_id: YES token ID
        no_token_id: NO token ID
        yes_price: YES token best ask price
        no_price: NO token best ask price
        implied_sum: Sum of YES + NO prices
        expected_profit: Expected profit percentage
        yes_size: YES token size to buy
        no_size: NO token size to buy
    """
    logger.info(
        "🎯 ARBITRAGE OPPORTUNITY FOUND",
        extra={
            "event": "arbitrage_opportunity",
            "condition_id": condition_id,
            "question": question,
            "yes_token_id": yes_token_id,
            "no_token_id": no_token_id,
            "yes_price": yes_price,
            "no_price": no_price,
            "implied_sum": implied_sum,
            "expected_profit_pct": expected_profit * 100,
            "yes_size": yes_size,
            "no_size": no_size,
        }
    )
    
    # Also log in human-readable format
    logger.info(f"  Market: {question}")
    logger.info(f"  YES Price: ${yes_price:.4f} | NO Price: ${no_price:.4f}")
    logger.info(f"  Implied Sum: {implied_sum:.4f} (Expected: 1.00)")
    logger.info(f"  Expected Profit: {expected_profit * 100:.2f}%")
    logger.info(f"  Position: {yes_size:.2f} YES + {no_size:.2f} NO tokens")


def log_trade_execution(
    condition_id: str,
    question: str,
    yes_order_id: str,
    no_order_id: str,
    yes_status: str,
    no_status: str,
    yes_filled: bool,
    no_filled: bool,
    execution_time_ms: float,
):
    """
    Log trade execution results.
    
    Args:
        condition_id: Market condition ID
        question: Market question
        yes_order_id: YES order ID
        no_order_id: NO order ID
        yes_status: YES order status
        no_status: NO order status
        yes_filled: Whether YES order was filled
        no_filled: Whether NO order was filled
        execution_time_ms: Execution time in milliseconds
    """
    success = yes_filled and no_filled
    
    if success:
        logger.success(
            "✅ TRADE EXECUTED SUCCESSFULLY",
            extra={
                "event": "trade_success",
                "condition_id": condition_id,
                "question": question,
                "yes_order_id": yes_order_id,
                "no_order_id": no_order_id,
                "execution_time_ms": execution_time_ms,
            }
        )
        logger.success(f"  Market: {question}")
        logger.success(f"  YES Order: {yes_order_id[:16]}... [{yes_status}]")
        logger.success(f"  NO Order: {no_order_id[:16]}... [{no_status}]")
        logger.success(f"  Execution Time: {execution_time_ms:.2f}ms")
    else:
        logger.error(
            "❌ TRADE EXECUTION FAILED (Partial Fill)",
            extra={
                "event": "trade_partial_fill",
                "condition_id": condition_id,
                "question": question,
                "yes_order_id": yes_order_id,
                "no_order_id": no_order_id,
                "yes_filled": yes_filled,
                "no_filled": no_filled,
                "yes_status": yes_status,
                "no_status": no_status,
                "execution_time_ms": execution_time_ms,
            }
        )
        logger.error(f"  Market: {question}")
        logger.error(f"  YES Order: {yes_order_id[:16] if yes_order_id else 'N/A'}... [{yes_status}] (Filled: {yes_filled})")
        logger.error(f"  NO Order: {no_order_id[:16] if no_order_id else 'N/A'}... [{no_status}] (Filled: {no_filled})")
        logger.error(f"  ⚠️ ASYMMETRIC POSITION - MANUAL HEDGE REQUIRED!")


def log_opportunity_skipped(condition_id: str, question: str, reason: str):
    """
    Log skipped arbitrage opportunity.
    
    Args:
        condition_id: Market condition ID
        question: Market question
        reason: Reason for skipping
    """
    logger.warning(
        f"⏭️ OPPORTUNITY SKIPPED: {reason}",
        extra={
            "event": "opportunity_skipped",
            "condition_id": condition_id,
            "question": question,
            "reason": reason,
        }
    )


def log_balance_check(wallet_address: str, usdc_balance: float, min_balance: float):
    """
    Log USDC balance check.
    
    Args:
        wallet_address: Wallet address
        usdc_balance: Current USDC balance
        min_balance: Minimum required balance
    """
    if usdc_balance >= min_balance:
        logger.info(
            f"💰 Balance Check: ${usdc_balance:.2f} USDC",
            extra={
                "event": "balance_check",
                "wallet_address": wallet_address,
                "usdc_balance": usdc_balance,
                "min_balance": min_balance,
                "status": "ok",
            }
        )
    else:
        logger.warning(
            f"⚠️ Low Balance: ${usdc_balance:.2f} USDC (Min: ${min_balance:.2f})",
            extra={
                "event": "balance_check",
                "wallet_address": wallet_address,
                "usdc_balance": usdc_balance,
                "min_balance": min_balance,
                "status": "low",
            }
        )


def log_websocket_event(event_type: str, asset_id: str, market: str, details: dict):
    """
    Log WebSocket events (DEBUG level).
    
    Args:
        event_type: Event type (book, price_change, etc.)
        asset_id: Asset ID (token ID)
        market: Market condition ID
        details: Event details
    """
    logger.debug(
        f"📡 WebSocket Event: {event_type}",
        extra={
            "event": "websocket_event",
            "event_type": event_type,
            "asset_id": asset_id,
            "market": market,
            "details": details,
        }
    )


def log_rate_limit_hit(endpoint: str, sleep_time: float):
    """
    Log rate limit event.
    
    Args:
        endpoint: API endpoint
        sleep_time: Sleep time in seconds
    """
    logger.warning(
        f"⏸️ Rate Limit Hit: {endpoint} (sleeping {sleep_time:.2f}s)",
        extra={
            "event": "rate_limit",
            "endpoint": endpoint,
            "sleep_time": sleep_time,
        }
    )


def log_error(error_msg: str, exception: Exception = None, context: dict = None):
    """
    Log error with optional exception and context.
    
    Args:
        error_msg: Error message
        exception: Exception object (optional)
        context: Additional context (optional)
    """
    extra_data = {"event": "error"}
    if context:
        extra_data.update(context)
    
    if exception:
        logger.exception(error_msg, extra=extra_data)
    else:
        logger.error(error_msg, extra=extra_data)


if __name__ == "__main__":
    # Test logger setup
    setup_logger("DEBUG", "logs/test.log")
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.success("This is a success message")
    
    # Test structured logging
    log_arbitrage_opportunity(
        condition_id="0xabc123",
        question="Will BTC hit $100k?",
        yes_token_id="12345",
        no_token_id="67890",
        yes_price=0.47,
        no_price=0.49,
        implied_sum=0.96,
        expected_profit=0.04,
        yes_size=53.13,
        no_size=51.04,
    )
    
    print("\n✓ Logger test completed! Check logs/test.log")


