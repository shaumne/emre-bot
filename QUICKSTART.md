# 🚀 Hızlı Başlangıç

Polymarket Arbitrage Bot'u 5 dakikada çalıştır!

## 📦 1. Kurulum

```bash
# 1. Bağımlılıkları yükle
pip install -r requirements.txt

# 2. Setup script'i çalıştır
python setup.py
```

## ⚙️ 2. Yapılandırma

`.env` dosyasını düzenle ve şu bilgileri ekle:

```env
# Zorunlu
POLY_PRIVATE_KEY=your_private_key_here
POLY_PROXY_ADDRESS=your_proxy_address_here
POLY_SIGNATURE_TYPE=1
```

### Private Key Nerede?

- **Email/Magic Login**: https://reveal.magic.link/polymarket
- **MetaMask**: Settings → Security → Reveal Private Key

### Proxy Address Nerede?

- Polymarket.com'da sağ üstteki profil fotoğrafının altında

## 🎮 3. Çalıştır

```bash
python bot.py
```

## ✅ 4. Bekle ve İzle

Bot şunları yapacak:

1. ✓ Crypto ve Politics marketlerini tarayacak
2. ✓ WebSocket bağlantısı kuracak
3. ✓ Arbitraj fırsatlarını izlemeye başlayacak
4. 🎯 Fırsat bulunca otomatik trade yapacak!

## 📊 İlk Trade'in

```
🎯 ARBITRAGE OPPORTUNITY DETECTED!
  Market: Will BTC hit $100k?
  YES: $0.47 | NO: $0.49 | Sum: 0.96
  Expected Profit: 4.17%
  
💰 Executing arbitrage trade...
✅ Trade executed successfully! (445ms)
```

## ⚠️ Önemli Notlar

- İlk trade'i küçük miktarla test et (`FIXED_INVESTMENT_AMOUNT=10.0`)
- USDC balance'ını kontrol et (Polygon ağında olmalı)
- Arbitraj fırsatları nadir, sabırlı ol (günde 10-20 fırsat)

## 🐛 Sorun mu Var?

**"POLY_PRIVATE_KEY is required"**
→ `.env` dosyasını düzenle ve private key ekle

**"Insufficient USDC balance"**
→ Polygon ağında USDC al

**"No arbitrage opportunities"**
→ Normal! Sabırla bekle veya `TRIGGER_THRESHOLD=0.99` yap

## 📚 Daha Fazla Bilgi

Detaylı dokümantasyon için: [README.md](README.md)

---

**Hazır mısın? `python bot.py` ile başla! 🚀**


