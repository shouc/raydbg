import abc
import importlib
import multiprocessing
import pprint
import sys
import time
from collections import defaultdict
from typing import Optional, List

import ray
import inspect
import itertools

from .utils import SourceCode


class Context:
    def __init__(self):
        self.known_source_code = {}
        self.execution_trace = []
        self.object_to_metadata = {}
        self.atomic_counter = itertools.count()
        self.time_cost = {}

    def to_result(self) -> dict:
        return {
            "known_source_code": self.known_source_code,
            "execution_trace": self.execution_trace,
            "object_to_metadata": self.object_to_metadata,
            "time_cost": self.time_cost,
        }

    def get_idx_execution(self, idx: int) -> Optional[dict]:
        ret = [
            x for x in self.execution_trace if x["idx"] == idx
        ]
        if len(ret) == 0:
            return None
        return ret[0]


original_ray_get = ray.get
original_ray_put = ray.put


@ray.remote
class ReportActor:
    def __init__(self, context: Context):
        self.context = context

    def gen_id(self) -> int:
        return next(self.context.atomic_counter)

    def add_trace(self,
                  idx: int,
                  source_code: SourceCode,
                  function_name: str,
                  ret: str,
                  args_info: List[dict],
                  slug: str):
        self.context.execution_trace.append({
            "type": "remote",
            "function": function_name,
            "args": args_info,
            "idx": idx,
            "slug": slug,
            "returns": ret,
        })
        self.add_object_ref(ret, {
            "type": "remote",
            "source": idx,
        })
        self.add_source_code(function_name, source_code)

    def add_get(self, arg: str, size: int, object_id: int):
        self.context.execution_trace.append({
            "type": "get",
            "target": arg,
            "idx": next(self.context.atomic_counter),
            "ret_size": size,
            "object_id": object_id,
        })

    def add_set(self, name: str, set_size: int, object_ref: str):
        idx = next(self.context.atomic_counter)
        self.context.execution_trace.append({
            "type": "set",
            "name": name,
            "idx": idx,
            "set_size": set_size,
        })
        self.add_object_ref(object_ref, {
            "type": "set",
            "name": name,
            "idx": idx
        })

    def report_time_cost(self, idx: int, time_cost: float) -> None:
        self.context.time_cost[idx] = time_cost

    def add_source_code(self, key: str, source_code: SourceCode) -> None:
        self.context.known_source_code[key] = source_code

    def add_object_ref(self, object_ref: str, metadata: dict) -> None:
        self.context.object_to_metadata[object_ref] = metadata

    def get_context(self) -> Context:
        return self.context


def func_wrapper(_func, _idx, reporter):
    def _wrapper(*_args, **_kwargs):
        print(_idx)
        start_time = time.time()
        func_ret = _func(*_args, **_kwargs)
        end_time = time.time()
        ray.wait([
            reporter.report_time_cost.remote(_idx, end_time - start_time)
        ])
        return func_ret
    return _wrapper


def cap(text, max_length=100):
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def remote_decorator(func, reporter):
    def wrapper(*args, **kwargs):
        function_to_execute = args[0]._function
        idx_ref = reporter.gen_id.remote()
        idx = ray.get(idx_ref)
        function_ref = str(function_to_execute)
        ret = func(*args, **kwargs)
        start_time = time.time()
        ray.wait([ret])
        end_time = time.time()

        args_info = []
        slug = ""
        for _args in kwargs["args"]:
            slug += cap(str(_args)) + ","
            args_info.append({
                "type": "args",
                "object_id": id(_args),
                "size": sys.getsizeof(_args),
                "is_ray_object": isinstance(_args, ray.ObjectRef),
                "slug": cap(str(_args)),
                "nth": len(args_info),
                "ray_object": str(_args) if isinstance(_args, ray.ObjectRef) else None,
            })

        for (_key, _arg) in kwargs["kwargs"]:
            slug += cap(str(_key)) + "=" + cap(str(_arg)) + ","
            args_info.append({
                "type": "kwargs",
                "object_id": id(_arg),
                "size": sys.getsizeof(_arg),
                "is_ray_object": isinstance(_arg, ray.ObjectRef),
                "ray_object": str(_arg) if isinstance(_arg, ray.ObjectRef) else None,
                "slug": cap(str(_key) + "=" + str(_arg)),
                "nth": _key,
                "key": _key,
            })
        if len(slug) > 0:
            slug = slug[:-1]

        ray.wait([
            reporter.add_trace.remote(
                idx,
                SourceCode.from_object(function_to_execute),
                function_ref,
                str(ret),
                args_info,
                slug
            ),
            reporter.report_time_cost.remote(idx, end_time - start_time)
        ])
        return ret

    return wrapper


