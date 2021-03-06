import os
import urllib2
from charmhelpers.fetch import (
    BaseFetchHandler,
    UnhandledSource
)
from charmhelpers.payload.archive import (
    get_archive_handler,
    extract,
)


class ArchiveUrlFetchHandler(BaseFetchHandler):
    """Handler for archives via generic URLs"""
    def can_handle(self, source):
        url_parts = self.parse_url(source)
        if url_parts.scheme not in ('http', 'https', 'ftp', 'file'):
            return "Wrong source type"
        if get_archive_handler(self.base_url(source)):
            return True
        return False

    def download(self, source, dest):
        # propogate all exceptions
        # URLError, OSError, etc
        response = urllib2.urlopen(source)
        with open(dest, 'w') as dest_file:
            dest_file.write(response.read())

    def install(self, source):
        url_parts = self.parse_url(source)
        dest_dir = os.path.join(os.environ.get('CHARM_DIR'), 'fetched')
        dld_file = os.path.join(dest_dir, os.path.basename(url_parts.path))
        try:
            self.download(source, dld_file)
        except urllib2.URLError as e:
            return UnhandledSource(e.reason)
        except OSError as e:
            return UnhandledSource(e.strerror)
        finally:
            if os.path.isfile(dld_file):
                os.unlink(dld_file)
        return extract(dld_file)
