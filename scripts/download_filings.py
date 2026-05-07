"""Download SEC filings for benchmark companies.

Wrapper around auditchain.utils.sec_client.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from auditchain.core.config import get_settings
from auditchain.core.logging import configure_logging, get_logger
from auditchain.data.known_fraud_cases import get_benchmark_companies
from auditchain.utils.sec_client import SECClient, download_company

logger = get_logger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="*", help="Limit to specific tickers")
    parser.add_argument(
        "--filing-type",
        nargs="*",
        default=["10-K"],
        choices=["10-K", "10-Q", "8-K", "20-F", "40-F"],
    )
    parser.add_argument("--max-filings", type=int, default=5)
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    output_dir = settings.raw_data_dir / "sec_edgar"
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = get_benchmark_companies()
    if args.tickers:
        cases = [c for c in cases if c.ticker in args.tickers]

    logger.info("download_started", companies=len(cases), output=str(output_dir))
    started = time.time()

    async with SECClient(settings.sec_user_agent) as client:
        for case in cases:
            await download_company(
                client=client,
                case=case,
                output_dir=output_dir,
                filing_types=tuple(args.filing_type),
                max_filings=args.max_filings,
            )

    logger.info("download_complete", duration_s=round(time.time() - started, 1))


if __name__ == "__main__":
    asyncio.run(main())
