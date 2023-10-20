import json
import multiprocessing
import os
import pathlib
import shutil

import tqdm
import wget
import sys

from .llm import LLM
from .utils import SourceCode, LIB_DIR

CODEQL_VERSION = "v2.15.1"


def bar_progress(current, total, width=80):
    progress_message = "Downloading: %d%% [%d / %d] MB" % (current / total * 100, current / 1e6, total / 1e6)
    sys.stdout.write("\r" + progress_message)
    sys.stdout.flush()


CODEQL_PATH = ""


def codeql_context(func):
    def wrapped_func(*args, **kwargs):
        cwd = os.getcwd()
        os.chdir(CODEQL_PATH)
        ret = func(*args, **kwargs)
        os.chdir(cwd)
        return ret

    return wrapped_func


class CodeQL:
    def __init__(self):
        self.setup_codeql()

    def setup_codeql(self):
        user_home = os.path.expanduser("~")
        # download codeql
        global CODEQL_PATH
        CODEQL_PATH = user_home + "/codeql-raydbg/codeql"
        if os.path.exists(CODEQL_PATH):
            return
        tmp_file = "/tmp/codeql.tar.gz"
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        print("Downloading CodeQL to", tmp_file)
        system_name = "osx64" if os.uname().sysname == "Darwin" else "linux64"
        url = f"https://github.com/github/codeql-action/releases/download/codeql-bundle-{CODEQL_VERSION}/codeql-bundle-{system_name}.tar.gz"
        wget.download(url, tmp_file, bar=bar_progress)
        print("Downloaded CodeQL:", tmp_file)
        # extract
        os.system(f"mkdir -p ~/codeql-raydbg")
        os.system(f"tar -xvf {tmp_file} -C ~/codeql-raydbg/")

    @codeql_context
    def create_database(self, source_path, force=False):
        db_path = source_path + "/.codeql_db"
        if os.path.exists(db_path) and not force:
            print("Database already exists:", db_path)
            return db_path
        shutil.rmtree(db_path, ignore_errors=True)
        os.system(f"./codeql database create --language python --source-root={source_path} -- {db_path}")
        return db_path

    @codeql_context
    def analyze_database(self, db_path, query_path, force=False):
        output_path = "./result.bqrs"
        try:
            os.remove(output_path)
        except FileNotFoundError:
            pass
        os.system(f"./codeql query run --output={output_path} --database={db_path} -- {query_path}")
        os.system("./codeql bqrs decode --format json --entities=all -o result.json -- ./result.bqrs")
        with open("result.json", "r") as fp:
            result = json.load(fp)
        return result


class StaticAnalysis(CodeQL):
    TITLE = ""
    DESCRIPTION = ""
    DOCS = ""
    QUERY_PATH = ""

    def parse_result(self, outs) -> list:
        print("Parsing result:", outs)
        return []

    def analyze(self, source_path):
        db_path = self.create_database(source_path)
        results = []
        for i in self.QUERY_PATH:
            outs = self.analyze_database(db_path, pathlib.Path.joinpath(LIB_DIR, i))
            results.extend(self.parse_result(outs))
        return results


class RayGlobalVar(StaticAnalysis):
    TITLE = "Ray-Global-Var"
    DESCRIPTION = "Using global variables to share state between tasks and actors. "
    DOCS = "https://docs.ray.io/en/latest/ray-core/patterns/global-variables.html"
    QUERY_PATH = ["queries/ray_global_var1.ql", "queries/ray_global_var2.ql"]
    ADDITIONAL_PROMPT = "Ignoring all global variable reads caused by imports."

    def parse_result(self, outs):
        results = set()
        for i in outs['#select']["tuples"]:
            global_var = i[0]["label"].replace("Global Variable ", "")
            actor = SourceCode.from_uri(i[1]["url"])
            name = i[2]
            slug = f"Global variable {global_var} is used in function {name} to share state between tasks and actors"
            results.add((slug, actor))
        return list(results)


# class RayDefineInLoop(StaticAnalysis):
#     TITLE = "Ray-Define-In-Loop"
#     DESCRIPTION = "Redefining the same remote function or class harms performance"
#     DOCS = "https://docs.ray.io/en/latest/ray-core/patterns/redefine-task-actor-loop.html"
#     QUERY_PATH = "queries/ray_define_in_loop.ql"


class UnnecessaryRayGet(StaticAnalysis):
    TITLE = "Unnecessary-Ray-Get"
    DESCRIPTION = "Calling ray.get unnecessarily harms performance. "
    DOCS = "https://docs.ray.io/en/latest/ray-core/patterns/unnecessary-ray-get.html"
    QUERY_PATH = ["queries/unnecessary_ray_get.ql"]
    ADDITIONAL_PROMPT = ""

    def parse_result(self, outs):
        results = set()
        for i in outs['#select']["tuples"]:
            src1 = SourceCode.from_uri(i[0]["url"])
            src2 = SourceCode.from_uri(i[1]["url"])
            slug = f"Calling ray.get unnecessarily at {src1} harms performance"
            results.add((slug, src1, src2))
        return list(results)


def analyze(source_path):
    return [
        (RayGlobalVar, RayGlobalVar().analyze(source_path)),
        # (RayDefineInLoop, RayDefineInLoop().analyze(source_path)),
        (UnnecessaryRayGet, UnnecessaryRayGet().analyze(source_path)),
    ]


def llm_analysis(source_path, llm):
    PROMPT = "You are a senior engineer at Anyscale debugging following Ray program. " + \
             "Here is an anti-pattern in the code your intern found. Confirm whether they are false positive. " + \
             "If it is a true positive, say 'true'. Say 'false' otherwise. Only reply 'true' or 'false'.\n\n"

    analysis_results = analyze(source_path)
    if llm is None:
        converted = {}
        for analysis, results in analysis_results:
            converted[analysis] = []
            for result in results:
                converted[analysis].append((result, True))
        return converted
    invokes = []
    infos = {}

    for analysis, results in analysis_results:
        for result in results:
            prompt = PROMPT + analysis.DESCRIPTION + analysis.ADDITIONAL_PROMPT + " Specifically, "
            prompt += result[0] + "\n"
            prompt += "\n\n"
            prompt += "```python\n"
            prompt += result[1].source
            prompt += "\n```\n"
            invokes.append(prompt)
            infos[prompt] = (analysis, result)

    print("Invoking LLM...")
    with multiprocessing.Pool(4) as pool:
        responses = list(tqdm.tqdm(pool.imap(llm.query, invokes), total=len(invokes)))

    counter = 0

    llm_results = {}
    for analysis, results in analysis_results:
        llm_results[analysis] = []
        for result in results:
            llm_results[analysis].append((result, "false" in responses[counter].strip()))
            counter += 1
    return llm_results


def llm_analysis_pretty(source, llm):
    ret = llm_analysis(source, llm)
    for analysis, results in ret.items():
        texts = set()
        if len(results) == 0:
            continue
        print(f"\033[92m> {analysis.DESCRIPTION}")
        print(f"> {analysis.DOCS}\033[0m")
        for result, is_true in results:
            text = result[0] + ": " + result[1].format() + (" (Potentially False Positive)" if not is_true else "")
            texts.add((text, is_true))

        for (text, is_true) in texts:
            if is_true:
                print("\033[91m" + text + "\033[0m")

        for (text, is_true) in texts:
            if not is_true:
                print("\033[93m" + text + "\033[0m")


if __name__ == "__main__":
    analysis = UnnecessaryRayGet()
    llm_analysis_pretty(sys.argv[1], LLM(os.environ["OPENAI_KEY"]))
