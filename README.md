Juju charm solr-jetty
=====================

Solr is an open source enterprise search server based on the Lucene Java
search library, with XML/HTTP and JSON APIs, hit highlighting, faceted
search, caching, replication, and a web administration interface. This
charm deploys Solr in the Java servlet container Jetty.

This charm is designed to be deployed as the backend to a second charm,
its interface should not be exposed directly as there are no controls over
who can update the stored data.

How to deploy the charm
--------------------------
juju deploy solr-jetty 

How to configure the charm
--------------------------
# Load custom solr schema
juju set solr-jetty "schema=$(base64 < my-schema.xml)"

# Set number of Jetty acceptors
juju set solr-jetty "acceptors=20"

# Explicitly set JVM min heap and max heap size
juju set solr-jetty java-min-heap-mb=256 java-max-heap-mb=512

# Add storage devices

juju set solr-jetty volume-map="{solr-jetty/0: /dev/vdb}" volume-ephemeral=false

# Add Ceph storage device

juju set solr-jetty volume-map="{solr-jetty/0: /dev/rbd/solr-jetty/solr}" volume-ephemeral=false
juju add-relation solr-jetty ceph

# Loading the example mem.xml from apache-solr-1.4.1.tgz
curl http://<ip>:8080/solr/update --data-binary @mem.xml -H 'Content-type:text/xml; charset=utf-8'
curl http://<ip>:8080/solr/update --data-binary '<commit/>' -H 'Content-type:text/xml; charset=utf-8'

# ... and querying it
curl http://<ip>:8080/solr/select?q=memory

Example:
--------------------------
# Define schema
echo '<?xml version="1.0" encoding="UTF-8" ?>
<schema name="example" version="1.2">
    <types>
        <fieldType name="string" class="solr.StrField" sortMissingLast="true" omitNorms="true"/>
        <fieldType name="textgen" class="solr.TextField" positionIncrementGap="100">
            <analyzer>
                <charFilter class="solr.MappingCharFilterFactory" mapping="mapping-ISOLatin1Accent.txt"/>
                <tokenizer class="solr.WhitespaceTokenizerFactory"/>
                <filter class="solr.WordDelimiterFilterFactory" generateWordParts="1"
                    generateNumberParts="1" catenateWords="1" catenateNumbers="1"
                    catenateAll="0" splitOnCaseChange="0"/>
                <filter class="solr.LowerCaseFilterFactory"/>
                <filter class="solr.PorterStemFilterFactory"/>
            </analyzer>
        </fieldType>
    </types>


    <fields>
        <field name="id" type="string" indexed="true" stored="true" required="true" /> 
        <field name="name" type="string" indexed="true" stored="true"/>
        <field name="description" type="textgen" indexed="true" stored="true" default="" /> 
    </fields>

    <uniqueKey>id</uniqueKey>
    <defaultSearchField>description</defaultSearchField>
</schema>' > snack-schema.xml

# Load schema
juju set solr-jetty "schema=$(base64 < snack-schema.xml)"

# Define data
echo '<add>
<doc>
  <field name="id">1</field>
  <field name="name">Chococapers</field>
  <field name="description">Delicious caper flavoured chocolate snack</field>
</doc>
<doc>
  <field name="id">2</field>
  <field name="name">Chillimilk</field>
  <field name="description">All the goodness of milk with a chilli twist</field>
</doc>
<doc>
  <field name="id">3</field>
  <field name="name">Caperyogurt</field>
  <field name="description">Thick yogurt infused with caper goodness </field>
</doc>
</add>' > snack-data.xml

# Loading the snack data
curl http://<ip>:8080/solr/update --data-binary @snack-data.xml -H 'Content-type:text/xml; charset=utf-8'
curl http://<ip>:8080/solr/update --data-binary '<commit/>' -H 'Content-type:text/xml; charset=utf-8'

# You're craving capers but what snack will satisfy you?
curl 'http://<ip>:8080/solr/select?q=caper'

# TODO

- Deploy Solr 4.x
  - Deploy with Solr Cloud
  - Manage cluster config within Zookeeper