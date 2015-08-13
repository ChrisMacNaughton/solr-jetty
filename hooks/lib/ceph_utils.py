#
# Copyright 2012 Canonical Ltd.
#
# This file is sourced from lp:charms/trusty/mysql
#
# Authors:
#  James Page <james.page@ubuntu.com>
#  Adam Gandelman <adamg@ubuntu.com>
#  Chris MacNaughton <chris@macnaughton.email>
#

import commands
import json
import subprocess
import os
import shutil
import time
import lib.utils as utils


KEYRING = '/etc/ceph/ceph.client.%s.keyring'
KEYFILE = '/etc/ceph/ceph.client.%s.key'

CEPH_CONF = """[global]
 auth supported = %(auth)s
 keyring = %(keyring)s
 mon host = %(mon_hosts)s
 log to syslog = %(use_syslog)s
 err to syslog = %(use_syslog)s
 clog to syslog = %(use_syslog)s
"""


def execute(cmd):
    subprocess.check_call(cmd)


def execute_shell(cmd):
    subprocess.check_call(cmd, shell=True)


def install():
    ceph_dir = "/etc/ceph"
    if not os.path.isdir(ceph_dir):
        os.mkdir(ceph_dir)
    utils.install('ceph-common')


def rbd_exists(service, pool, rbd_img):
    (rc, out) = commands.getstatusoutput('rbd list --id %s --pool %s' %
                                         (service, pool))
    return rbd_img in out


def create_rbd_image(service, pool, image, sizemb):
    cmd = [
        'rbd',
        'create',
        image,
        '--size',
        str(sizemb),
        '--id',
        service,
        '--pool',
        pool]
    execute(cmd)


def pool_exists(service, name):
    (rc, out) = commands.getstatusoutput("rados --id %s lspools" % service)
    return name in out


def ceph_version():
    ''' Retrieve the local version of ceph '''
    if os.path.exists('/usr/bin/ceph'):
        cmd = ['ceph', '-v']
        output = subprocess.check_output(cmd)
        output = output.split()
        if len(output) > 3:
            return output[2]
        else:
            return None
    else:
        return None


def get_osds(service):
    '''
    Return a list of all Ceph Object Storage Daemons
    currently in the cluster
    '''
    version = ceph_version()
    if version and version >= '0.56':
        cmd = ['ceph', '--id', service, 'osd', 'ls', '--format=json']
        return json.loads(subprocess.check_output(cmd))
    else:
        return None


def create_pool(service, name, replicas=2):
    ''' Create a new RADOS pool '''
    if pool_exists(service, name):
        utils.juju_log('WARNING',
                       "Ceph pool {} already exists, "
                       "skipping creation".format(name))
        return

    osds = get_osds(service)
    if osds:
        pgnum = (len(osds) * 100 / replicas)
    else:
        # NOTE(james-page): Default to 200 for older ceph versions
        # which don't support OSD query from cli
        pgnum = 200

    cmd = [
        'ceph', '--id', service,
        'osd', 'pool', 'create',
        name, str(pgnum)
    ]
    subprocess.check_call(cmd)
    cmd = [
        'ceph', '--id', service,
        'osd', 'pool', 'set', name,
        'size', str(replicas)
    ]
    subprocess.check_call(cmd)


def keyfile_path(service):
    return KEYFILE % service


def keyring_path(service):
    return KEYRING % service


def create_keyring(service, key):
    keyring = keyring_path(service)
    if os.path.exists(keyring):
        utils.juju_log('INFO', 'ceph: Keyring exists at %s.' % keyring)
    cmd = [
        'ceph-authtool',
        keyring,
        '--create-keyring',
        '--name=client.%s' % service,
        '--add-key=%s' % key]
    execute(cmd)
    utils.juju_log('INFO', 'ceph: Created new ring at %s.' % keyring)


def create_key_file(service, key):
    # create a file containing the key
    keyfile = keyfile_path(service)
    if os.path.exists(keyfile):
        utils.juju_log('INFO', 'ceph: Keyfile exists at %s.' % keyfile)
    fd = open(keyfile, 'w')
    fd.write(key)
    fd.close()
    utils.juju_log('INFO', 'ceph: Created new keyfile at %s.' % keyfile)


def get_ceph_nodes():
    hosts = []
    for r_id in utils.relation_ids('ceph'):
        for unit in utils.relation_list(r_id):
            ceph_addr = \
                utils.relation_get('ceph-public-address', rid=r_id,
                                   unit=unit) or \
                utils.relation_get('private-address', rid=r_id, unit=unit)
            hosts.append(ceph_addr)

    return hosts


def configure(service, key, auth, use_syslog):
    create_keyring(service, key)
    create_key_file(service, key)
    hosts = get_ceph_nodes()
    mon_hosts = ",".join(map(str, hosts))
    keyring = keyring_path(service)
    with open('/etc/ceph/ceph.conf', 'w') as ceph_conf:
        ceph_conf.write(CEPH_CONF % locals())
    modprobe_kernel_module('rbd')


def image_mapped(image_name):
    (rc, out) = commands.getstatusoutput('rbd showmapped')
    return image_name in out


def map_block_storage(service, pool, image):
    cmd = [
        'rbd',
        'map',
        '%s/%s' % (pool, image),
        '--user',
        service,
        '--secret',
        keyfile_path(service)]
    execute(cmd)


# TODO: re-use
def modprobe_kernel_module(module):
    utils.juju_log('INFO', 'Loading kernel module')
    cmd = ['modprobe', module]
    execute(cmd)
    cmd = 'echo %s >> /etc/modules' % module
    execute_shell(cmd)


def filesystem_mounted(fs):
    return subprocess.call(['grep', '-wqs', fs, '/proc/mounts']) == 0


def make_filesystem(blk_device, fstype='ext4'):
    utils.juju_log('INFO',
                   'ceph: Formatting block device %s as filesystem %s.' %\
                   (blk_device, fstype))
    cmd = ['mkfs', '-t', fstype, blk_device]
    execute(cmd)

def ensure_ceph_storage(service, pool, rbd_img, sizemb, mount_point,
                        blk_device, fstype, system_services=[],
                        rbd_pool_replicas=2):
    """
    Ensures given pool and RBD image exists, is mapped to a block device,
    and the device is formatted.
    """
    # Ensure pool, RBD image, RBD mappings are in place.
    if not pool_exists(service, pool):
        utils.juju_log('INFO', 'ceph: Creating new pool %s.' % pool)
        create_pool(service, pool, replicas=rbd_pool_replicas)

    if not rbd_exists(service, pool, rbd_img):
        utils.juju_log('INFO', 'ceph: Creating RBD image (%s).' % rbd_img)
        create_rbd_image(service, pool, rbd_img, sizemb)

    if not image_mapped(rbd_img):
        utils.juju_log('INFO', 'ceph: Mapping RBD Image as a Block Device.')
        map_block_storage(service, pool, rbd_img)
    if not filesystem_mounted(mount_point):
        make_filesystem(blk_device, fstype)
