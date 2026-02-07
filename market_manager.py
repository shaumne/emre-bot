"""
Market manager for fetching and caching market data from Gamma API.
Handles tag-based market discovery and filtering.
"""

import asyncio
import json
from typing import List, Dict, Optional, Any
import aiohttp
from loguru import logger

from config import get_config
from rate_limiter import RateLimiter

# Get config instance
config = get_config()


class Market:
    """Represents a Polymarket market with YES/NO tokens."""
    
    def __init__(self, data: Dict[str, Any]):
        """
        Initialize market from API data.
        
        Args:
            data: Market data dictionary from Gamma API
        """
        # conditionId can be in camelCase (from API) or condition_id (from our code)
        self.condition_id = data.get("conditionId", "") or data.get("condition_id", "")
        self.question = data.get("question", "")
        self.slug = data.get("slug", "")
        
        # Extract token IDs from tokens array
        tokens = data.get("tokens", [])
        self.yes_token_id = ""
        self.no_token_id = ""
        
        if tokens:
            # Standard format: array of dicts with outcome info
            for token in tokens:
                if isinstance(token, dict):
                    outcome = token.get("outcome", "").lower()
                    token_id = token.get("token_id", "") or token.get("tokenId", "")
                    
                    if outcome == "yes":
                        self.yes_token_id = token_id
                    elif outcome == "no":
                        self.no_token_id = token_id
        
        # If tokens not found, try clobTokenIds
        if not self.yes_token_id or not self.no_token_id:
            clob_token_ids = data.get("clobTokenIds", [])
            
            # clobTokenIds can be a string (JSON array) or a list
            if isinstance(clob_token_ids, str):
                try:
                    clob_token_ids = json.loads(clob_token_ids)
                except (json.JSONDecodeError, ValueError):
                    clob_token_ids = []
            
            # Index 0 = NO, Index 1 = YES (Polymarket convention for binary markets)
            if isinstance(clob_token_ids, list) and len(clob_token_ids) >= 2:
                self.no_token_id = str(clob_token_ids[0])
                self.yes_token_id = str(clob_token_ids[1])
        
        # Market metadata
        self.volume_24hr = float(data.get("volume24hr", 0.0))
        self.liquidity = float(data.get("liquidity", 0.0))
        self.tick_size = data.get("tick_size", "0.01")
        self.active = data.get("active", True)
        self.closed = data.get("closed", False)
        
        # Tags
        self.tags = [tag.lower() for tag in data.get("tags", [])]
    
    def is_valid(self) -> bool:
        """Check if market has all required data."""
        return bool(
            self.condition_id and
            self.yes_token_id and
            self.no_token_id and
            self.question
        )
    
    def __repr__(self) -> str:
        return (
            f"Market(question='{self.question[:50]}...', "
            f"volume=${self.volume_24hr:.2f})"
        )


