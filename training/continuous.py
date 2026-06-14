"""CLI for continuous learning — curate, merge dataset, optional retrain."""

from __future__ import annotations

import argparse

from safety_eval.learning.pipeline import get_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Jekyll & Hyde continuous learning")
    parser.add_argument("--curate-only", action="store_true", help="Curate pending interactions only")
    parser.add_argument("--merge-only", action="store_true", help="Regenerate JSONL dataset")
    parser.add_argument("--train", action="store_true", help="Run incremental LoRA + merge + hot reload")
    args = parser.parse_args()

    pipe = get_pipeline()
    if args.merge_only:
        ok = pipe.maybe_merge_dataset()
        print("Dataset merged:" if ok else "Merge failed", pipe.store.status())
        return

    if args.curate_only:
        from safety_eval.learning.curator import LearningCurator

        n = LearningCurator().curate_pending()
        pipe.maybe_merge_dataset()
        print(f"Curated {n} interactions", pipe.store.status())
        return

    result = pipe.run_now(train=args.train)
    print(result)


if __name__ == "__main__":
    main()
