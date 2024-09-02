"""DigitalOcean API client wrapper for SkyPilot.

Example usage of `pydo` client library was mostly taken from here:
https://github.com/digitalocean/pydo/blob/main/examples/poc_droplets_volumes_sshkeys.py
"""

import os
import time
from typing import Any, Dict, List, Optional
import urllib
import uuid

from azure.core.exceptions import HttpResponseError
import pydo

from sky import sky_logging
from sky.provision import common
from sky.provision.do import constants
from sky.utils import common_utils

logger = sky_logging.init_logger(__name__)

POSSIBLE_CREDENTIALS_PATHS = [
    os.path.expanduser(
        '~/Library/Application Support/doctl/config.yaml'),  # OS X
    os.path.expanduser(
        os.path.join(os.getenv('XDG_CONFIG_HOME', '~/.config/'),
                     'doctl/config.yaml')),  # Linux
]
INITIAL_BACKOFF_SECONDS = 10
MAX_BACKOFF_FACTOR = 10
MAX_ATTEMPTS = 6
SSH_KEY_NAME = f'sky-key-{common_utils.get_user_hash()}'
IMAGE = 'ubuntu-22-04-x64'

CREDENTIALS_PATH = '~/.config/doctl/config.yaml'
_client = None
_ssh_key_id = None


class DigitalOceanError(Exception):
    pass


def _init_client():
    global _client, CREDENTIALS_PATH
    if _client is None:
        CREDENTIALS_PATH = None
        for path in POSSIBLE_CREDENTIALS_PATHS:
            if os.path.exists(path):
                CREDENTIALS_PATH = path
        if CREDENTIALS_PATH is None:
            raise DigitalOceanError(
                'no credentials file found from '
                f'the following paths {POSSIBLE_CREDENTIALS_PATHS}')

        try:
            api_token = common_utils.read_yaml(
                CREDENTIALS_PATH)['auth-contexts']['skypilot']
        except KeyError as e:
            raise KeyError('No valid token found for skypilot.'
                           'Try setting your auth token'
                           'to the skypilot context,'
                           '`doctl auth init --context skypilot`') from e

        _client = pydo.Client(token=api_token)
    return _client


def client():
    global _client
    if _client is None:
        _client = _init_client()
    return _client


def ssh_key_id():
    global _ssh_key_id
    if _ssh_key_id is None:
        page = 1
        paginated = True
        while paginated:
            try:
                resp = client().ssh_keys.list(per_page=50, page=page)
                for ssh_key in resp['ssh_keys']:
                    if ssh_key['name'] == SSH_KEY_NAME:
                        _ssh_key_id = ssh_key
                        return _ssh_key_id
            except HttpResponseError as err:
                raise DigitalOceanError('Error: {0} {1}: {2}'.format(
                    err.status_code, err.reason, err.error.message)) from err

            pages = resp.links.pages
            if 'next' in pages.keys():
                parsed_url = urllib.parse.urlparse(pages['next'])
                page = urllib.parse.parse_qs(parsed_url.query)['page'][0]
            else:
                paginated = False
    return _ssh_key_id


def _wait_for_action(action_id: str, wait: int = constants.POLL_INTERVAL):
    """Waits for action to complete before throwing an error.

    Args:
        action_id (str): action id
        wait (int, optional): wait time before polling status of action
    """
    status = 'in-progress'
    while status == 'in-progress':
        try:
            resp = client().actions.get(action_id)
        except HttpResponseError as err:
            raise DigitalOceanError('Error: {0} {1}: {2}'.format(
                err.status_code, err.reason, err.error.message)) from err
        else:
            status = resp['action']['status']
            if status == 'in-progress':
                time.sleep(wait)
            elif status == 'errored':
                raise Exception('{0} action {1} {2}'.format(
                    resp['action']['type'], resp['action']['id'], status))


def _create_volume(request: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = client().volumes.create(body=request)
        volume = resp['volume']
    except HttpResponseError as err:
        raise DigitalOceanError('Error: {0} {1}: {2}'.format(
            err.status_code, err.reason, err.error.message)) from err
    else:
        return volume


def _create_droplet(request: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = client().droplets.create(body=request)
        droplet_id = resp['droplet']['id']
        _wait_for_action(resp['links']['actions'][0]['id'])

        get_resp = client().droplets.get(droplet_id)
        droplet = get_resp['droplet']
    except HttpResponseError as err:
        raise DigitalOceanError('Error: {0} {1}: {2}'.format(
            err.status_code, err.reason, err.error.message)) from err
    return droplet


def create_instance(region: str, cluster_name_on_cloud: str, instance_type: str,
                    config: common.ProvisionConfig) -> Dict[str, Any]:
    """Creates a instance and mounts the requested block storage

    Args:
        region (str): instance region
        instance_name (str): name of instance
        config (common.ProvisionConfig): provisioner configuration

    Returns:
        Dict[str, Any]: instance metadata
    """
    instance_name = (f'{cluster_name_on_cloud}-'
                     f'{uuid.uuid4().hex[:4]}-{instance_type}')
    instance_request = {
        'name': instance_name,
        'region': region,
        'size': config.node_config['InstanceType'],
        'image': IMAGE,
        'ssh_keys': [ssh_key_id()['fingerprint']],
        'tags': ['skypilot', cluster_name_on_cloud]
    }
    instance = _create_droplet(instance_request)

    volume_request = {
        'size_gigabytes': config.node_config['DiskSize'],
        'name': instance_name,
        'region': region,
        'filesystem_type': 'ext4',
    }
    volume = _create_volume(volume_request)

    attach_request = {'type': 'attach', 'droplet_id': instance['id']}
    try:
        action_response = client().volume_actions.post_by_id(
            volume['id'], attach_request)
        _wait_for_action(action_response['action']['id'])
    except HttpResponseError as err:
        raise DigitalOceanError('Error: {0} {1}: {2}'.format(
            err.status_code, err.reason, err.error.message)) from err
    logger.debug(f'{instance_name} created')
    return instance


def filter_instances(
        cluster_name_on_cloud: str,
        status_filters: Optional[List[str]] = None) -> Dict[str, Any]:
    """Returns Dict mapping instance name
    to instance metadata filtered by status
    """

    filtered_instances: Dict[str, Any] = {}
    page = 1
    paginated = True
    while paginated:
        try:
            resp = client().droplets.list(tag_name=cluster_name_on_cloud,
                                          per_page=50,
                                          page=page)
            for instance in resp['droplets']:
                if status_filters is None or instance[
                        'status'] in status_filters:
                    filtered_instances[instance['name']] = instance
        except HttpResponseError as err:
            DigitalOceanError('Error: {0} {1}: {2}'.format(
                err.status_code, err.reason, err.error.message))

        pages = resp.links.pages
        if 'next' in pages.keys():
            parsed_url = urllib.parse.urlparse(pages['next'])
            page = int(urllib.parse.parse_qs(parsed_url.query)['page'][0])
        else:
            paginated = False
    return filtered_instances