class MarketManager:
    """
    Manages market discovery and caching from Gamma API.
    """
    
    def __init__(self, config: Config, rate_limiter: RateLimiter):
        """
        Initialize market manager.
        
        Args:
            config: Configuration object
            rate_limiter: Rate limiter for API calls
        """
        self.config = config
        self.rate_limiter = rate_limiter
        self.markets: Dict[str, Market] = {}  # condition_id -> Market
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info("MarketManager initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("MarketManager session closed")
    
    async def _fetch_event_by_slug(self, slug: str) -> Optional[dict]:
        """
        Fetch full event details by slug.
        
        Args:
            slug: Event slug
        
        Returns:
            Event data dict or None if error
        """
        try:
            session = await self._get_session()
            url = f"{config.gamma_api_url}/events/slug/{slug}"
            
            await self.rate_limiter.acquire("gamma_api")
            
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"Failed to fetch event {slug}: HTTP {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching event {slug}: {e}")
            return None
    
    async def _fetch_market_by_slug(self, slug: str) -> Optional[dict]:
        """
        Fetch full market details by slug.
        
        Args:
            slug: Market slug
        
        Returns:
            Market data dict or None if error
        """
        try:
            session = await self._get_session()
            url = f"{self.config.gamma_api_url}/markets/slug/{slug}"
            
            await self.rate_limiter.acquire("gamma_api")
            
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.debug(f"Failed to fetch market {slug}: HTTP {resp.status}")
                    return None
        except Exception as e:
            logger.debug(f"Error fetching market {slug}: {e}")
            return None
    
    async def fetch_btc_eth_markets(
        self,
        duration_minutes: int = 15,
        limit: int = 50,
    ) -> List[Market]:
        """
        Fetch BTC and ETH markets using search API, then fetch full market details.
        
        Args:
            duration_minutes: Market duration in minutes (default: 15)
            limit: Maximum markets to fetch
        
        Returns:
            List of BTC/ETH Market objects
        """
        session = await self._get_session()
        markets = []
        market_slugs = set()  # Track slugs to avoid duplicates
        
        # Search terms for "Up or Down" markets
        search_terms = [
            "Bitcoin Up or Down",
            "BTC Up or Down",
            "Ethereum Up or Down",
            "ETH Up or Down",
        ]
        
        logger.info(f"Searching for BTC/ETH 'Up or Down' markets...")
        
        try:
            # Step 1: Use search to find market slugs
            for search_term in search_terms:
                await self.rate_limiter.acquire("gamma_api_search")
                
                params = {
                    "q": search_term,
                    "events_status": "active",
                    "limit_per_type": 50,
                    "keep_closed_markets": 0,
                }
                
                url = f"{self.config.gamma_api_url}/public-search"
                
                logger.debug(f"Searching: '{search_term}'")
                
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.debug(f"Search failed: HTTP {resp.status}")
                        continue
                    
                    result = await resp.json()
                    events = result.get("events", [])
                    
                    if not events:
                        logger.debug(f"No events found for '{search_term}'")
                        continue
                    
                    logger.info(f"Found {len(events)} events for '{search_term}'")
                    
                    # Collect market slugs from search results
                    for event in events:
                        event_markets = event.get("markets", [])
                        for market in event_markets:
                            market_slug = market.get("slug")
                            if market_slug:
                                market_slugs.add(market_slug)
            
            logger.info(f"Found {len(market_slugs)} unique market slugs, fetching details...")
            
            # Step 2: Fetch full market details for each slug
            for i, market_slug in enumerate(market_slugs, 1):
                if len(markets) >= limit:
                    break
                
                await self.rate_limiter.acquire("gamma_api")
                
                market_data = await self._fetch_market_by_slug(market_slug)
                if not market_data:
                    continue
                
                # Create Market object
                market = Market(market_data)
                
                # DEBUG: Log first market details
                if len(markets) == 0:
                    logger.debug(f"      First market question: {market.question}")
                    logger.debug(f"      Raw clobTokenIds: {market_data.get('clobTokenIds', 'NOT FOUND')}")
                    logger.debug(f"      Raw tokens: {market_data.get('tokens', 'NOT FOUND')}")
                    logger.debug(f"      Is valid: {market.is_valid()}")
                    logger.debug(f"      YES token: {market.yes_token_id[:10] if market.yes_token_id else 'None'}")
                    logger.debug(f"      NO token: {market.no_token_id[:10] if market.no_token_id else 'None'}")
                
                # Check if already added
                if market.condition_id in self.markets:
                    continue
                
                if not market.is_valid():
                    logger.debug(f"    Market invalid: {market.question[:50]}...")
                    continue
                
                # Check if question contains coin name and "up or down"
                question_lower = market.question.lower() if market.question else ""
                
                # Must contain coin name
                has_coin = any(kw in question_lower for kw in ["btc", "bitcoin", "eth", "ethereum"])
                if not has_coin:
                    continue
                
                # Must contain "up or down"
                if "up or down" not in question_lower:
                    continue
                
                # Add to list
                markets.append(market)
                self.markets[market.condition_id] = market
                
                logger.info(
                    f"✓ [{i}/{len(market_slugs)}] {market.question[:70]}... "
                    f"(YES: {market.yes_token_id[:10] if market.yes_token_id else 'None'}, "
                    f"NO: {market.no_token_id[:10] if market.no_token_id else 'None'})"
                )
            
            logger.success(
                f"Fetched {len(markets)} valid BTC/ETH markets (from {len(market_slugs)} slugs)"
            )
            
            # Sort by volume
            markets.sort(key=lambda m: m.volume_24hr, reverse=True)
            
            # Log top markets
            if markets:
                logger.info("Top markets by volume:")
                for i, market in enumerate(markets[:5], 1):
                    logger.info(
                        f"  {i}. {market.question[:60]}... "
                        f"(${market.volume_24hr:.2f})"
                    )
            
            return markets[:limit]
            
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching BTC/ETH markets: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching BTC/ETH markets: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def fetch_markets_by_tag(
        self,
        tag: str,
        limit: int = 100,
        min_volume: Optional[float] = None,
        min_liquidity: Optional[float] = None,
    ) -> List[Market]:
        """
        Fetch markets by tag from Gamma API.
        
        Args:
            tag: Tag to filter by (e.g., "crypto", "politics")
            limit: Maximum number of markets to fetch
            min_volume: Minimum 24h volume filter
            min_liquidity: Minimum liquidity filter
        
        Returns:
            List of Market objects
        """
        await self.rate_limiter.acquire(f"gamma_api_{tag}")
        
        session = await self._get_session()
        
        try:
            # Build query parameters
            params = {
                "tag": tag,
                "closed": "false",
                "limit": limit,
                "order": "volume24hr",
                "ascending": "false",
            }
            
            url = f"{self.config.gamma_api_url}/events"
            
            logger.info(f"Fetching markets for tag: {tag} (limit: {limit})")
            
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.error(
                        f"Failed to fetch markets: HTTP {resp.status}"
                    )
                    return []
                
                events = await resp.json()
                
                if not events:
                    logger.warning(f"No events found for tag: {tag}")
                    return []
                
                logger.debug(f"Raw API response sample: {events[0] if events else 'empty'}")
                
                # Parse markets from events
                markets = []
                
                for event in events:
                    # Each event can have multiple markets
                    event_markets = event.get("markets", [])
                    
                    # If markets is empty, the event itself might be a market
                    if not event_markets and event.get("tokens"):
                        event_markets = [event]
                    
                    for market_data in event_markets:
                        # Add condition_id from event level
                        market_data["condition_id"] = event.get("condition_id", "")
                        
                        # Create Market object
                        market = Market(market_data)
                        
                        # Validate market
                        if not market.is_valid():
                            logger.debug(
                                f"Skipping invalid market: {market.question}"
                            )
                            continue
                        
                        # Apply filters
                        if min_volume and market.volume_24hr < min_volume:
                            logger.debug(
                                f"Skipping low volume market: "
                                f"{market.question} (${market.volume_24hr:.2f})"
                            )
                            continue
                        
                        if min_liquidity and market.liquidity < min_liquidity:
                            logger.debug(
                                f"Skipping low liquidity market: "
                                f"{market.question} (${market.liquidity:.2f})"
                            )
                            continue
                        
                        markets.append(market)
                        
                        # Cache market
                        self.markets[market.condition_id] = market
                
                logger.success(
                    f"Fetched {len(markets)} markets for tag '{tag}' "
                    f"(total events: {len(events)})"
                )
                
                return markets
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching markets for {tag}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching markets for {tag}: {e}")
            return []
    
    async def fetch_all_target_markets(self) -> List[Market]:
        """
        Fetch all markets for configured target tags.
        
        Returns:
            List of all fetched Market objects
        """
        logger.info(f"Fetching markets for tags: {self.config.target_tags}")
        
        all_markets = []
        
        # Fetch markets for each tag in parallel
        tasks = [
            self.fetch_markets_by_tag(
                tag=tag,
                limit=self.config.max_ws_subscriptions,
                min_volume=self.config.min_market_volume,
                min_liquidity=self.config.min_liquidity,
            )
            for tag in self.config.target_tags
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Failed to fetch markets for tag "
                    f"'{self.config.target_tags[i]}': {result}"
                )
            else:
                all_markets.extend(result)
        
        # Remove duplicates (same market might appear in multiple tags)
        unique_markets = {}
        for market in all_markets:
            if market.condition_id not in unique_markets:
                unique_markets[market.condition_id] = market
        
        final_markets = list(unique_markets.values())
        
        logger.success(
            f"Total unique markets fetched: {len(final_markets)} "
            f"(before dedup: {len(all_markets)})"
        )
        
        return final_markets
    
    async def fetch_market_by_slug(self, slug: str) -> Optional[Market]:
        """
        Fetch a specific market by slug.
        
        Args:
            slug: Market slug (from URL)
        
        Returns:
            Market object or None if not found
        """
        await self.rate_limiter.acquire(f"gamma_api_slug")
        
        session = await self._get_session()
        
        try:
            url = f"{self.config.gamma_api_url}/events/slug/{slug}"
            
            logger.info(f"Fetching market by slug: {slug}")
            
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(
                        f"Failed to fetch market {slug}: HTTP {resp.status}"
                    )
                    return None
                
                event = await resp.json()
                
                # Extract first market from event
                markets = event.get("markets", [])
                if not markets:
                    logger.warning(f"No markets found for slug: {slug}")
                    return None
                
                market_data = markets[0]
                market_data["condition_id"] = event.get("condition_id", "")
                
                market = Market(market_data)
                
                if not market.is_valid():
                    logger.error(f"Invalid market data for slug: {slug}")
                    return None
                
                # Cache market
                self.markets[market.condition_id] = market
                
                logger.success(f"Fetched market: {market.question}")
                
                return market
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error fetching market {slug}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching market {slug}: {e}")
            return None
    
    def get_market(self, condition_id: str) -> Optional[Market]:
        """
        Get cached market by condition_id.
        
        Args:
            condition_id: Market condition ID
        
        Returns:
            Market object or None if not cached
        """
        return self.markets.get(condition_id)
    
    def get_all_markets(self) -> List[Market]:
        """Get all cached markets."""
        return list(self.markets.values())
    
    def get_market_count(self) -> int:
        """Get number of cached markets."""
        return len(self.markets)
    
    def clear_cache(self):
        """Clear market cache."""
        self.markets.clear()
        logger.info("Market cache cleared")


