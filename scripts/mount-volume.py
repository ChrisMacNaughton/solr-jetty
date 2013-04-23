#!/usr/bin/env python

import sys
import os
from charmsupport import volumes
from charmsupport import hookenv
from charmsupport import host
from pwd import getpwnam

def storage_is_persistent():
    if os.path.islink(SOLR_DIR):
        target = os.readlink(SOLR_DIR)
        if os.path.ismount(target):
            return True
    return False

def volume_change_pre():
    host.service_stop('jetty')


def volume_change_post():
    pass


def set_permissions():
    if storage_is_persistent():
        # make sure data on external storage are owned
        # by the jetty user
        jetty_uid = getpwnam('jetty').pw_uid
        os.chown(SOLR_DIR, jetty_uid, -1)
        for root, dirs, files in os.walk(SOLR_DIR):
            for entry in dirs + files:
                os.chown(os.path.join(SOLR_DIR, entry), jetty_uid, -1)


SOLR_DIR = '/var/lib/solr'
SAVED_DIR = "{}.{}".format(SOLR_DIR, 'charm_saved')

if __name__ == '__main__':
    try:
        mountpoint = volumes.configure_volume(before_change=volume_change_pre, after_change=volume_change_post)
    except volumes.VolumeConfigurationError:
        hookenv.log('Storage could not be configured', hookenv.ERROR)
        sys.exit(1)

    if mountpoint == 'ephemeral':
        if os.path.islink(SOLR_DIR):
            os.remove(SOLR_DIR)
            if os.path.isdir(SAVED_DIR):
                os.rename(SAVED_DIR, SOLR_DIR)
            else:
                os.path.mkdir(SOLR_DIR)
    else:
        if not storage_is_persistent():
            try:
                os.rename(SOLR_DIR, SAVED_DIR)
            except OSError as e:
                hookenv.log('ERROR: could not preserve existing log directory', hookenv.ERROR)
                hookenv.log(e.strerror, hookenv.ERROR)
                sys.exit(1)
            os.symlink(mountpoint, SOLR_DIR)
            set_permissions()
            host.service_start('jetty')
