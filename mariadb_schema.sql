-- MariaDB schema for OCR document metadata
-- Ejecutar en la base de datos 'ocr' o ajustar nombre
CREATE TABLE IF NOT EXISTS nodes (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  parent_id BIGINT NULL,
  name VARCHAR(512) NOT NULL,
  path VARCHAR(2000) NOT NULL,
  is_dir TINYINT(1) NOT NULL DEFAULT 0,
  size BIGINT NULL,
  mtime DATETIME NULL,
  checksum CHAR(64) NULL,
  mime VARCHAR(255) NULL,
  extra JSON NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_nodes_path (path),
  KEY idx_nodes_parent (parent_id),
  KEY idx_nodes_checksum (checksum)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS contents (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  checksum CHAR(64) NOT NULL UNIQUE,
  size BIGINT,
  storage_path VARCHAR(2000) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pdf_metadata (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  node_id BIGINT NOT NULL,
  content_id BIGINT NULL,
  pages INT NULL,
  text_found TINYINT(1) DEFAULT 0,
  ocr_status ENUM('pending','processing','done','failed') DEFAULT 'pending',
  ocr_provider VARCHAR(100) NULL,
  ocr_pdf_path VARCHAR(2000) NULL,
  ocr_text LONGTEXT NULL,
  snippet VARCHAR(1000) NULL,
  last_error TEXT NULL,
  ocr_started_at DATETIME NULL,
  ocr_finished_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_pdf_node (node_id),
  KEY idx_pdf_status (ocr_status),
  CONSTRAINT fk_pdf_node FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
  CONSTRAINT fk_pdf_content FOREIGN KEY (content_id) REFERENCES contents(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Opcional: FULLTEXT index si solo MariaDB se va a usar para búsqueda
-- ALTER TABLE pdf_metadata ADD FULLTEXT KEY ft_ocr (ocr_text);
