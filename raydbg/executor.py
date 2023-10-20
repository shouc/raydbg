import subprocess
import sys

VERBOSE_LEVEL = 1


def execute(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout = ''
    stderr = ''

    while True:
        output = process.stdout.readline()
        if output == '' or process.poll() is not None:
            break
        if output:
            print(output.decode().strip())
            stdout += output.decode()

    rc = process.poll()

    if rc != 0:
        while True:
            output = process.stderr.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                if VERBOSE_LEVEL > 0:
                    print(output.decode().strip())
                stderr += output.decode()

    return rc, stdout, stderr


