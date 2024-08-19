"""TailScale cluster provisioning."""
import copy
import time
from typing import Any, Dict, Optional

from sky import exceptions
from sky import sky_logging
from sky import status_lib
from sky.adaptors import kubernetes
from sky.provision import common
from sky.provision.kubernetes import config as config_lib
from sky.provision.kubernetes import network_utils
from sky.provision.kubernetes import utils as kubernetes_utils
import sky.provision.kubernetes.instance as instance_utils
from sky.utils import common_utils
from sky.utils import kubernetes_enums
from sky.utils import subprocess_utils
from sky.utils import ux_utils

logger = sky_logging.init_logger(__name__)
TAG_RAY_CLUSTER_NAME = 'ray-cluster-name'
TAG_SKYPILOT_CLUSTER_NAME = 'skypilot-cluster-name'
TAG_POD_INITIALIZED = 'skypilot-initialized'

