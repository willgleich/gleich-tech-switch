import googleapiclient.discovery
import logging
import base64
import os
import CloudFlare
from google.cloud import secretmanager

logging.basicConfig(level=logging.INFO)
logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)


class CloudRunService(object):
    '''
    A Class to Handle abstraction of CloudRun service operations
    '''


    def __init__(self, service_name, project, location):
        '''
        :param service_name: Name of either a new or aleady existist service
        :param project: Project name ex: main-285019
        :param location: GCP Region
        '''
        self.service_name = service_name
        self.project = project
        self.location = location
        self.cloud_run = googleapiclient.discovery.build('run', 'v1')


    def _exists(flag):
        '''
        Decorator function to provide proper error reporting depending on whether the service exists or needs to be created
        :return:
        '''
        def decorator(function):
            def inner(self, *args, **kwargs):
                if self.exists() == flag:
                    function(self, *args, **kwargs)
                if flag:
                    raise ValueError(f"ERROR :: {self.service_name} doesn't exist yet and is required for this operation"
                                     f"It can be created using the CloudRunService.create() method")
                else:
                    raise ValueError(
                        f"ERROR :: {self.service_name} exists already, can't preform operation")
            return inner
        return decorator

    @_exists(False)
    def create(self, image):
        '''
        Creates a new service utilizing the service name, and a required docker image path
        Docker image must be within gcr
        :param image: string
        :return:
        '''
        body = {'apiVersion': 'serving.knative.dev/v1',
                'kind': 'Service',
                'metadata': {'name': self.service_name,
                             'namespace': '248394897420',
                             'generation': 1},
                'spec': {'template': {'metadata': {'name': f"{self.service_name}-00001-qel",
                                                   'annotations': {'run.googleapis.com/client-name': 'cloud-console',
                                                                   'autoscaling.knative.dev/maxScale': '1000'}},
                                      'spec': {'containerConcurrency': 80,
                                               'timeoutSeconds': 300,
                                               'containers': [{'image': image,
                                                               'resources': {
                                                                   'limits': {'cpu': '1000m', 'memory': '256Mi'}},
                                                               'ports': [{'containerPort': 8080}]}]}},
                         'traffic': [{'percent': 100, 'latestRevision': True}]}}
        return self.cloud_run.projects().locations().services().create(
            parent=f"projects/{self.project}/locations/{self.location}", body=body).execute()

    @_exists(True)
    def delete(self):
        '''

        :return: response from cloud_run api
        '''
        return self.cloud_run.projects().locations().services().delete(
            name=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}").execute()

    def exists(self):
        r = self.cloud_run.projects().locations().services().list(
            parent=f"projects/{self.project}/locations/us-west1").execute()
        if "items" in r.keys():
            for run_svc in r["items"]:
                if run_svc["metadata"]["name"] == self.service_name:
                    return True
        return False

    @_exists(True)
    def allow_unauthenticated(self):
        '''
        Modified the CloudRun Service permissions to allow for unauthenticated access "allUsers" to the cloudrun.invoker
        :return: None
        '''
        policy = {'policy': {'bindings': [{'role': 'roles/run.invoker', 'members': ['allUsers']}]}}
        self.cloud_run.projects().locations().services().setIamPolicy(
            resource=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}",
            body=policy).execute()

    @_exists(True)
    def disallow_unauthenticated(self):
        '''
        Modified the CloudRun Service permissions to allow for unauthenticated access "allUsers" to the cloudrun.invoker
        :return:
        '''
        policy = self.cloud_run.projects().locations().services().getIamPolicy(
            resource=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}").execute()
        #List comp to filter out any rules targeting ['allUsers']
        policy['bindings'] = [x for x in policy['bindings'] if not x['members'] == ['allUsers']]
        policy = {"policy": policy}
        self.cloud_run.projects().locations().services().setIamPolicy(
            resource=f"projects/{self.project}/locations/{self.location}/services/{self.service_name}",
            body=policy).execute()

    @_exists(True)
    def attach_domain(self, domain_name):
        body = {"metadata": {
            "name": domain_name},
            "spec": {
                "routeName": self.service_name,
            },
            "apiVersion": "domains.cloudrun.com/v1",
            "kind": "DomainMapping"
        }
        self.cloud_run.projects().locations().domainmappings().create(
            parent=f"projects/{self.project}/locations/{self.location}", body=body).execute()

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
    gleich_tech = CloudRunService("gleich-tech", project_id, "us-west1")
    logging.info("started the function")
    logging.info("initalized the cloud_run")
    gleich_tech.allow_unauthenticated()
    logging.info("set permissions on gleich-tech svc")
    #Cloudflare section
    cf = CloudFlare.CloudFlare(token=get_secret("cloudflare-api-key"))
    zone_id = get_cloudflare_zone_id(cf, "gleich.tech")
    create_page_rule(cf, zone_id)
    logging.info(f"attached page rule")
    return f"function moved through successfully"


if __name__ == '__main__':
    pass