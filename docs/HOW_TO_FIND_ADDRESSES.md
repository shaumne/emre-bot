# Adres ve Private Key Bulma Kılavuzu

## 1. Kendi Proxy Adresinizi Bulma

### Yöntem 1: Polymarket Web Sitesi (En Kolay)

1. [Polymarket.com](https://polymarket.com) adresine gidin
2. Giriş yapın (Email veya MetaMask ile)
3. Sağ üst köşedeki profil resminize tıklayın
4. **Profil resminizin altında gösterilen adres sizin Proxy adresinizdir**

**Not**: Bu adres (POLY_PROXY_ADDRESS / BROWSER_ADDRESS olarak da bilinir), Polymarket'e USDC gönderdiğiniz ve pozisyonlarınızın tutulduğu adrestir. **Email/Magic Link (POLY_PROXY) modunda bu adres zorunludur.**

### Yöntem 2: Blockchain Explorer

Eğer EOA (MetaMask) adresinizi biliyorsanız:
1. [Polygonscan.com](https://polygonscan.com) adresine gidin
2. EOA adresinizi arayın
3. "Internal Txns" veya "Token Transfers" sekmesinde Polymarket proxy factory ile yapılan işlemleri bulun
4. Proxy wallet adresi bu işlemlerde görünecektir

## 2. Kendi Private Key'inizi Bulma

### ⚠️ ÖNEMLİ: Paper Trading Modu (Önerilen)

**Private key'e ihtiyacınız yoksa paper trading modunu kullanın!**

Paper trading modunda:
- Gerçek para kullanılmaz
- Private key gerekmez
- Sadece simülasyon yapılır
- `.env` dosyasında sadece `PAPER_TRADING=true` ve `TARGET_WALLET_ADDRESS` yeterlidir

```env
PAPER_TRADING=true
TARGET_WALLET_ADDRESS=0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d
```

### Email/Magic Login Kullanıyorsanız:

**Not**: `reveal.magic.link` artık çalışmıyor olabilir. Aşağıdaki alternatif yöntemleri deneyin:

#### Yöntem 1: Magic Link Developer Console (Gelişmiş)

1. Polymarket'e email ile giriş yapın
2. Browser Developer Console'u açın (F12)
3. Local Storage'da Magic Link key'lerini kontrol edin
4. **Not**: Bu yöntem teknik bilgi gerektirir ve güvenli değildir

#### Yöntem 2: MetaMask'a Geçiş (Önerilen)

1. MetaMask extension'ını yükleyin
2. Yeni bir MetaMask wallet oluşturun veya mevcut birini import edin
3. Polymarket'te MetaMask ile giriş yapın
4. MetaMask'tan private key'i export edin (aşağıdaki MetaMask bölümüne bakın)
5. `POLY_SIGNATURE_TYPE=2` kullanın

#### Yöntem 3: Yeni EOA Wallet Oluşturma

1. MetaMask ile yeni bir wallet oluşturun
2. Private key'i export edin
3. Polymarket'te bu wallet ile giriş yapın
4. `POLY_SIGNATURE_TYPE=0` veya `2` kullanın (MetaMask ile giriş yaptıysanız `2`)

**⚠️ UYARI**: Magic Link private key'ini almak artık zor veya imkansız olabilir. MetaMask kullanmanız önerilir.

### MetaMask Kullanıyorsanız:

1. MetaMask extension'ını açın
2. Sağ üst köşedeki üç nokta menüsüne tıklayın
3. "Account Details" seçeneğine tıklayın
4. "Export Private Key" butonuna tıklayın
5. Şifrenizi girin
6. Private key'iniz gösterilecektir
7. **ÖNEMLİ**: Bu private key'i güvenli bir yerde saklayın, kimseyle paylaşmayın!

### EOA (External Owned Account) Kullanıyorsanız:

Eğer direkt EOA'dan trade yapıyorsanız (proxy kullanmıyorsanız):
- `POLY_SIGNATURE_TYPE=0` kullanın
- `POLY_PROXY_ADDRESS` boş bırakın

## 3. Target Wallet Proxy Adresini Bulma

### Yöntem 1: Polymarket Web Sitesi (Eğer Kullanıcı Profili Varsa)

1. Hedef kullanıcının Polymarket profil sayfasına gidin
2. Profil resminin altındaki adres proxy adresidir

### Yöntem 2: Trade Verilerinden

Bot çalışırken trade verilerinde `taker` veya `maker_address` field'larında proxy adresi görünecektir. Bot otomatik olarak bu adresleri kontrol eder.

### Yöntem 3: Blockchain Explorer

1. Hedef kullanıcının EOA adresini biliyorsanız
2. [Polygonscan.com](https://polygonscan.com) adresine gidin
3. EOA adresini arayın
4. Polymarket ile yapılan işlemlerde proxy adresini bulun

### Yöntem 4: Bot Logları

Bot çalışırken trade'lerde `taker` veya `maker_address` field'ları loglanır. Bu adresler genellikle proxy adresleridir.

## 4. Signature Type Belirleme

### POLY_SIGNATURE_TYPE Değerleri:

- **0**: EOA (External Owned Account) - Direkt cüzdan, proxy kullanmıyor
- **1**: Email/Magic Login - Polymarket'e email ile giriş yapıyorsanız
- **2**: Browser Wallet (MetaMask, Coinbase Wallet, vb.) - MetaMask ile giriş yapıyorsanız

### Nasıl Belirlenir?

- **Email ile giriş yapıyorsanız**: `POLY_SIGNATURE_TYPE=1`
- **MetaMask ile giriş yapıyorsanız**: `POLY_SIGNATURE_TYPE=2`
- **Direkt EOA kullanıyorsanız**: `POLY_SIGNATURE_TYPE=0`

## 5. .env Dosyası Örneği

### Email/Magic Login İçin:

```env
POLY_PRIVATE_KEY=0x...  # reveal.magic.link/polymarket'ten alın
POLY_PROXY_ADDRESS=0x...  # Polymarket profil resminin altındaki adres (BROWSER_ADDRESS - zorunlu)
POLY_SIGNATURE_TYPE=1
```

### MetaMask İçin:

```env
POLY_PRIVATE_KEY=0x...  # MetaMask'tan export edin
POLY_PROXY_ADDRESS=0x...  # Polymarket profil resminin altındaki adres
POLY_SIGNATURE_TYPE=2
```

### EOA (Proxy Kullanmıyor) İçin:

```env
POLY_PRIVATE_KEY=0x...  # MetaMask veya diğer wallet'tan
POLY_PROXY_ADDRESS=  # Boş bırakın
POLY_SIGNATURE_TYPE=0
```

## 6. Target Wallet İçin

Target wallet için genellikle sadece EOA adresi yeterlidir. Bot trade'leri izlerken otomatik olarak proxy adreslerini de kontrol eder.

```env
TARGET_WALLET_ADDRESS=0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d
TARGET_WALLET_PROXY_ADDRESSES=  # Opsiyonel, bot otomatik bulur
```

## Güvenlik Uyarıları

⚠️ **ÖNEMLİ**:
- Private key'inizi asla kimseyle paylaşmayın
- Private key'inizi git'e commit etmeyin
- `.env` dosyasını `.gitignore`'a ekleyin (zaten ekli)
- Private key'inizi güvenli bir yerde saklayın
- Paper trading modunda private key gerekli değildir

## Yardımcı Script

`find_addresses.py` scriptini çalıştırarak adreslerinizi kontrol edebilirsiniz (oluşturulacak).

