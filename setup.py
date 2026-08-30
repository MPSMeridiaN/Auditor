"""Minimal setuptools bridge for deterministic source distributions."""

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.sdist import sdist as _sdist


class SourceDistribution(_sdist):
    """Keep setuptools' generated egg metadata out of the source archive."""

    def make_release_tree(self, base_dir, files):
        filtered = [
            path
            for path in files
            if ".egg-info" not in Path(path).parts
        ]
        super().make_release_tree(base_dir, filtered)
        for metadata in Path(base_dir).rglob("*.egg-info"):
            if metadata.is_dir() and not metadata.is_symlink():
                shutil.rmtree(metadata)
        build_dir = Path(base_dir) / "build"
        if build_dir.is_dir() and not build_dir.is_symlink():
            shutil.rmtree(build_dir)


setup(
    cmdclass={"sdist": SourceDistribution},
)
