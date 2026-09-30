# jev-netlify-mcp

[English](README.md)

TypeSafe'in **Jev** modelini (System One karar modeli) Claude Code, Codex CLI, Claude Desktop ya da
herhangi bir MCP istemcisinden kullanmanı sağlar. Masrafı Netlify'ın ücretsiz kredilerinden çıkar
ve sadece sende olan bir anahtarla kilitlidir.

İki parçadan oluşur:

1. **Anahtar kilitli Netlify vekili** (`proxy/`). TypeSafe API'sinin adreslerini
   (`POST /v1/systemone`, `GET /v1/models`) sunan tek bir küçük fonksiyon. Çağrıları
   [Netlify AI Gateway](https://docs.netlify.com/build/ai-gateway/overview/) üzerinden iletir.
   Kimlik bilgilerini Netlify kendisi verir, yani TypeSafe API anahtarı almana gerek yok.
   Senin anahtarın olmayan istekler `401` alır ve modele hiç ulaşmaz.
2. **MCP sunucusu** (`src/jev_netlify_mcp/`). İki araç (`jev_evaluate` ve `jev_models`) ve ajana
   Jev'e nasıl iyi soru sorulacağını öğreten talimatlar: tek konulu sorular, üç soru tipi, İngilizce
   olmayan metni İngilizceye çevirip cevabı kullanıcının dilinde verme, düşük güvenli cevapları işaretleme.

MCP sunucusu, elinde TypeSafe anahtarı varsa doğrudan TypeSafe API'siyle de çalışır.

## Neden

Zaten birçok Jev MCP sunucusu var. Bu repo onların kapsamadığı kısım için var: TypeSafe bakiyesi
olmadan, Netlify'ın ücretsiz planıyla (ayda 300 kredi) özel Jev erişimi. Bizim ölçümümüzde 18.000
Jev token'ı 0,11 kredi tuttu. Asıl masraf yayına almak: her canlı yayın (production deploy) 15 kredi.
O yüzden bir kez yükle ve dokunma.

## Gerekenler

- Python 3.10 ya da üstü
- Netlify hesabı (ücretsiz plan yeterli), yapay zeka özellikleri kapatılmamış olmalı
- Node.js 20 ya da üstü (sadece vekil testlerini çalıştırmak istersen)

## Kurulum

```bash
git clone <bu reponun adresi>
cd jev-netlify-mcp
pip install .                         # jev-netlify-mcp komutunu kurar

python scripts/setup.py new-key       # anahtarını üretir, dist/jev-proxy.zip dosyasını hazırlar
```

Netlify'a giriş yap, sonra `dist/jev-proxy.zip` dosyasını [Netlify Drop](https://app.netlify.com/drop)
sayfasına sürükle (ya da `dist/site` klasörünü). Giriş yapmadan yüklenen Drop siteleri bir süre sonra
silinir. Drop ile yüklenen site canlı yayın sayılır, AI Gateway de bununla açılır. Sonra site
adresini kaydet ve kontrol et:

```bash
python scripts/setup.py set-url https://<senin-siten>.netlify.app
python scripts/setup.py check          # anahtarsız 401, anahtarla 200 bekler
python scripts/setup.py check --live   # Jev'e bir de gerçek soru sorar (çok az kredi harcar)
```

Anahtar kullanıcı ayar dosyana yazılır (Windows'ta `%APPDATA%\jev-netlify-mcp\config.env`,
diğerlerinde `~/.config/jev-netlify-mcp/config.env`). Windows'ta ayrıca kullanıcı ortam
değişkenlerine de yazılır. Fonksiyona sadece anahtarın SHA-256 özeti konur. `setup.py`, sen
`show-key` demedikçe anahtarı ekrana yazmaz.

Özetin yüklenen dosyada durmasını istemiyorsan Netlify'da `JEV_PROXY_KEY_SHA256` adlı bir ortam
değişkeni oluşturup özeti oraya yaz ve yeniden yükle. Değişkene `TYPESAFE_*` adı verme: bunları
kendin tanımlarsan Netlify AI Gateway kimlik bilgilerini vermeyi bırakır.

## Ajanına bağla

**Claude Code**

```bash
claude mcp add --scope user jev -- jev-netlify-mcp
```

**Codex CLI** (`~/.codex/config.toml`)

```toml
[mcp_servers.jev]
command = "jev-netlify-mcp"

# isteğe bağlı: `codex exec` araçları sormadan kullanabilsin
[mcp_servers.jev.tools.jev_evaluate]
approval_mode = "approve"

[mcp_servers.jev.tools.jev_models]
approval_mode = "approve"
```

**Claude Desktop** (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "jev": { "command": "jev-netlify-mcp" }
  }
}
```

Komut PATH'te değilse Python'un tam yolunu yaz, argüman olarak da `["-m", "jev_netlify_mcp"]` ver.

Sonra Türkçe sorman yeterli, örneğin: *"Jev ile bak: bu destek maili acil mi, hangi ekibe gitmeli:
satış, lojistik ya da teknik destek?"*

## Ayarlar

| Değişken | Anlamı |
|---|---|
| `JEV_PROXY_URL` | Netlify site adresin |
| `JEV_PROXY_KEY` | Vekil anahtarın |
| `TYPESAFE_BASE_URL`, `TYPESAFE_API_KEY` | Yedek; sunucu doğrudan TypeSafe API'siyle de çalışsın diye |

Her değer önce çalışan sürecin ortamında, sonra (Windows'ta) kayıt defterindeki kullanıcı
değişkenlerinde, en son ayar dosyasında aranır. Kayıt defteri adımı önemli, çünkü bazı MCP
istemcileri ortam değişkenlerini sunucuya aktarmıyor. Kayıt defterini atlamak için
`JEV_NETLIFY_MCP_NO_REGISTRY=1` ayarla.

Resmi TypeSafe SDK'ları da vekille çalışır: `TYPESAFE_BASE_URL` değerini sitene, `TYPESAFE_API_KEY`
değerini vekil anahtarına ayarla (`python scripts/setup.py show-key`).

## Araçlar

- `jev_evaluate(state, questions, model="jev-latest")`: her metin için bir çağrı, istediğin kadar
  soru. Soru tipleri: `noul` (evet/hayır, olasılık döner), `choice` (adlandırılmış seçeneklerden
  biri) ve `score` (sıralı seviyeler, en fazla 10). Metin ve sorular toplam yaklaşık 32 bin token.
- `jev_models()`: adresteki modelleri listeler.

## Güvenlik notları

- Site adresini ve anahtarını kimseyle paylaşma. İkisine birden sahip olan senin kredini harcayabilir.
- Anahtar sızarsa: `python scripts/setup.py new-key --force`, sonra `dist/` klasörünü yeniden yükle.
- Ücretsiz planda AI Gateway sınırı dakikada 90 kredi. Kredi bitince site ay sonuna kadar durur;
  ücretsiz planda ek ücret çıkmaz.

## Testler

```bash
node --test tests/*.test.mjs     # vekil fonksiyonu, internetsiz
python -m pytest tests -q        # MCP sunucusu (sahte Jev'e karşı) ve setup.py
```

## Sorumluluk reddi

TypeSafe ya da Netlify ile bağlantılı değildir. Jev, TypeSafe ve Netlify sahiplerinin markalarıdır.
Buna güvenmeden önce Netlify ve TypeSafe'in güncel kullanım şartlarına bak.

## Lisans

MIT