async def test_market_manager():
    """Test market manager functionality."""
    from config import Config
    
    print("Testing MarketManager...")
    
    # Create config and rate limiter
    try:
        config = Config()
    except Exception as e:
        print(f"⚠️  Config error: {e}")
        print("   Using default config for testing")
        # Create minimal config for testing
        import os
        os.environ["POLY_PRIVATE_KEY"] = "test"
        config = Config()
    
    rate_limiter = RateLimiter(max_calls=10, period=60.0)
    
    # Create market manager
    manager = MarketManager(config, rate_limiter)
    
    # Test fetching crypto markets
    print("\n1. Fetching crypto markets...")
    crypto_markets = await manager.fetch_markets_by_tag("crypto", limit=5)
    print(f"   Found {len(crypto_markets)} crypto markets")
    
    if crypto_markets:
        market = crypto_markets[0]
        print(f"   Example market: {market.question}")
        print(f"   - YES token: {market.yes_token_id[:20]}...")
        print(f"   - NO token: {market.no_token_id[:20]}...")
        print(f"   - Volume 24h: ${market.volume_24hr:.2f}")
    
    # Test fetching all target markets
    print("\n2. Fetching all target markets...")
    all_markets = await manager.fetch_all_target_markets()
    print(f"   Total markets: {len(all_markets)}")
    
    # Test cache
    print("\n3. Testing cache...")
    cached_count = manager.get_market_count()
    print(f"   Cached markets: {cached_count}")
    
    # Close session
    print("\n4. Closing session...")
    await manager.close()
    
    print("\n✓ MarketManager test completed!")


if __name__ == "__main__":
    asyncio.run(test_market_manager())

