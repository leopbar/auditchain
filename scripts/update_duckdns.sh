#!/bin/bash
echo url="https://www.duckdns.org/update?domains=audit-bigfour&token=b52e0c9d-02ad-447d-8d54-4ea142b93ae4&ip=" | curl -k -o /opt/auditchain/duckdns.log -K -
