#!/usr/bin/env python

import sys
import os

import lib.utils as utils
import lib.ceph_utils as ceph
import lib.cluster_utils as cluster

from charmhelpers.contrib.peerstorage import (
    peer_echo,
)

# CEPH
SERVICE_NAME = os.getenv('JUJU_UNIT_NAME').split('/')[0]

UNIT_ID = os.getenv('JUJU_UNIT_NAME').split('/')[1]
POOL_NAME = SERVICE_NAME

def ceph_joined():
    utils.juju_log('INFO', 'Start Ceph Relation Joined')
    ceph.install()
    utils.juju_log('INFO', 'Finish Ceph Relation Joined')


def ceph_changed():
    utils.juju_log('INFO', 'Start Ceph Relation Changed')
    auth = utils.relation_get('auth')
    key = utils.relation_get('key')
    use_syslog = utils.relation_get('use_syslog')
    if None in [auth, key]:
        utils.juju_log('INFO', 'Missing key or auth in relation')
        return

    ceph.configure(service=SERVICE_NAME, key=key, auth=auth,
                   use_syslog=use_syslog)

      sizemb = int(utils.config_get('block-size')) * 1024
      rbd_img = utils.config_get('rbd-name')
      blk_device = '/dev/rbd/%s/%s%s' % (POOL_NAME, rbd_img, UNIT_ID)
      rbd_pool_rep_count = utils.config_get('ceph-osd-replication-count')
      ceph.ensure_ceph_storage(service=SERVICE_NAME, pool=POOL_NAME,
                               rbd_img=rbd_img, sizemb=sizemb,
                               fstype='ext4', blk_device=blk_device,
                               system_services=['mysql'],
                               rbd_pool_replicas=rbd_pool_rep_count)

    # If 'ha' relation has been made before the 'ceph' relation
    # it is important to make sure the ha-relation data is being
    # sent.
    if utils.is_relation_made('ha'):
        utils.juju_log('INFO',
                       '*ha* relation exists. Making sure the ha'
                       ' relation data is sent.')
        ha_relation_joined()
        return

    utils.juju_log('INFO', 'Finish Ceph Relation Changed')

hooks = {
    "ceph-relation-joined": ceph_joined,
    "ceph-relation-changed": ceph_changed,
}

utils.do_hooks(hooks)