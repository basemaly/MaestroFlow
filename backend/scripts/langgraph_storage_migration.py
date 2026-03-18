from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.langgraph.storage_migration import (
    build_migration_report,
    default_backup_dir,
    default_ops_catalog_path,
    load_ops_catalog,
    normalize_for_json,
    resolve_checkpointer_url,
    summarize_catalog,
    summarize_checkpoints,
    write_catalog_backup,
)
from src.langgraph.catalog_store import ThreadCatalogStore


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit and back up LangGraph's split local storage before a runtime migration."
    )
    parser.add_argument(
        "command",
        choices=["audit", "backup", "import-catalog"],
        help="Print an audit report, write a full JSON backup bundle, or import the visible thread catalog into Postgres.",
    )
    parser.add_argument(
        "--ops-path",
        default=str(default_ops_catalog_path()),
        help="Path to the host-mounted .langgraph_ops.pckl file.",
    )
    parser.add_argument(
        "--checkpointer-url",
        default=None,
        help="Postgres URL for the LangGraph checkpointer. Defaults to LANGGRAPH_CHECKPOINTER_URL or the local dev database.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file for audit JSON or the backup bundle.",
    )
    return parser


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()

    ops_path = Path(args.ops_path).expanduser().resolve()
    checkpointer_url = resolve_checkpointer_url(args.checkpointer_url)

    catalog = load_ops_catalog(ops_path, database_uri=checkpointer_url)
    catalog_summary = summarize_catalog(catalog)
    checkpoint_summary = summarize_checkpoints(checkpointer_url)
    report = build_migration_report(catalog_summary, checkpoint_summary)
    report_payload = {
        "ops_path": str(ops_path),
        "checkpointer_url": checkpointer_url,
        "report": report,
    }

    if args.command == "audit":
        rendered = json.dumps(normalize_for_json(report_payload), indent=2, ensure_ascii=True)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        print(rendered)
        return 0

    if args.command == "import-catalog":
        store = ThreadCatalogStore(checkpointer_url, ops_path)
        imported = store.bootstrap_from_ops_catalog()
        print(json.dumps({"imported_threads": imported, "ops_path": str(ops_path)}, indent=2))
        return 0

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = Path(args.output) if args.output else default_backup_dir() / f"catalog-backup-{timestamp}.json"
    destination = write_catalog_backup(
        catalog,
        report=report_payload,
        output_path=output_path,
        source_path=ops_path,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
