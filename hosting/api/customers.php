<?php
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/db.php';

$action = $_GET['action'] ?? '';
$pdo = db();

if ($action === 'register') {
  $d = json_input();
  $name = trim($d['name'] ?? '');
  $email = strtolower(trim($d['email'] ?? ''));
  if (!$name || !$email || empty($d['password'])) json_out(['error' => 'Eksik bilgi'], 400);
  $exists = $pdo->prepare("SELECT 1 FROM customers WHERE email=?");
  $exists->execute([$email]);
  if ($exists->fetch()) json_out(['error' => 'Bu e-posta zaten kayıtlı'], 400);
  $id = uuid();
  $pdo->prepare("INSERT INTO customers (id, name, email, phone, password_hash) VALUES (?,?,?,?,?)")
    ->execute([$id, $name, $email, trim($d['phone'] ?? ''), password_hash($d['password'], PASSWORD_DEFAULT)]);
  $token = make_token(['type' => 'customer', 'id' => $id, 'email' => $email, 'name' => $name]);
  json_out(['token' => $token, 'id' => $id, 'name' => $name, 'email' => $email]);
}

if ($action === 'login') {
  $d = json_input();
  $email = strtolower(trim($d['email'] ?? ''));
  $stmt = $pdo->prepare("SELECT * FROM customers WHERE email=?");
  $stmt->execute([$email]);
  $u = $stmt->fetch();
  if (!$u || !password_verify($d['password'] ?? '', $u['password_hash'])) {
    json_out(['error' => 'E-posta veya parola hatalı'], 401);
  }
  $token = make_token(['type' => 'customer', 'id' => $u['id'], 'email' => $u['email'], 'name' => $u['name']]);
  json_out(['token' => $token, 'id' => $u['id'], 'name' => $u['name'], 'email' => $u['email'], 'phone' => $u['phone']]);
}

json_out(['error' => 'Bilinmeyen işlem'], 400);
