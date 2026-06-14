"""Disk and data storage optimization for Jekyll & Hyde."""

from safety_eval.storage.optimizer import StorageOptimizer, get_optimizer

__all__ = ["StorageOptimizer", "get_optimizer"]


def build_install_archive(*args, **kwargs):
    from safety_eval.storage.packager import build_install_archive as _build

    return _build(*args, **kwargs)


def release_info():
    from safety_eval.storage.packager import release_info as _info

    return _info()
