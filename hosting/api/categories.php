<?php
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/db.php';

$action = $_GET['action'] ?? '';
$pdo = db();

if ($action === 'list') {
  json_out($pdo->query("SELECT id, name FROM categories ORDER BY name")->fetchAll());
}

if ($action === 'create') {
  require_staff('yonetici');
  $d = json_input();
  $name = trim($d['name'] ?? '');
  if (!$name) json_out(['error' => 'Kategori adı zorunlu'], 400);
  $id = 'c' . substr(uuid(), 0, 8);
  $pdo->prepare("INSERT INTO categories (id, name) VALUES (?,?)")->execute([$id, $name]);
  json_out(['ok' => true, 'id' => $id]);
}

if ($action === 'update') {
  require_staff('yonetici');
  $d = json_input();
  $name = trim($d['name'] ?? '');
  if (empty($d['id']) || !$name) json_out(['error' => 'Eksik bilgi'], 400);
  $pdo->prepare("UPDATE categories SET name=? WHERE id=?")->execute([$name, $d['id']]);
  json_out(['ok' => true]);
}

if ($action === 'delete') {
  require_staff('yonetici');
  $d = json_input();
  $count = $pdo->prepare("SELECT COUNT(*) c FROM products WHERE category_id=?");
  $count->execute([$d['id'] ?? '']);
  if ($count->fetch()['c'] > 0) json_out(['error' => 'Bu kategoride ürün var, önce onları taşıyın'], 400);
  $pdo->prepare("DELETE FROM categories WHERE id=?")->execute([$d['id'] ?? '']);
  json_out(['ok' => true]);
}

json_out(['error' => 'Bilinmeyen işlem'], 400);
