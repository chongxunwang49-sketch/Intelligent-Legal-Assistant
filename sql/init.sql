-- ============================================================
-- 智法通 V2 —— 数据库初始化（仅建库；表结构由后端 ORM 启动时自动创建）
-- 手动执行：mysql -u root -p < sql/init.sql
-- ============================================================
CREATE DATABASE IF NOT EXISTS zhifatong
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE zhifatong;
