<?php
require_once __DIR__ . '/config.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

function json_out($data, $status = 200) {
  http_response_code($status);
  echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
  exit;
}

function json_input() {
  $raw = file_get_contents('php://input');
  $d = json_decode($raw, true);
  return is_array($d) ? $d : [];
}

/* ---- basit HMAC oturum belirteci (harici kütüphane gerekmez) ---- */
function make_token($payload) {
  $payload['exp'] = time() + 60 * 60 * 24 * 30; // 30 gün
  $body = base64_encode(json_encode($payload));
  $sig = hash_hmac('sha256', $body, SECRET_KEY);
  return $body . '.' . $sig;
}

function verify_token($token) {
  if (!$token || strpos($token, '.') === false) return null;
  [$body, $sig] = explode('.', $token, 2);
  $expected = hash_hmac('sha256', $body, SECRET_KEY);
  if (!hash_equals($expected, $sig)) return null;
  $payload = json_decode(base64_decode($body), true);
  if (!$payload || ($payload['exp'] ?? 0) < time()) return null;
  return $payload;
}

function bearer_token() {
  $h = $_SERVER['HTTP_AUTHORIZATION'] ?? ($_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
  if (preg_match('/Bearer\s+(\S+)/', $h, $m)) return $m[1];
  return null;
}

function require_staff($minRole = 'personel') {
  $ranks = ['personel' => 1, 'yonetici' => 2, 'owner' => 3];
  $payload = verify_token(bearer_token());
  if (!$payload || ($payload['type'] ?? '') !== 'staff') {
    json_out(['error' => 'Giriş gerekli'], 401);
  }
  if (($ranks[$payload['role']] ?? 0) < ($ranks[$minRole] ?? 99)) {
    json_out(['error' => 'Bu işlem için yetkiniz yok'], 403);
  }
  return $payload;
}

function current_customer() {
  $payload = verify_token(bearer_token());
  if ($payload && ($payload['type'] ?? '') === 'customer') return $payload;
  return null;
}
