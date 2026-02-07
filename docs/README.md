# Poly Market Copy Trading Bot

Profesyonel seviye bir Poly Market copy trading botu. Belirli bir cüzdan adresinden gelen tradeleri otomatik olarak kopyalar.

## Özellikler

- ✅ Rate limit korumalı REST API polling (spesifik adres sorgusu, limit=10)
- ✅ Batch trade handling (aynı saniyede birden fazla trade'i timestamp ascending sıralayıp işleme)
- ✅ Slippage koruması (max slippage limit)
- ✅ IOC (Immediate-Or-Cancel) limit order stratejisi (kısmi fill kabul, FOK riski yok)
- ✅ Fixed multiplier/amount sizing (market/outcome tıpa tıp aynı, sadece pozisyon boyutu ayarlanır)
- ✅ Proxy cüzdan desteği
- ✅ Token ID cache mekanizması (bot başlangıcında yükleme, trade anında API çağrısı YOK)
- ✅ Trade tracking (duplicate prevention, processed_trade_ids set)
- ✅ Comprehensive logging ve error handling
- ✅ Rate limit tracking ve dynamic backoff
- ✅ **Paper Trading Modu**: Gerçek para olmadan simülasyon
- ✅ **PnL Hesaplama**: Profit/Loss takibi ve raporlama
- ✅ **Pozisyon Takibi**: Tüm pozisyonlar JSON dosyasına kaydedilir
- ✅ **Gerçekçi Simülasyon**: Kısmi fill, slippage simülasyonu

## Kurulum

1. Python 3.8+ yüklü olduğundan emin olun

2. Bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

3. Yapılandırma dosyasını oluşturun:

**En Kolay Yol (Önerilen):**
```bash
python create_env.py
```

Bu komut varsayılan ayarlarla `.env` dosyasını oluşturur (Paper Trading modu aktif).

**Alternatif:**
```bash
# Windows
copy env_template.txt .env

# Linux/Mac
cp env_template.txt .env
```

4. `.env` dosyasını düzenleyin (opsiyonel - paper trading için gerekli değil):
   - `POLY_PRIVATE_KEY`: Polygon private key'iniz
   - `POLY_PROXY_ADDRESS`: Proxy cüzdan adresiniz (eğer kullanıyorsanız)
   - `POLY_SIGNATURE_TYPE`: 0 (EOA), 1 (Email/Magic Proxy), veya 2 (Browser Wallet Proxy)
   - `TARGET_WALLET_ADDRESS`: Kopyalanacak cüzdan adresi
   - Diğer ayarları ihtiyacınıza göre yapılandırın

**💡 Yardım**: Adres ve private key bulma konusunda yardım için:
```bash
python find_addresses.py
```
veya `HOW_TO_FIND_ADDRESSES.md` dosyasına bakın.

## Kullanım

```bash
python bot.py
```

## Yapılandırma

### Paper Trading Modu

Paper trading modunu etkinleştirmek için `.env` dosyasına ekleyin:
```
PAPER_TRADING=true
PAPER_TRADING_INITIAL_BALANCE=1000.0
```

Paper trading modunda:
- Gerçek para kullanılmaz, sadece simülasyon yapılır
- Pozisyonlar `positions.json` dosyasına kaydedilir
- PnL (Profit and Loss) hesaplanır ve raporlanır
- Her 5 dakikada bir PnL özeti gösterilir
- Gerçekçi fill simülasyonu (kısmi fill, slippage)

### Trading Ayarları

- `MAX_SLIPPAGE`: Maksimum slippage oranı (varsayılan: 0.01 = %1)
- `SLIPPAGE_BUFFER`: Limit order için slippage buffer (varsayılan: 0.005 = %0.5)
- `FIXED_MULTIPLIER`: Hedef trade boyutunun çarpanı (örn: 0.1 = %10)
- `FIXED_AMOUNT`: Her trade için sabit miktar (USDC cinsinden)
- `POLLING_INTERVAL`: API polling aralığı (saniye, varsayılan: 0.75)
- `PAPER_TRADING`: Paper trading modu (true/false)
- `PAPER_TRADING_INITIAL_BALANCE`: Paper trading başlangıç bakiyesi (varsayılan: 1000.0)

**Not**: `FIXED_MULTIPLIER` ve `FIXED_AMOUNT`'tan sadece birini kullanın. Diğerini 0 yapın.

## Güvenlik

- Private key ve API credentials `.env` dosyasında saklanır
- `.env` dosyasını asla git'e commit etmeyin
- Rate limiting otomatik olarak yönetilir
- Slippage koruması ile fiyat kaymasından korunma

## Logging

Bot tüm aktiviteleri loglar:
- Trade tespiti
- Order yerleştirme (veya paper trading simülasyonu)
- Hatalar ve uyarılar
- Rate limit durumu
- PnL raporları (paper trading modunda her 5 dakikada bir)

## Paper Trading

Paper trading modunda bot:
- Gerçek para kullanmaz, sadece simülasyon yapar
- Pozisyonları `positions.json` dosyasına kaydeder
- Her trade sonrası ve 5 dakikada bir PnL raporu gösterir
- Gerçekçi fill simülasyonu yapar (70-100% fill rate, slippage)
- Başlangıç bakiyesini takip eder ve günceller

PnL raporu şunları gösterir:
- Initial Balance (Başlangıç bakiyesi)
- Current Balance (Mevcut bakiye)
- Position Value (Pozisyon değeri)
- Total Equity (Toplam varlık)
- Unrealized PnL (Gerçekleşmemiş kar/zarar)
- Total Return (Toplam getiri)

## Lisans

Bu proje eğitim amaçlıdır. Kendi sorumluluğunuzda kullanın.

