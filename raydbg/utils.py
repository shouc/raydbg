import inspect
import pathlib

LIB_DIR = pathlib.Path(__file__).parent.resolve()


class SourceCode:
    def __init__(self, line, file, source):
        self.line = line
        self.file = file
        self.source = source

    @staticmethod
    def from_object(object):
        return SourceCode(
            inspect.getsourcelines(object)[1],
            inspect.getsourcefile(object),
            inspect.getsource(object),
        )

    @staticmethod
    def from_uri(codeql_uri):
        file_name = ":".join(codeql_uri["uri"].split(":")[1:])
        start_line = codeql_uri["startLine"]
        end_line = codeql_uri["endLine"]

        with open(file_name) as file:
            lines = file.readlines()
            source = "".join(lines[start_line - 1:end_line + 10])

        return SourceCode(
            start_line,
            file_name,
            source,
        )

    def __hash__(self):
        return hash((self.line, self.file, self.source))

    def __eq__(self, other):
        return (
            self.line == other.line
            and self.file == other.file
            and self.source == other.source
        )

    def format(self):
        return f"{self.file}:{self.line}"
