"""TailScale Provisioner
The current kubernetes provisioner can only manage a single cluster.
The semantics of launching multiple clusters becomes tricky under the 
current implementation since there's no way to distinguish clusters/jobs
launched on one cluster before switching kube-contexts

The approach with the TailScale Provisioner is that we:
    - Maintain a set of k8s clusters that we can access via the tailnet.
    - Critically, the node launching clusters/jobs needs to be located within
      the tailnet. 
    - This allows us to list what clusters are available and most
      importantly are up. 
    - Executing commands on the given cluster is as simple
      as setting the kubeconfig to pointing the desired cluster within the
      tailnet. 
    - Each cluster can be treated as a different "region/zone" within
      the TailScale cloud. 
    - The tags for each cluster will hold metadata around
      the gpu type in the cluster, and (optionally) which user owns it.
    - Clusters that depend on autoscaling will just have a couple of low cost
      CPU VMs to keep the cluster up without breaking the bank.
"""

import subprocess
import typing
from typing import Dict, List, Optional, Tuple

from sky import clouds
from sky import sky_logging
from sky.clouds.kubernetes import Kubernetes
from sky.utils import resources_utils

if typing.TYPE_CHECKING:
    # Renaming to avoid shadowing variables.
    from sky import resources as resources_lib

logger = sky_logging.init_logger(__name__)

@clouds.CLOUD_REGISTRY.register
class TailScale(Kubernetes):
    """TailScale k8s Provisioner"""

    _REPR = 'TailScale'
    _regions: List[clouds.Region] = []

    @classmethod
    def check_credentials(cls) -> Tuple[bool, Optional[str]]:
      """Checks for access to tailnet and existence of k8s clusters.
      Any detected clusters are added to the tailnet

      Returns:
        Tuple[bool, Optional[str]]: _description_
      """
      try:
        subprocess.check_output(
          "tailscale status --json",
          shell=True
        )
      except subprocess.CalledProcessError as e:
        return False, f"`tailscale status --json` failed. Check if tailscale CLI is installed: {str(e)}"
      except Exception as e:
         return False, str(e)

      return True, None
         
      