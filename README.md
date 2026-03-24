# Exceptionless Demo

Self-hosted Exceptionless kurulumu. Mevcut projelerine eklenti olarak entegre edip hata takibi, log toplama ve Telegram üzerinden bildirim alabilirsin.

## Gereksinimler

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) kurulu olmalı

## Kurulum

```bash
git clone https://github.com/oguzhanalayont/exceptionless-demo.git
cd exceptionless-demo
cp .env.example .env
docker compose up -d --build
```

İlk seferde image'lar indirilir ve Elasticsearch build edilir (~3-5 dk). Sonraki başlatmalar hızlıdır.

Servislerin durumunu kontrol et:

```bash
docker compose ps
```

Tüm container'lar "Running" olana kadar bekle (~1 dk).

## API Key Alma

1. Tarayıcıda **http://localhost:5200** aç
2. **Sign Up** ile hesap oluştur (ilk kullanıcı otomatik admin olur)
3. Organization ve Project oluştur
4. Project Settings > API Keys bölümünden **API Key**'i kopyala
5. `.env` dosyasındaki `EXCEPTIONLESS_API_KEY` değerini güncelle

## Telegram Bildirim Sistemi

Belirli eşikler aşıldığında Telegram üzerinden otomatik bildirim alabilirsin. İki tür bildirim desteklenir:

- **Toplam event uyarısı**: Belirlenen sürede toplam event sayısı eşiği aşarsa bildirim gelir
- **Tekrarlayan hata alarmı**: Aynı hata belirli sürede belirli sayıdan fazla tekrarlanırsa, hata detaylarıyla birlikte bildirim gelir

### Telegram Bot Kurulumu

1. Telegram'da **@BotFather**'a `/newbot` yaz
2. Botuna bir isim ve username ver
3. BotFather'ın verdiği **API token**'ı kaydet
4. Botu bildirimleri alacağın gruba ekle
5. Grupta bir mesaj yaz, sonra tarayıcıda şu URL'yi aç:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
6. Dönen JSON'daki `"chat":{"id": -100...}` değeri senin **Chat ID**'n

### Yapılandırma

`.env` dosyasını düzenle:

```env
TELEGRAM_BOT_TOKEN=bot_tokenin_buraya
TELEGRAM_CHAT_ID=chat_id_buraya
EVENT_THRESHOLD=100
ERROR_THRESHOLD=10
POLL_INTERVAL=10
COOLDOWN_SECONDS=60
EXCEPTIONLESS_API_KEY=senin_api_keyin
```

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `TELEGRAM_BOT_TOKEN` | - | Telegram bot API token'ı |
| `TELEGRAM_CHAT_ID` | - | Bildirim gönderilecek chat/grup ID'si |
| `EVENT_THRESHOLD` | 100 | Toplam event uyarısı için eşik değeri |
| `ERROR_THRESHOLD` | 10 | Tekrarlayan hata alarmı için eşik değeri |
| `POLL_INTERVAL` | 10 | Kaç saniyede bir kontrol edilsin (saniye) |
| `COOLDOWN_SECONDS` | 60 | Aynı alarm için tekrar bekleme süresi (saniye) |

### Servisi Başlatma

```bash
docker compose up -d --build telegram-notifier
```

### Bildirim Örnekleri

**Toplam event uyarısı** (10 saniyede 100+ event):

```
Exceptionless Uyarısı

Son 10 saniyede 333 event algılandı!
Hız: 33.3 event/saniye
Zaman: 2026-03-24 15:45:00
```

**Tekrarlayan hata alarmı** (10 saniyede aynı hatadan 10+):

```
Tekrarlayan Hata Alarmı

Hata: NullReferenceException: Object reference not set to an instance of an object
Tip: error
Tekrar: Son 10s içinde 47 kez
Etiketler: production, payment-service
Konum: /src/Services/PaymentService.cs:142 → ProcessPayment
Zaman: 2026-03-24 15:45:00
```

## Kendi Projene Entegre Etme

Exceptionless'ı mevcut projelerine NuGet paketi olarak ekleyip kullanabilirsin. Aşağıda platform bazlı entegrasyon adımları var.

### ASP.NET Core / Web API

```bash
dotnet add package Exceptionless.AspNetCore
```

**Program.cs:**

```csharp
using Exceptionless;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddExceptionless(config =>
{
    config.ApiKey = "SENIN_API_KEYIN";
    config.ServerUrl = "http://localhost:5200";
});

var app = builder.Build();

app.UseExceptionless();

// Uygulaman devam eder...
app.Run();
```

Bu kadar. Unhandled exception'lar otomatik olarak yakalanıp Exceptionless'a gönderilir.

### Console / Worker Service

```bash
dotnet add package Exceptionless
```

```csharp
using Exceptionless;

var client = new ExceptionlessClient(config =>
{
    config.ApiKey = "SENIN_API_KEYIN";
    config.ServerUrl = "http://localhost:5200";
});

// Manuel hata gönderme
try
{
    // ...
}
catch (Exception ex)
{
    ex.ToExceptionless(client).Submit();
}

// Log gönderme
client.CreateLog("MyApp", "Bir işlem tamamlandı", "Info").Submit();

// Uygulama kapanırken kuyruktaki event'leri gönder
client.ProcessQueue();
```

### appsettings.json ile Yapılandırma

API key'i kod içine gömmek yerine config dosyasından okuyabilirsin:

**appsettings.json:**

```json
{
  "Exceptionless": {
    "ApiKey": "SENIN_API_KEYIN",
    "ServerUrl": "http://localhost:5200"
  }
}
```

**Program.cs:**

