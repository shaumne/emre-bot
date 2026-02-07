# Hızlı Başlangıç Kılavuzu

## 1. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

## 2. Yapılandırma Dosyasını Oluşturun

### Seçenek A: Otomatik Setup (En Kolay - Önerilen)

```bash
python create_env.py
```

Bu komut varsayılan ayarlarla `.env` dosyasını oluşturur (Paper Trading modu aktif).

### Seçenek B: Setup Script

```bash
python setup.py
```

Bu komut `env_template.txt` dosyasından `.env` dosyasını oluşturur.

### Seçenek C: Manuel Oluşturma

```bash
# Windows
copy env_template.txt .env

# Linux/Mac
cp env_template.txt .env
```

Veya manuel olarak `.env` dosyası oluşturun.

## 3. .env Dosyasını Düzenleyin

`.env` dosyasını açın ve aşağıdaki değerleri doldurun:

### Paper Trading Modu (Önerilen - Başlangıç için)

```env
PAPER_TRADING=true
PAPER_TRADING_INITIAL_BALANCE=1000.0
TARGET_WALLET_ADDRESS=0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d
```

**Not**: Paper trading modunda `POLY_PRIVATE_KEY` gerekli değildir!

### Gerçek Trading Modu

```env
PAPER_TRADING=false
POLY_PRIVATE_KEY=your_private_key_here
POLY_PROXY_ADDRESS=your_proxy_address_if_using_proxy
POLY_SIGNATURE_TYPE=1
TARGET_WALLET_ADDRESS=0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d
```

### Trading Ayarları (Opsiyonel)

```env
MAX_SLIPPAGE=0.01              # %1 maksimum slippage
SLIPPAGE_BUFFER=0.005          # %0.5 slippage buffer
FIXED_MULTIPLIER=0.1           # Hedef trade'in %10'u kadar al
FIXED_AMOUNT=0                 # Sabit miktar (0 = multiplier kullan)
POLLING_INTERVAL=0.75          # 0.75 saniye polling
```

## 4. Botu Başlatın

```bash
python bot.py
```

## Paper Trading Modu

Paper trading modunda:
- ✅ Gerçek para kullanılmaz
- ✅ Pozisyonlar `positions.json` dosyasına kaydedilir
- ✅ Her 5 dakikada bir PnL raporu gösterilir
- ✅ Bot kapatıldığında final PnL raporu

## Sorun Giderme

### "POLY_PRIVATE_KEY is required" Hatası

Paper trading modunda bu hata olmamalı. `.env` dosyasında `PAPER_TRADING=true` olduğundan emin olun.

### "Module not found" Hatası

Bağımlılıkları yükleyin:
```bash
pip install -r requirements.txt
```

### Token Cache Boş

Bot başlangıcında Gamma API'den marketleri yükler. İnternet bağlantınızı kontrol edin.

## Yardım

Daha fazla bilgi için `README.md` dosyasına bakın.

