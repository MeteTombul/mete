<?php
/**
 * Lumas Butik — veritabanı bağlantı ayarları.
 *
 * Hostinger hPanel -> Databases -> MySQL Databases bölümünden aldığın
 * bilgileri aşağıya yaz. Hostinger'da DB_HOST genelde "localhost"tur.
 */

define('DB_HOST', 'localhost');
define('DB_NAME', 'DEĞİŞTİR_veritabani_adi');
define('DB_USER', 'DEĞİŞTİR_kullanici_adi');
define('DB_PASS', 'DEĞİŞTİR_parola');

/**
 * Oturum belirteçlerini (token) imzalamak için rastgele, uzun ve gizli
 * bir anahtar. Kimseyle paylaşma. Aşağıdaki örneği MUTLAKA kendi
 * rastgele metninle değiştir (ör. 40+ karakter, harf+rakam karışık).
 */
define('SECRET_KEY', 'DEĞİŞTİR_uzun_rastgele_gizli_anahtar_12345');

/**
 * İlk kurulumda tek seferlik sahip (owner) hesabını oluşturmak için
 * kullanılan anahtar. setup.php dosyasını çalıştırdıktan sonra burayı
 * da değiştirmen veya setup.php dosyasını sunucudan silmen önerilir.
 */
define('SETUP_KEY', 'DEĞİŞTİR_kurulum_anahtari');
