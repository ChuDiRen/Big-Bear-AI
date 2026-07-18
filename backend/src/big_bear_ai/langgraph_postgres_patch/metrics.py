from langgraph_api import config
from typing_extensions import TypedDict

from big_bear_ai.langgraph_postgres_patch import queue


class WorkerMetrics(TypedDict):
    max: int
    active: int
    available: int
# noqa  MC8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2VjBad1dRPT06NWJkOTZlOGE=


class Metrics(TypedDict):
    workers: WorkerMetrics
# type: ignore  MS8yOmFIVnBZMlhsdktEbHY1ZnBtNFE2VjBad1dRPT06NWJkOTZlOGE=


def get_metrics() -> Metrics:
    workers_max = config.N_JOBS_PER_WORKER
    workers_active = queue.get_num_workers()
    return Metrics(
        workers=WorkerMetrics(
            max=workers_max,
            active=workers_active,
            available=workers_max - workers_active,
        )
    )
