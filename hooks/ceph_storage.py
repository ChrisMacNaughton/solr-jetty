#!/usr/bin/env python

import sys
import os

import lib.utils as utils
import lib.ceph_utils as ceph
import lib.mount_volume as mount
from lib.charmhelpers.core import host
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
    blk_device = '/dev/rbd/%s/%s' % (POOL_NAME, rbd_img)
    rbd_pool_rep_count = utils.config_get('ceph-osd-replication-count')
    ceph.ensure_ceph_storage(service=SERVICE_NAME, pool=POOL_NAME,
                             rbd_img=rbd_img, sizemb=sizemb,
                             fstype='ext4', mount_point='/srv/juju/volumes/' + SERVICE_NAME + '-' + UNIT_ID,
                             blk_device=blk_device,
                             system_services=['mysql'],
                             rbd_pool_replicas=rbd_pool_rep_count)

    mount.mount()
    host.service_start('jetty')
    utils.juju_log('INFO', 'Finish Ceph Relation Changed')

hooks = {
    "ceph-relation-joined": ceph_joined,
    "ceph-relation-changed": ceph_changed,
}

utils.do_hooks(hooks)