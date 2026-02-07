# Market Maker Strategy - Inventory Skew

## Genel Bakış

`InventorySkewStrategy` sınıfı, Polymarket için profesyonel seviyede bir market maker stratejisi sunar. Bu strateji, **Linear Inventory Skew** modelini kullanarak inventory riskini yönetir ve delta-neutral pozisyon hedefler.

## Temel Mantık

Market making stratejisi şu prensiple çalışır:

- **Long (Pozitif Inventory)** → Fiyatları düşür → Satış teşvik et
- **Short (Negatif Inventory)** → Fiyatları yükselt → Alış teşvik et

Bu sayede sürekli olarak **Delta Neutral** (yönlü risksiz) pozisyonda kalırsın.

## Matematiksel Model

```
1. Mid_Price = (Best_Bid + Best_Ask) / 2
2. Inventory_Risk_Adj = Current_Inventory × Skew_Factor
3. Fair_Value = Mid_Price - Inventory_Risk_Adj
4. My_Bid_Price = Fair_Value - (Spread / 2)
5. My_Ask_Price = Fair_Value + (Spread / 2)
```

### Örnek Hesaplama

Market durumu:
- Best Bid: $0.48
- Best Ask: $0.50
- Current Inventory: +500 token (Long)
- Skew Factor: 0.0001
- Target Spread: 0.02 (2 cent)

Hesaplama:
```python
Mid_Price = (0.48 + 0.50) / 2 = 0.49
Inventory_Adj = 500 × 0.0001 = 0.05
Fair_Value = 0.49 - 0.05 = 0.44

My_Bid = 0.44 - 0.01 = 0.43
My_Ask = 0.44 + 0.01 = 0.45
```

Görüldüğü gibi, Long pozisyonumuz olduğu için fiyatları düşürdük (0.48/0.50 → 0.43/0.45) ve böylece satış teşvik edildi.

## Kullanım

### 1. Temel Kullanım

```python
from inventory_skew_strategy import InventorySkewStrategy

# Strateji oluştur
strategy = InventorySkewStrategy(
    target_spread=0.02,     # 2 cent kar marjı
    skew_factor=0.0001,     # Her token için 0.01 cent fiyat kayması
    max_inventory=1000      # Maksimum ±1000 token pozisyon
)

# Market verisi al
best_bid = 0.48
best_ask = 0.50
current_inventory = 500  # Long 500 token

# Quote hesapla
result = strategy.calculate_quotes(best_bid, best_ask, current_inventory)

# Sonuçları kontrol et
if result["reason"]:
    print(f"Quote geçersiz: {result['reason']}")
else:
    print(f"Bid: ${result['bid_price']}")
    print(f"Ask: ${result['ask_price']}")
    
    # Risk kontrolü
    if not result["should_stop_buying"]:
        # Bid order gönder
        place_order(side="BUY", price=result["bid_price"])
    
    if not result["should_stop_selling"]:
        # Ask order gönder
        place_order(side="SELL", price=result["ask_price"])
```

### 2. Detaylı Sonuç

`calculate_quotes()` şu bilgileri döndürür:

```python
{
    "bid_price": 0.43,              # Bid fiyatımız
    "ask_price": 0.45,              # Ask fiyatımız
    "fair_value": 0.4400,           # Hesaplanan adil değer
    "inventory_adjustment": 0.05,   # Inventory nedeniyle yapılan ayarlama
    "should_stop_buying": False,    # True = Daha fazla alma
    "should_stop_selling": False,   # True = Daha fazla satma
    "mid_price": 0.49,              # Market orta fiyat
    "spread": 0.02,                 # Kullanılan spread
    "reason": None                  # Hata varsa açıklama
}
```

### 3. Parametreleri Güncelleme

Canlı trading sırasında parametreleri değiştirebilirsin:

```python
# Volatilite arttı, spread'i genişlet
strategy.update_parameters(target_spread=0.03)

# Risk iştahı azaldı, inventory limitini düşür
strategy.update_parameters(max_inventory=500)

# Daha agresif inventory yönetimi
strategy.update_parameters(skew_factor=0.0002)
```

### 4. İstatistikler

Strateji istatistiklerini görmek için:

```python
stats = strategy.get_strategy_stats(current_inventory=750)
print(stats)

# Çıktı:
# {
#     "target_spread": 0.02,
#     "skew_factor": 0.0001,
#     "max_inventory": 1000,
#     "current_inventory": 750,
#     "inventory_utilization_pct": 75.0,    # %75 inventory kullanımı
#     "max_price_skew": 0.1,                # Maksimum fiyat kayması
#     "is_at_max_long": False,
#     "is_at_max_short": False
# }
```

