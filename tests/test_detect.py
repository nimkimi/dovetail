from dovetail.detect import detect_triggers, is_trivial, is_structural


def test_detects_loop_as_runtime_cost():
    added = "for item in items:\n    total += item.value\n"
    assert "runtime-cost" in detect_triggers(added, "app/calc.py")


def test_string_mentioning_for_is_not_runtime_cost():
    added = 'msg = "scanning for updates"\n'
    assert "runtime-cost" not in detect_triggers(added, "app/status.py")


def test_detects_c_style_for_loop_as_runtime_cost():
    added = "for (let i = 0; i < items.length; i++) {\n"
    assert "runtime-cost" in detect_triggers(added, "src/render.ts")


def test_detects_while_loop_as_runtime_cost():
    added = "while (queue.length > 0) {\n"
    assert "runtime-cost" in detect_triggers(added, "src/worker.ts")


def test_full_line_comments_do_not_trigger():
    added = "# delete from the cache once the import settles\nx = 1\n"
    assert detect_triggers(added, "app/core.py") == []


def test_slash_comment_mentioning_env_does_not_trigger():
    added = "// read process.env.API_KEY here later\nconst y = 2\n"
    assert detect_triggers(added, "src/note.ts") == []


def test_detects_new_python_import_as_reuse():
    added = "import os\n"
    assert "reuse" in detect_triggers(added, "app/util.py")


def test_detects_python_from_import_as_reuse():
    added = "from collections import defaultdict\n"
    assert "reuse" in detect_triggers(added, "app/util.py")


def test_detects_js_require_as_reuse():
    added = "const lodash = require('lodash')\n"
    assert "reuse" in detect_triggers(added, "src/index.js")


def test_detects_js_esm_import_as_reuse():
    added = "import { useState } from 'react'\n"
    assert "reuse" in detect_triggers(added, "src/App.tsx")


def test_detects_package_json_dependency_as_dep_vet():
    added = '    "left-pad": "^1.3.0",\n'
    assert "dep-vet" in detect_triggers(added, "package.json")


def test_package_json_name_field_is_not_dep_vet():
    added = '  "name": "my-app",\n'
    assert "dep-vet" not in detect_triggers(added, "package.json")


def test_package_json_version_field_is_not_dep_vet():
    added = '  "version": "1.0.0",\n'
    assert "dep-vet" not in detect_triggers(added, "package.json")


def test_detects_requirements_txt_dependency_as_dep_vet():
    added = "requests==2.31.0\n"
    assert "dep-vet" in detect_triggers(added, "requirements.txt")


def test_requirements_txt_comment_is_not_dep_vet():
    added = "# pin versions for reproducible builds\n"
    assert "dep-vet" not in detect_triggers(added, "requirements.txt")


def test_detects_pyproject_dependency_as_dep_vet():
    added = 'requests = "^2.31.0"\n'
    assert "dep-vet" in detect_triggers(added, "pyproject.toml")


def test_detects_go_mod_dependency_as_dep_vet():
    added = "\tgithub.com/pkg/errors v0.9.1\n"
    assert "dep-vet" in detect_triggers(added, "go.mod")


def test_detects_exported_interface_as_breaking_change():
    added = "export interface UserDTO {\n  id: string\n}\n"
    assert "breaking-change" in detect_triggers(added, "src/types.ts")


def test_detects_exported_type_alias_as_breaking_change():
    added = "export type UserId = string\n"
    assert "breaking-change" in detect_triggers(added, "src/types.ts")


def test_detects_db_schema_change_as_breaking_change():
    added = "ALTER TABLE users ADD COLUMN email text;\n"
    assert "breaking-change" in detect_triggers(added, "db/migrations/003_add_email.sql")


def test_detects_env_var_access_as_breaking_change():
    added = "const apiKey = process.env.API_KEY\n"
    assert "breaking-change" in detect_triggers(added, "src/config.ts")


def test_detects_cli_flag_as_breaking_change():
    added = "    parser.add_argument('--retries', type=int)\n"
    assert "breaking-change" in detect_triggers(added, "cli.py")


def test_plain_exported_const_is_not_breaking_change():
    added = "export const greet = (n: string) => `hi ${n}`\n"
    assert "breaking-change" not in detect_triggers(added, "src/util.ts")


def test_detects_sql_delete_as_blast_radius():
    added = "DELETE FROM sessions WHERE expired = true;\n"
    assert "blast-radius" in detect_triggers(added, "app/cleanup.py")


def test_detects_rm_rf_as_blast_radius():
    added = "rm -rf ./build\n"
    assert "blast-radius" in detect_triggers(added, "scripts/clean.sh")


def test_detects_truncate_as_blast_radius():
    added = "TRUNCATE TABLE audit_log;\n"
    assert "blast-radius" in detect_triggers(added, "app/reset.py")


def test_detects_migration_path_as_blast_radius():
    added = "CREATE INDEX idx_email ON users (email);\n"
    assert "blast-radius" in detect_triggers(added, "db/migrations/004_idx.sql")


def test_detects_retry_as_blast_radius():
    added = "for attempt in range(retries):\n    do_charge()\n"
    assert "blast-radius" in detect_triggers(added, "app/billing.py")


def test_plain_select_is_not_blast_radius():
    added = "rows = db.query('SELECT * FROM users')\n"
    assert "blast-radius" not in detect_triggers(added, "app/queries.py")


def test_detects_file_open_as_failure_path():
    added = "f = open(path)\n"
    assert "failure-path" in detect_triggers(added, "app/io.py")


def test_detects_network_call_as_failure_path():
    added = "resp = requests.get(url)\n"
    assert "failure-path" in detect_triggers(added, "app/client.py")


def test_detects_json_parse_as_failure_path():
    added = "data = JSON.parse(body)\n"
    assert "failure-path" in detect_triggers(added, "src/api.ts")


def test_detects_except_block_as_failure_path():
    added = "try:\n    risky()\nexcept ValueError:\n    handle()\n"
    assert "failure-path" in detect_triggers(added, "app/svc.py")


def test_plain_print_is_not_failure_path():
    added = "print('hello world this is fine')\n"
    assert "failure-path" not in detect_triggers(added, "app/cli.py")


def test_non_code_file_is_trivial():
    assert is_trivial("# My Project\n\nDocs mentioning a for loop and an import.\n", "README.md")


def test_lockfile_is_trivial():
    assert is_trivial('    "left-pad": "^1.3.0",\n', "package-lock.json")


def test_whitespace_only_change_is_trivial():
    assert is_trivial("\n   \n\t\n", "app/core.py")


def test_comment_only_change_is_trivial():
    assert is_trivial("# explain the tradeoff here\n# part two of the note\n", "app/core.py")


def test_tiny_cosmetic_edit_is_trivial():
    assert is_trivial(")\n", "app/core.py")


def test_substantial_code_change_is_not_trivial():
    added = "def charge(user):\n    total = sum(i.price for i in user.cart)\n    return total\n"
    assert not is_trivial(added, "app/billing.py")


def test_manifest_dependency_change_is_not_trivial():
    added = '    "left-pad": "^1.3.0",\n'
    assert not is_trivial(added, "package.json")


def test_new_class_is_structural():
    assert is_structural("class PaymentGateway:\n    pass\n")


def test_exported_interface_is_structural():
    assert is_structural("export interface Config {\n  port: number\n}\n")


def test_create_table_is_structural():
    assert is_structural("CREATE TABLE invoices (id serial primary key);\n")


def test_plain_function_is_not_structural():
    assert not is_structural("def add(a, b):\n    return a + b\n")
