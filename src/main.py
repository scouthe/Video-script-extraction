import argparse
from pathlib import Path

from .config import get_settings
from .pipeline.run import run_pipeline
from .exporters.word_exporter import export_word
from .exporters.excel_exporter import export_excel
from .exporters.srt_exporter import export_srt
from .collectors.douyin_profile import collect_profile_links
from .utils.file import sanitize_filename


def _read_links_file(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Douyin delivery tool")
    parser.add_argument("--name", required=True, help="Batch name, e.g. 客户A_账号xxx")
    parser.add_argument("--links", help="Path to links.txt (one per line)")
    parser.add_argument("--inputs", nargs="*", help="Links or local file paths")
    parser.add_argument("--uid", help="Douyin UID or profile URL to collect video links")
    parser.add_argument("--count", type=int, default=0, help="Max number of videos to collect")
    parser.add_argument("--platform", choices=["douyin", "bilibili", "auto"], default="auto")
    parser.add_argument(
        "--export",
        nargs="+",
        choices=["docx", "xlsx", "srt"],
        default=["docx", "xlsx"],
    )
    parser.add_argument("--summary", action="store_true", help="Generate summary with LLM")
    parser.add_argument("--no-cache", action="store_true", help="Disable transcript cache")
    parser.add_argument("--output-dir", default="outputs", help="Output root directory")
    parser.add_argument("--tmp-dir", default="tmp", help="Temporary working directory")

    args = parser.parse_args()

    inputs: list[str] = []
    if args.links:
        inputs.extend(_read_links_file(Path(args.links)))
    if args.inputs:
        inputs.extend(args.inputs)
    if args.uid:
        result = collect_profile_links(args.uid, limit=args.count)
        inputs.extend(result.links)

    if not inputs:
        raise SystemExit("No inputs provided. Use --links or --inputs.")

    settings = get_settings()
    output_root = Path(args.output_dir)
    tmp_root = Path(args.tmp_dir)

    output_dir, results = run_pipeline(
        inputs=inputs,
        settings=settings,
        batch_name=args.name,
        output_root=output_root,
        tmp_root=tmp_root,
        enable_summary=args.summary,
        use_cache=not args.no_cache,
        platform=args.platform,
    )

    safe_name = sanitize_filename(args.name) or "delivery"
    if "docx" in args.export:
        export_word(results, output_dir / f"{safe_name}.docx", args.name)
    if "xlsx" in args.export:
        export_excel(results, output_dir / f"{safe_name}.xlsx")
    if "srt" in args.export:
        export_srt(results, output_dir)

    print(f"Done. Output: {output_dir}")


if __name__ == "__main__":
    main()