## Parametre Rehberi

### `target_spread` (Kar Marjı)

Bid ile Ask arasındaki hedef fark. Bu senin kar marjın.

- **Düşük (0.01-0.015)**: Yüksek rekabet, düşük kar
- **Orta (0.02-0.03)**: Dengeli, önerilen
- **Yüksek (0.04+)**: Düşük rekabet, yüksek kar ama daha az işlem

**Öneri:** `0.02` ile başla (2 cent = %2 kar marjı)

### `skew_factor` (Inventory Hassasiyeti)

Her token başına ne kadar fiyat kayması yapılacağı.

- **Düşük (0.00005-0.0001)**: Yavaş inventory yönetimi, daha uzun süre Long/Short kalabilirsin
- **Orta (0.0001-0.0002)**: Dengeli
- **Yüksek (0.0003+)**: Agresif inventory yönetimi, hızlı hedging

**Öneri:** `0.0001` ile başla

**Formül:** `Max_Price_Change = max_inventory × skew_factor`
- Örnek: `1000 × 0.0001 = 0.1` ($0.10 maksimum fiyat kayması)

### `max_inventory` (Risk Limiti)

Maksimum inventory pozisyonu (hem pozitif hem negatif için).

- **Düşük (100-500)**: Düşük risk, sık hedging
- **Orta (500-1000)**: Dengeli
- **Yüksek (1000+)**: Yüksek risk, büyük pozisyonlar

**Öneri:** Sermayenin %10-20'si kadar. Örneğin $10,000 sermaye ile 1000-2000 token.

**Önemli:** `should_stop_buying` ve `should_stop_selling` flaglerini mutlaka kontrol et!

## Risk Yönetimi

### 1. Position Limits

```python
result = strategy.calculate_quotes(0.48, 0.50, 1000)

if result["should_stop_buying"]:
    # Inventory çok yüksek, sadece satış yap
    cancel_all_buy_orders()
    place_sell_order(result["ask_price"])

if result["should_stop_selling"]:
    # Inventory çok düşük (short), sadece alış yap
    cancel_all_sell_orders()
    place_buy_order(result["bid_price"])
```

### 2. Invalid Quotes

```python
result = strategy.calculate_quotes(best_bid, best_ask, inventory)

if result["reason"]:
    # Quote hesaplanamadı
    print(f"Market geçersiz: {result['reason']}")
    cancel_all_orders()  # Tüm orderları iptal et
```

### 3. Spread Kontrolü

```python
# Market spread çok geniş mi?
market_spread = best_ask - best_bid

if market_spread > 0.10:  # 10 cent'ten fazla
    print("Market spread çok geniş, dikkatli ol!")
    # Daha geniş spread kullan
    strategy.update_parameters(target_spread=market_spread * 0.5)
```

## Örnek Senaryolar

### Senaryo 1: Neutral Position

```
Market: Bid=0.48, Ask=0.50
Inventory: 0 (Neutral)

Sonuç:
  Fair Value: $0.49
  Our Bid: $0.48
  Our Ask: $0.50
  → Market'in ortasında quote veriyoruz
```

### Senaryo 2: Long Position

```
Market: Bid=0.48, Ask=0.50
Inventory: +500 (Long)

Sonuç:
  Fair Value: $0.44
  Our Bid: $0.43
  Our Ask: $0.45
  → Fiyatları düşürdük, satış teşvik ediliyor
```

### Senaryo 3: Short Position

```
Market: Bid=0.48, Ask=0.50
Inventory: -500 (Short)

Sonuç:
  Fair Value: $0.54
  Our Bid: $0.53
  Our Ask: $0.55
  → Fiyatları yükselttik, alış teşvik ediliyor
```

### Senaryo 4: Max Long (Risk Limiti)

```
Market: Bid=0.48, Ask=0.50
Inventory: +1000 (Max Long)

Sonuç:
  Fair Value: $0.39
  Our Bid: $0.38
  Our Ask: $0.40
  should_stop_buying: True
  → Sadece satış yapabiliriz (Bid orderını gönderme!)
```

## İleri Seviye Kullanım

### 1. Multi-Market Trading

```python
# Her market için ayrı strateji
strategies = {
    "BTC_market": InventorySkewStrategy(0.02, 0.0001, 1000),
    "ETH_market": InventorySkewStrategy(0.015, 0.00015, 1500),
}

# Her market için inventory takibi
inventories = {
    "BTC_market": 0,
    "ETH_market": 0,
}

# Quote hesapla ve order gönder
for market_id, strategy in strategies.items():
    best_bid, best_ask = get_market_data(market_id)
    inventory = inventories[market_id]
    
    result = strategy.calculate_quotes(best_bid, best_ask, inventory)
    
    if not result["reason"]:
        update_quotes(market_id, result["bid_price"], result["ask_price"])
```

