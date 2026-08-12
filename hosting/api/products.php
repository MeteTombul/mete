<?php
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/db.php';

$action = $_GET['action'] ?? '';
$pdo = db();

function row_out($r) {
  $r['sized'] = (bool)$r['sized'];
  $r['sizes'] = json_decode($r['sizes'] ?? '{}', true) ?: new stdClass();
  $r['images'] = json_decode($r['images'] ?? '[]', true) ?: [];
  $r['price'] = (float)$r['price'];
  $r['stock'] = (int)$r['stock'];
  return $r;
}

if ($action === 'list') {
  $sql = "SELECT * FROM products";
  $params = [];
  if (!empty($_GET['gender'])) { $sql .= " WHERE gender=?"; $params[] = $_GET['gender']; }
  $sql .= " ORDER BY created_at DESC";
  $stmt = $pdo->prepare($sql);
  $stmt->execute($params);
  json_out(array_map('row_out', $stmt->fetchAll()));
}

if ($action === 'create') {
  require_staff('yonetici');
  $d = json_input();
  $name = trim($d['name'] ?? '');
  if (!$name) json_out(['error' => 'Ürün adı zorunlu'], 400);
  $id = uuid();
  $sized = !empty($d['sized']);
  $sizes = $sized ? ($d['sizes'] ?? []) : [];
  $stock = $sized ? array_sum(array_map('intval', $sizes)) : (int)($d['stock'] ?? 0);
  $stmt = $pdo->prepare("INSERT INTO products (id,name,gender,category_id,price,sized,sizes,stock,sku,description,images) VALUES (?,?,?,?,?,?,?,?,?,?,?)");
  $stmt->execute([
    $id, $name, $d['gender'] ?? 'kadin', $d['category'] ?? $d['category_id'] ?? null,
    (float)($d['price'] ?? 0), $sized ? 1 : 0, json_encode($sizes), $stock,
    trim($d['sku'] ?? ''), trim($d['desc'] ?? $d['description'] ?? ''), json_encode($d['images'] ?? [])
  ]);
  json_out(['ok' => true, 'id' => $id]);
}

if ($action === 'update') {
  require_staff('yonetici');
  $d = json_input();
  if (empty($d['id'])) json_out(['error' => 'Eksik id'], 400);
  $sized = !empty($d['sized']);
  $sizes = $sized ? ($d['sizes'] ?? []) : [];
  $stock = $sized ? array_sum(array_map('intval', $sizes)) : (int)($d['stock'] ?? 0);
  $stmt = $pdo->prepare("UPDATE products SET name=?, gender=?, category_id=?, price=?, sized=?, sizes=?, stock=?, sku=?, description=?, images=? WHERE id=?");
  $stmt->execute([
    trim($d['name'] ?? ''), $d['gender'] ?? 'kadin', $d['category'] ?? $d['category_id'] ?? null,
    (float)($d['price'] ?? 0), $sized ? 1 : 0, json_encode($sizes), $stock,
    trim($d['sku'] ?? ''), trim($d['desc'] ?? $d['description'] ?? ''), json_encode($d['images'] ?? []),
    $d['id']
  ]);
  json_out(['ok' => true]);
}

if ($action === 'delete') {
  require_staff('yonetici');
  $d = json_input();
  $pdo->prepare("DELETE FROM products WHERE id=?")->execute([$d['id'] ?? '']);
  json_out(['ok' => true]);
}

json_out(['error' => 'Bilinmeyen işlem'], 400);
