-- Munim schema v1: docs/ARCHITECTURE.md section 4 with PLAN_REVIEW D8 and D13.
CREATE TABLE cases (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  supplier_name TEXT NOT NULL,
  buyer_name TEXT NOT NULL,
  supplier_address TEXT,
  buyer_address TEXT,
  udyam_number TEXT,
  udyam_date TEXT,
  enterprise_size TEXT CHECK (enterprise_size IN ('micro', 'small', 'medium') OR enterprise_size IS NULL),
  agreement TEXT CHECK (agreement IN ('written', 'none') OR agreement IS NULL),
  credit_days INTEGER CHECK (credit_days IS NULL OR credit_days >= 0),
  objection_removed_on TEXT,
  acceptance_date TEXT,
  interest_base TEXT NOT NULL DEFAULT 'invoice_total' CHECK (interest_base IN ('invoice_total', 'taxable_total')),
  as_on_date TEXT,
  notice_days INTEGER NOT NULL DEFAULT 15 CHECK (notice_days BETWEEN 1 AND 90),
  confirmed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE papers (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('invoice', 'challan', 'po')),
  original_path TEXT NOT NULL,
  derived_path TEXT,
  sha256 TEXT NOT NULL,
  file_type TEXT NOT NULL,
  width INTEGER,
  height INTEGER,
  rotation INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK (status IN ('added', 'reading', 'repairing', 'read', 'failed')),
  provider TEXT,
  model TEXT,
  prompt_version TEXT,
  replayed INTEGER NOT NULL DEFAULT 0,
  read_at TEXT,
  error TEXT,
  dark INTEGER NOT NULL DEFAULT 0,
  blurred INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE (case_id, kind)
);

CREATE TABLE claims (
  id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  field TEXT NOT NULL,
  line_index INTEGER NOT NULL DEFAULT -1,
  value_read TEXT,
  value_current TEXT,
  box_y1 INTEGER, box_x1 INTEGER, box_y2 INTEGER, box_x2 INTEGER,
  source TEXT NOT NULL CHECK (source IN ('model', 'repair', 'user')),
  repair_attempts INTEGER NOT NULL DEFAULT 0,
  repair_via TEXT,
  repair_outcome TEXT,
  repair_reason TEXT,
  review_flag TEXT,
  animate INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 1,
  UNIQUE (paper_id, field, line_index)
);

CREATE TABLE acceptances (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  rule_id TEXT NOT NULL,
  fields_json TEXT NOT NULL,
  versions_json TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE findings (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  rule_id TEXT NOT NULL,
  status TEXT NOT NULL,
  severity TEXT NOT NULL,
  message_key TEXT NOT NULL,
  params_json TEXT NOT NULL,
  fields_json TEXT NOT NULL,
  rule_version TEXT NOT NULL
);

CREATE TABLE payments (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  paid_on TEXT NOT NULL,
  amount_paise INTEGER NOT NULL CHECK (amount_paise > 0)
);

CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE bank_rates (
  effective_from TEXT PRIMARY KEY,
  percent TEXT NOT NULL,
  source TEXT NOT NULL,
  confirmed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT,
  at TEXT NOT NULL,
  kind TEXT NOT NULL,
  detail_json TEXT NOT NULL
);
