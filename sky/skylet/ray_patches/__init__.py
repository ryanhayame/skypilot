"""Patch files"""
import os
import shutil


def patch() -> None:
    # Patch the buggy ray file. This should only be called
    # from an isolated python process, because once imported
    # the python module would persist in the memory.
    from ray import worker
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'worker.py')
    shutil.copyfile(path, worker.__file__)