def get_decorator(func, reporter):
    def wrapper(*args, **kwargs):
        ret = func(*args, **kwargs)
        ray.wait([
            reporter.add_get.remote(str(args[0]), sys.getsizeof(ret), id(ret))
        ])
        return ret
    return wrapper


def set_decorator(func, reporter):
    def wrapper(*args, **kwargs):
        ret = func(*args, **kwargs)
        ray.wait([
            reporter.add_set.remote(args[0], sys.getsizeof(args[1]), str(ret))
        ])
        return ret

    return wrapper


def analyze(file, argv=None):
    if argv:
        sys.argv = argv
    reporter = ReportActor.remote(Context())
    ray.get = get_decorator(ray.get, reporter)
    ray.put = set_decorator(ray.put, reporter)
    ray.remote_function.RemoteFunction._remote = remote_decorator(
        ray.remote_function.RemoteFunction._remote,
        reporter
    )

    exec_file = importlib.machinery.SourceFileLoader("content", file).load_module()
    exec_file.ray = ray
    context = original_ray_get(reporter.get_context.remote())

    return [
        (LoopAnalysis, LoopAnalysis().analyze(context)),
        (OverParallelAnalysis, OverParallelAnalysis().analyze(context)),
        (PassingAnalysis, PassingAnalysis().analyze(context)),
    ]


def analyze_pretty(file, argv=None):
    ret = analyze(file, argv)
    for (analysis, results) in ret:
        texts = set()
        if len(results) == 0:
            continue
        print(f"\033[92m> {analysis.DESCRIPTION}")
        print(f"> {analysis.DOCS}\033[0m")
        for result in results:
            texts.add(result[1] + ": " + result[0].format())
        for text in texts:
            print("\033[91m" + text + "\033[0m")


class AnalysisPass(abc.ABC):
    TITLE = ""
    DESCRIPTION = ""
    DOCS = ""

    def analyze(self, context: Context):
        raise NotImplementedError()


class OverParallelAnalysis(AnalysisPass):
    TITLE = "Over-Parallelization"
    DESCRIPTION = "Over-parallelizing with too fine-grained tasks harms speedup"
    DOCS = "https://docs.ray.io/en/latest/ray-core/patterns/too-fine-grained-tasks.html"

    def analyze(self, context: Context):
        results = set()
        for (execution_idx, time_taken) in context.time_cost.items():
            if time_taken < 0.1:
                execution = context.get_idx_execution(execution_idx)
                if execution is None or execution["type"] != "remote":
                    continue
                source_code = context.known_source_code.get(execution["function"])
                if source_code is None:
                    continue

                function_name = execution["function"]
                slug = execution["slug"]
                function_call_str = f"{function_name}({slug})"

                results.add((source_code, f"Calling {function_call_str} only takes {time_taken}s"))
        return list(results)


class LoopAnalysis(AnalysisPass):
    TITLE = "Sequential-Execution"
    DESCRIPTION = "Calling ray.get in a loop harms parallelism"
    DOCS = "https://docs.ray.io/en/latest/ray-core/patterns/ray-get-loop.html"

    def analyze(self, context: Context):
        results = set()
        call_then_get_occurs = defaultdict(int)

        for nth, execution in enumerate(context.execution_trace):
            if nth >= len(context.execution_trace) - 1:
                continue
            if execution["type"] != "remote":
                continue
            if context.execution_trace[nth + 1]["type"] != "get":
                continue
            call_then_get_occurs[execution["function"]] += 1

        for function, count in call_then_get_occurs.items():
            if count > 2:
                source_code = context.known_source_code.get(function)
                if source_code is None:
                    continue
                results.add((source_code, f"Calling {function} and ray.get in a loop"))
        return list(results)


class PassingAnalysis(AnalysisPass):
    TITLE = "Remote-Pass"
    DESCRIPTION = "Passing the same large argument by value repeatedly harms performance"
    DOCS = "https://docs.ray.io/en/latest/ray-core/patterns/pass-large-arg-by-value.html"

    def analyze(self, context: Context):
        results = set()
        occurences = defaultdict(int)

        for execution in context.execution_trace:
            if execution["type"] != "remote":
                continue
            for (kth, arg) in enumerate(execution["args"]):
                if arg["is_ray_object"]:
                    continue
                if arg["size"] > 10000:  # 10KB
                    occurences[arg["object_id"]] += 1

            for execution in context.execution_trace:
                if execution["type"] != "remote":
                    continue
                for (kth, arg) in enumerate(execution["args"]):
                    if arg["is_ray_object"] or occurences[arg["object_id"]] < 2:
                        continue
                    source_code = context.known_source_code.get(execution["function"])
                    if source_code is None:
                        continue
                    results.add((
                        source_code,
                        f"Passing very large argument {arg['nth']}: {arg['slug']} by value in {execution['function']}")
                    )
        return list(results)


if __name__ == "__main__":
    analyze_pretty(sys.argv[1])
