import contextlib
import json
import subprocess
from typing import Any, Dict, List

from sky.adaptors import kubernetes
from sky.provision.kubernetes import utils as kubernetes_utils

# Hack to force client to be reloaded. Should probably live elsewhere
def _reset_config() -> None:
    kubernetes._configured = False
    kubernetes._core_api = None
    kubernetes._auth_api = None
    kubernetes._networking_api = None
    kubernetes._custom_objects_api = None
    kubernetes._node_api = None
    kubernetes._apps_api = None
    kubernetes._api_client = None


def switch_tailscale_config(cluster_name: str) -> None:
    """configures kubecontext to point to new tailscale kube API proxy

    Args:
        cluster_name (str): name of k8s cluster as named within tailscale
    """

    subprocess.check_output(
        f'tailscale configure kubeconfig {cluster_name}',
        shell=True
    )
    

@contextlib.contextmanager
def set_tailscale_context(cluster_name: str) -> None:
    """Context manager for running switching tailnet configs and then switching back.
    Upon switching back, no validation is done to check if the old context was valid.

    Args:
        cluster_name (str): name of k8s cluster as named within tailscale
    """
    _reset_config()
    original_context = kubernetes_utils.get_current_kube_config_context_name()
    switch_tailscale_config(cluster_name)
    try:
        yield
    finally:
        if original_context is not None:
            subprocess.check_output(
                f'kubectl config use-context {original_context}',
                shell=True
            )


def list_active_clusters(only_online: bool = True) -> Dict[str, Any]:
    """Lists available tailscale clusters as well 
    Args:
        only_active (bool): name of k8s cluster as named within tailscale

    Returns:
        List[str]: _description_
    """
    devices: Dict[str, Any] = json.loads(subprocess.check_output(
        'tailscale status --json',
        shell=True
    ))

    available_clusters: Dict[str, Any] = {}
    
    for device in devices['Peer'].values():
        if 'tag:k8s-operator' in device.get('Tags', []) and (device['Online'] or not only_online):
            short_domain = device['DNSName'].split('.')[0]
            with set_tailscale_context(short_domain):
                is_connected, _ = kubernetes_utils.check_credentials()
                if is_connected:
                    available_clusters[short_domain] = device
    
    return available_clusters
