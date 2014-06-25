import fabric
from .check import check_cluster, test
from .deploy import deploy, switch, copy, shell
from .modules import make_tag, check_versions


__all__ = [
        k for k,v in globals().items()
        if not k.startswith('_')
        and isinstance(v, fabric.tasks.WrappedCallableTask)
        ]