### 2. Dynamic Parameter Adjustment

```python
# Market volatilitesine göre spread ayarla
volatility = calculate_volatility(market_id)

if volatility > 0.05:  # Yüksek volatilite
    strategy.update_parameters(
        target_spread=0.03,      # Spread'i genişlet
        skew_factor=0.0002,      # Daha agresif inventory yönetimi
        max_inventory=500        # Risk limitini düşür
    )
else:  # Düşük volatilite
    strategy.update_parameters(
        target_spread=0.015,     # Spread'i daralt
        skew_factor=0.0001,      # Normal inventory yönetimi
        max_inventory=1000       # Normal risk limiti
    )
```

### 3. PnL Takibi

```python
class InventoryTracker:
    def __init__(self):
        self.inventory = 0
        self.avg_buy_price = 0.0
        self.total_pnl = 0.0
    
    def on_fill(self, side, price, size):
        if side == "BUY":
            # Inventory arttı
            total_cost = (self.inventory * self.avg_buy_price) + (size * price)
            self.inventory += size
            self.avg_buy_price = total_cost / self.inventory
        else:  # SELL
            # Inventory azaldı
            pnl = (price - self.avg_buy_price) * size
            self.total_pnl += pnl
            self.inventory -= size
            
            if self.inventory == 0:
                self.avg_buy_price = 0.0
        
        print(f"PnL: ${self.total_pnl:.2f}, Inventory: {self.inventory}")
```

## Test

Test senaryolarını çalıştırmak için:

```bash
python inventory_skew_strategy.py
```

Bu, 9 farklı senaryo ile stratejiyi test eder:
- Neutral inventory
- Long position (500)
- Short position (-500)
- Max long (1000)
- Max short (-1000)
- Over max (1500)
- Low price market
- High price market
- Extremely wide spread

## Uyarılar

1. **Fees**: Polymarket'in transaction fee'lerini hesaba kat. Spread'in en az fee'leri karşılaması gerekir.

2. **Slippage**: Büyük orderlar için slippage olabilir. `FIXED_INVESTMENT_AMOUNT`'u dikkatlice ayarla.

3. **Market Impact**: Küçük likidite havuzlarında büyük orderlar fiyatı etkileyebilir.

4. **Resolution Risk**: Market resolve olduğunda inventory'deki pozisyonlar otomatik olarak settle olur. Bunu stratejinde dikkate al.

5. **WebSocket Gecikmeleri**: Gerçek zamanlı veriler gecikmeli gelebilir. Stale quote'ları tespit et ve iptal et.

## Sonraki Adımlar

1. **Mevcut arbitrage bot'a entegre et**: `bot.py`'a market maker modu ekle
2. **Order management ekle**: Cancel, update, replace fonksiyonları
3. **PnL tracking ekle**: Kar/zarar takibi ve raporlama
4. **Multi-market support**: Birden fazla market'te aynı anda market making
5. **Advanced risk management**: Stop-loss, maximum drawdown limitleri

## Örnek Entegrasyon

Mevcut arbitrage bot'una entegre etmek için:

```python
# bot.py'a ekle
from inventory_skew_strategy import InventorySkewStrategy

class PolymarketArbitrageBot:
    def __init__(self, config: Config):
        # ...
        self.mm_strategy = InventorySkewStrategy(
            target_spread=config.mm_target_spread,
            skew_factor=config.mm_skew_factor,
            max_inventory=config.mm_max_inventory
        )
        self.inventory = 0  # Track inventory
    
    async def on_orderbook_update(self, market_id: str, orderbook):
        best_bid = orderbook["bids"][0]["price"]
        best_ask = orderbook["asks"][0]["price"]
        
        # Market maker logic
        quotes = self.mm_strategy.calculate_quotes(
            best_bid, best_ask, self.inventory
        )
        
        if not quotes["reason"]:
            await self.update_quotes(market_id, quotes)
```

## Lisans

Bu kod, prop trading firmaları için tasarlanmış profesyonel bir stratejidir. Gerçek para ile kullanmadan önce extensive backtesting ve paper trading yapmanız önerilir.

---

**Yazan:** Senior Quantitative Developer  
**Tarih:** 30 Aralık 2025  
**Versiyon:** 1.0.0

