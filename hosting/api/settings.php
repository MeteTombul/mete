<?php
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/db.php';

$action = $_GET['action'] ?? ($_SERVER['REQUEST_METHOD'] === 'GET' ? 'get' : '');
$pdo = db();

if ($action === 'get') {
  $row = $pdo->query("SELECT * FROM settings WHERE id=1")->fetch();
  json_out($row ?: new stdClass());
}

if ($action === 'update') {
  require_staff('yonetici');
  $d = json_input();
  $stmt = $pdo->prepare("UPDATE settings SET store_name=?, currency=?, low_stock=?, work_start=?, work_end=? WHERE id=1");
  $stmt->execute([
    $d['store_name'] ?? 'Lumas Butik',
    $d['currency'] ?? '₺',
    (int)($d['low_stock'] ?? 5),
    (int)($d['work_start'] ?? 9),
    (int)($d['work_end'] ?? 17),
  ]);
  json_out(['ok' => true]);
}

json_out(['error' => 'Bilinmeyen işlem'], 400);
