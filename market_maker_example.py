"""
Market Maker Strategy - Kullanım Örneği

Bu dosya, InventorySkewStrategy'nin nasıl kullanılacağını gösterir.
"""

import asyncio
from inventory_skew_strategy import InventorySkewStrategy
from typing import Dict, Any

# Simülasyon için örnek market data
EXAMPLE_MARKETS = [
    {
        "id": "btc_market_1",
        "best_bid": 0.48,
        "best_ask": 0.50,
    },
    {
        "id": "eth_market_1",
        "best_bid": 0.52,
        "best_ask": 0.55,
    }
]


class SimpleMarketMaker:
    """Basit market maker örneği."""
    
    def __init__(self):
        # Market maker stratejisi
        self.strategy = InventorySkewStrategy(
            target_spread=0.02,      # 2 cent kar marjı
            skew_factor=0.0001,      # Her token için 0.01 cent kayma
            max_inventory=1000       # Max ±1000 token
        )
        
        # Her market için inventory takibi
        self.inventories: Dict[str, int] = {
            "btc_market_1": 0,
            "eth_market_1": 0,
        }
        
        # Aktif orderlar (simülasyon)
        self.active_orders: Dict[str, Dict[str, Any]] = {}
    
    def get_market_data(self, market_id: str) -> tuple[float, float]:
        """Market datasını al (simülasyon)."""
        for market in EXAMPLE_MARKETS:
            if market["id"] == market_id:
                return market["best_bid"], market["best_ask"]
        return 0.0, 0.0
    
    async def place_order(
        self,
        market_id: str,
        side: str,
        price: float,
        size: int = 10
    ):
        """Order gönder (simülasyon)."""
        order_id = f"{market_id}_{side}_{price}"
        
        print(f"  [ORDER] {side} {size} @ ${price:.2f} on {market_id}")
        
        self.active_orders[order_id] = {
            "market_id": market_id,
            "side": side,
            "price": price,
            "size": size,
            "filled": 0
        }
    
    async def cancel_orders(self, market_id: str):
        """Tüm orderları iptal et (simülasyon)."""
        to_remove = [
            order_id for order_id, order in self.active_orders.items()
            if order["market_id"] == market_id
        ]
        
        for order_id in to_remove:
            del self.active_orders[order_id]
        
        if to_remove:
            print(f"  [X] Cancelled {len(to_remove)} orders for {market_id}")
    
    def on_order_filled(self, market_id: str, side: str, price: float, size: int):
        """Order fill event (simülasyon)."""
        # Inventory güncelle
        if side == "BUY":
            self.inventories[market_id] += size
            print(f"  [OK] Bought {size} @ ${price:.2f}")
        else:
            self.inventories[market_id] -= size
            print(f"  [OK] Sold {size} @ ${price:.2f}")
        
        print(f"  [INFO] New Inventory: {self.inventories[market_id]:+d}")
    
    async def update_quotes(self, market_id: str):
        """Market için quote'ları güncelle."""
        print(f"\n{'='*60}")
        print(f"Updating quotes for {market_id}")
        print(f"{'='*60}")
        
        # Market data al
        best_bid, best_ask = self.get_market_data(market_id)
        current_inventory = self.inventories[market_id]
        
        print(f"Market: Bid=${best_bid:.2f}, Ask=${best_ask:.2f}")
        print(f"Current Inventory: {current_inventory:+d}")
        
        # Quote hesapla
        result = self.strategy.calculate_quotes(
            best_bid=best_bid,
            best_ask=best_ask,
            current_inventory=current_inventory
        )
        
        # Hata kontrolü
        if result["reason"]:
            print(f"[ERROR] Cannot quote: {result['reason']}")
            await self.cancel_orders(market_id)
            return
        
        print(f"\n[QUOTES] Calculated Quotes:")
        print(f"  Fair Value: ${result['fair_value']:.4f}")
        print(f"  Our Bid: ${result['bid_price']:.2f}")
        print(f"  Our Ask: ${result['ask_price']:.2f}")
        print(f"  Spread: ${result['spread']:.4f} ({result['spread']*100:.2f}%)")
        print(f"  Inventory Adjustment: ${result['inventory_adjustment']:+.6f}")
        
        # Risk kontrolü
        if result["should_stop_buying"]:
            print(f"\n[!] RISK: Inventory too HIGH -> Only SELL orders")
        if result["should_stop_selling"]:
            print(f"\n[!] RISK: Inventory too LOW -> Only BUY orders")
        
        # Eski orderları iptal et
        await self.cancel_orders(market_id)
        
        print(f"\n[ORDERS] Placing new orders:")
        
        # Bid order (alış)
        if not result["should_stop_buying"]:
            await self.place_order(
                market_id=market_id,
                side="BUY",
                price=result["bid_price"],
                size=10
            )
        
        # Ask order (satış)
        if not result["should_stop_selling"]:
            await self.place_order(
                market_id=market_id,
                side="SELL",
                price=result["ask_price"],
                size=10
            )
    
    async def run_simulation(self):
        """Market maker simülasyonu çalıştır."""
        print("\n" + "="*60)
        print("MARKET MAKER SIMULATION")
        print("="*60)
        
        # İlk quote'lar (inventory = 0)
        for market_id in self.inventories.keys():
            await self.update_quotes(market_id)
        
        # Simülasyon: BTC market'te alış yapıldı
        print("\n\n" + "="*60)
        print("SIMULATION: BUY order filled on btc_market_1")
        print("="*60)
        self.on_order_filled("btc_market_1", "BUY", 0.48, 500)
        
        # Quote güncelle (inventory = +500)
        await self.update_quotes("btc_market_1")
        
        # Simülasyon: ETH market'te satış yapıldı
        print("\n\n" + "="*60)
        print("SIMULATION: SELL order filled on eth_market_1")
        print("="*60)
        self.on_order_filled("eth_market_1", "SELL", 0.55, 400)
        
        # Quote güncelle (inventory = -400)
        await self.update_quotes("eth_market_1")
        
        # Simülasyon: BTC'de max inventory'ye ulaşıldı
        print("\n\n" + "="*60)
        print("SIMULATION: BUY order filled on btc_market_1 (MAX INVENTORY)")
        print("="*60)
        self.on_order_filled("btc_market_1", "BUY", 0.48, 500)
        
        # Quote güncelle (inventory = +1000, max limit)
        await self.update_quotes("btc_market_1")
        
        # İstatistikler
        print("\n\n" + "="*60)
        print("FINAL STATISTICS")
        print("="*60)
        
        for market_id, inventory in self.inventories.items():
            stats = self.strategy.get_strategy_stats(inventory)
            print(f"\n{market_id}:")
            print(f"  Inventory: {stats['current_inventory']:+d}")
            print(f"  Utilization: {stats['inventory_utilization_pct']:.1f}%")
            print(f"  At Max Long: {stats['is_at_max_long']}")
            print(f"  At Max Short: {stats['is_at_max_short']}")
        
        print("\n" + "="*60)
        print("[OK] Simulation completed!")
        print("="*60)


async def main():
    """Ana fonksiyon."""
    mm = SimpleMarketMaker()
    await mm.run_simulation()


if __name__ == "__main__":
    asyncio.run(main())

