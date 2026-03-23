# Exceptionless Demo - Log Flood Test

Self-hosted Exceptionless + test microservice ile log flood, deduplication ve bildirim davranışını test etmek için kurulum.

## Gereksinimler

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) kurulu olmalı

## Kurulum

```bash
git clone https://github.com/oguzhanalayont/exceptionless-demo.git
cd exceptionless-demo
docker compose up -d
```

İlk seferde image'lar indirilir (~2-3 dk). Elasticsearch'ün hazır olması ~30-60 saniye sürer.

Servislerin durumunu kontrol et:

```bash
docker compose ps
```

## API Key Alma

1. Tarayıcıda **http://localhost:5200** aç
2. **Sign Up** ile hesap oluştur (ilk kullanıcı otomatik admin olur)
3. Organization ve Project oluştur (proje tipi: **Web API**)
4. Sana verilen **API Key**'i kopyala

## Microservice'i Yapılandır

```bash
# .env dosyası oluştur
echo "EXCEPTIONLESS_API_KEY=senin_api_keyin" > .env

# Microservice'i yeniden başlat
docker compose up -d --build log-bomb-service
```

Çalıştığını doğrula:

```bash
curl http://localhost:5050/health
```

## Test Endpoint'leri

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/health` | GET | Sağlık kontrolü |
| `/fire` | POST | Tek bir hata fırlat |
| `/flood?count=1000` | POST | Aynı hatadan N adet fırlat |
| `/mixed?count=100` | POST | 5 farklı hata türünden karışık fırlat |
| `/log-levels?count=500` | POST | Info/Warn/Error karışık log gönder |
| `/stats` | GET | Client konfigürasyonunu göster |

## Test Senaryoları

### 1. Tek hata
```bash
curl -X POST http://localhost:5050/fire
```

### 2. Flood / Deduplication testi
```bash
curl -X POST "http://localhost:5050/flood?count=1000"
```

### 3. Karışık hata türleri
```bash
curl -X POST "http://localhost:5050/mixed?count=100"
```

### 4. Log seviyesi testi
```bash
curl -X POST "http://localhost:5050/log-levels?count=500"
```

## Mimari

```
┌─────────────────┐     ┌──────────────────┐
│  Log Bomb        │────▶│  Exceptionless   │
│  Service :5050   │     │  API :5000       │
└─────────────────┘     └────────┬─────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
              ┌─────▼────┐ ┌────▼─────┐ ┌────▼──────┐
              │  Redis   │ │  Elastic │ │  UI :5200 │
              │  :6379   │ │  :9200   │ │           │
              └──────────┘ └────┬─────┘ └───────────┘
                                │
                          ┌─────▼──────┐
                          │  Kibana    │
                          │  :5601     │
                          └────────────┘

              ┌──────────────────────┐
              │  Exceptionless Jobs  │
              │  (arka plan işleri)  │
              └──────────────────────┘
```

## Servisler

| Servis | Port | Açıklama |
|--------|------|----------|
| Exceptionless API | 5000 | REST API |
| Exceptionless UI | 5200 | Dashboard |
| Log Bomb Service | 5050 | Test microservice (.NET 8) |
| Elasticsearch | 9200 | Veri deposu |
| Kibana | 5601 | Elasticsearch görselleştirme |
| Redis | 6379 | Cache + message bus + queue |

## Sıfırlama

```bash
docker compose down -v
docker compose up -d
```
