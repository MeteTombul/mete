-- Lumas Butik — Hostinger (MySQL/MariaDB) veritabanı şeması
--
-- Kurulum:
-- 1) Hostinger hPanel -> Databases -> MySQL Databases
--    - Yeni veritabanı oluştur (ör. u123456789_lumas)
--    - Yeni kullanıcı oluştur, veritabanına tam yetkiyle bağla
--    - Veritabanı adı / kullanıcı adı / parola / host bilgisini not al
-- 2) hPanel -> Databases -> phpMyAdmin -> oluşturduğun veritabanını seç
-- 3) Üstte "Import" (İçe Aktar) sekmesine gir, bu dosyayı seç, "Go" / "Git" de
-- 4) api/config.php içine 1. adımdaki bilgileri yaz (bkz. o dosyadaki yorumlar)

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS settings (
  id INT PRIMARY KEY DEFAULT 1,
  store_name VARCHAR(120) NOT NULL DEFAULT 'Lumas Butik',
  currency VARCHAR(4) NOT NULL DEFAULT '₺',
  low_stock INT NOT NULL DEFAULT 5,
  work_start INT NOT NULL DEFAULT 9,
  work_end INT NOT NULL DEFAULT 17
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO settings (id) VALUES (1);

CREATE TABLE IF NOT EXISTS categories (
  id VARCHAR(20) PRIMARY KEY,
  name VARCHAR(120) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO categories (id, name) VALUES
  ('c1','Elbise'), ('c2','Üst Giyim'), ('c3','Alt Giyim'), ('c4','Aksesuar');

CREATE TABLE IF NOT EXISTS products (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  gender ENUM('kadin','erkek') NOT NULL,
  category_id VARCHAR(20),
  price DECIMAL(10,2) NOT NULL DEFAULT 0,
  sized TINYINT(1) NOT NULL DEFAULT 1,
  sizes JSON NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  sku VARCHAR(60) DEFAULT '',
  description TEXT,
  images JSON NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
  id VARCHAR(36) PRIMARY KEY,
  code VARCHAR(20) UNIQUE NOT NULL,
  customer_name VARCHAR(150) NOT NULL,
  phone VARCHAR(40),
  address TEXT,
  customer_email VARCHAR(150),
  total DECIMAL(10,2) NOT NULL DEFAULT 0,
  status ENUM('hazirlaniyor','kargoda','teslim','iptal') NOT NULL DEFAULT 'hazirlaniyor',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_lines (
  id VARCHAR(36) PRIMARY KEY,
  order_id VARCHAR(36) NOT NULL,
  product_id VARCHAR(36),
  product_name VARCHAR(200) NOT NULL,
  size VARCHAR(10) DEFAULT '',
  qty INT NOT NULL DEFAULT 1,
  price DECIMAL(10,2) NOT NULL DEFAULT 0,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS customers (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(150) NOT NULL,
  email VARCHAR(150) UNIQUE NOT NULL,
  phone VARCHAR(40),
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS staff (
  id VARCHAR(36) PRIMARY KEY,
  username VARCHAR(80) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('owner','yonetici','personel') NOT NULL DEFAULT 'personel',
  name VARCHAR(150) DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Not: MeteTombul / 05052005 kullanıcısı burada eklenmiyor çünkü şifre
-- burada düz metin değil "hash" olarak saklanmalı. api/setup.php dosyasını
-- ÇALIŞTIRDIĞINDA bu kullanıcı otomatik ve güvenli şekilde oluşturulur
-- (bkz. HOSTINGER-KURULUM.md).
