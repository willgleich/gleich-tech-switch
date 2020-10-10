import googleapiclient.discovery
import logging
import base64
import os
import CloudFlare
from google.cloud import secretmanager
from google_methods import CloudRunService, create_check_and_alert, remove_check_and_alert

logging.basicConfig(level=logging.INFO)
logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)

def get_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    secret_name = secret_name
    project_id = os.environ["GCP_PROJECT"]
    resource_name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(name=resource_name)
    return response.payload.data.decode('UTF-8')


def get_cloudflare_zone_id(cf, domain_name):
    zones = cf.zones.get(params = {'per_page':100})
    for zone in zones:
        if domain_name == zone['name']:
            return zone['id']
    return None

def create_page_rule(cf, zone_id):
    new_rule = {'targets': [{'target': 'url',
                             'constraint': {'operator': 'matches', 'value': 'will.gleich.tech/*'}}],
                'actions': [{'id': 'forwarding_url',
                             'value': {'url': 'https://will.iam.gleich.tech', 'status_code': 302}}],
                'priority': 2,
                'status': 'active'}
    return cf.zones.pagerules.post(zone_id, data=new_rule)

def delete_page_rule(cf, zone_id):
    for rule in cf.zones.pagerules.get(zone_id):
        if rule['targets'][0]['constraint']['value'].startswith("will.gleich.tech"):
            return cf.zones.pagerules.delete(zone_id, rule['id'])
    return None



def gleich_switch(event, context):
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    logging.info(f"REQUEST_BODY: {pubsub_message}")
    project_id = os.environ["GCP_PROJECT"]
    gleich_tech = CloudRunService("gleich-tech", project_id, "us-central1")
    logging.info("started the function")
    logging.info("initalized the cloud_run")
    remove_check_and_alert('will.gleich.tech')
    gleich_tech.allow_unauthenticated()
    logging.info("set permissions on gleich-tech svc")
    #Cloudflare section
    cf = CloudFlare.CloudFlare(token=get_secret("cloudflare-api-key"))
    zone_id = get_cloudflare_zone_id(cf, "gleich.tech")
    create_page_rule(cf, zone_id)
    logging.info(f"attached page rule")
    return f"function moved through successfully"

def cleanup_switch():
    project_id = os.environ["GCP_PROJECT"]
    gleich_tech = CloudRunService("gleich-tech", project_id, "us-central1")
    gleich_tech.disallow_unauthenticated()
    create_check_and_alert('will.gleich.tech')
    #Cloudflare section
    cf = CloudFlare.CloudFlare(token=get_secret("cloudflare-api-key"))
    zone_id = get_cloudflare_zone_id(cf, "gleich.tech")
    logging.info("set permissions on gleich-tech svc")
    delete_page_rule(cf, zone_id)

if __name__ == '__main__':
    cleanup_switch()
    pass