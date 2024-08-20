"""TailScale provisioner for SkyPilot."""

from sky.provision.kubernetes.config import bootstrap_instances
from sky.provision.kubernetes.instance import get_cluster_info
from sky.provision.kubernetes.instance import get_command_runners
from sky.provision.kubernetes.instance import query_instances
from sky.provision.kubernetes.instance import run_instances
from sky.provision.kubernetes.instance import stop_instances
from sky.provision.kubernetes.instance import terminate_instances
from sky.provision.kubernetes.instance import wait_instances
from sky.provision.kubernetes.network import cleanup_ports
from sky.provision.kubernetes.network import open_ports
from sky.provision.kubernetes.network import query_ports

__all__ = [
    'bootstrap_instances',
    'get_cluster_info',
    'get_command_runners',
    'query_instances',
    'run_instances',
    'stop_instances',
    'terminate_instances',
    'wait_instances',
    'cleanup_ports',
    'open_ports',
    'query_ports',
]