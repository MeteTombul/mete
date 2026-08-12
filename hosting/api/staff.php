<?php
require_once __DIR__ . '/helpers.php';
require_once __DIR__ . '/db.php';

$action = $_GET['action'] ?? '';
$pdo = db();

if ($action === 'login') {
  $d = json_input();
  $stmt = $pdo->prepare("SELECT * FROM staff WHERE username=?");
  $stmt->execute([trim($d['username'] ?? '')]);
  $u = $stmt->fetch();
  if (!$u || !password_verify($d['password'] ?? '', $u['password_hash'])) {
    json_out(['error' => 'Kullanıcı adı veya parola hatalı'], 401);
  }
  $token = make_token(['type' => 'staff', 'id' => $u['id'], 'role' => $u['role'], 'username' => $u['username']]);
  json_out(['token' => $token, 'id' => $u['id'], 'username' => $u['username'], 'role' => $u['role'], 'name' => $u['name']]);
}

if ($action === 'me') {
  $p = require_staff('personel');
  $stmt = $pdo->prepare("SELECT id, username, role, name FROM staff WHERE id=?");
  $stmt->execute([$p['id']]);
  json_out($stmt->fetch());
}

if ($action === 'list') {
  require_staff('owner');
  json_out($pdo->query("SELECT id, username, role, name FROM staff ORDER BY role")->fetchAll());
}

if ($action === 'create') {
  require_staff('owner');
  $d = json_input();
  $username = trim($d['username'] ?? '');
  if (!$username || empty($d['password'])) json_out(['error' => 'Kullanıcı adı ve parola zorunlu'], 400);
  $exists = $pdo->prepare("SELECT 1 FROM staff WHERE username=?");
  $exists->execute([$username]);
  if ($exists->fetch()) json_out(['error' => 'Bu kullanıcı adı zaten var'], 400);
  $role = in_array($d['role'] ?? '', ['yonetici', 'personel']) ? $d['role'] : 'personel';
  $id = uuid();
  $pdo->prepare("INSERT INTO staff (id, username, password_hash, role, name) VALUES (?,?,?,?,?)")
    ->execute([$id, $username, password_hash($d['password'], PASSWORD_DEFAULT), $role, trim($d['name'] ?? '')]);
  json_out(['ok' => true, 'id' => $id]);
}

if ($action === 'update') {
  $me = require_staff('personel'); // kendi parolasını değiştirebilir; başkasını değiştirmek owner ister
  $d = json_input();
  if (empty($d['id'])) json_out(['error' => 'Eksik id'], 400);
  if ($d['id'] !== $me['id']) require_staff('owner');

  $fields = []; $params = [];
  if (isset($d['name'])) { $fields[] = 'name=?'; $params[] = trim($d['name']); }
  if (isset($d['username'])) { $fields[] = 'username=?'; $params[] = trim($d['username']); }
  if (isset($d['role']) && $d['id'] !== $me['id']) { $fields[] = 'role=?'; $params[] = $d['role']; }
  if (!empty($d['password'])) { $fields[] = 'password_hash=?'; $params[] = password_hash($d['password'], PASSWORD_DEFAULT); }
  if (!$fields) json_out(['error' => 'Güncellenecek alan yok'], 400);
  $params[] = $d['id'];
  $pdo->prepare("UPDATE staff SET " . implode(',', $fields) . " WHERE id=?")->execute($params);
  json_out(['ok' => true]);
}

if ($action === 'delete') {
  require_staff('owner');
  $d = json_input();
  $stmt = $pdo->prepare("SELECT role FROM staff WHERE id=?");
  $stmt->execute([$d['id'] ?? '']);
  $u = $stmt->fetch();
  if ($u && $u['role'] === 'owner') json_out(['error' => 'Sahip hesabı silinemez'], 400);
  $pdo->prepare("DELETE FROM staff WHERE id=?")->execute([$d['id'] ?? '']);
  json_out(['ok' => true]);
}

json_out(['error' => 'Bilinmeyen işlem'], 400);
