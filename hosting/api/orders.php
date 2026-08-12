<?php
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/db.php';

$action = $_GET['action'] ?? '';
$pdo = db();

function order_code($pdo) {
  $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  do {
    $code = 'LMS-';
    for ($i = 0; $i < 6; $i++) $code .= $chars[random_int(0, strlen($chars) - 1)];
    $exists = $pdo->prepare("SELECT 1 FROM orders WHERE code=?");
    $exists->execute([$code]);
  } while ($exists->fetch());
  return $code;
}

function lines_out($pdo, $orderId) {
  $stmt = $pdo->prepare("SELECT product_name AS name, size, qty, price FROM order_lines WHERE order_id=?");
  $stmt->execute([$orderId]);
  return $stmt->fetchAll();
}

if ($action === 'place') {
  $d = json_input();
  $name = trim($d['name'] ?? '');
  $phone = trim($d['phone'] ?? '');
  $addr = trim($d['address'] ?? '');
  $items = $d['items'] ?? [];
  if (!$name || !$phone || !$addr || !$items) json_out(['error' => 'Eksik bilgi'], 400);

  $customer = current_customer();
  $email = $customer['email'] ?? ($d['email'] ?? '');

  try {
    $pdo->beginTransaction();
    $total = 0;
    $lineData = [];

    foreach ($items as $it) {
      $pid = $it['id'] ?? '';
      $size = trim($it['size'] ?? '');
      $qty = max(1, (int)($it['qty'] ?? 1));

      $stmt = $pdo->prepare("SELECT * FROM products WHERE id=? FOR UPDATE");
      $stmt->execute([$pid]);
      $p = $stmt->fetch();
      if (!$p) throw new Exception('Ürün bulunamadı');

      $sized = (bool)$p['sized'];
      $sizes = json_decode($p['sizes'] ?? '{}', true) ?: [];

      $available = $sized ? (int)($sizes[$size] ?? 0) : (int)$p['stock'];
      if ($available < $qty) throw new Exception('"' . $p['name'] . '" için yeterli stok yok (' . ($size ?: 'genel') . ')');

      if ($sized) {
        $sizes[$size] = $available - $qty;
        $newStock = array_sum(array_map('intval', $sizes));
        $pdo->prepare("UPDATE products SET sizes=?, stock=? WHERE id=?")
          ->execute([json_encode($sizes), $newStock, $pid]);
      } else {
        $pdo->prepare("UPDATE products SET stock=? WHERE id=?")
          ->execute([$available - $qty, $pid]);
      }

      $lineTotal = (float)$p['price'] * $qty;
      $total += $lineTotal;
      $lineData[] = [$pid, $p['name'], $size, $qty, (float)$p['price']];
    }

    $orderId = uuid();
    $code = order_code($pdo);
    $pdo->prepare("INSERT INTO orders (id, code, customer_name, phone, address, customer_email, total, status) VALUES (?,?,?,?,?,?,?, 'hazirlaniyor')")
      ->execute([$orderId, $code, $name, $phone, $addr, $email, $total]);

    foreach ($lineData as $l) {
      $pdo->prepare("INSERT INTO order_lines (id, order_id, product_id, product_name, size, qty, price) VALUES (?,?,?,?,?,?,?)")
        ->execute([uuid(), $orderId, $l[0], $l[1], $l[2], $l[3], $l[4]]);
    }

    $pdo->commit();
    json_out(['ok' => true, 'code' => $code, 'total' => $total]);
  } catch (Exception $e) {
    $pdo->rollBack();
    json_out(['error' => $e->getMessage()], 400);
  }
}

if ($action === 'track') {
  $code = strtoupper(trim($_GET['code'] ?? ''));
  $stmt = $pdo->prepare("SELECT id, code, customer_name, total, status, created_at FROM orders WHERE code=?");
  $stmt->execute([$code]);
  $o = $stmt->fetch();
  if (!$o) json_out(['error' => 'Sipariş bulunamadı'], 404);
  $o['lines'] = lines_out($pdo, $o['id']);
  json_out($o);
}

if ($action === 'my') {
  $customer = current_customer();
  if (!$customer) json_out(['error' => 'Giriş gerekli'], 401);
  $stmt = $pdo->prepare("SELECT id, code, total, status, created_at FROM orders WHERE customer_email=? ORDER BY created_at DESC");
  $stmt->execute([$customer['email']]);
  json_out($stmt->fetchAll());
}

if ($action === 'list') {
  require_staff('personel');
  $status = $_GET['status'] ?? '';
  $sql = "SELECT id, code, customer_name, phone, address, customer_email, total, status, created_at FROM orders";
  $params = [];
  if ($status) { $sql .= " WHERE status=?"; $params[] = $status; }
  $sql .= " ORDER BY created_at DESC";
  $stmt = $pdo->prepare($sql);
  $stmt->execute($params);
  $orders = $stmt->fetchAll();
  foreach ($orders as &$o) { $o['lines'] = lines_out($pdo, $o['id']); }
  json_out($orders);
}

if ($action === 'update_status') {
  require_staff('personel');
  $d = json_input();
  $valid = ['hazirlaniyor', 'kargoda', 'teslim', 'iptal'];
  if (empty($d['id']) || !in_array($d['status'] ?? '', $valid)) json_out(['error' => 'Geçersiz istek'], 400);
  $pdo->prepare("UPDATE orders SET status=? WHERE id=?")->execute([$d['status'], $d['id']]);
  json_out(['ok' => true]);
}

json_out(['error' => 'Bilinmeyen işlem'], 400);