```csharp
builder.Services.AddExceptionless(builder.Configuration);
```

### Manuel Event Gönderme

Otomatik yakalama dışında, istediğin yerde manuel event gönderebilirsin:

```csharp
using Exceptionless;

// Hata gönder
try
{
    throw new Exception("Bir şeyler ters gitti");
}
catch (Exception ex)
{
    ex.ToExceptionless()
        .AddTags("critical", "payment")
        .SetProperty("orderId", 12345)
        .Submit();
}

// Log gönder
ExceptionlessClient.Default
    .CreateLog("OrderService", "Sipariş oluşturuldu", "Info")
    .SetProperty("orderId", 12345)
    .Submit();

// Feature usage takibi
ExceptionlessClient.Default
    .CreateFeatureUsage("Premium Export")
    .Submit();
```

### Diğer Platformlar

| Platform | Paket |
|----------|-------|
| ASP.NET Core | `Exceptionless.AspNetCore` |
| Console / Worker | `Exceptionless` |
| ASP.NET (Framework) | `Exceptionless.Mvc` veya `Exceptionless.WebApi` |
| Windows Forms / WPF | `Exceptionless.Windows` |
| JavaScript / Node.js | `exceptionless` (npm) |

Tüm paketlerde `ServerUrl` olarak `http://localhost:5200` (veya deploy ettiğin adres) belirtmen yeterli.

## Test Microservice (Log Bomb)

Repoda hazır bir test microservice var. Exceptionless'ın davranışını test etmek için kullanabilirsin.

### Yapılandırma

`.env` dosyasındaki `EXCEPTIONLESS_API_KEY` değerini ayarla ve servisi başlat:

```bash
docker compose up -d --build log-bomb-service
```

### Test Endpoint'leri

Log Bomb Service **http://localhost:5050** adresinde çalışır.

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/health` | GET | Sağlık kontrolü |
| `/fire` | POST | Tek bir hata fırlat |
| `/flood?count=1000` | POST | Aynı hatadan N adet fırlat (deduplication testi) |
| `/mixed?count=100` | POST | 5 farklı hata türünden karışık fırlat |
| `/log-levels?count=500` | POST | Info/Warn/Error karışık log gönder |
| `/stats` | GET | Client konfigürasyonunu göster |

### Test Senaryoları

```bash
# Tek hata
curl -X POST http://localhost:5050/fire

# Flood - 1000 adet aynı hata (deduplication kontrolü)
curl -X POST "http://localhost:5050/flood?count=1000"

# Karışık - 5 farklı hata türü
curl -X POST "http://localhost:5050/mixed?count=100"

# Log seviyeleri
curl -X POST "http://localhost:5050/log-levels?count=500"
```

### Beklenen Davranış

- **Deduplication**: Aynı exception tek bir "stack" altında gruplanır, occurrence sayısı artar
- **Gruplama**: Farklı exception türleri ayrı stack'lerde toplanır
- **Log seviyeleri**: Dashboard'da Info/Warn/Error olarak filtrelenebilir
- **Rate limiting**: Client tarafında throttling yapılır
- **Telegram bildirimi**: Eşik aşıldığında otomatik bildirim gelir

## Mimari

```
                         ┌──────────────────────────────┐
                         │   Exceptionless (all-in-one)  │
┌─────────────────┐      │   API + UI + Jobs             │
│  Log Bomb       │─────▶│   :5200                       │
│  Service :5050  │      └──────────┬───────────────────┘
└─────────────────┘                 │
                       ┌────────────┼────────────┐
                       │                         │
                 ┌─────▼────┐          ┌─────────▼─────────┐
                 │  Redis   │          │  Elasticsearch     │
                 │  :6379   │          │  :9200             │
                 └──────────┘          │  + mapper-size     │
                                       └─────────┬─────────┘
                                                  │
                                  ┌───────────────┼───────────────┐
                                  │                               │
                       ┌──────────▼────────┐          ┌───────────▼───────┐
                       │  Kibana           │          │  Telegram         │
                       │  :5601            │          │  Notifier :5001   │
                       └───────────────────┘          └───────────────────┘
```

## Servisler

| Servis | Port | Açıklama |
|--------|------|----------|
| Exceptionless | 5200 | Dashboard + API (all-in-one) |
| Log Bomb Service | 5050 | Test microservice (.NET 8) |
| Elasticsearch | 9200 | Veri deposu (mapper-size plugin'li) |
| Kibana | 5601 | Elasticsearch görselleştirme |
| Redis | 6379 | Cache + message bus + queue |
| Telegram Notifier | 5001 | Bildirim servisi (Telegram entegrasyonu) |

## Sıfırlama

Tüm verileri silip baştan başlamak için:

```bash
docker compose down -v
docker compose up -d --build
```

## Sorun Giderme

**Container'lar ayağa kalkmıyorsa:**

```bash
docker logs exceptionless 2>&1 | tail -20
docker logs exceptionless-elasticsearch 2>&1 | tail -20
```

**Event'ler dashboard'da görünmüyorsa:**

```bash
# Storage hatası var mı kontrol et
docker logs exceptionless 2>&1 | grep -i "denied\|error saving"

# ES bağlantısı var mı kontrol et
curl http://localhost:9200
```

**Telegram bildirimi gelmiyorsa:**

```bash
# Notifier loglarını kontrol et
docker logs telegram-notifier --tail 20

# ES'e event düşüyor mu kontrol et
curl -s "http://localhost:9200/prod-events-v1-*/_count"

# Bot'un mesaj gönderip gönderemediğini test et
curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d chat_id=<CHAT_ID> \
  -d text="Test mesajı"
```
