# Market Maker Bot - Hızlı Başlangıç

## 🚀 5 Dakikada Başla

### 1. Config Ayarla

`.env` dosyana ekle (veya güncelle):

```env
# Market Maker Settings
MM_PAPER_TRADING=true
MM_PAPER_TRADING_FILE=mm_paper_trades.csv
MM_TARGET_SPREAD=0.02
MM_SKEW_FACTOR=0.0001
MM_MAX_INVENTORY=1000
MM_QUOTE_UPDATE_INTERVAL=5.0
```

### 2. Market Maker Bot'u Başlat

**Windows:**
```bash
run_market_maker.bat
```

**Veya doğrudan:**
```bash
python market_maker_bot.py
```

### 3. İzle

Bot şunları yapacak:
1. Marketleri fetch edecek
2. WebSocket'e bağlanacak
3. Orderbook güncellemelerini izleyecek
4. Quote'ları hesaplayacak
5. Paper trading modda log'layacak (gerçek order göndermeyecek)

### 4. Logları Kontrol Et

```bash
# Logs klasöründe
logs/bot_2025-12-30.log

# Paper trades
mm_paper_trades.csv
```

---

## 📊 Ne Göreceksin?

Bot çalışırken şöyle loglar göreceksin:

```
============================================================
Market: Bitcoin Up or Down - December 30, 10:00AM-10:05AM...
  Current: Bid=$0.4800, Ask=$0.5000
  Inventory: +0 (Util: 0.0%)
  Our Quotes: Bid=$0.4800, Ask=$0.5000
  Fair Value: $0.4900 (Adj: $+0.000000)
  Spread: $0.0200 (2.00%)
  [PAPER] Would place orders:
    BID: 0.4800 (skip: False)
    ASK: 0.5000 (skip: False)
```

**Inventory değişince:**
```
============================================================
Market: Bitcoin Up or Down - December 30, 10:00AM-10:05AM...
  Current: Bid=$0.4800, Ask=$0.5000
  Inventory: +500 (Util: 50.0%)           <- Long 500 token
  Our Quotes: Bid=$0.4300, Ask=$0.4500    <- Fiyatlar düştü!
  Fair Value: $0.4400 (Adj: $+0.050000)   <- 5 cent düşüş
  Spread: $0.0200 (2.00%)
  [PAPER] Would place orders:
    BID: 0.4300 (skip: False)
    ASK: 0.4500 (skip: False)
```

---

## ⚙️ Parametreleri Ayarla

### Daha Agresif Yapmak İçin:

```env
MM_TARGET_SPREAD=0.015          # Daha dar spread
MM_SKEW_FACTOR=0.0002           # Daha hızlı inventory yönetimi
MM_MAX_INVENTORY=500            # Daha düşük risk limiti
MM_QUOTE_UPDATE_INTERVAL=2.0   # Daha sık güncelleme
```

### Daha Conservative Yapmak İçin:

```env
MM_TARGET_SPREAD=0.03           # Daha geniş spread
MM_SKEW_FACTOR=0.00005          # Daha yavaş inventory yönetimi
MM_MAX_INVENTORY=2000           # Daha yüksek risk limiti
MM_QUOTE_UPDATE_INTERVAL=10.0  # Daha az sık güncelleme
```

---

## 🧪 Test Senaryoları

### Senaryo 1: Inventory = 0 (Neutral)
Bot market'in ortasında quote verecek:
- Market: $0.48 / $0.50
- Quotes: $0.48 / $0.50

### Senaryo 2: Inventory = +500 (Long)
Bot fiyatları düşürecek (satış teşvik):
- Market: $0.48 / $0.50
- Quotes: $0.43 / $0.45

### Senaryo 3: Inventory = -500 (Short)
Bot fiyatları yükseltecek (alış teşvik):
- Market: $0.48 / $0.50
- Quotes: $0.53 / $0.55

### Senaryo 4: Inventory = +1000 (Max Long)
Bot sadece SELL order verecek:
- Market: $0.48 / $0.50
- Quotes: $0.38 / $0.40
- [!] STOP BUYING - Inventory too HIGH

---

## 📈 Sonuçları Analiz Et

### Paper Trades CSV'yi Kontrol Et

```csv
timestamp,market,inventory,best_bid,best_ask,our_bid,our_ask,spread,inventory_adj
2025-12-30 10:05:00,BTC Market,0,0.48,0.50,0.48,0.50,0.02,0.0
2025-12-30 10:10:00,BTC Market,500,0.48,0.50,0.43,0.45,0.02,0.05
```

### İstatistikler

Bot durdurduğunda:
```
============================================================
FINAL STATISTICS - Market Maker
============================================================
Markets Tracked: 50
Paper Trading: True
Total Inventory (absolute): 0
============================================================
```

---

## ✅ Sonraki Adımlar

### 1. Paper Trading'de Test Et (1-2 Gün)
- Bot'u çalıştır
- Logları izle
- Parametreleri ayarla
- Sonuçları analiz et

### 2. Real Trading'e Geçiş
`.env` dosyasında değiştir:
```env
MM_PAPER_TRADING=false
```

**UYARI:** Real trading için:
- Yeterli USDC balance olmalı
- Private key doğru olmalı
- Risk yönetimini anlamış olmalısın

### 3. İki Bot'u Birlikte Çalıştır

**Terminal 1: Arbitrage Bot**
```bash
python main.py
```

**Terminal 2: Market Maker Bot**
```bash
python market_maker_bot.py
```

İki bot birbirinden bağımsız çalışır:
- Arbitrage: Fırsatları yakalar
- Market Maker: Sürekli quote verir

---

## 🆘 Sorun Giderme

### "No markets found"
→ `.env` dosyasında `MARKET_MODE` ve ilgili ayarları kontrol et

### "WebSocket connection failed"
→ `WSS_URL` doğru mu kontrol et

### "Invalid orderbook"
→ Normal, bazı marketlerde orderbook boş olabilir

### Bot çok sık güncelleme yapıyor
→ `MM_QUOTE_UPDATE_INTERVAL` değerini artır

### Bot hiç quote vermiyor
→ Logları kontrol et, orderbook geliyor mu bak

---

## 💡 Pro Tips

1. **İlk test conservative başla:**
   - `MM_TARGET_SPREAD=0.03`
   - `MM_SKEW_FACTOR=0.00005`
   - `MM_MAX_INVENTORY=500`

2. **Inventory'yi simüle et:**
   - `market_maker_example.py` dosyasını çalıştır
   - Farklı senaryoları gör

3. **Logları takip et:**
   - `tail -f logs/bot_2025-12-30.log` (Linux/Mac)
   - Notepad++ ile aç (Windows)

4. **İki bot birlikte:**
   - Arbitrage daha az agresif
   - Market maker sürekli aktif
   - Complementer stratejiler

---

## 📚 Daha Fazla Bilgi

- `MARKET_MAKER_README.md` - Detaylı dokümantasyon
- `ENTEGRASYON_REHBERI.md` - Entegrasyon seçenekleri
- `inventory_skew_strategy.py` - Strateji kodu

---

**Hazır mısın? Başla! 🚀**

```bash
python market_maker_bot.py
```

