jetty_start() {
    juju-log "Starting solr-jetty"
    /etc/init.d/jetty start
    # Wait for solr-jetty to start responding
    curl_rc=-1
    counter=0
    while [[ $curl_rc -ne 0 ]]; do
        juju-log "Waiting for solr-jetty to respond ($counter)"
        set +e
        curl --silent --max-time 5 "http://localhost:8080/solr/select?q=test" 2>&1 > /dev/null
        curl_rc=$?
        if [[ $counter -gt 5 ]]; then
            juju-log "solr-jetty not responding"
    	    exit 1
        fi
        sleep 2
        let counter++
        set -e
    done
}
