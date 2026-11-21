-- ============================================================================
-- DRAFT · 未编号入账 · 未执行 · 不在 resources/db/poetry 下（不会被迁移工具读到）
-- 来源：docs/review/architecture-review.md §7.3–§7.4。对应决定点见 docs/handoff/A.md §14。
-- 约束：MySQL 5.6.40；无外键、无 JSON、无 CHECK、无生成列；标识符 utf8mb4_bin。
-- 索引字节核算（上限 767）：
--   poetry_corpus.corpus_id      VARCHAR(64) utf8mb4_bin  = 256 字节（主键）
--   poetry_corpus.file_sha256    CHAR(64)    utf8mb4_bin  = 256 字节（普通索引）
--   poetry_source_corpus_check   主键 = BIGINT 自增（8 字节）；不做 (source_id,corpus_id,span_sha256) 复合主键，
--                                那是 256+256+256 = 768 字节，超限。
-- 本文件不加任何版本账本插入；若采用，编号与账本由用户决定。
-- ============================================================================

-- 1. 语料登记（权威，只由人写入）。每份语料一行；文件内容变化 = 新 corpus_id，不覆盖旧行。
CREATE TABLE IF NOT EXISTS poetry_corpus (
  corpus_id VARCHAR(64) COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  institution VARCHAR(200) NOT NULL,         -- 来源机构/项目（写具体，不写「网上」）
  edition VARCHAR(200) NOT NULL,             -- 底本/版次；与 poetry_source.edition 对应核对
  file_path VARCHAR(300) NOT NULL,           -- 相对于语料根的路径，不写绝对路径
  file_sha256 CHAR(64) COLLATE utf8mb4_bin NOT NULL,
  rights_note TEXT NOT NULL,                 -- 许可来源与核实情况原文
  rights_status VARCHAR(16) NOT NULL,        -- UNVERIFIED | VERIFIED | RESTRICTED（默认应为 UNVERIFIED）
  allowed_use VARCHAR(64) NOT NULL,          -- INTERNAL_CHECK（仅内部核对）| PUBLIC_QUOTE（需 VERIFIED）
  status VARCHAR(16) NOT NULL DEFAULT 'REGISTERED',   -- REGISTERED | RETIRED
  registered_by VARCHAR(100) NOT NULL,
  registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_poetry_corpus_sha (file_sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 核对记录（追加，永不 UPDATE）。记录「某来源的某个定位符，是在哪一版语料文件上核对的」。
--    这正是 §7.4(6)：语料文件 sha256 变化后，verifySource 据此判断是否要人重新确认。
--    locator 是结构化文本（格式见 corpus-chunwang-locator-plan.md），不是自由文本。
CREATE TABLE IF NOT EXISTS poetry_source_corpus_check (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_id VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
  corpus_id VARCHAR(64) COLLATE utf8mb4_bin NOT NULL,
  file_sha256_at_check CHAR(64) COLLATE utf8mb4_bin NOT NULL,
  locator VARCHAR(500) NOT NULL,
  span_sha256 CHAR(64) COLLATE utf8mb4_bin NOT NULL,
  checked_by VARCHAR(100) NOT NULL,
  checked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_poetry_source_corpus_check_source (source_id, id),
  KEY ix_poetry_source_corpus_check_corpus (corpus_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 结构断言（执行时若列缺失会报 1054；本草案只做形状检查，不执行）
SELECT corpus_id, title, institution, edition, file_path, file_sha256, rights_note,
       rights_status, allowed_use, status, registered_by, registered_at FROM poetry_corpus LIMIT 0;
SELECT id, source_id, corpus_id, file_sha256_at_check, locator, span_sha256, checked_by, checked_at
  FROM poetry_source_corpus_check LIMIT 0;

-- 回滚草案（若采用后撤回）：两表都只有新增，撤回时先改名保留（与 V009 相同的理由：核对记录不可丢）。
-- ALTER TABLE poetry_source_corpus_check RENAME TO poetry_source_corpus_check_rolledback_YYYYMMDD;
-- ALTER TABLE poetry_corpus RENAME TO poetry_corpus_rolledback_YYYYMMDD;
