-- Lumas Butik — Supabase şeması
-- Supabase projende: sol menü "SQL Editor" -> "New query" -> bu dosyanın
-- tamamını yapıştır -> "Run". Tek seferde tüm tabloları ve güvenlik
-- kurallarını kurar.

create extension if not exists "pgcrypto";

-- ---------- Ayarlar (tek satır) ----------
create table if not exists settings (
  id int primary key default 1,
  store_name text not null default 'Lumas Butik',
  currency text not null default '₺',
  low_stock int not null default 5,
  work_start int not null default 9,
  work_end int not null default 17,
  constraint single_row check (id = 1)
);
insert into settings (id) values (1) on conflict (id) do nothing;

-- ---------- Kategoriler ----------
create table if not exists categories (
  id text primary key,
  name text not null
);
insert into categories (id, name) values
  ('c1','Elbise'), ('c2','Üst Giyim'), ('c3','Alt Giyim'), ('c4','Aksesuar')
on conflict (id) do nothing;

-- ---------- Ürünler ----------
create table if not exists products (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  gender text not null check (gender in ('kadin','erkek')),
  category_id text references categories(id) on delete set null,
  price numeric not null default 0,
  sized boolean not null default true,
  sizes jsonb not null default '{}'::jsonb,   -- {"S":2,"M":4,...}
  stock int not null default 0,               -- sized=false ürünler için
  sku text default '',
  description text default '',
  images text[] not null default '{}',        -- Supabase Storage URL'leri
  created_at timestamptz not null default now()
);

-- ---------- Siparişler ----------
create table if not exists orders (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  customer_name text not null,
  phone text,
  address text,
  customer_email text,
  total numeric not null default 0,
  status text not null default 'hazirlaniyor'
    check (status in ('hazirlaniyor','kargoda','teslim','iptal')),
  created_at timestamptz not null default now()
);

create table if not exists order_lines (
  id uuid primary key default gen_random_uuid(),
  order_id uuid references orders(id) on delete cascade,
  product_id uuid references products(id) on delete set null,
  product_name text not null,
  size text default '',
  qty int not null default 1,
  price numeric not null default 0
);

-- ---------- Müşteri hesapları ----------
create table if not exists customers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text unique not null,
  phone text,
  password text not null,   -- basit demo; ileride Supabase Auth'a taşınabilir
  created_at timestamptz not null default now()
);

-- ---------- Personel (yönetici paneli) ----------
create table if not exists staff (
  id uuid primary key default gen_random_uuid(),
  username text unique not null,
  password text not null,   -- basit demo; ileride Supabase Auth'a taşınabilir
  role text not null default 'personel' check (role in ('owner','yonetici','personel')),
  name text default ''
);
insert into staff (username, password, role, name)
values ('MeteTombul', '05052005', 'owner', 'Mete Tombul')
on conflict (username) do nothing;

-- =====================================================================
-- ROW LEVEL SECURITY
-- Site (herkes / "anon" anahtarı): ürün+kategori+ayar okuyabilir,
-- sipariş oluşturabilir, kendi siparişini kod ile sorgulayabilir,
-- hesap açıp giriş yapabilir (bu tablolara sınırlı erişim).
-- Panel de aynı "anon" anahtarını kullanır ama kullanıcı adı/şifreyi
-- kendi kontrol eder (bu basit modelde tüm anon istemciler read/write
-- yapabilir — gerçek çoklu-mağaza güvenliği için sonraki adımda
-- Supabase Auth'a taşınabilir).
-- =====================================================================

alter table settings enable row level security;
alter table categories enable row level security;
alter table products enable row level security;
alter table orders enable row level security;
alter table order_lines enable row level security;
alter table customers enable row level security;
alter table staff enable row level security;

create policy "settings_read" on settings for select using (true);
create policy "settings_write" on settings for update using (true);

create policy "categories_read" on categories for select using (true);
create policy "categories_write" on categories for all using (true);

create policy "products_read" on products for select using (true);
create policy "products_write" on products for all using (true);

create policy "orders_read" on orders for select using (true);
create policy "orders_insert" on orders for insert with check (true);
create policy "orders_update" on orders for update using (true);

create policy "order_lines_read" on order_lines for select using (true);
create policy "order_lines_insert" on order_lines for insert with check (true);

create policy "customers_read" on customers for select using (true);
create policy "customers_insert" on customers for insert with check (true);

create policy "staff_read" on staff for select using (true);
create policy "staff_write" on staff for all using (true);
