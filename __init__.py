import fabric
from .check import check_cluster, test
from .deploy import update, deploy, switch, copy
from .modules import prepare_release

__all__ = [
        k for k,v in globals().items()
        if not k.startswith('_')
        and isinstance(v, fabric.tasks.WrappedCallableTask)
        ]

