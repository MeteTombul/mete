<?php
/**
 * Tek seferlik kurulum: sahip (owner) hesabını GÜVENLİ (hash'lenmiş
 * parolayla) şekilde oluşturur. schema-mysql.sql'i içe aktardıktan
 * sonra tarayıcıdan bir kez şu adresi aç:
 *
 *   https://SENIN-DOMAININ.com/api/setup.php?key=SETUP_KEY_DEĞERİN
 *
 * Başarılı olursa "kuruldu" mesajı görürsün. Ardından bu dosyayı
 * (setup.php) sunucudan SİLMEN önerilir; tekrar erişilirse anlamsız
 * olacaktır çünkü zaten owner varsa hiçbir şey yapmaz.
 */
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/db.php';

if (($_GET['key'] ?? '') !== SETUP_KEY) {
  json_out(['error' => 'Geçersiz kurulum anahtarı'], 403);
}

$pdo = db();
$count = $pdo->query("SELECT COUNT(*) c FROM staff")->fetch()['c'];
if ($count > 0) {
  json_out(['ok' => true, 'message' => 'Zaten kurulmuş, personel kayıtları mevcut.']);
}

$stmt = $pdo->prepare("INSERT INTO staff (id, username, password_hash, role, name) VALUES (?,?,?,?,?)");
$stmt->execute([uuid(), 'MeteTombul', password_hash('05052005', PASSWORD_DEFAULT), 'owner', 'Mete Tombul']);

json_out(['ok' => true, 'message' => 'Sahip hesabı oluşturuldu: MeteTombul / 05052005. Şimdi bu dosyayı sunucudan silebilirsin.']);
