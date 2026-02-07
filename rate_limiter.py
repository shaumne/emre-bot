"""
Rate limiter for Polymarket API calls.
Implements token bucket algorithm to respect API rate limits.
"""

import time
import asyncio
from collections import deque
from typing import Optional
from loguru import logger


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    
    Polymarket API limits:
    - REST API: 100 requests per minute
    - WebSocket: 100 subscriptions per connection
    """
    
    def __init__(self, max_calls: int, period: float = 60.0):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed in the period
            period: Time period in seconds (default: 60 seconds)
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self._lock = asyncio.Lock()
        
        logger.debug(f"RateLimiter initialized: {max_calls} calls per {period}s")
    
    async def acquire(self, endpoint: str = "API"):
        """
        Acquire permission to make an API call.
        Blocks if rate limit is exceeded until capacity is available.
        
        Args:
            endpoint: Name of the endpoint (for logging purposes)
        """
        async with self._lock:
            now = time.time()
            
            # Remove calls outside the time window
            while self.calls and self.calls[0] < now - self.period:
                self.calls.popleft()
            
            # Check if we've hit the rate limit
            if len(self.calls) >= self.max_calls:
                # Calculate sleep time needed
                oldest_call = self.calls[0]
                sleep_time = self.period - (now - oldest_call)
                
                if sleep_time > 0:
                    logger.warning(
                        f"Rate limit reached for {endpoint}: "
                        f"{len(self.calls)}/{self.max_calls} calls. "
                        f"Sleeping for {sleep_time:.2f}s"
                    )
                    await asyncio.sleep(sleep_time)
                    
                    # Clean up old calls after sleeping
                    now = time.time()
                    while self.calls and self.calls[0] < now - self.period:
                        self.calls.popleft()
            
            # Record this call
            self.calls.append(now)
            
            # Log current rate limit usage
            usage_pct = (len(self.calls) / self.max_calls) * 100
            logger.debug(
                f"Rate limit usage: {len(self.calls)}/{self.max_calls} "
                f"({usage_pct:.1f}%)"
            )
    
    def get_current_usage(self) -> tuple[int, int, float]:
        """
        Get current rate limit usage.
        
        Returns:
            Tuple of (current_calls, max_calls, usage_percentage)
        """
        now = time.time()
        
        # Remove expired calls
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        current = len(self.calls)
        usage_pct = (current / self.max_calls) * 100
        
        return current, self.max_calls, usage_pct
    
    def reset(self):
        """Reset rate limiter (clear all recorded calls)."""
        self.calls.clear()
        logger.info("Rate limiter reset")
    
    async def wait_if_needed(self, endpoint: str = "API"):
        """
        Check rate limit and wait if needed (non-blocking check).
        
        Args:
            endpoint: Name of the endpoint (for logging purposes)
        """
        async with self._lock:
            now = time.time()
            
            # Remove calls outside the time window
            while self.calls and self.calls[0] < now - self.period:
                self.calls.popleft()
            
            # Check if we need to wait
            if len(self.calls) >= self.max_calls:
                oldest_call = self.calls[0]
                sleep_time = self.period - (now - oldest_call)
                
                if sleep_time > 0:
                    logger.warning(
                        f"Rate limit check for {endpoint}: "
                        f"Need to wait {sleep_time:.2f}s"
                    )
                    return sleep_time
            
            return 0


class MultiEndpointRateLimiter:
    """
    Rate limiter that manages multiple endpoints with different limits.
    """
    
    def __init__(self):
        """Initialize multi-endpoint rate limiter."""
        self.limiters = {}
        logger.debug("MultiEndpointRateLimiter initialized")
    
    def add_limiter(self, endpoint: str, max_calls: int, period: float = 60.0):
        """
        Add a rate limiter for a specific endpoint.
        
        Args:
            endpoint: Endpoint name
            max_calls: Maximum calls per period
            period: Time period in seconds
        """
        self.limiters[endpoint] = RateLimiter(max_calls, period)
        logger.info(f"Added rate limiter for {endpoint}: {max_calls} calls per {period}s")
    
    async def acquire(self, endpoint: str):
        """
        Acquire permission for an endpoint.
        
        Args:
            endpoint: Endpoint name
        
        Raises:
            ValueError: If endpoint limiter doesn't exist
        """
        if endpoint not in self.limiters:
            raise ValueError(f"No rate limiter configured for endpoint: {endpoint}")
        
        await self.limiters[endpoint].acquire(endpoint)
    
    def get_usage(self, endpoint: str) -> Optional[tuple[int, int, float]]:
        """
        Get usage for specific endpoint.
        
        Args:
            endpoint: Endpoint name
        
        Returns:
            Tuple of (current_calls, max_calls, usage_percentage) or None
        """
        if endpoint not in self.limiters:
            return None
        
        return self.limiters[endpoint].get_current_usage()
    
    def get_all_usage(self) -> dict:
        """
        Get usage for all endpoints.
        
        Returns:
            Dictionary mapping endpoint names to usage tuples
        """
        return {
            endpoint: limiter.get_current_usage()
            for endpoint, limiter in self.limiters.items()
        }


# Exponential backoff decorator
async def with_exponential_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    *args,
    **kwargs
):
    """
    Execute async function with exponential backoff retry logic.
    
    Args:
        func: Async function to execute
        max_retries: Maximum number of retries
        base_delay: Base delay in seconds (doubles each retry)
        max_delay: Maximum delay in seconds
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
    
    Returns:
        Function result
    
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                # Calculate exponential backoff delay
                delay = min(base_delay * (2 ** attempt), max_delay)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {max_retries + 1} attempts failed. Last error: {e}"
                )
    
    # If we get here, all retries failed
    raise last_exception


if __name__ == "__main__":
    # Test rate limiter
    async def test_rate_limiter():
        print("Testing RateLimiter...")
        
        # Create limiter: 5 calls per 10 seconds
        limiter = RateLimiter(max_calls=5, period=10.0)
        
        # Make 10 calls rapidly
        for i in range(10):
            print(f"\nCall {i + 1}:")
            await limiter.acquire(f"TestEndpoint_{i}")
            current, max_calls, usage = limiter.get_current_usage()
            print(f"  Usage: {current}/{max_calls} ({usage:.1f}%)")
        
        print("\n✓ RateLimiter test completed!")
        
        # Test multi-endpoint limiter
        print("\nTesting MultiEndpointRateLimiter...")
        multi_limiter = MultiEndpointRateLimiter()
        multi_limiter.add_limiter("rest_api", max_calls=3, period=5.0)
        multi_limiter.add_limiter("websocket", max_calls=2, period=5.0)
        
        # Test REST API calls
        for i in range(4):
            print(f"\nREST API Call {i + 1}:")
            await multi_limiter.acquire("rest_api")
        
        print("\n✓ MultiEndpointRateLimiter test completed!")
        
        # Test exponential backoff
        print("\nTesting exponential backoff...")
        
        async def failing_function():
            print("  Attempting call...")
            raise Exception("Simulated failure")
        
        try:
            await with_exponential_backoff(
                failing_function,
                max_retries=3,
                base_delay=0.5,
            )
        except Exception as e:
            print(f"  Final failure (expected): {e}")
        
        print("\n✓ Exponential backoff test completed!")
    
    # Run tests
    asyncio.run(test_rate_limiter())


