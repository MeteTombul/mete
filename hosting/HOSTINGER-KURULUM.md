# Lumas Butik — Hostinger Kurulum Rehberi

Bu paket **tamamen kendi hostinginde** çalışır. Hiçbir dış servise (Supabase,
GitHub vb.) ihtiyaç yok — veritabanı da Hostinger'ın kendi MySQL'i.

## 1) Veritabanı oluştur

1. Hostinger **hPanel** → **Databases** → **MySQL Databases**
2. Yeni bir veritabanı oluştur (ör. `u123456789_lumas`)
3. Yeni bir veritabanı kullanıcısı oluştur, oluşturduğun veritabanına
   **tam yetkiyle** bağla
4. Şu 4 bilgiyi bir kenara not al: **veritabanı adı, kullanıcı adı,
   parola, host** (host genelde `localhost`'tur)

## 2) Şemayı içe aktar

1. hPanel → **Databases** → **phpMyAdmin** → oluşturduğun veritabanını seç
2. Üstte **Import** (İçe Aktar) sekmesine gir
3. `db/schema-mysql.sql` dosyasını seç → **Go / Git**
4. Tüm tabloların oluştuğunu doğrula (categories, products, orders,
   order_lines, customers, staff, settings)

## 3) Dosyaları yükle

1. hPanel → **Dosyalar (File Manager)** → `public_html` klasörüne gir
2. Bu paketin **içeriğini** (kendisini değil, içindekileri) doğrudan
   `public_html`'e yükle. Sonuçta şöyle olmalı:
   ```
   public_html/
   ├─ index.html          (mağaza — ana sayfa)
   ├─ admin/index.html    (personel paneli)
   ├─ assets/*.png
   └─ api/*.php           (arka uç)
   ```

## 4) `api/config.php` dosyasını düzenle

File Manager'dan `api/config.php` dosyasını aç, 1. adımdaki bilgileri yaz:

```php
define('DB_HOST', 'localhost');
define('DB_NAME', 'u123456789_lumas');      // kendi veritabanı adın
define('DB_USER', 'u123456789_lumasuser');  // kendi kullanıcı adın
define('DB_PASS', 'senin-parolan');
define('SECRET_KEY', '...uzun rastgele bir metin...');   // rastgele değiştir
define('SETUP_KEY', '...başka rastgele bir metin...');   // rastgele değiştir
```

`SECRET_KEY` ve `SETUP_KEY` için örnek: klavyeden rastgele 40 karakter
karıştırıp yapıştır, kimseyle paylaşma.

## 5) Sahip (owner) hesabını oluştur

Tarayıcıdan **bir kez** şu adresi aç (SETUP_KEY'i kendi belirlediğin
değerle değiştir):

```
https://senin-domainin.com/api/setup.php?key=SENIN_SETUP_KEY_DEGERIN
```

`"Sahip hesabı oluşturuldu: MeteTombul / 05052005"` mesajını görmelisin.

**Sonra bu dosyayı sil:** File Manager'dan `api/setup.php` dosyasını sil
(veya adını değiştir). Artık gerek yok, dışarıdan tekrar erişilmesin.

## 6) Kontrol et

- `https://senin-domainin.com/` → mağaza açılmalı, ürünler görünmeli
- `https://senin-domainin.com/admin/` → **MeteTombul / 05052005** ile giriş yap
- Panelden bir ürün ekle → mağazada anında görünmeli
- Mağazadan bir test siparişi ver → panelin Siparişler'inde görünmeli,
  stok otomatik düşmeli

## 7) Parolanı değiştir

Giriş yaptıktan sonra **Ayarlar → Kendi Parolam** bölümünden
`05052005` parolasını hemen kendi parolana çevir.

---

## Önemli notlar

- **`api/config.php` ve `api/setup.php` hassastır.** config.php'deki
  bilgiler veritabanına erişim sağlar; kimseyle paylaşma. setup.php'yi
  kurulumdan sonra sil.
- Fotoğraflar veritabanında (metne çevrilmiş halde) saklanıyor; ürün
  başına birkaç fotoğraf için sorun yok, yüzlerce yüksek çözünürlüklü
  görsel için ileride ayrı bir dosya deposuna geçmek gerekebilir.
- Bir sorunla karşılaşırsan (beyaz sayfa, "Veritabanına bağlanılamadı"
  vb.) önce `api/config.php`'deki 4 bilgiyi kontrol et.
